"""Alerts: the notification list, the daily deadline reminders and the penalty
estimate.

Tray entries are always created. Emails go out only when the user's `email_notifications`
switch is on, and only after the caller's commit, so nobody is emailed about something
that was not saved.

Penalties are data: `penalty_rules` rows, matched by form code and the filing's due date.
An amount that is not confirmed yet is empty (NULL) and skipped: the estimate then says
what is missing instead of showing a number.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

import click
from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from app import compliance
from app.models import (
    Business, CaProfile, ComplianceItem, Engagement, EngagementItem, EngagementStatus,
    Notification, NotificationType, PenaltyRule, ReminderKind, ReminderLog, User, UserRole, db,
    today_in_india, utcnow,
)
from app.utils import (
    ApiError, current_business, current_user, invalid, iso, login_required, money, page_of,
    read_amount, roles_required, send_email,
)

bp = Blueprint("alerts", __name__)


# --- The tray ----------------------------------------------------------------------------


def notify(user, notification_type, title, body, link=None):
    """Add a tray entry for `user` (never put PAN, GSTIN or other sensitive data in it)."""
    notification = Notification(user_id=user.id, type=notification_type, title=title, body=body, link=link)
    db.session.add(notification)
    return notification


def email_notice(user, title, body):
    """Email a tray entry's text to the user, if they want emails. Call after the commit."""
    if user.email_notifications:
        send_email(user.email, title, "notification", name=user.full_name, title=title, body=body)


def notification_to_dict(notification):
    return {
        "id": str(notification.id), "type": notification.type, "title": notification.title,
        "body": notification.body, "link": notification.link, "read_at": iso(notification.read_at),
        "created_at": iso(notification.created_at),
    }


# --- Reminders (the worker runs send_reminders every morning) -----------------------------

# (kind, fewest days left, most days left). Windows instead of exact days: if the worker
# did not run on the 7th day before, the reminder still goes out on the 6th, 5th or 4th.
# Only the current window's reminder is sent; one that was missed is not sent late.
REMINDER_WINDOWS = (
    (ReminderKind.T_MINUS_7, 4, 7),
    (ReminderKind.T_MINUS_3, 2, 3),
    (ReminderKind.T_MINUS_1, 0, 1),
)


def reminder_kind(days_left):
    """The reminder due `days_left` days before the due date (negative = late), or None."""
    if days_left < 0:
        return ReminderKind.OVERDUE
    for kind, fewest, most in REMINDER_WINDOWS:
        if fewest <= days_left <= most:
            return kind
    return None


def send_reminders(today=None):
    """Remind businesses (and the CA working on it) of filings due soon or overdue.
    Returns how many reminders were recorded. Runs daily; running it again the same day
    sends nothing new.

    - Each filing gets each kind (T-7, T-3, T-1, overdue) at most once (reminder_log).
    - A filing due before the business registered gets no reminder.
    - Every reminder is a tray entry; each person who wants emails then gets ONE summary
      email for the run.
    """
    today = today or today_in_india()
    filings = db.session.scalars(select(ComplianceItem).where(
        ComplianceItem.due_date <= today + timedelta(days=7),
        ComplianceItem.status.not_in(compliance.DONE_STATUSES),
    ).order_by(ComplianceItem.due_date)).all()
    sent = db.session.execute(select(ReminderLog.compliance_item_id, ReminderLog.kind))
    already_sent = {tuple(row) for row in sent}
    # {filing id: the CA's User} for the filings in an ACTIVE engagement.
    ca_users = dict(db.session.execute(
        select(EngagementItem.compliance_item_id, User).join(Engagement).join(CaProfile)
        .join(User, CaProfile.user_id == User.id).where(Engagement.status == EngagementStatus.ACTIVE)
    ).all())

    emails = {}  # user id -> (user, [(title, body) for the summary email])
    count = 0
    for filing in filings:
        days_left = (filing.due_date - today).days
        kind = reminder_kind(days_left)
        business = db.session.get(Business, filing.business_id)
        registered_on = business.created_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if kind is None or (filing.id, kind) in already_sent or filing.due_date < registered_on:
            continue
        db.session.add(ReminderLog(compliance_item_id=filing.id, kind=kind, sent_at=utcnow()))
        count += 1
        due_text = f"{filing.due_date.day} {filing.due_date:%b %Y}"  # "20 Sep 2026"
        if kind == ReminderKind.OVERDUE:
            notification_type = NotificationType.OVERDUE
            body = f"It was due on {due_text}. File it as soon as you can."
        else:
            notification_type = NotificationType.DEADLINE_REMINDER
            body = f"Due on {due_text}."
        title = reminder_title(filing, days_left)
        recipients = [(db.session.get(User, business.user_id), title, f"/business/compliance/{filing.id}")]
        if filing.id in ca_users:
            ca_title = f"{business.legal_name}: {title}"
            recipients.append((ca_users[filing.id], ca_title, f"/ca/clients/{business.id}"))
        for user, user_title, link in recipients:
            notify(user, notification_type, user_title, body, link)
            if user.email_notifications:
                emails.setdefault(user.id, (user, []))[1].append((user_title, body))

    db.session.commit()
    for user, reminders in emails.values():
        subject = reminders[0][0] if len(reminders) == 1 else f"{len(reminders)} filings need your attention"
        lines = [f"{title}. {body}" for title, body in reminders]
        send_email(user.email, subject, "reminders", name=user.full_name, lines=lines)
    return count


