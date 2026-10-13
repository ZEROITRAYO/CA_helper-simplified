import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  ADMIN_CAS_KEY,
  ADMIN_STATS_KEY,
  adminCaKey,
  errorMessage,
  rejectCa,
  useAdminCa,
  useAdminCas,
  useAdminDashboard,
  useAdminStats,
  useAdminUsers,
  useCertificateFile,
  useRefresh,
  verifyCa,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  Notice,
  NumberCard,
  Options,
  Pager,
  QueryStatus,
  Row,
  Section,
  Table,
  useAction,
  useObjectUrl,
  Welcome,
} from "@/components/shared";
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
  Select,
  Textarea,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  COMPLIANCE_STATUS_LABELS,
  formatDateTime,
  label,
  labelList,
  USER_ROLE_LABELS,
} from "@/lib";

// --- AdminDashboardPage ------------------------------------------------------------------------

/** Admin home page: a welcome message and the counts that need an eye on them. */
export function AdminDashboardPage() {
  const dashboard = useAdminDashboard();
  const stats = useAdminStats();

  return (
    <div className="space-y-6">
      <Welcome query={dashboard} />
      {stats.isSuccess && <Counts stats={stats.data} />}
      {stats.isSuccess && <Filings stats={stats.data} />}
    </div>
  );
}

function Counts({ stats }) {
  const cards = [
    ["Business users", stats.users_by_role.business],
    ["CAs", stats.users_by_role.ca],
    ["Admins", stats.users_by_role.admin],
    ["Businesses registered", stats.businesses],
    ["CAs pending verification", stats.cas_by_status.pending, "/admin/users"],
    ["Open engagements", stats.open_engagements],
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map(([title, value, link]) => (
        <NumberCard key={title} title={title} value={value}>
          {link && value > 0 && (
            <Link to={link} className={"text-sm " + linkClass}>
              Review them
            </Link>
          )}
        </NumberCard>
      ))}
    </div>
  );
}

