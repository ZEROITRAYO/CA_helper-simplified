import { useState } from "react";
import { Link } from "react-router";

import { useFilings } from "@/api";
import { QueryStatus, RegisterFirst, Row, StatusBadge, Table } from "@/components/shared";
import { linkClass } from "@/components/ui";
import { daysLeftText, daysUntil, filingFormLabel, formatDate, monthLabel } from "@/lib";

// The filter chips: which forms each one keeps.
const FORM_FILTERS = {
  All: null,
  GST: ["gstr_1", "gstr_3b", "cmp_08", "gstr_4"],
  TDS: ["tds_24q", "tds_26q"],
  ITR: ["itr"],
};
const DONE = ["filed", "filed_verified"];
const STATUS_FILTERS = {
  All: () => true,
  Upcoming: (item) => !DONE.includes(item.status) && daysUntil(item.due_date) >= 0,
  Overdue: (item) => !DONE.includes(item.status) && daysUntil(item.due_date) < 0,
};

/** /business/compliance: this year's filings, late ones first, then by month. */
export function CompliancePage() {
  const filings = useFilings();
  const [formFilter, setFormFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");

  let content;
  if (!filings.isSuccess) {
    content = <QueryStatus query={filings} />;
  } else if (filings.data === null) {
    content = <RegisterFirst>to see which filings apply to you and when they are due.</RegisterFirst>;
  } else if (filings.data.length === 0) {
    content = (
      <p className="text-sm text-hint">No filings due for the rest of this year.</p>
    );
  } else {
    const forms = FORM_FILTERS[formFilter];
    const shown = filings.data.filter(
      (item) =>
        (forms === null || forms.includes(item.form_code)) && STATUS_FILTERS[statusFilter](item),
    );
    content = (
      <>
        <div className="flex flex-wrap gap-4">
          <Chips
            name="Form"
            options={Object.keys(FORM_FILTERS)}
            value={formFilter}
            onChange={setFormFilter}
          />
          <Chips
            name="Status"
            options={Object.keys(STATUS_FILTERS)}
            value={statusFilter}
            onChange={setStatusFilter}
          />
        </div>
        {shown.length === 0 ? (
          <p className="text-sm text-hint">No filings match these filters.</p>
        ) : (
          <FilingSections filings={shown} />
        )}
      </>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compliance calendar</h1>
      {content}
    </div>
  );
}

// A row of toggle buttons; exactly one is on.
function Chips({ name, options, value, onChange }) {
  return (
    <div role="group" aria-label={name} className="flex flex-wrap items-center gap-1">
      <span className="text-sm text-hint">{name}:</span>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={
            "rounded-full border px-3 py-0.5 text-sm " +
            (value === option
              ? "border-primary bg-primary text-white"
              : "hover:bg-soft")
          }
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function FilingSections({ filings }) {
  const earlier = filings.filter((item) => daysUntil(item.due_date) < 0);
  // {"October 2026": [filings]}, in due-date order (the API sends them soonest first).
  const byMonth = {};
  for (const item of filings) {
    if (daysUntil(item.due_date) >= 0) {
      const month = monthLabel(item.due_date);
      byMonth[month] ??= [];
      byMonth[month].push(item);
    }
  }

  return (
    <div className="space-y-8">
      {earlier.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Earlier this year: due dates already passed</h2>
          <p className="text-sm text-hint">
            If you already filed this, you'll be able to mark it as filed.
          </p>
          <FilingTable filings={earlier} />
        </section>
      )}
      {Object.entries(byMonth).map(([month, items]) => (
        <section key={month} className="space-y-2">
          <h2 className="text-lg font-semibold">{month}</h2>
          <FilingTable filings={items} />
        </section>
      ))}
    </div>
  );
}

function FilingTable({ filings }) {
  return (
    <Table headers={["Form", "Period", "Due date", "Days left", "Status"]}>
      {filings.map((item) => (
        <Row
          key={item.id}
          cells={[
            <Link to={`/business/compliance/${item.id}`} className={linkClass}>
              {filingFormLabel(item.form_code, item.period_label)}
            </Link>,
            item.period_label,
            formatDate(item.due_date),
            <span className="tabular-nums">
              {DONE.includes(item.status) ? "—" : daysLeftText(item.due_date)}
            </span>,
            <StatusBadge status={item.status} />,
          ]}
        />
      ))}
    </Table>
  );
}
