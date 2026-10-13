import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  caMarkFiled,
  cancelDocumentRequest,
  createDocumentRequest,
  downloadDocument,
  useCaBatches,
  useCaClient,
  useCaClients,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  PageTitle,
  QueryStatus,
  Row,
  Section,
  StatusBadge,
  Table,
  useAction,
} from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
} from "@/components/ui";
import {
  daysLeftText,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  label,
  MSME_TIER_LABELS,
} from "@/lib";

// --- CaWorkspacePage ---------------------------------------------------------------------------

/** /ca/clients: the CA's active clients, most urgent first, with why. */
export function CaWorkspacePage() {
  const clients = useCaClients();

  return (
    <div className="max-w-5xl space-y-6">
      <PageTitle title="My clients">
        Businesses you are working for, most urgent first. Open a client to see their filings, ask
        for documents and mark filings as filed.
      </PageTitle>
      <QueryStatus query={clients} />
      {clients.isSuccess && clients.data.length === 0 && (
        <p className="text-sm text-hint">
          No active clients yet. Accepted requests in{" "}
          <Link to="/ca/engagements" className="underline">
            My engagements
          </Link>{" "}
          appear here.
        </p>
      )}
      {clients.isSuccess && clients.data.map((row) => <ClientCard key={row.business_id} row={row} />)}
    </div>
  );
}

