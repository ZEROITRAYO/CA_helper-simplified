import { Link } from "react-router";

import { useCaDashboard, useCaProfile, useCaServices } from "@/api";
import { Welcome } from "@/components/shared";
import { buttonClass, Card, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { CA_VERIFICATION_STATUS_LABELS, label } from "@/lib";

/** CA home dashboard: a welcome message and what is left before businesses can find them. */
export function CaDashboardPage() {
  const dashboard = useCaDashboard();

  return (
    <div className="space-y-6">
      <Welcome query={dashboard} />
      <ProfileReminder />
    </div>
  );
}

/** What the CA still has to do before businesses can find them (nothing once verified). */
const REMINDERS = {
  missing: {
    title: "Complete your profile",
    text: "Add your membership and Certificate of Practice numbers, city, languages and specializations. Businesses can find you once an admin has verified them.",
    action: "Complete profile",
  },
  pending: {
    title: "Your profile is waiting for verification",
    text: "An admin is checking your membership and CoP numbers. You will appear in the marketplace once verified.",
    action: "View profile",
  },
  rejected: {
    title: "Your profile needs changes",
    text: "An admin could not confirm your numbers. Correct your details and save to ask for a new check.",
    action: "Edit profile",
  },
};

function ProfileReminder() {
  const profile = useCaProfile();
  const menu = useCaServices();
  if (!profile.isSuccess) return null;
  const reminder = REMINDERS[profile.data?.verification_status ?? "missing"];
  if (!reminder) return null; // verified

  return (
    <Card>
      <CardHeader>
        <CardTitle>{reminder.title}</CardTitle>
        <CardDescription>{reminder.text}</CardDescription>
        <SetupChecklist profile={profile.data} hasPrices={menu.data?.items.length > 0} />
        <div>
          <Link to="/ca/profile" className={buttonClass()}>{reminder.action}</Link>
        </div>
      </CardHeader>
    </Card>
  );
}

/** The steps to being listed: profile, certificate, prices, then the admin's check. */
function SetupChecklist({ profile, hasPrices }) {
  const steps = [
    { name: "Profile", done: Boolean(profile) },
    { name: "Certificate uploaded", done: Boolean(profile?.has_certificate) },
    { name: "Prices set", done: hasPrices },
  ];
  const status = profile?.verification_status;
  return (
    <ul aria-label="Setup checklist" className="space-y-1 pt-2 text-sm">
      {steps.map((step) => (
        <li key={step.name}>
          <span aria-hidden="true">{step.done ? "✓" : "✗"}</span> {step.name}
          <span className="sr-only">{step.done ? ": done" : ": to do"}</span>
        </li>
      ))}
      <li>
        Verification: {status ? label(CA_VERIFICATION_STATUS_LABELS, status) : "not started"}
        {status === "rejected" && profile.rejection_reason && ` (${profile.rejection_reason})`}
      </li>
    </ul>
  );
}
