// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";

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
  linkClass,
} from "@/components/ui";
import {
  CA_SPECIALIZATION_LABELS,
  cn,
  COMPLIANCE_STATUS_LABELS,
  ENGAGEMENT_STATUS_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
} from "@/lib";

// --- Hooks -------------------------------------------------------------------------------------

/**
 * Busy and error state for a button or form. run(async () => ...) clears the error, shows
 * the API's message if the action fails, and returns true when it worked.
 */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await action();
      return true;
    } catch (failure) {
      setError(errorMessage(failure));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, setError, run };
}

/** A local link to a downloaded file (a Blob); freed again when the page closes. */
export function useObjectUrl(blob) {
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob]);
  useEffect(() => () => url && URL.revokeObjectURL(url), [url]);
  return url;
}

// --- Messages ----------------------------------------------------------------------------------

/** An error message (nothing when there is none). */
export function ErrorText({ children, className }) {
  if (!children) return null;
  return (
    <p role="alert" className={cn("text-sm text-danger", className)}>
      {children}
    </p>
  );
}

/** A short "done" message (nothing when there is none). */
export function Notice({ children }) {
  if (!children) return null;
  return (
    <p role="status" className="text-sm text-hint">
      {children}
    </p>
  );
}

/** "Loading..." while a query (or any of a list of queries) waits, else its error, else nothing. */
export function QueryStatus({ query }) {
  const queries = [].concat(query);
  if (queries.some((one) => one.isPending)) {
    return <p className="text-sm text-hint">Loading...</p>;
  }
  const failed = queries.find((one) => one.isError);
  return failed ? <ErrorText>{errorMessage(failed.error)}</ErrorText> : null;
}

// --- Page parts --------------------------------------------------------------------------------

/** A page's heading, with an optional line under it. */
export function PageTitle({ title, children }) {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {children && <p className="text-sm text-hint">{children}</p>}
    </div>
  );
}

/** A dashboard's heading: the API's welcome message, or why it could not be loaded. */
export function Welcome({ query }) {
  let title = "Loading...";
  if (query.isError) title = "Dashboard";
  if (query.isSuccess) title = query.data.message;
  return (
    <>
      <h1 className="text-2xl font-semibold">{title}</h1>
      {query.isError && (
        <Section title="Could not load the dashboard" description={errorMessage(query.error)} />
      )}
    </>
  );
}

/** A dashboard card with one big number (red when `alert`); `note` and `children` go under it. */
export function NumberCard({ title, value, note, alert, children }) {
  return (
    <Card className={alert ? "ring-red-300" : undefined}>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className={cn("text-2xl tabular-nums", alert && "text-red-700")}>{value}</CardTitle>
        {note && <p className="text-xs text-hint">{note}</p>}
        {children}
      </CardHeader>
    </Card>
  );
}

/** A card with a title, an optional description and optional content. */
export function Section({ title, description, contentClassName, children, ...cardProps }) {
  return (
    <Card {...cardProps}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      {children && <CardContent className={contentClassName}>{children}</CardContent>}
    </Card>
  );
}

/** "← Back to ..." at the top of a page. */
export function BackLink({ to, children }) {
  return (
    <Link to={to} className={cn("text-sm", linkClass)}>
      ← {children}
    </Link>
  );
}

/** For a business that has not registered yet: a link to the form and why. */
export function RegisterFirst({ children }) {
  return (
    <p className="text-sm">
      <Link to="/business/onboarding" className="underline">
        Register your business
      </Link>{" "}
      {children}
    </p>
  );
}

/** A table with a header row; the rows are <Row>s. */
export function Table({ headers, children }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b text-hint">
          <tr>
            {headers.map((header, index) => (
              <th key={index} className={cn("py-2 font-medium", index < headers.length - 1 && "pr-4")}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** One table row; `cells` are what each column shows. */
export function Row({ cells }) {
  return (
    <tr className="border-b align-top">
      {cells.map((cell, index) => (
        <td key={index} className={cn("py-2", index < cells.length - 1 && "pr-4")}>
          {cell}
        </td>
      ))}
    </tr>
  );
}

// --- Form fields -------------------------------------------------------------------------------

/** A label above a control (a select, a file input...) and its error. */
export function Field({ id, label, error, className = "space-y-2", children }) {
  return (
    <div className={className}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && <p className="text-sm text-danger">{error.message}</p>}
    </div>
  );
}

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
        <p id={id + "-error"} className="text-sm text-danger">
          {error.message}
        </p>
      ) : (
        hint && <p className="text-xs text-hint">{hint}</p>
      )}
    </div>
  );
}

/** The props of a React Hook Form field: <FormField label="Email" {...field(form, "email")} />. */
export function field(form, name) {
  return { id: name, error: form.formState.errors[name], ...form.register(name) };
}

