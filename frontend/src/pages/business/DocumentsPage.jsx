import { useState } from "react";

import {
  deleteDocument,
  DOCUMENTS_KEY,
  downloadDocument,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useRefresh,
} from "@/api";
import {
  ErrorText,
  Field,
  Options,
  PageTitle,
  Pager,
  QueryStatus,
  Row,
  Section,
  Table,
  useAction,
} from "@/components/shared";
import { Button, Input, Select } from "@/components/ui";
import { DOCUMENT_TYPE_LABELS, formatDateTime, label } from "@/lib";

const PAGE_SIZE = 20;

/** /business/documents: the vault; upload, open and delete files. */
export function DocumentsPage() {
  const [page, setPage] = useState(1);
  const documents = useDocuments({ page, page_size: PAGE_SIZE });

  return (
    <div className="max-w-5xl space-y-6">
      <PageTitle title="Document vault">
        Your documents, stored encrypted. Link them to a filing from its page, so your CA can see
        them while working on it.
      </PageTitle>
      <UploadCard />
      <Section
        title="Your documents"
        description={documents.isSuccess && `${documents.data.total} documents`}
        contentClassName="space-y-4"
      >
        <QueryStatus query={documents} />
        {documents.isSuccess && <DocumentTable result={documents.data} page={page} onPage={setPage} />}
      </Section>
    </div>
  );
}

function UploadCard() {
  const refresh = useRefresh();
  const [done, setDone] = useState(null);
  const [warning, setWarning] = useState(null);
  const { busy, error, setError, run } = useAction();

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const file = formElement.elements.file.files[0];
    const docType = new FormData(formElement).get("doc_type");
    setDone(null);
    setWarning(null);
    if (!file) return setError("Choose a file to upload.");
    await run(async () => {
      const document = await uploadDocument(file, { doc_type: docType });
      setDone(`Uploaded ${document.original_filename}.`);
      // The file was read (OCR) and seems to be another type than the one chosen.
      if (document.type_warning) {
        setWarning(
          `Check the type: this file seems to be "${label(DOCUMENT_TYPE_LABELS, document.type_warning)}", ` +
            `but you chose "${label(DOCUMENT_TYPE_LABELS, document.doc_type)}".`,
        );
      }
      formElement.reset();
      refresh(DOCUMENTS_KEY);
    });
  }

  return (
    <Section title="Upload a document" description="PDF, JPG or PNG.">
      <form className="grid gap-3 sm:grid-cols-2 sm:items-end" onSubmit={onSubmit}>
        <Field id="upload_file" label="File">
          <Input id="upload_file" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
        </Field>
        <Field id="upload_type" label="Type">
          <Select id="upload_type" name="doc_type" defaultValue="other">
            <Options labels={DOCUMENT_TYPE_LABELS} codes={UPLOAD_TYPES} />
          </Select>
        </Field>
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? "Uploading..." : "Upload"}
          </Button>
          {done && <p className="text-sm text-muted-foreground">{done}</p>}
          <ErrorText>{error}</ErrorText>
        </div>
        {warning && (
          <p role="note" className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900 sm:col-span-2">
            {warning}
          </p>
        )}
      </form>
    </Section>
  );
}

function DocumentTable({ result, page, onPage }) {
  if (result.items.length === 0) {
    return <p className="text-sm text-muted-foreground">No documents here yet.</p>;
  }
  const actions = <span className="sr-only">Actions</span>;
  return (
    <div className="space-y-3">
      <Table headers={["File", "Type", "Year / period", "Uploaded", actions]}>
        {result.items.map((document) => (
          <DocumentRow key={document.id} document={document} />
        ))}
      </Table>
      <Pager data={{ ...result, page, page_size: PAGE_SIZE }} onPage={onPage} />
    </div>
  );
}

function DocumentRow({ document }) {
  const refresh = useRefresh();
  const { busy, error, run } = useAction();

  async function onDelete() {
    if (!window.confirm(`Delete ${document.original_filename}?`)) return;
    if (await run(() => deleteDocument(document.id))) refresh(DOCUMENTS_KEY);
  }

  return (
    <Row
      cells={[
        <span className="break-all">{document.original_filename}</span>,
        <>
          {label(DOCUMENT_TYPE_LABELS, document.doc_type)}
          {/* The file was read (OCR) and looks like another type. */}
          {document.type_warning && (
            <span className="block text-xs text-amber-700">
              Seems to be: {label(DOCUMENT_TYPE_LABELS, document.type_warning)}
            </span>
          )}
        </>,
        [document.fy, document.period_label].filter(Boolean).join(" · ") || "—",
        formatDateTime(document.created_at),
        <>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => run(() => downloadDocument(document))}
            >
              Open
            </Button>
            <Button variant="outline" size="sm" disabled={busy} onClick={onDelete}>
              Delete
            </Button>
          </div>
          <ErrorText className="mt-1 max-w-60 text-xs">{error}</ErrorText>
        </>,
      ]}
    />
  );
}
