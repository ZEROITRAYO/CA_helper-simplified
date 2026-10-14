import { useQuery, useQueryClient } from "@tanstack/react-query";

// --- client ------------------------------------------------------------------------------------

/**
 * apiFetch(): the one way the frontend calls the backend.
 *
 *   apiFetch("/api/v1/compliance/dashboard")
 *   apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } })
 *
 * - Every URL is the full path ("/api/v1/..."). The Vite dev server forwards /api
 *   to Flask, so requests go to the page's own origin.
 * - Sends `body` as JSON (a FormData body, for file uploads, as it is) and returns the
 *   parsed JSON response (null if there is none). apiDownload() gets a file instead.
 * - Adds `Authorization: Bearer <token>` while someone is logged in.
 * - Throws ApiRequestError (status, code, message) for every error response.
 * - A 401 on a request that carried a token logs the user out (the token expired or
 *   the account no longer exists).
 * - A request with no answer after REQUEST_TIMEOUT fails with code TIMEOUT, so a
 *   hung server shows a clear message instead of a page that never finishes.
 *
 * The functions below use it directly, or through useGet() and sendForm().
 */

/** A failed API call: switch on `code` (e.g. INVALID_CREDENTIALS) and show `message`. */
export class ApiRequestError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

// How long a request may take, in milliseconds (20000 ms = 20 seconds), before it fails with code TIMEOUT.
export const REQUEST_TIMEOUT = 20_000;

// The logged-in user's token and how to log them out. AuthProvider
// (auth.jsx) sets both through setAuth() whenever the session changes.
let accessToken = null;
let logout = () => {};

export function setAuth(token, logoutFunction) {
  accessToken = token;
  logout = logoutFunction;
}

// My PR #7 version (no timeout yet). The timeout below is added later, see MY_LATER_TODO.md.
//
// export async function apiFetch(path, { method = "GET", body } = {}) {
//   const headers = {};
//   const isForm = body instanceof FormData; // a file upload: the browser sets the type
//   if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
//   if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
//
//   const response = await fetch(path, {
//     method,
//     headers,
//     body: body === undefined || isForm ? body : JSON.stringify(body),
//   });
//   // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
//   const data = await response.json().catch(() => null);
//   if (response.ok) return data;
//   fail(response, data, headers.Authorization);
// }

export async function apiFetch(path, { method = "GET", body } = {}) {
  const headers = {};
  const isForm = body instanceof FormData; // a file upload: the browser sets the type
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
  let response;
  let data;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined || isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
    data = await response.json().catch(() => null);
  } catch (error) {
    if (!controller.signal.aborted) throw error; // a network failure: see errorMessage()
  } finally {
    clearTimeout(timer);
  }
  if (controller.signal.aborted) {
    throw new ApiRequestError(
      0,
      "TIMEOUT",
      "The server did not answer within 20 seconds. Try again in a moment.",
    );
  }
  if (response.ok) return data;
  fail(response, data, headers.Authorization);
}

/** Download a file the API sends as a Blob; errors throw ApiRequestError like apiFetch(). */
export async function apiDownload(path) {
  const hadToken = Boolean(accessToken);
  const response = await fetch(path, {
    headers: hadToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (response.ok) return response.blob();
  fail(response, await response.json().catch(() => null), hadToken);
}

// Throws the ApiRequestError of a failed response; a 401 to a request with a token logs out.
function fail(response, data, hadToken) {
  if (response.status === 401 && hadToken) logout();
  let code = "HTTP_ERROR";
  let message = response.status;
  if (data && data.error) {
    code = data.error.code;
    message = data.error.message;
  }
  throw new ApiRequestError(response.status, code, message);
}

/** Text to show for any error thrown by a query: the API's message, or a network hint. */
export function errorMessage(error) {
  if (error instanceof ApiRequestError) return error.message;
  return "Cannot reach the server. Check your connection and try again.";
}


// --- Helpers for the calls below ---------------------------------------------------------------

// A GET. With `notFound` (an error code), that error answers null instead, e.g. for a
// business that has not registered yet.
async function get(path, notFound) {
  try {
    return await apiFetch(path);
  } catch (error) {
    if (notFound && error.code === notFound) return null;
    throw error;
  }
}

// A GET as a cached query: useGet(KEY, "/api/v1/...", { notFound, enabled, ... }).
function useGet(queryKey, path, { notFound, ...options } = {}) {
  return useQuery({ queryKey, queryFn: () => get(path, notFound), ...options });
}

// POST a file upload: every field that has a value (a File or text) goes in the form.
function sendForm(path, fields) {
  const form = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    if (value) form.append(name, value);
  }
  return apiFetch(path, { method: "POST", body: form });
}

// path?name=value&... without the empty values ("", null or undefined).
function withQuery(path, params) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== "" && value !== null && value !== undefined) query.set(name, value);
  }
  const text = query.toString();
  return text ? path + "?" + text : path;
}

