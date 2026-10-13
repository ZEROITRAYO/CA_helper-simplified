import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  chooseFilingPath,
  DASHBOARD_KEY,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  filingKey,
  FILINGS_KEY,
  fulfilDocumentRequest,
  linkDocument,
  markFiled,
  tickChecklist,
  unlinkDocument,
  unmarkFiled,
  UPLOAD_TYPES,
  uploadDocument,
  useAcknowledgementFile,
  useDocuments,
  useFiling,
  useMyDocumentRequests,
  useMyEngagements,
  usePeerInsights,
  usePenaltyEstimate,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  FormField,
  Markdown,
  Options,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
  useObjectUrl,
} from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, Input, Select } from "@/components/ui";
import {
  daysLeftText,
  daysUntil,
  DOCUMENT_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
  MSME_TIER_LABELS,
} from "@/lib";

// Statuses in which the business itself can still act on the filing.
const OPEN_FOR_BUSINESS = ["upcoming", "docs_pending", "ready", "overdue"];
const FILED = ["filed", "filed_verified"];
// Engagement statuses in which a CA request or CA work is still going on.
const OPEN_ENGAGEMENTS = ["requested", "active"];
const FILE_TYPES = ".pdf,.jpg,.jpeg,.png";

/** /business/compliance/:itemId: one filing, its checklist, how to file it, mark filed. */
export function FilingPage() {
  const { itemId } = useParams();
  const filing = useFiling(itemId);
  const queryClient = useQueryClient();
  const refresh = useRefresh();

  // Every action returns the updated filing: show it at once, and refresh the lists.
  function showUpdated(updated) {
    queryClient.setQueryData(filingKey(itemId), updated);
    refresh(FILINGS_KEY, DASHBOARD_KEY);
  }

  return (
    <div className="max-w-3xl space-y-6">
      <BackLink to="/business/compliance">Compliance calendar</BackLink>
      <QueryStatus query={filing} />
      {filing.isSuccess && (
        <>
          <Header page={filing.data} />
          {!FILED.includes(filing.data.filing.status) &&
            daysUntil(filing.data.filing.due_date) < 0 && <Penalty item={filing.data.filing} />}
          <HowToFile page={filing.data} onUpdated={showUpdated} />
          <PeerInsights item={filing.data.filing} />
          <CaRequests page={filing.data} />
          <Checklist page={filing.data} onUpdated={showUpdated} />
          <Guide page={filing.data} />
        </>
      )}
    </div>
  );
}

function Header({ page }) {
  const item = page.filing;
  return (
    <div className="space-y-1">
      <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold">
        {filingFormLabel(item.form_code, item.period_label)} · {item.period_label}
        <StatusBadge status={item.status} />
      </h1>
      <p className="text-sm text-hint">
        {page.form_name} · due {formatDate(item.due_date)}
        {!FILED.includes(item.status) && ` · ${daysLeftText(item.due_date)}`}
      </p>
    </div>
  );
}

// --- What being late may cost --------------------------------------------------------------

function Penalty({ item }) {
  const [taxDue, setTaxDue] = useState("");
  // The amount the estimate was last asked for (only on "Estimate", not on every key).
  const [askedTaxDue, setAskedTaxDue] = useState("");
  const estimate = usePenaltyEstimate(item.id, askedTaxDue, true);
  const amount = (value) => (value === null ? "not available" : formatRupees(value));

  function onSubmit(event) {
    event.preventDefault();
    setAskedTaxDue(taxDue.trim());
  }

  return (
    <Section
      title="Late fees and interest"
      description={estimate.data?.label ?? "Estimate (rules pending verification)"}
      className="ring-red-300"
      contentClassName="space-y-3 text-sm"
    >
      <QueryStatus query={estimate} />
      {estimate.isSuccess && (
        <div className="space-y-1">
          <p>{estimate.data.days_late} days late.</p>
          <p>Late fee: {amount(estimate.data.late_fee)}</p>
          <p>Interest: {amount(estimate.data.interest)}</p>
          {estimate.data.total !== null && (
            <p className="font-medium">Total: {formatRupees(estimate.data.total)}</p>
          )}
          {estimate.data.notes.map((note) => (
            <p key={note} className="text-hint">
              {note}
            </p>
          ))}
        </div>
      )}
      <form className="flex flex-wrap items-end gap-2" onSubmit={onSubmit}>
        <FormField
          id="tax_due"
          label="Tax due (₹, optional, for the interest)"
          inputMode="decimal"
          value={taxDue}
          onChange={(event) => setTaxDue(event.target.value)}
        />
        <Button type="submit" variant="outline">
          Estimate
        </Button>
      </form>
    </Section>
  );
}

