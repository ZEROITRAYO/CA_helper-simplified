import ReactMarkdown from "react-markdown";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  COMPLIANCE_STATUS_LABELS,
  ENGAGEMENT_STATUS_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
} from "@/lib";

// --- QueryStatus ---------------------------------------------------------------------------------

/** "Loading..." while a query waits, its error message if it failed, else nothing. */
export function QueryStatus({ query }) {
  if (query.isPending) return <p className="text-sm text-muted-foreground">Loading...</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(query.error)}
      </p>
    );
  }
  return null;
}

// --- Pager ---------------------------------------------------------------------------------------

/** Previous / Next buttons for a paginated API answer ({ page, page_size, total }). */
export function Pager({ data, onPage }) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  if (pages === 1) return null;
  return (
    <div className="flex items-center gap-3 text-sm">
      <Button variant="outline" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>
        Previous
      </Button>
      <span>
        Page {data.page} of {pages}
      </span>
      <Button variant="outline" disabled={data.page >= pages} onClick={() => onPage(data.page + 1)}>
        Next
      </Button>
    </div>
  );
}

// --- FormField ---------------------------------------------------------------------------------

/** A labelled input with its error (linked for screen readers), for React Hook Form. */
export function FormField({ id, label, error, hint, ...inputProps }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        aria-invalid={!!error}
        aria-describedby={error ? id + "-error" : undefined}
        {...inputProps}
      />
      {error ? (
        <p id={id + "-error"} className="text-sm text-destructive">
          {error.message}
        </p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

// --- FormCard ----------------------------------------------------------------------------------

/** A small centred card holding one form: login, signup, passwords. */
export function FormCard({ title, description, children }) {
  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader>
        <CardTitle>
          <h1 className="text-xl font-semibold">{title}</h1>
        </CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

// --- StatusBadge -------------------------------------------------------------------------------

// A colour per filing status, so what needs attention stands out.
const COLOURS = {
  overdue: "bg-red-100 text-red-900",
  docs_pending: "bg-amber-100 text-amber-900",
  ready: "bg-sky-100 text-sky-900",
  with_ca: "bg-violet-100 text-violet-900",
  filed: "bg-green-100 text-green-900",
  filed_verified: "bg-green-100 text-green-900",
};

/** A filing's status (compliance_items.status) as a coloured badge. */
export function StatusBadge({ status }) {
  return (
    <Badge variant="secondary" className={COLOURS[status]}>
      {label(COMPLIANCE_STATUS_LABELS, status)}
    </Badge>
  );
}

// --- Stars -------------------------------------------------------------------------------------

/** Star ratings: <Stars stars={4} /> and <RatingSummary average={4.5} count={12} />. */

// Five characters: filled stars first, then empty ones, e.g. 3 -> "★★★☆☆".
function starText(stars) {
  let text = "";
  for (let i = 1; i <= 5; i++) {
    if (i <= stars) {
      text = text + "★";
    } else {
      text = text + "☆";
    }
  }
  return text;
}

export function Stars({ stars }) {
  return (
    <span className="text-amber-500" role="img" aria-label={stars + " out of 5 stars"}>
      {starText(stars)}
    </span>
  );
}

// A CA's average rating and how many ratings it is based on.
export function RatingSummary({ average, count }) {
  if (!count) {
    return <span className="text-muted-foreground">No ratings yet</span>;
  }
  const word = count === 1 ? "rating" : "ratings";
  return (
    <span>
      <span className="text-amber-500">★</span> {average} ({count} {word})
    </span>
  );
}

// --- Markdown ----------------------------------------------------------------------------------

// Styles for the HTML that Markdown produces (headings, lists, links), written as
// Tailwind "child" selectors so each piece looks like the rest of the app.
const STYLES = [
  "space-y-3 text-sm leading-relaxed",
  "[&_h1]:text-lg [&_h1]:font-semibold",
  "[&_h2]:mt-5 [&_h2]:font-semibold",
  "[&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5",
  "[&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-5",
  "[&_a]:text-primary [&_a]:underline-offset-4 [&_a]:hover:underline",
].join(" ");

/** Shows a Markdown text (e.g. a form's explanation from content/forms/) as formatted text. */
export function Markdown({ children }) {
  return (
    <div className={STYLES}>
      <ReactMarkdown
        components={{
          // Links to official portals open in a new tab.
          a: ({ href, children: text }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {text}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

// --- EngagementCard ----------------------------------------------------------------------------

// Badge colour for each engagement status.
const STATUS_COLORS = {
  requested: "bg-amber-100 text-amber-800",
  active: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-700",
  declined: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-700",
};

// Adds up the (fixed, listed) prices of all filings.
function total(items) {
  let sum = 0;
  for (const item of items) {
    sum = sum + Number(item.listed_price);
  }
  return sum;
}

// The steps shown for each status, e.g. Requested → Active → Completed.
function stepsFor(status) {
  if (status === "declined" || status === "cancelled") {
    return ["requested", status];
  }
  return ["requested", "active", "completed"];
}

// How a step looks: bold for the current one, grey for done ones, lighter for the rest.
function stepClass(index, current) {
  if (index === current) {
    return "font-semibold";
  }
  if (index < current) {
    return "text-muted-foreground";
  }
  return "text-muted-foreground/60";
}

// ✓ for a done step, ● for the current one, ○ for one still to come.
function stepMark(index, current) {
  if (index < current) {
    return "✓ ";
  }
  if (index === current) {
    return "● ";
  }
  return "○ ";
}

/** Where the engagement is: ✓ done steps, ● the current one (bold), ○ steps still to come. */
function Timeline({ status }) {
  const steps = stepsFor(status);
  const current = steps.indexOf(status);
  return (
    <ol aria-label="Progress" className="flex flex-wrap items-center gap-1 text-xs">
      {steps.map((step, index) => (
        <li
          key={step}
          aria-current={index === current ? "step" : undefined}
          className={stepClass(index, current)}
        >
          {index > 0 && <span aria-hidden="true">→ </span>}
          {stepMark(index, current)}
          {label(ENGAGEMENT_STATUS_LABELS, step)}
        </li>
      ))}
    </ol>
  );
}

/** One engagement as a card; `children` are the action buttons for its status. */
export function EngagementCard({ engagement, title, children }) {
  const items = engagement.items;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h3>{title}</h3>
          <Badge className={STATUS_COLORS[engagement.status]}>
            {label(ENGAGEMENT_STATUS_LABELS, engagement.status)}
          </Badge>
        </CardTitle>
        <CardDescription>
          Requested {formatDateTime(engagement.requested_at)}
        </CardDescription>
        <Timeline status={engagement.status} />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <table className="w-full text-left">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">Filing</th>
              <th className="py-1 pr-3 font-medium">Service</th>
              <th className="py-1 font-medium">Price</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b">
                <td className="py-1 pr-3">
                  {item.form_code
                    ? filingFormLabel(item.form_code, item.period_label)
                    : "Removed filing"}{" "}
                  {item.period_label}
                  {item.due_date && (
                    <span className="text-muted-foreground">
                      {" "}
                      · due {formatDate(item.due_date)}
                    </span>
                  )}
                </td>
                <td className="py-1 pr-3">{item.service_name}</td>
                <td className="py-1">{formatRupees(item.listed_price)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="font-medium">
            <tr>
              <td className="py-1 pr-3" colSpan={2}>
                Total
              </td>
              <td className="py-1">{formatRupees(total(items))}</td>
            </tr>
          </tfoot>
        </table>
        {engagement.rating && (
          <p>
            <span className="font-medium">Rating: </span>
            <Stars stars={engagement.rating.stars} />
            {engagement.rating.review && <span> “{engagement.rating.review}”</span>}
          </p>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
