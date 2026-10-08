import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  deleteDocument,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
} from "@/api";
import { Pager, QueryStatus } from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import { DOCUMENT_TYPE_LABELS, formatDateTime, label } from "@/lib";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

const PAGE_SIZE = 20;

/** /business/documents: the vault; upload, open and delete files. */
export function DocumentsPage() {
  const [page, setPage] = useState(1);
  const documents = useDocuments({ page, page_size: PAGE_SIZE });

  return (
    <div className="max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Document vault</h1>
        <p className="text-sm text-muted-foreground">
          Your documents, stored encrypted. Link them to a filing from its page, so your CA can see
          them while working on it.
        </p>
      </div>
      <UploadCard />
      <Card>
        <CardHeader>
          <CardTitle>Your documents</CardTitle>
          <CardDescription>
            {documents.isSuccess && `${documents.data.total} documents`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <QueryStatus query={documents} />
          {documents.isSuccess && (
            <DocumentTable result={documents.data} page={page} onPage={setPage} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function UploadCard() {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const [warning, setWarning] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = formElement.elements.file.files[0];
    setError(null);
    setDone(null);
    setWarning(null);
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setBusy(true);
    try {
      const document = await uploadDocument(file, { doc_type: form.get("doc_type") });
      setDone(`Uploaded ${document.original_filename}.`);
      // The file was read (OCR) and seems to be another type than the one chosen.
      if (document.type_warning) {
        setWarning(
          `Check the type: this file seems to be "${label(DOCUMENT_TYPE_LABELS, document.type_warning)}", ` +
            `but you chose "${label(DOCUMENT_TYPE_LABELS, document.doc_type)}".`,
        );
      }
      formElement.reset();
      queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a document</CardTitle>
        <CardDescription>PDF, JPG or PNG.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 sm:grid-cols-2 sm:items-end" onSubmit={onSubmit}>
          <div className="space-y-2">
            <Label htmlFor="upload_file">File</Label>
            <Input id="upload_file" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload_type">Type</Label>
            <select id="upload_type" name="doc_type" defaultValue="other" className={SELECT_CLASS}>
              {UPLOAD_TYPES.map((code) => (
                <option key={code} value={code}>
                  {DOCUMENT_TYPE_LABELS[code]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Uploading..." : "Upload"}
            </Button>
            {done && <p className="text-sm text-muted-foreground">{done}</p>}
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
          {warning && (
            <p role="note" className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900 sm:col-span-2">
              {warning}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

function DocumentTable({ result, page, onPage }) {
  if (result.items.length === 0) {
    return <p className="text-sm text-muted-foreground">No documents here yet.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-medium">File</th>
              <th className="py-2 pr-4 font-medium">Type</th>
              <th className="py-2 pr-4 font-medium">Year / period</th>
              <th className="py-2 pr-4 font-medium">Uploaded</th>
              <th className="py-2 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((document) => (
              <DocumentRow key={document.id} document={document} />
            ))}
          </tbody>
        </table>
      </div>
      <Pager data={{ ...result, page, page_size: PAGE_SIZE }} onPage={onPage} />
    </div>
  );
}

function DocumentRow({ document }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function onDelete() {
    if (!window.confirm(`Delete ${document.original_filename}?`)) return;
    run(async () => {
      await deleteDocument(document.id);
      queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    });
  }

  return (
    <tr className="border-b align-top">
      <td className="py-2 pr-4 break-all">{document.original_filename}</td>
      <td className="py-2 pr-4">
        {label(DOCUMENT_TYPE_LABELS, document.doc_type)}
        {/* The file was read (OCR) and looks like another type. */}
        {document.type_warning && (
          <span className="block text-xs text-amber-700">
            Seems to be: {label(DOCUMENT_TYPE_LABELS, document.type_warning)}
          </span>
        )}
      </td>
      <td className="py-2 pr-4">
        {[document.fy, document.period_label].filter(Boolean).join(" · ") || "—"}
      </td>
      <td className="py-2 pr-4">{formatDateTime(document.created_at)}</td>
      <td className="py-2">
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
        {error && (
          <p role="alert" className="mt-1 max-w-60 text-xs text-destructive">
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}