// Filings across all businesses by status, and how many due ones were late.
function Filings({ stats }) {
  const rate = stats.overdue_rate === null ? "No filing is due yet" : `${stats.overdue_rate}%`;
  return (
    <Card>
      <CardHeader>
        <CardDescription>Overdue rate</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{rate}</CardTitle>
        <CardDescription>
          {stats.filings_late} of {stats.filings_due_so_far} filings due so far were not filed on
          time (still unfiled, or filed after the due date).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-2 text-sm font-medium">Filings by status</p>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(stats.filings_by_status).map(([status, count]) => (
            <div key={status} className="flex justify-between gap-2">
              <dt>{label(COMPLIANCE_STATUS_LABELS, status)}</dt>
              <dd className="tabular-nums">{count}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

// --- AdminUsersPage ----------------------------------------------------------------------------

const USER_TABS = ["Pending verification", "All users"];

/** /admin/users: CAs waiting for verification first, then every account. */
export function AdminUsersPage() {
  const [tab, setTab] = useState(USER_TABS[0]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users & CAs</h1>
      <div role="tablist" className="flex gap-2">
        {USER_TABS.map((name) => (
          <Button
            key={name}
            role="tab"
            aria-selected={tab === name}
            variant={tab === name ? "default" : "outline"}
            size="sm"
            onClick={() => setTab(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      {tab === USER_TABS[0] ? <PendingCas /> : <AllUsers />}
    </div>
  );
}

function PendingCas() {
  const cas = useAdminCas("pending");
  if (!cas.isSuccess) return <QueryStatus query={cas} />;
  if (cas.data.length === 0) {
    return <p className="text-sm text-hint">No CA is waiting for verification.</p>;
  }
  return (
    <Table headers={["CA", "Membership no.", "City", "Certificate", "Waiting since", ""]}>
      {cas.data.map((ca) => (
        <Row
          key={ca.id}
          cells={[
            <>
              {ca.full_name}
              <div className="text-xs text-hint">{ca.email}</div>
            </>,
            ca.membership_no,
            ca.city,
            ca.has_certificate ? "Uploaded" : "Missing",
            formatDateTime(ca.updated_at),
            <Link to={"/admin/cas/" + ca.id} className={linkClass}>
              Review {ca.full_name}
            </Link>,
          ]}
        />
      ))}
    </Table>
  );
}

function AllUsers() {
  const [filters, setFilters] = useState({ role: "", search: "", page: 1 });
  const users = useAdminUsers(filters);

  function onSearch(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFilters({ role: form.get("role"), search: form.get("search").trim(), page: 1 });
  }

  return (
    <div className="space-y-4">
      <form className="flex flex-wrap items-end gap-3" onSubmit={onSearch}>
        <Field id="role" label="Role">
          <Select id="role" name="role" defaultValue={filters.role} className="w-auto">
            <Options labels={USER_ROLE_LABELS} empty="All" />
          </Select>
        </Field>
        <Field id="search" label="Name or email">
          <Input id="search" name="search" defaultValue={filters.search} />
        </Field>
        <Button type="submit">Search</Button>
      </form>

      <QueryStatus query={users} />
      {users.isSuccess && (
        <>
          <p className="text-sm text-hint">
            {users.data.total === 1 ? "1 account" : `${users.data.total} accounts`}
          </p>
          <Table headers={["Name", "Email", "Role", "Email verified", "Joined"]}>
            {users.data.items.map((user) => (
              <Row
                key={user.id}
                cells={[
                  user.full_name,
                  user.email,
                  label(USER_ROLE_LABELS, user.role),
                  user.email_verified ? "Yes" : "No",
                  formatDateTime(user.created_at),
                ]}
              />
            ))}
          </Table>
          <Pager data={users.data} onPage={(page) => setFilters({ ...filters, page })} />
        </>
      )}
    </div>
  );
}

// --- AdminCaDetailPage -------------------------------------------------------------------------

/** /admin/cas/:caId: check a CA's numbers against the certificate, verify or reject. */
export function AdminCaDetailPage() {
  const { caId } = useParams();
  const ca = useAdminCa(caId);

  return (
    <div className="max-w-3xl space-y-6">
      <BackLink to="/admin/users">Back to Users & CAs</BackLink>
      <QueryStatus query={ca} />
      {ca.isSuccess && (
        <>
          <Details ca={ca.data} />
          <Certificate ca={ca.data} />
          <Decision ca={ca.data} />
        </>
      )}
    </div>
  );
}

function Details({ ca }) {
  const rows = [
    ["Email", ca.email],
    ["ICAI membership number", ca.membership_no],
    ["Certificate of Practice number", ca.cop_number],
    ["City", ca.city],
    ["Years of experience", ca.years_experience],
    ["Capacity (clients at a time)", ca.capacity],
    ["Specializations", labelList(CA_SPECIALIZATION_LABELS, ca.specializations)],
    ["Languages", labelList(CA_LANGUAGE_LABELS, ca.languages)],
    ["About", ca.about || "—"],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{ca.full_name}</h1>
          <Badge variant="secondary">{label(CA_VERIFICATION_STATUS_LABELS, ca.verification_status)}</Badge>
        </CardTitle>
        <CardDescription>Last changed {formatDateTime(ca.updated_at)}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y text-sm">
          {rows.map(([name, value]) => (
            <div key={name} className="grid gap-1 py-2 sm:grid-cols-3">
              <dt className="text-hint">{name}</dt>
              <dd className="sm:col-span-2">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/** Loads the certificate (admins only) and offers it as a link that opens it. */
function Certificate({ ca }) {
  const file = useCertificateFile(ca.id, ca.has_certificate);
  const url = useObjectUrl(file.data);

  return (
    <Section
      title="Certificate of Practice"
      description={
        ca.has_certificate
          ? "Check that the name and numbers match the profile above."
          : "Not uploaded yet: the CA cannot be verified until they upload it."
      }
      contentClassName="text-sm"
    >
      {ca.has_certificate && (
        <>
          <ErrorText>{file.isError && errorMessage(file.error)}</ErrorText>
          {url ? (
            <a href={url} target="_blank" rel="noreferrer" className={linkClass}>
              Open the certificate
            </a>
          ) : (
            !file.isError && <span className="text-hint">Loading the certificate...</span>
          )}
        </>
      )}
    </Section>
  );
}

function Decision({ ca }) {
  const queryClient = useQueryClient();
  const refresh = useRefresh();
  const [reason, setReason] = useState("");
  const [done, setDone] = useState(null);
  const { busy, error, run } = useAction();

  function decide(action, doneText) {
    setDone(null);
    run(async () => {
      queryClient.setQueryData(adminCaKey(ca.id), await action());
      refresh(ADMIN_CAS_KEY, ADMIN_STATS_KEY);
      setDone(doneText);
      setReason("");
    });
  }

  return (
    <Section
      title="Decision"
      description="Verifying lists the CA in the marketplace. Rejecting needs a reason, which the CA sees."
      contentClassName="space-y-3"
    >
      <Button
        onClick={() => decide(() => verifyCa(ca.id), "Verified. The CA has been emailed.")}
        disabled={busy || ca.verification_status === "verified" || !ca.has_certificate}
      >
        Verify
      </Button>
      <div className="space-y-2">
        <Label htmlFor="reason">Reason for rejecting</Label>
        <Textarea id="reason" rows={2} value={reason} onChange={(event) => setReason(event.target.value)} />
        <Button
          variant="outline"
          onClick={() => decide(() => rejectCa(ca.id, reason), "Rejected. The CA has been emailed.")}
          disabled={busy || !reason.trim()}
        >
          Reject
        </Button>
      </div>
      <ErrorText>{error}</ErrorText>
      <Notice>{done}</Notice>
    </Section>
  );
}