/** refresh(KEY, OTHER_KEY, ...): load these cached queries again, after a change. */
export function useRefresh() {
  const queryClient = useQueryClient();
  return function refresh(...keys) {
    for (const key of keys) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  };
}

// --- health ------------------------------------------------------------------------------------

/** GET /api/health; plain fetch, because its 503 body is data to show, not an error. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch("/api/health");
      if (response.ok || response.status === 503) return response.json();
      throw new Error(`API returned HTTP ${response.status}`);
    },
    retry: false,
  });
}

// --- auth --------------------------------------------------------------------------------------

/** The new (unverified) user. Signing up is only possible after ticking "I agree to the Terms". */
export function signup({ full_name, email, password, role }) {
  return apiFetch("/api/v1/auth/signup", {
    method: "POST",
    body: { full_name, email, password, role, terms_accepted: true },
  });
}

/** The 6-digit code emailed at signup. */
export function verifyEmail(email, code) {
  return apiFetch("/api/v1/auth/verify-email", { method: "POST", body: { email, code } });
}

export function resendVerificationCode(email) {
  return apiFetch("/api/v1/auth/verify-email/resend", { method: "POST", body: { email } });
}

/** Emails a reset code. */
export function forgotPassword(email) {
  return apiFetch("/api/v1/auth/forgot-password", { method: "POST", body: { email } });
}

export function resetPassword(email, code, newPassword) {
  return apiFetch("/api/v1/auth/reset-password", {
    method: "POST",
    body: { email, code, new_password: newPassword },
  });
}


export const SETTINGS_KEY = ["auth", "settings"];

/** { email_notifications } */
export function useSettings() {
  return useGet(SETTINGS_KEY, "/api/v1/auth/settings");
}

/** Switch the notification emails on or off; returns the settings. */
export function saveSettings(emailNotifications) {
  return apiFetch("/api/v1/auth/settings", {
    method: "PUT",
    body: { email_notifications: emailNotifications },
  });
}

// --- onboarding --------------------------------------------------------------------------------

export const MY_BUSINESS_KEY = ["onboarding", "business"];

/** { business, profile, nic_code }, or null before the business is registered. */
export function useMyBusiness() {
  return useGet(MY_BUSINESS_KEY, "/api/v1/onboarding/business", { notFound: "BUSINESS_NOT_FOUND" });
}

/** Registers the business (once); the backend works out the profile and makes the filings. */
export function registerBusiness(form) {
  return apiFetch("/api/v1/onboarding/business", { method: "POST", body: form });
}

/** Edits the business; the answer also has changes: { profile: [{line, old, new}], filings }. */
export function updateBusiness(form) {
  return apiFetch("/api/v1/onboarding/business", { method: "PUT", body: form });
}

/** Searches the NIC list by code or words, once at least 2 characters are typed. */
export function useNicSearch(query) {
  const text = query.trim();
  const path = "/api/v1/onboarding/nic-codes?q=" + encodeURIComponent(text);
  return useGet(["onboarding", "nic-codes", text], path, { enabled: text.length >= 2 });
}

/** Returns { code, description }. */
export function saveNicCode(code) {
  return apiFetch("/api/v1/onboarding/business/nic-code", { method: "PUT", body: { code } });
}

/** The states with their GST codes; reference data, so it is loaded once. */
export function useGstStates() {
  return useGet(["onboarding", "states"], "/api/v1/onboarding/states", { staleTime: Infinity });
}

/** Reads a GST certificate or PAN card (not stored): { found: { pan?, gstin?, ... } }. */
export function readRegistrationDocument(file) {
  return sendForm("/api/v1/onboarding/autofill", { file });
}

// --- compliance --------------------------------------------------------------------------------

export const FILINGS_KEY = ["compliance", "items"];
export const DASHBOARD_KEY = ["compliance", "dashboard"];