// --- How the filing gets done: path, CA, mark filed ----------------------------------------

function HowToFile({ page, onUpdated }) {
  const item = page.filing;
  const engagements = useMyEngagements();
  // The CA engagement this filing is in, if any (a request or active work).
  const engagement = (engagements.data || []).find(
    (candidate) =>
      OPEN_ENGAGEMENTS.includes(candidate.status) &&
      candidate.items.some((engagementItem) => engagementItem.compliance_item_id === item.id),
  );

  if (FILED.includes(item.status)) {
    return <Filed page={page} onUpdated={onUpdated} />;
  }
  if (!engagement && item.status !== "with_ca") {
    return <ChoosePath page={page} onUpdated={onUpdated} />;
  }
  let text = "A CA is working on this filing. They will mark it as filed.";
  if (engagement && engagement.status === "active") {
    text = `${engagement.ca_name} is working on this filing. They will mark it as filed.`;
  } else if (engagement) {
    text = `Your request to ${engagement.ca_name} is waiting for an answer.`;
  }
  return (
    <Section
      title="With a CA"
      description={
        <>
          {text}{" "}
          <Link to="/business/engagements" className="text-primary hover:underline">
            See my engagements
          </Link>
        </>
      }
    />
  );
}

function ChoosePath({ page, onUpdated }) {
  const item = page.filing;
  const { busy, error, run } = useAction();
  // The marketplace can pre-select the matching service; ITR has several, so no filter.
  const findCaLink =
    item.form_code === "itr" ? "/business/marketplace" : `/business/marketplace?service=${item.form_code}`;

  function pathButton(path, text) {
    const chosen = item.filing_path === path;
    return (
      <Button
        variant={chosen ? "default" : "outline"}
        aria-pressed={chosen}
        disabled={busy}
        onClick={() => run(async () => onUpdated(await chooseFilingPath(item.id, path)))}
      >
        {text}
      </Button>
    );
  }

  return (
    <Section
      title="How will you file it?"
      description="File it yourself on the government portal, or let a CA do it for you."
      contentClassName="space-y-4"
    >
      {OPEN_FOR_BUSINESS.includes(item.status) && (
        <div className="flex flex-wrap gap-2">
          {pathButton("self", "I'll file it myself")}
          {pathButton("ca", "Get a CA")}
        </div>
      )}
      <ErrorText>{error}</ErrorText>
      {item.filing_path === "ca" && (
        <p className="text-sm">
          <Link to={findCaLink} className="text-primary hover:underline">
            Find a CA for this filing →
          </Link>
        </p>
      )}
      {item.filing_path === "self" && <MarkFiledForm page={page} onUpdated={onUpdated} />}
    </Section>
  );
}

function MarkFiledForm({ page, onUpdated }) {
  const [arn, setArn] = useState("");
  const [file, setFile] = useState(null);
  const { busy, error, run } = useAction();

  function onSubmit(event) {
    event.preventDefault();
    run(async () => onUpdated(await markFiled(page.filing.id, arn.trim(), file)));
  }

  return (
    <form className="space-y-3 border-t pt-4" onSubmit={onSubmit}>
      <p className="text-sm font-medium">Filed it on the portal? Mark it as filed.</p>
      <FormField
        id="acknowledgement_no"
        label="Acknowledgement number / ARN (optional)"
        value={arn}
        onChange={(event) => setArn(event.target.value)}
      />
      <Field id="acknowledgement_file" label="Acknowledgement file (optional: PDF, JPG or PNG)">
        <input
          id="acknowledgement_file"
          type="file"
          accept="application/pdf,image/jpeg,image/png"
          className="block text-sm"
          onChange={(event) => setFile(event.target.files[0] || null)}
        />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button type="submit" disabled={busy}>
        {busy ? "Saving..." : "Mark as filed"}
      </Button>
    </form>
  );
}