function ClientCard({ row }) {
  const next = row.next_deadline
    ? `next deadline ${formatDate(row.next_deadline)} (${daysLeftText(row.next_deadline).toLowerCase()})`
    : "no upcoming deadline";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          <Link to={"/ca/clients/" + row.business_id} className="hover:underline">
            {row.business_name}
          </Link>
          <span
            className={
              "rounded-md px-2 py-0.5 text-sm tabular-nums " +
              (row.score > 0 ? "bg-red-100 text-red-800" : "bg-soft text-hint")
            }
          >
            Urgency {row.score}
          </span>
        </CardTitle>
        <CardDescription>
          {row.open_filing_count} of {row.filing_count} filings to do · {next} ·{" "}
          {row.overdue_count} overdue · {row.open_request_count} open document requests
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm">
        {row.reasons.length === 0 ? (
          <p className="text-hint">Nothing urgent.</p>
        ) : (
          <>
            <p className="font-medium">Why flagged</p>
            <ul className="list-disc pl-5">
              {row.reasons.map((reason) => (
                <li key={reason.reason}>
                  {reason.reason} <span className="text-hint">(+{reason.points})</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// --- CaClientPage ------------------------------------------------------------------------------

const FILED = ["filed", "filed_verified"];

/** /ca/clients/:businessId: one client's profile, filings, files and requests. */
export function CaClientPage() {
  const { businessId } = useParams();
  const client = useCaClient(businessId);
  const refresh = useRefresh();

  return (
    <div className="max-w-4xl space-y-6">
      <BackLink to="/ca/clients">My clients</BackLink>
      <QueryStatus query={client} />
      {client.isSuccess && (
        <>
          <h1 className="text-2xl font-semibold">{client.data.business.legal_name}</h1>
          <Profile business={client.data.business} profile={client.data.profile} />
          <h2 className="text-lg font-semibold">Filings you work on</h2>
          {client.data.filings.length === 0 && (
            <p className="text-sm text-hint">No filings in active work.</p>
          )}
          {client.data.filings.map((row) => (
            <FilingCard
              key={row.filing.id}
              businessId={businessId}
              row={row}
              onChanged={() => refresh(CA_WORKSPACE_KEY)}
            />
          ))}
        </>
      )}
    </div>
  );
}

function Profile({ business, profile }) {
  const lines = [
    ["Entity type", label(ENTITY_TYPE_LABELS, business.entity_type)],
    ["State", business.state],
    ["PAN", business.pan],
    ["GSTIN", business.gstin || "Not registered"],
    ["TAN", business.tan || "—"],
    ["Phone", business.phone],
    ["Annual turnover", formatRupees(business.annual_turnover)],
  ];
  if (profile) {
    lines.push(
      ["MSME tier", label(MSME_TIER_LABELS, profile.msme_tier)],
      ["GST scheme", label(GST_SCHEME_LABELS, profile.gst_scheme)],
      ["ITR form", label(ITR_FORM_LABELS, profile.itr_form)],
      ["Tax audit", profile.audit_applicable ? "Applies" : "Does not apply"],
    );
  }
  return (
    <Section title="Business profile" description={business.description}>
      <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        {lines.map(([name, value]) => (
          <div key={name} className="flex gap-2">
            <dt className="text-hint">{name}:</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function FilingCard({ businessId, row, onChanged }) {
  const item = row.filing;
  const filed = FILED.includes(item.status);
  const labels = { general: "Other", acknowledgement: "Acknowledgement" };
  for (const entry of row.checklist) labels[entry.key] = entry.label;
  const required = row.checklist.filter((entry) => entry.required);
  const ready = required.filter((entry) => entry.ticked);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          {filingFormLabel(item.form_code, item.period_label)} · {item.period_label}
          <StatusBadge status={item.status} />
        </CardTitle>
        <CardDescription>
          Due {formatDate(item.due_date)}
          {!filed && ` · ${daysLeftText(item.due_date)}`}
          {item.acknowledgement_no && ` · Acknowledgement number ${item.acknowledgement_no}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <p className="font-medium">
            Documents: {ready.length} of {required.length} required ready
          </p>
          <ul className="space-y-0.5">
            {row.checklist.map((entry) => (
              <li key={entry.key}>
                <span aria-hidden="true">{entry.ticked ? "✓" : "○"}</span> {entry.label}
                {!entry.required && <span className="text-hint"> (if it applies)</span>}
              </li>
            ))}
          </ul>
        </div>
        <Files files={row.documents} labels={labels} />
        <Requests requests={row.open_requests} labels={labels} onChanged={onChanged} />
        {!filed && (
          <RequestForm businessId={businessId} item={item} checklist={row.checklist} onChanged={onChanged} />
        )}
        {item.status === "with_ca" && (
          <MarkFiledForm businessId={businessId} item={item} onChanged={onChanged} />
        )}
      </CardContent>
    </Card>
  );
}

function Files({ files, labels }) {
  const { error, run } = useAction();

  function open(file) {
    run(() => downloadDocument({ id: file.document_id, original_filename: file.original_filename }));
  }

  return (
    <div>
      <p className="font-medium">Files</p>
      {files.length === 0 ? (
        <p className="text-hint">No files yet.</p>
      ) : (
        <ul>
          {files.map((file) => (
            <li key={file.document_id + file.checklist_key} className="flex flex-wrap items-center gap-2">
              <span className="break-all">{file.original_filename}</span>
              <span className="text-hint">({label(labels, file.checklist_key)})</span>
              <Button
                variant="link"
                size="sm"
                aria-label={"Open " + file.original_filename}
                onClick={() => open(file)}
              >
                Open
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

function Requests({ requests, labels, onChanged }) {
  const { error, run } = useAction();

  async function cancel(request) {
    if (await run(() => cancelDocumentRequest(request.id))) onChanged();
  }

  if (requests.length === 0) return null;
  return (
    <div>
      <p className="font-medium">Waiting for the client</p>
      <ul>
        {requests.map((request) => (
          <li key={request.id} className="flex flex-wrap items-center gap-2">
            <span>
              {label(labels, request.checklist_key)}: {request.message}
            </span>
            <Button variant="link" size="sm" onClick={() => cancel(request)}>
              Cancel request
            </Button>
          </li>
        ))}
      </ul>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

function RequestForm({ businessId, item, checklist, onChanged }) {
  const [sent, setSent] = useState(false);
  const { busy, error, run } = useAction();

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSent(false);
    const message = form.get("message").trim();
    if (await run(() => createDocumentRequest(businessId, item.id, form.get("checklist_key"), message))) {
      formElement.reset();
      setSent(true);
      onChanged();
    }
  }

  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p className="font-medium">Ask for a document</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <Field id={"key-" + item.id} label="Document" className="space-y-1">
          <Select
            id={"key-" + item.id}
            name="checklist_key"
            defaultValue={checklist.find((entry) => !entry.ticked)?.key ?? "general"}
          >
            {checklist.map((entry) => (
              <option key={entry.key} value={entry.key}>
                {entry.label}
              </option>
            ))}
            <option value="general">Something else</option>
          </Select>
        </Field>
        <Field id={"message-" + item.id} label="Message" className="space-y-1">
          <Input
            id={"message-" + item.id}
            name="message"
            required
            maxLength={1000}
            placeholder="What exactly you need"
          />
        </Field>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" disabled={busy}>
          Send request
        </Button>
        {sent && <p className="text-hint">Sent. The client sees it as a to-do.</p>}
        <ErrorText>{error}</ErrorText>
      </div>
    </form>
  );
}

function MarkFiledForm({ businessId, item, onChanged }) {
  const [done, setDone] = useState(null);
  const { busy, error, run } = useAction();

  function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const arn = new FormData(formElement).get("acknowledgement_no").trim();
    run(async () => {
      const result = await caMarkFiled(businessId, item.id, arn, formElement.elements.file.files[0]);
      setDone(
        result.engagement_completed
          ? "Marked as filed. That was the last filing of the engagement, so it is now completed."
          : "Marked as filed.",
      );
      onChanged();
    });
  }

  if (done) return <p className="text-hint">{done}</p>;
  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p className="font-medium">Mark as filed</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <Field id={"arn-" + item.id} label="Acknowledgement number (ARN), optional" className="space-y-1">
          <Input id={"arn-" + item.id} name="acknowledgement_no" maxLength={50} />
        </Field>
        <Field id={"ack-" + item.id} label="Acknowledgement file, optional" className="space-y-1">
          <Input id={"ack-" + item.id} name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
        </Field>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" disabled={busy}>
          Mark as filed
        </Button>
        <ErrorText>{error}</ErrorText>
      </div>
    </form>
  );
}

// --- CaBatchesPage -----------------------------------------------------------------------------

/** /ca/batches: open filings across clients by form and due date, with readiness. */
export function CaBatchesPage() {
  const batches = useCaBatches();

  return (
    <div className="max-w-4xl space-y-6">
      <PageTitle title="Deadline batches">
        The same filing for several clients, due on the same day: see whose documents are ready.
      </PageTitle>
      <QueryStatus query={batches} />
      {batches.isSuccess && batches.data.length === 0 && (
        <p className="text-sm text-hint">No filings to do in your active work.</p>
      )}
      {batches.isSuccess &&
        batches.data.map((batch) => (
          <Section
            key={batch.form_code + batch.due_date}
            title={`${filingFormLabel(batch.form_code, batch.filings[0]?.period_label)} · due ${formatDate(batch.due_date)}`}
            description={`${daysLeftText(batch.due_date)} · ${batch.ready_count} of ${batch.filings.length} clients have every required document`}
          >
            <Table headers={["Client", "Period", "Status", "Documents"]}>
              {batch.filings.map((row) => (
                <Row
                  key={row.compliance_item_id}
                  cells={[
                    <Link to={"/ca/clients/" + row.business_id} className="underline">
                      {row.business_name}
                    </Link>,
                    row.period_label,
                    <StatusBadge status={row.status} />,
                    row.ready
                      ? "Ready"
                      : `${row.required_ready} of ${row.required_total} ready · missing: ${row.missing.join(", ")}`,
                  ]}
                />
              ))}
            </Table>
          </Section>
        ))}
    </div>
  );
}