export function useComplianceDashboard() {
  return useGet(DASHBOARD_KEY, "/api/v1/compliance/dashboard");
}

/** The business's filings, soonest due first; null before the business is registered. */
export function useFilings() {
  return useGet(FILINGS_KEY, "/api/v1/compliance/items", { notFound: "BUSINESS_NOT_FOUND" });
}

/** One filing in the cache; the actions below return the updated filing for it. */
export function filingKey(itemId) {
  return ["compliance", "item", itemId];
}

/** { filing, form_name, content_status, explanation, instructions, checklist, acknowledgement } */
export function useFiling(itemId) {
  return useGet(filingKey(itemId), "/api/v1/compliance/items/" + itemId);
}

/** path is "self" (file it myself) or "ca" (with a CA). */
export function chooseFilingPath(itemId, path) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/path", {
    method: "POST",
    body: { path },
  });
}

export function tickChecklist(itemId, key, ticked) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/checklist", {
    method: "POST",
    body: { key, ticked },
  });
}

/** "I filed it myself". Both the ARN and the file are optional. */
export function markFiled(itemId, acknowledgementNo, file) {
  const path = "/api/v1/compliance/items/" + itemId + "/mark-filed";
  return sendForm(path, { acknowledgement_no: acknowledgementNo, file });
}

/** Undo a mistaken "mark as filed". */
export function unmarkFiled(itemId) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/unmark-filed", { method: "POST" });
}

/** The uploaded acknowledgement file (a Blob), loaded only when there is one. */
export function useAcknowledgementFile(itemId, enabled) {
  return useQuery({
    queryKey: [...filingKey(itemId), "acknowledgement"],
    queryFn: () => apiDownload("/api/v1/compliance/items/" + itemId + "/acknowledgement"),
    enabled,
  });
}

/** How similar businesses file this form. */
export function usePeerInsights(itemId) {
  const path = "/api/v1/compliance/items/" + itemId + "/peer-insights";
  return useGet([...filingKey(itemId), "peers"], path);
}

// --- documents ---------------------------------------------------------------------------------

// The types a business can upload (every documents.doc_type but a CA's certificate).
export const UPLOAD_TYPES = [
  "gst_certificate",
  "pan_card",
  "sales_register",
  "purchase_register",
  "bank_statement",
  "invoice",
  "salary_register",
  "tds_challan",
  "acknowledgement",
  "other",
];

// Every documents list in the cache starts with this; refresh it after a change.
export const DOCUMENTS_KEY = ["documents"];

/** { items, page, page_size, total }, newest first; params are the filters. */
export function useDocuments(params, enabled = true) {
  return useGet([...DOCUMENTS_KEY, params], withQuery("/api/v1/documents", params), { enabled });
}

/** Only doc_type is needed; compliance_item_id (and checklist_key) also link it to a filing. */
export function uploadDocument(file, fields) {
  return sendForm("/api/v1/documents", { file, ...fields });
}

/** Fails with DOCUMENT_IN_USE for the proof of a filed filing. */
export function deleteDocument(documentId) {
  return apiFetch("/api/v1/documents/" + documentId, { method: "DELETE" });
}

/** Link a vault file to a filing's checklist entry ("general" for none); ticks the entry. */
export function linkDocument(documentId, complianceItemId, checklistKey) {
  return apiFetch("/api/v1/documents/" + documentId + "/links", {
    method: "POST",
    body: { compliance_item_id: complianceItemId, checklist_key: checklistKey },
  });
}

/** Remove one link (its id is in the document's `links`). */
export function unlinkDocument(linkId) {
  return apiFetch("/api/v1/documents/links/" + linkId, { method: "DELETE" });
}

/** Download the file and save it under its own name. */
export async function downloadDocument(document) {
  const blob = await apiDownload("/api/v1/documents/" + document.id + "/file");
  const href = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = href;
  anchor.download = document.original_filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(href), 60_000); // after the browser has read it
}

// --- alerts ------------------------------------------------------------------------------------

export const NOTIFICATIONS_KEY = ["alerts", "notifications"];

/** One page of my notifications, newest first: { items, page, page_size, total }. */
export function useNotifications(page) {
  return useGet([...NOTIFICATIONS_KEY, page], `/api/v1/alerts/notifications?page=${page}`);
}

