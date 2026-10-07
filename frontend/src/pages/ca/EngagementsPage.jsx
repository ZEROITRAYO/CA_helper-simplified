import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { CA_ENGAGEMENTS_KEY, engagementAction, errorMessage, useCaEngagements } from "@/api";
import { EngagementCard, QueryStatus } from "@/components/shared";
import { Button } from "@/components/ui";
import { isPast } from "@/lib";

// --- CaEngagementsPage -------------------------------------------------------------------------

// The groups on the page, in order, and which statuses belong to each.
const GROUPS = [
  { title: "New requests", statuses: ["requested"] },
  { title: "Active", statuses: ["active"] },
  { title: "Finished", statuses: ["completed", "declined", "expired", "cancelled"] },
];

// /ca/engagements: every request businesses sent to this CA, grouped by status, with
// the CA's actions (accept at the listed prices, decline, mark as completed).
export function CaEngagementsPage() {
  const engagements = useCaEngagements();

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">My engagements</h1>
      <QueryStatus query={engagements} />
      {engagements.isSuccess && engagements.data.length === 0 && (
        <p className="text-sm">
          No requests yet. Businesses can find you in the marketplace once your profile is verified.
        </p>
      )}
      {engagements.isSuccess &&
        GROUPS.map((group) => {
          const inGroup = engagements.data.filter((engagement) =>
            group.statuses.includes(engagement.status),
          );
          if (inGroup.length === 0) {
            return null;
          }
          return (
            <section key={group.title} className="space-y-3">
              <h2 className="text-lg font-semibold">{group.title}</h2>
              {inGroup.map((engagement) => (
                <EngagementCard
                  key={engagement.id}
                  engagement={engagement}
                  title={engagement.business_name}
                >
                  <CaActions engagement={engagement} />
                </EngagementCard>
              ))}
            </section>
          );
        })}
    </div>
  );
}

// The buttons the CA has for one engagement.
function CaActions({ engagement }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await engagementAction(engagement.id, action);
      queryClient.invalidateQueries({ queryKey: CA_ENGAGEMENTS_KEY });
    } catch (actionError) {
      setError(errorMessage(actionError));
    }
    setBusy(false);
  }

  // After 48 hours the CA can no longer answer; the worker will close the request.
  const answerTimeOver =
    engagement.status === "requested" && engagement.expires_at && isPast(engagement.expires_at);

  let buttons = null;
  if (answerTimeOver) {
    buttons = (
      <p className="text-muted-foreground">
        The 48 hours to answer are over. This request will close automatically.
      </p>
    );
  } else if (engagement.status === "requested") {
    buttons = (
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => run("accept")} disabled={busy}>
          Accept at listed prices
        </Button>
        <Button variant="outline" onClick={() => run("decline")} disabled={busy}>
          Decline
        </Button>
      </div>
    );
  } else if (engagement.status === "active") {
    buttons = (
      <Button onClick={() => run("complete")} disabled={busy}>
        Mark as completed
      </Button>
    );
  }

  return (
    <div className="space-y-2">
      {buttons}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