/** An <option> per code of a label map (or only `codes`), after an optional empty choice. */
export function Options({ labels, codes = Object.keys(labels), empty }) {
  return (
    <>
      {empty !== undefined && <option value="">{empty}</option>}
      {codes.map((code) => (
        <option key={code} value={code}>
          {label(labels, code)}
        </option>
      ))}
    </>
  );
}

/** A checkbox or radio button with its text. */
export function Choice({ id, type = "checkbox", text, ...inputProps }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input id={id} type={type} {...inputProps} />
      {text}
    </label>
  );
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

// --- A CA's facts ------------------------------------------------------------------------------

/** "Pune · 8 years of experience · ICAI no. 123456" */
export function caFacts(ca) {
  const years = ca.years_experience === 1 ? "year" : "years";
  return `${ca.city} · ${ca.years_experience} ${years} of experience · ICAI no. ${ca.membership_no}`;
}

/** The CA's specializations as badges. */
export function SpecializationBadges({ codes }) {
  return (
    <div className="flex flex-wrap gap-1">
      {codes.map((code) => (
        <Badge key={code} variant="outline">
          {label(CA_SPECIALIZATION_LABELS, code)}
        </Badge>
      ))}
    </div>
  );
}

export function VerifiedBadge() {
  return <Badge className="bg-green-100 text-green-700">Verified</Badge>;
}

// --- Stars -------------------------------------------------------------------------------------

/** 3 -> "★★★☆☆" */
export function Stars({ stars }) {
  return (
    <span className="text-amber-500" role="img" aria-label={stars + " out of 5 stars"}>
      {"★".repeat(stars) + "☆".repeat(5 - stars)}
    </span>
  );
}

/** A CA's average rating and how many ratings it is based on. */
export function RatingSummary({ average, count }) {
  if (!count) {
    return <span className="text-hint">No ratings yet</span>;
  }
  return (
    <span>
      <span className="text-amber-500">★</span> {average} ({count} {count === 1 ? "rating" : "ratings"})
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

/** Shows a Markdown text (e.g. a form's explanation, made from content/forms/<FORM>/explanation.json) as formatted text. */
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

// --- Engagements -------------------------------------------------------------------------------

// Badge colour for each engagement status.
const STATUS_COLORS = {
  requested: "bg-amber-100 text-amber-800",
  active: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-700",
  declined: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-700",
};

/** Where the engagement is: ✓ done steps, ● the current one (bold), ○ steps still to come. */
function Timeline({ status }) {
  const ended = status === "declined" || status === "cancelled";
  const steps = ended ? ["requested", status] : ["requested", "active", "completed"];
  const current = steps.indexOf(status);
  return (
    <ol aria-label="Progress" className="flex flex-wrap items-center gap-1 text-xs">
      {steps.map((step, index) => (
        <li
          key={step}
          aria-current={index === current ? "step" : undefined}
          className={cn(
            index === current && "font-semibold",
            index < current && "text-hint",
            index > current && "text-hint/60",
          )}
        >
          {index > 0 && <span aria-hidden="true">→ </span>}
          {index < current ? "✓ " : index === current ? "● " : "○ "}
          {label(ENGAGEMENT_STATUS_LABELS, step)}
        </li>
      ))}
    </ol>
  );
}

/** One engagement as a card; `children` are the action buttons for its status. */
function EngagementCard({ engagement, title, children }) {
  const items = engagement.items;
  const total = items.reduce((sum, item) => sum + Number(item.listed_price), 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h3>{title}</h3>
          <Badge className={STATUS_COLORS[engagement.status]}>
            {label(ENGAGEMENT_STATUS_LABELS, engagement.status)}
          </Badge>
        </CardTitle>
        <CardDescription>Requested {formatDateTime(engagement.requested_at)}</CardDescription>
        <Timeline status={engagement.status} />
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <table className="w-full text-left">
          <thead className="border-b text-hint">
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
                    <span className="text-hint"> · due {formatDate(item.due_date)}</span>
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
              <td className="py-1">{formatRupees(total)}</td>
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

/**
 * Engagements in three groups (waiting, active, finished), each as a card titled
 * titleOf(engagement) with actions(engagement) as its buttons.
 */
export function EngagementGroups({ engagements, waitingTitle, titleOf, actions }) {
  const groups = [
    [waitingTitle, ["requested"]],
    ["Active", ["active"]],
    ["Finished", ["completed", "declined", "cancelled"]],
  ];
  return groups.map(([title, statuses]) => {
    const inGroup = engagements.filter((engagement) => statuses.includes(engagement.status));
    if (inGroup.length === 0) return null;
    return (
      <section key={title} className="space-y-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        {inGroup.map((engagement) => (
          <EngagementCard key={engagement.id} engagement={engagement} title={titleOf(engagement)}>
            {actions(engagement)}
          </EngagementCard>
        ))}
      </section>
    );
  });
}