export function markNotificationRead(notificationId) {
  return apiFetch(`/api/v1/alerts/notifications/${notificationId}/read`, { method: "POST" });
}

/** One filing's late fee estimate; taxDue ("" or an amount) adds the interest. */
export function usePenaltyEstimate(itemId, taxDue, enabled) {
  const query = taxDue ? `?tax_due=${encodeURIComponent(taxDue)}` : "";
  const path = `/api/v1/alerts/penalties/${itemId}${query}`;
  return useGet(["alerts", "penalty", itemId, taxDue], path, { enabled });
}

/** The late fees of all overdue filings, for the dashboard. */
export function usePenaltyExposure(enabled) {
  return useGet(["alerts", "penalties"], "/api/v1/alerts/penalties", { enabled });
}

// --- marketplace -------------------------------------------------------------------------------

export const CA_PROFILE_KEY = ["marketplace", "ca-profile"];

/** The logged-in CA's profile, or null before they save one. */
export function useCaProfile() {
  const path = "/api/v1/marketplace/ca-profile";
  return useGet(CA_PROFILE_KEY, path, { notFound: "CA_PROFILE_NOT_FOUND" });
}

/** Returns the saved profile. */
export function saveCaProfile(profile) {
  return apiFetch("/api/v1/marketplace/ca-profile", { method: "PUT", body: profile });
}

/** The Certificate of Practice; returns the profile, now waiting for an admin check. */
export function uploadCertificate(file) {
  return sendForm("/api/v1/marketplace/ca-profile/certificate", { file });
}

/** Verified CAs for "Find a CA"; with a service chosen, each has their `price` for it. */
export function useVerifiedCas({ specialization, language, city, service, page }) {
  const url = withQuery("/api/v1/marketplace/cas", {
    specialization,
    language,
    city,
    service,
    page: page > 1 ? page : "",
  });
  return useGet(["marketplace", "cas", url], url);
}

/** One verified CA with their services and prices (404 CA_NOT_FOUND for others). */
export function useVerifiedCa(caId) {
  return useGet(["marketplace", "ca", caId], "/api/v1/marketplace/cas/" + caId);
}

/** Every catalog service. */
export function useServices() {
  return useGet(["marketplace", "services"], "/api/v1/marketplace/services");
}

export const CA_SERVICES_KEY = ["marketplace", "ca-services"];

/** The services the logged-in CA offers: { items: [{ service_id, price }] }. */
export function useCaServices() {
  return useGet(CA_SERVICES_KEY, "/api/v1/marketplace/ca-services");
}

/** Saves the CA's whole price menu (it replaces the old one). */
export function saveCaServices(items) {
  return apiFetch("/api/v1/marketplace/ca-services", { method: "PUT", body: { items } });
}

// --- Engagements (a business working with a CA) --------------------------------------------

export const MY_ENGAGEMENTS_KEY = ["marketplace", "my-engagements"];
export const CA_ENGAGEMENTS_KEY = ["marketplace", "ca-engagements"];
export const REQUESTABLE_KEY = ["marketplace", "requestable-filings"];

/** The business's filings with this CA's prices; null before the business is registered. */
export function useRequestableFilings(caId) {
  const path = "/api/v1/marketplace/cas/" + caId + "/requestable-filings";
  return useGet([...REQUESTABLE_KEY, caId], path, { notFound: "BUSINESS_NOT_FOUND" });
}

/** items = [{ compliance_item_id, service_id }] */
export function sendRequest(caId, items) {
  return apiFetch("/api/v1/marketplace/engagements", {
    method: "POST",
    body: { ca_profile_id: caId, items },
  });
}

/** The business's engagements, newest first; null before the business is registered. */
export function useMyEngagements() {
  const path = "/api/v1/marketplace/my-engagements";
  return useGet(MY_ENGAGEMENTS_KEY, path, { notFound: "BUSINESS_NOT_FOUND" });
}

export function useCaEngagements() {
  return useGet(CA_ENGAGEMENTS_KEY, "/api/v1/marketplace/ca-engagements");
}

/** e.g. engagementAction(id, "accept") or (id, "rating", { stars, review }). */
export function engagementAction(engagementId, action, body) {
  return apiFetch("/api/v1/marketplace/engagements/" + engagementId + "/" + action, {
    method: "POST",
    body: body,
  });
}

// --- caWorkspace -------------------------------------------------------------------------------