/** What the acknowledgement showed when read; why it did not verify, if it did not. */
function Verification({ verification }) {
  if (verification.verified) {
    return (
      <p className="rounded-lg bg-green-50 p-3 text-green-900">
        ✓ Verified from the acknowledgement: number {verification.acknowledgement_no}, filed on{" "}
        {formatDate(verification.filing_date)}.
      </p>
    );
  }
  return (
    <div className="rounded-lg bg-amber-50 p-3 text-amber-900">
      <p className="font-medium">We could not verify it from the acknowledgement:</p>
      <ul className="list-disc pl-5">
        {verification.problems.map((problem) => (
          <li key={problem}>{problem}</li>
        ))}
      </ul>
      <p className="mt-1 text-xs">
        Check that you uploaded the acknowledgement of this filing. It stays marked as filed.
      </p>
    </div>
  );
}

function Filed({ page, onUpdated }) {
  const item = page.filing;
  const acknowledgement = page.acknowledgement;
  const { error, run } = useAction();
  const file = useAcknowledgementFile(item.id, acknowledgement !== null);
  const url = useObjectUrl(file.data);

  return (
    <Section
      title={item.status === "filed_verified" ? "Filed and verified" : "Filed"}
      description={
        <>
          {item.filed_at ? `Marked as filed on ${formatDateTime(item.filed_at)}.` : "Filed."}
          {item.acknowledgement_no && ` Acknowledgement number: ${item.acknowledgement_no}.`}
        </>
      }
      contentClassName="space-y-3 text-sm"
    >
      {acknowledgement === null ? (
        <p className="text-hint">No acknowledgement file was uploaded.</p>
      ) : url ? (
        <a href={url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
          Open the acknowledgement ({acknowledgement.filename})
        </a>
      ) : (
        <p className="text-hint">Loading the acknowledgement...</p>
      )}
      {acknowledgement !== null && <Verification verification={acknowledgement.verification} />}
      {item.filing_path === "self" && (
        <div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => run(async () => onUpdated(await unmarkFiled(item.id)))}
          >
            Undo: not filed yet
          </Button>
        </div>
      )}
      <ErrorText>{error}</ErrorText>
    </Section>
  );
}

// --- Documents to have ready ---------------------------------------------------------------

function Checklist({ page, onUpdated }) {
  const item = page.filing;
  const refresh = useRefresh();
  const [busyKey, setBusyKey] = useState(null);
  const { error, run } = useAction();
  const locked = FILED.includes(item.status);
  const documents = useDocuments({ compliance_item_id: item.id, page_size: 100 });
  const linked = linksByKey(documents.data, item.id);
  const required = page.checklist.filter((entry) => entry.required);
  const requiredTicked = required.filter((entry) => entry.ticked);

  async function toggle(entry) {
    setBusyKey(entry.key);
    await run(async () => onUpdated(await tickChecklist(item.id, entry.key, !entry.ticked)));
    setBusyKey(null);
  }

  // A file was added or removed: the documents, and maybe a tick and the status, changed.
  function onChanged() {
    refresh(DOCUMENTS_KEY, filingKey(item.id), FILINGS_KEY, DASHBOARD_KEY);
  }

  function documentsOf(key, entryLabel) {
    return (
      <EntryDocuments
        item={item}
        entryKey={key}
        entryLabel={entryLabel}
        links={linked[key] ?? []}
        locked={locked}
        onChanged={onChanged}
      />
    );
  }

  return (
    <Section
      title="Documents to have ready"
      description={
        `Tick what you have, or add the file: it is ticked for you, and a CA working on this ` +
        `filing can open it. ${requiredTicked.length} of ${required.length} required documents ready.`
      }
      contentClassName="space-y-3"
    >
      {page.checklist.map((entry) => (
        <div key={entry.key} className="space-y-1">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={entry.ticked}
              disabled={locked || busyKey !== null}
              onChange={() => toggle(entry)}
            />
            <span>
              {entry.label}
              {!entry.required && <span className="text-hint"> (if it applies)</span>}
              {entry.help && <span className="block text-xs text-hint">{entry.help}</span>}
            </span>
          </label>
          {documentsOf(entry.key, entry.label)}
        </div>
      ))}
      <div className="space-y-1 border-t pt-3">
        <p className="text-sm font-medium">Other documents for this filing</p>
        {documentsOf("general", "this filing")}
      </div>
      <ErrorText>{documents.isError && errorMessage(documents.error)}</ErrorText>
      <ErrorText>{error}</ErrorText>
    </Section>
  );
}

// {checklist key: [{ link, document }]}: the files linked to this filing, per entry.
function linksByKey(documents, itemId) {
  const byKey = {};
  for (const document of documents?.items ?? []) {
    for (const link of document.links) {
      if (link.compliance_item_id !== itemId) continue;
      byKey[link.checklist_key] ??= [];
      byKey[link.checklist_key].push({ link, document });
    }
  }
  return byKey;
}

