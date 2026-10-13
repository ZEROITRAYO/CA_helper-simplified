import { CA_ENGAGEMENTS_KEY, engagementAction, useCaEngagements, useRefresh } from "@/api";
import { EngagementGroups, ErrorText, QueryStatus, useAction } from "@/components/shared";
import { Button } from "@/components/ui";

// --- CaEngagementsPage -------------------------------------------------------------------------

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
      {engagements.isSuccess && (
        <EngagementGroups
          engagements={engagements.data}
          waitingTitle="New requests"
          titleOf={(engagement) => engagement.business_name}
          actions={(engagement) => <CaActions engagement={engagement} />}
        />
      )}
    </div>
  );
}

// The buttons the CA has for one engagement.
function CaActions({ engagement }) {
  const refresh = useRefresh();
  const { busy, error, run } = useAction();

  async function act(action) {
    if (await run(() => engagementAction(engagement.id, action))) refresh(CA_ENGAGEMENTS_KEY);
  }

  return (
    <div className="space-y-2">
      {engagement.status === "requested" && (
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => act("accept")} disabled={busy}>
            Accept at listed prices
          </Button>
          <Button variant="outline" onClick={() => act("decline")} disabled={busy}>
            Decline
          </Button>
        </div>
      )}
      {engagement.status === "active" && (
        <Button onClick={() => act("complete")} disabled={busy}>
          Mark as completed
        </Button>
      )}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