def reminder_title(filing, days_left):
    name = compliance.filing_name(filing)
    if days_left < 0:
        return f"{name} is overdue"
    if days_left <= 1:
        return f"{name} is due {'today' if days_left == 0 else 'tomorrow'}"
    return f"{name} is due in {days_left} days"


# --- Penalty estimate ------------------------------------------------------------------------

LABEL_PENDING = "Estimate (rules pending verification)"
LABEL_VERIFIED = "Estimate"
CENT = Decimal("0.01")


def estimate(filing, today, tax_due):
    """Late fee (and interest with `tax_due`) of one filing today, as JSON."""
    days_late = max((today - filing.due_date).days, 0)
    result = {
        "compliance_item_id": str(filing.id), "form_code": filing.form_code,
        "period_label": filing.period_label, "due_date": iso(filing.due_date),
        "days_late": days_late, "status": "estimated", "late_fee": None, "interest": None,
        "total": None, "notes": [], "label": LABEL_PENDING,
    }
    if filing.status in compliance.DONE_STATUSES:
        result.update(status="filed", days_late=0)
        return result
    if days_late == 0:
        result["status"] = "not_late"
        return result
    # The penalty rule of the form in force on the filing's due date.
    rule = db.session.scalar(select(PenaltyRule).where(
        PenaltyRule.form_code == filing.form_code, PenaltyRule.effective_from <= filing.due_date,
        or_(PenaltyRule.effective_to.is_(None), PenaltyRule.effective_to > filing.due_date),
    ).order_by(PenaltyRule.effective_from.desc()))
    if rule is None:
        result.update(status="pending", notes=["There is no penalty rule for this form yet."])
        return result
    if "TODO_VERIFY" not in rule.source_reference:
        result["label"] = LABEL_VERIFIED

    # A flat fee, else days × the daily fee up to the cap; None if not confirmed.
    late_fee = rule.flat_late_fee
    if late_fee is None and rule.late_fee_per_day is not None:
        late_fee = rule.late_fee_per_day * days_late
        if rule.max_late_fee is not None:
            late_fee = min(late_fee, rule.max_late_fee)
    if late_fee is None:
        result["notes"].append("The late fee for this form is not confirmed yet.")
    interest = None
    if rule.annual_interest_rate is None:
        result["notes"].append("The interest rate is not confirmed yet.")
    elif tax_due is None:
        result["notes"].append("Enter the tax due to estimate the interest.")
    else:
        interest = (tax_due * rule.annual_interest_rate / 100 * days_late / 365).quantize(CENT, ROUND_HALF_UP)
    amounts = [amount for amount in (late_fee, interest) if amount is not None]
    result.update(
        late_fee=money(late_fee), interest=money(interest), total=money(sum(amounts)) if amounts else None,
        status="estimated" if amounts else "pending",
    )
    return result


# --- Routes ------------------------------------------------------------------------------


@bp.get("/alerts/notifications")
@login_required
def list_notifications():
    """The user's tray, newest first, paginated."""
    stmt = select(Notification).where(Notification.user_id == current_user().id)
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id)
    return jsonify(page_of(stmt, notification_to_dict))


@bp.post("/alerts/notifications/<uuid:notification_id>/read")
@login_required
def mark_read(notification_id):
    """Mark one of the user's entries read (again is fine)."""
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user().id:
        raise ApiError(404, "NOTIFICATION_NOT_FOUND", "This notification was not found.")
    notification.read_at = notification.read_at or utcnow()
    db.session.commit()
    return jsonify(notification_to_dict(notification))


@bp.get("/alerts/penalties")
@roles_required(UserRole.BUSINESS)
def get_penalty_exposure():
    """The late fees of all the business's overdue filings, for the dashboard (interest not
    included)."""
    today = today_in_india()
    items = [
        estimate(filing, today, None) for filing in compliance.list_filings(current_business())
        if filing.status not in compliance.DONE_STATUSES and filing.due_date < today
    ]
    fees = [Decimal(item["late_fee"]) for item in items if item["late_fee"] is not None]
    verified = items and all(item["label"] == LABEL_VERIFIED for item in items)
    return jsonify({
        "total_late_fees": money(sum(fees, Decimal("0.00"))), "overdue_count": len(items),
        "estimated_count": len(fees), "pending_count": len(items) - len(fees),
        "label": LABEL_VERIFIED if verified else LABEL_PENDING, "items": items,
    })


@bp.get("/alerts/penalties/<uuid:item_id>")
@roles_required(UserRole.BUSINESS)
def get_penalty_estimate(item_id):
    """One filing's late fee, and its interest when ?tax_due= (unpaid tax, rupees) is given."""
    tax_due = request.args.get("tax_due")
    if tax_due is not None:
        tax_due = read_amount(tax_due, 0, 10**10)  # rupees; the estimate's input limit
        if tax_due is None:
            raise invalid("tax_due", "Enter an amount from 0 to 10000000000.", "query")
    filing = compliance.own_filing(current_business(), item_id)
    return jsonify(estimate(filing, today_in_india(), tax_due))


# `flask alerts send-reminders [--date 2026-10-06]`: run the daily reminder job now, for
# demos and testing. --date runs it as if it were that day (the reminders it records then
# count as sent, so the real day sends them no second time).
@bp.cli.command("send-reminders")
@click.option("--date", "day", type=click.DateTime(formats=["%Y-%m-%d"]), help="YYYY-MM-DD")
def send_reminders_command(day):
    """Send the deadline and overdue reminders now (what the worker does every morning)."""
    count = send_reminders(day.date() if day else None)
    click.echo(f"Recorded {count} reminder(s).")