// Every ca_workspace query in the cache starts with this; refresh it after a change.
export const CA_WORKSPACE_KEY = ["ca_workspace"];

export function useCaDashboard() {
  return useGet([...CA_WORKSPACE_KEY, "dashboard"], "/api/v1/ca-workspace/dashboard");
}

/** The CA's clients, most urgent first, with their reasons. */
export function useCaClients() {
  return useGet([...CA_WORKSPACE_KEY, "clients"], "/api/v1/ca-workspace/clients");
}

/** The business, its profile and the engaged filings. */
export function useCaClient(businessId) {
  const path = "/api/v1/ca-workspace/clients/" + businessId;
  return useGet([...CA_WORKSPACE_KEY, "client", businessId], path);
}

/** Open filings across clients by form and due date. */
export function useCaBatches() {
  return useGet([...CA_WORKSPACE_KEY, "batches"], "/api/v1/ca-workspace/batches");
}

/** The CA asks the client for a document for one filing ("general" for no checklist entry). */
export function createDocumentRequest(businessId, complianceItemId, checklistKey, message) {
  return apiFetch("/api/v1/ca-workspace/clients/" + businessId + "/document-requests", {
    method: "POST",
    body: { compliance_item_id: complianceItemId, checklist_key: checklistKey, message },
  });
}

export function cancelDocumentRequest(requestId) {
  return apiFetch("/api/v1/ca-workspace/document-requests/" + requestId + "/cancel", { method: "POST" });
}

/** The CA filed one filing. Both the ARN and the file are optional. */
export function caMarkFiled(businessId, itemId, acknowledgementNo, file) {
  const path = "/api/v1/ca-workspace/clients/" + businessId + "/filings/" + itemId + "/mark-filed";
  return sendForm(path, { acknowledgement_no: acknowledgementNo, file });
}

/** The business's open requests from its CAs (its to-dos), oldest first. */
export function useMyDocumentRequests(itemId) {
  const query = itemId ? "?compliance_item_id=" + itemId : "";
  const path = "/api/v1/ca-workspace/document-requests" + query;
  return useGet([...CA_WORKSPACE_KEY, "my-requests", itemId ?? "all"], path);
}

/** Answer a request with a document already in the vault (upload it first if needed). */
export function fulfilDocumentRequest(requestId, documentId) {
  const path = "/api/v1/ca-workspace/document-requests/" + requestId + "/fulfil";
  return apiFetch(path, { method: "POST", body: { document_id: documentId } });
}

// --- admin -------------------------------------------------------------------------------------

export const ADMIN_CAS_KEY = ["admin", "cas"];
export const ADMIN_STATS_KEY = ["admin", "stats"];

export function useAdminDashboard() {
  return useGet(["admin", "dashboard"], "/api/v1/admin/dashboard");
}

/** Counts of users, CAs, engagements and filings, and the overdue rate. */
export function useAdminStats() {
  return useGet(ADMIN_STATS_KEY, "/api/v1/admin/stats");
}

/** Every account; empty filters are not sent. */
export function useAdminUsers({ role, search, page }) {
  const url = withQuery("/api/v1/admin/users", { role, search, page: page > 1 ? page : "" });
  return useGet(["admin", "users", url], url);
}

/** CA profiles in one status, the longest-waiting first. */
export function useAdminCas(status) {
  return useGet([...ADMIN_CAS_KEY, status], "/api/v1/admin/cas?status=" + status);
}

export function adminCaKey(caId) {
  return [...ADMIN_CAS_KEY, "one", caId];
}

/** One CA with everything to check. */
export function useAdminCa(caId) {
  return useGet(adminCaKey(caId), "/api/v1/admin/cas/" + caId);
}

/** The CA's Certificate of Practice file (a Blob), when they have uploaded one. */
export function useCertificateFile(caId, enabled) {
  return useQuery({
    queryKey: [...ADMIN_CAS_KEY, "certificate", caId],
    queryFn: () => apiDownload("/api/v1/admin/cas/" + caId + "/certificate"),
    enabled,
  });
}

export function verifyCa(caId) {
  return apiFetch("/api/v1/admin/cas/" + caId + "/verify", { method: "POST" });
}

export function rejectCa(caId, reason) {
  return apiFetch("/api/v1/admin/cas/" + caId + "/reject", { method: "POST", body: { reason } });
}