// The files linked to one checklist entry (or "general"), and "Add a file" for more.
function EntryDocuments({ item, entryKey, entryLabel, links, locked, onChanged }) {
  const [adding, setAdding] = useState(false);
  const { busy, error, run } = useAction();

  // "Open" or "Remove" next to a file.
  function linkButton(text, document, action) {
    return (
      <Button
        variant="link"
        size="sm"
        disabled={busy}
        aria-label={text + " " + document.original_filename}
        onClick={() => run(action)}
      >
        {text}
      </Button>
    );
  }

  return (
    <div className="ml-6 space-y-1 text-sm">
      {links.map(({ link, document }) => (
        <div key={link.id} className="flex flex-wrap items-center gap-x-2">
          <span className="break-all">{document.original_filename}</span>
          {linkButton("Open", document, () => downloadDocument(document))}
          {!locked &&
            linkButton("Remove", document, async () => {
              await unlinkDocument(link.id);
              onChanged();
            })}
        </div>
      ))}
      {!locked && !adding && (
        <Button
          variant="outline"
          size="sm"
          aria-label={"Add a file for " + entryLabel}
          onClick={() => setAdding(true)}
        >
          Add a file
        </Button>
      )}
      {adding && (
        <AddDocument
          item={item}
          entryKey={entryKey}
          links={links}
          onAdded={() => {
            setAdding(false);
            onChanged();
          }}
          onCancel={() => setAdding(false)}
        />
      )}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** A <select> of the business's vault files (all, or all but `except`). */
function VaultSelect({ id, except = [], withType }) {
  const vault = useDocuments({ page_size: 100 });
  const choices = (vault.data?.items ?? []).filter((document) => !except.includes(document.id));
  return (
    <Select id={id} name="document_id" defaultValue="">
      <option value="">{vault.isPending ? "Loading..." : "Choose a file"}</option>
      {choices.map((document) => (
        <option key={document.id} value={document.id}>
          {document.original_filename}
          {withType && ` (${label(DOCUMENT_TYPE_LABELS, document.doc_type)})`}
        </option>
      ))}
    </Select>
  );
}

// Upload a new file for the entry, or link one that is already in the vault.
function AddDocument({ item, entryKey, links, onAdded, onCancel }) {
  const { busy, error, setError, run } = useAction();

  async function add(action) {
    if (await run(action)) onAdded();
  }

  function onUpload(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = event.currentTarget.elements.file.files[0];
    if (!file) return setError("Choose a file to upload.");
    const fields = { doc_type: form.get("doc_type"), compliance_item_id: item.id, checklist_key: entryKey };
    add(() => uploadDocument(file, fields));
  }

  function onLink(event) {
    event.preventDefault();
    const documentId = new FormData(event.currentTarget).get("document_id");
    if (!documentId) return setError("Choose a file from your vault.");
    add(() => linkDocument(documentId, item.id, entryKey));
  }

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <form className="flex flex-wrap items-end gap-2" onSubmit={onUpload}>
        <Field id={"file-" + entryKey} label="Upload a new file" className="space-y-1">
          <Input id={"file-" + entryKey} name="file" type="file" accept={FILE_TYPES} />
        </Field>
        <Field id={"type-" + entryKey} label="Type" className="space-y-1">
          <Select id={"type-" + entryKey} name="doc_type" defaultValue="other">
            <Options labels={DOCUMENT_TYPE_LABELS} codes={UPLOAD_TYPES} />
          </Select>
        </Field>
        <Button type="submit" size="sm" disabled={busy}>
          Upload
        </Button>
      </form>
      <form className="flex flex-wrap items-end gap-2" onSubmit={onLink}>
        <Field id={"existing-" + entryKey} label="Or link one from your vault" className="space-y-1">
          <VaultSelect
            id={"existing-" + entryKey}
            except={links.map(({ document }) => document.id)}
            withType
          />
        </Field>
        <Button type="submit" size="sm" disabled={busy}>
          Link
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </form>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

// --- How similar businesses file it --------------------------------------------------------

function PeerInsights({ item }) {
  const peers = usePeerInsights(item.id);
  if (!peers.isSuccess) return null;
  const data = peers.data;
  const form = filingFormLabel(item.form_code, item.period_label);

  let who = `all ${data.business_count} businesses on CA Helper that filed ${form}`;
  if (data.scope === "segment") {
    const tier = label(MSME_TIER_LABELS, data.msme_tier).toLowerCase();
    const type = label(ENTITY_TYPE_LABELS, data.entity_type).toLowerCase();
    who = `${data.business_count} ${tier} businesses like yours (${type}) that filed ${form}`;
  }
  if (data.scope === "none") {
    return (
      <Section
        title="How similar businesses file it"
        description={`Not enough businesses have filed ${form} here yet to compare (at least ${data.min_businesses} are needed).`}
      />
    );
  }
  return (
    <Section
      title="How similar businesses file it"
      description={`Among ${who}:`}
      contentClassName="grid gap-3 text-sm sm:grid-cols-2"
    >
      <PeerPath title="Filed it themselves" figures={data.self} />
      <PeerPath title="Filed it through a CA" figures={data.ca} />
    </Section>
  );
}

function PeerPath({ title, figures }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-hint">{title}</p>
      <p className="text-2xl font-semibold tabular-nums">{figures.share_pct ?? 0}%</p>
      <p>{figures.on_time_pct === null ? "No filings yet" : `${figures.on_time_pct}% of them on time`}</p>
    </div>
  );
}

// --- Documents the CA asked for ------------------------------------------------------------

function CaRequests({ page }) {
  const item = page.filing;
  const requests = useMyDocumentRequests(item.id);
  const refresh = useRefresh();
  if (!requests.isSuccess || requests.data.length === 0) return null;

  const labels = { general: "A document" };
  for (const entry of page.checklist) labels[entry.key] = entry.label;

  return (
    <Section
      title="Your CA asked for documents"
      description="Send each file here; your CA is told when it arrives."
      className="ring-amber-300"
      contentClassName="space-y-4 text-sm"
    >
      {requests.data.map((request) => (
        <AnswerRequest
          key={request.id}
          request={request}
          what={label(labels, request.checklist_key)}
          // The file, the ticks and the to-dos changed.
          onAnswered={() => refresh(CA_WORKSPACE_KEY, DOCUMENTS_KEY, filingKey(item.id), FILINGS_KEY)}
        />
      ))}
    </Section>
  );
}

// Answer one request with a new file (uploaded to the vault first) or a vault file.
function AnswerRequest({ request, what, onAnswered }) {
  const { busy, error, setError, run } = useAction();

  async function onSubmit(event) {
    event.preventDefault();
    const file = event.currentTarget.elements.file.files[0];
    const documentId = new FormData(event.currentTarget).get("document_id");
    if (!file && !documentId) return setError("Choose a file to upload, or one from your vault.");
    const sent = await run(async () => {
      const chosen = file ? (await uploadDocument(file, { doc_type: "other" })).id : documentId;
      await fulfilDocumentRequest(request.id, chosen);
    });
    if (sent) onAnswered();
  }

  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p>
        <span className="font-medium">{what}</span> · {request.ca_name}: “{request.message}”
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <Field id={"answer-file-" + request.id} label="Upload a file" className="space-y-1">
          <Input id={"answer-file-" + request.id} name="file" type="file" accept={FILE_TYPES} />
        </Field>
        <Field id={"answer-vault-" + request.id} label="or choose from your vault" className="space-y-1">
          <VaultSelect id={"answer-vault-" + request.id} />
        </Field>
        <Button type="submit" size="sm" disabled={busy}>
          Send to my CA
        </Button>
      </div>
      <ErrorText>{error}</ErrorText>
    </form>
  );
}

// --- What the form is and how to file it ---------------------------------------------------

function Guide({ page }) {
  const [tab, setTab] = useState("instructions");
  const texts = {
    instructions: ["How to file it yourself", page.instructions],
    explanation: ["What is this form?", page.explanation],
  };

  return (
    <Card>
      <CardHeader>
        <div role="tablist" className="flex gap-2">
          {Object.entries(texts).map(([key, [title]]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={
                "rounded-full border px-3 py-1 text-sm " +
                (tab === key ? "border-primary bg-primary text-white" : "hover:bg-soft")
              }
            >
              {title}
            </button>
          ))}
        </div>
        {page.content_status !== "DONE" && (
          <CardDescription>
            This guide is a draft that has not been checked yet. Follow the official portal when in
            doubt.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <Markdown>{texts[tab][1]}</Markdown>
      </CardContent>
    </Card>
  );
}
