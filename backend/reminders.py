# The background jobs. Only ONE teammate runs this (docker compose --profile worker up):
#   - every 15 minutes: filings past their due date that were not started become "overdue"
#   - every morning after 8:15 (Indian time): deadline reminders 7, 3 and 1 day before the
#     due date, and once when a filing is overdue, to the business and the CA working on it.
#
#     python reminders.py                       keep running (the worker)
#     python reminders.py --once [2026-10-06]   run both jobs now (as if on that day), then stop

import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import app
from filings import DONE, filing_name
from helpers import date, notify, send_email, now
from models import Business, CaProfile, ComplianceItem, Engagement, EngagementItem, ReminderLog, User, db, now


def mark_overdue(today):
    """Filings not started yet whose due date has passed become "overdue" (not those with a CA)."""
    late = ComplianceItem.query.filter(ComplianceItem.status.in_(["upcoming", "docs_pending", "ready"]),
                                       ComplianceItem.due_date < today).all()
    for filing in late:
        filing.status = "overdue"
    db.session.commit()
    return len(late)


def reminder_kind(days_left):
    """Which reminder is due. Windows instead of single days, so a reminder still goes out if
    the worker missed a day; a reminder that was missed is not sent late."""
    if days_left < 0:
        return "overdue"
    if days_left <= 1:
        return "t_minus_1"
    if days_left <= 3:
        return "t_minus_3"
    if days_left <= 7:
        return "t_minus_7"
    return None


def reminder_title(filing, days_left):
    if days_left < 0:
        return f"{filing_name(filing)} is overdue"
    if days_left == 0:
        return f"{filing_name(filing)} is due today"
    if days_left == 1:
        return f"{filing_name(filing)} is due tomorrow"
    return f"{filing_name(filing)} is due in {days_left} days"


def send_reminders(today):
    """Each filing gets each kind of reminder once (reminder_log). Every reminder goes to the
    inbox; each person who wants emails then gets ONE email listing all of today's reminders."""
    filings = ComplianceItem.query.filter(ComplianceItem.due_date <= today + timedelta(days=7),
                                          ComplianceItem.status.notin_(DONE)).order_by(ComplianceItem.due_date)
    emails = {}  # user -> [(title, body)] for their summary email
    count = 0
    for filing in filings:
        days_left = (filing.due_date - today).days
        kind = reminder_kind(days_left)
        business = db.session.get(Business, filing.business_id)
        if kind is None or ReminderLog.query.filter_by(compliance_item_id=filing.id, kind=kind).first():
            continue
        if filing.due_date < date(business.created_at):  # due before the business joined
            continue
        db.session.add(ReminderLog(compliance_item_id=filing.id, kind=kind, sent_at=now()))
        count += 1
        due = f"{filing.due_date.day} {filing.due_date:%b %Y}"  # e.g. "20 Sep 2026"
        if kind == "overdue":
            body = f"It was due on {due}. File it as soon as you can."
        else:
            body = f"Due on {due}."
        title = reminder_title(filing, days_left)
        people = [(db.session.get(User, business.user_id), title, f"/business/compliance/{filing.id}")]
        engagement = (Engagement.query.join(EngagementItem, EngagementItem.engagement_id == Engagement.id)
                      .filter(EngagementItem.compliance_item_id == filing.id, Engagement.status == "active").first())
        if engagement:  # the CA working on it is reminded too
            ca_user = db.session.get(User, db.session.get(CaProfile, engagement.ca_profile_id).user_id)
            people.append((ca_user, f"{business.legal_name}: {title}", f"/ca/clients/{business.id}"))
        for user, user_title, link in people:
            notify(user, "overdue" if kind == "overdue" else "deadline_reminder", user_title, body, link)
            if user.email_notifications:
                emails.setdefault(user, []).append((user_title, body))
    db.session.commit()
    for user, lines in emails.items():
        subject = lines[0][0] if len(lines) == 1 else f"{len(lines)} filings need your attention"
        send_email(user.email, subject, "reminders", name=user.full_name,
                   lines=[f"{title}. {body}" for title, body in lines])
    return count


if __name__ == "__main__":
    with app.app_context():
        if "--once" in sys.argv:
            day = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else now()
            print("Overdue:", mark_overdue(day), "- reminders recorded:", send_reminders(day))
            sys.exit()
        last_reminder_day = None
        while True:
            mark_overdue(now())
            india_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            if india_now.strftime("%H:%M") >= "08:15" and last_reminder_day != india_now.date():
                print("Reminders recorded:", send_reminders(india_now.date()))
                last_reminder_day = india_now.date()
            time.sleep(15 * 60)  # check again in 15 minutes
