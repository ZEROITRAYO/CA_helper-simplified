import { useState } from "react";
import { Link, useLocation } from "react-router";

import { engagementAction, FILINGS_KEY, MY_ENGAGEMENTS_KEY, useMyEngagements, useRefresh } from "@/api";
import { EngagementGroups, ErrorText, QueryStatus, RegisterFirst, useAction } from "@/components/shared";
import { Button, buttonClass, linkClass, Textarea } from "@/components/ui";

// --- MyEngagementsPage -------------------------------------------------------------------------

// /business/engagements: every request the business sent to a CA, grouped by status,
// with the actions it can take (withdraw a request, rate a finished one).
export function MyEngagementsPage() {
  const engagements = useMyEngagements();
  const justSent = useLocation().state?.sent;

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">My engagements</h1>
      {justSent && (
        <p role="status" className="text-sm font-medium text-green-700">
          Your request was sent. The CA has been emailed.
        </p>
      )}
      <QueryStatus query={engagements} />
      {engagements.isSuccess && engagements.data === null && (
        <RegisterFirst>first, then request a CA from "Find a CA".</RegisterFirst>
      )}
      {engagements.data?.length === 0 && (
        <p className="text-sm">
          You have not requested a CA yet.{" "}
          <Link to="/business/marketplace" className="underline">
            Find a CA
          </Link>
        </p>
      )}
      {engagements.data && (
        <EngagementGroups
          engagements={engagements.data}
          waitingTitle="Waiting for the CA"
          titleOf={(engagement) => engagement.ca_name}
          actions={(engagement) => <BusinessActions engagement={engagement} />}
        />
      )}
    </div>
  );
}

// The buttons the business has for one engagement: withdraw a request the CA has not
// answered, or find another CA when one was declined or withdrawn.
function BusinessActions({ engagement }) {
  const refresh = useRefresh();
  const { busy, error, run } = useAction();
  const status = engagement.status;

  async function withdraw() {
    // The filings may no longer be "With CA".
    if (await run(() => engagementAction(engagement.id, "withdraw"))) refresh(MY_ENGAGEMENTS_KEY, FILINGS_KEY);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {status === "requested" && (
          <Button variant="outline" onClick={withdraw} disabled={busy}>
            Withdraw request
          </Button>
        )}
        {/* The CA did not take it: the filings are free, so offer to pick another CA. */}
        {(status === "declined" || status === "cancelled") && (
          <Link to="/business/marketplace" className={buttonClass()}>Find another CA</Link>
        )}
        {status === "completed" && !engagement.rating && <RateForm engagement={engagement} />}
        <Link to={"/business/marketplace/" + engagement.ca_profile_id} className={"self-center " + linkClass}>
          View CA
        </Link>
      </div>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

// Rate the CA once the work is completed (1 to 5 stars and an optional review).
function RateForm({ engagement }) {
  const refresh = useRefresh();
  const [stars, setStars] = useState(0);
  const [review, setReview] = useState("");
  const { busy, error, setError, run } = useAction();

  async function onSubmit(event) {
    event.preventDefault();
    if (stars === 0) return setError("Choose 1 to 5 stars.");
    if (await run(() => engagementAction(engagement.id, "rating", { stars, review }))) {
      refresh(MY_ENGAGEMENTS_KEY);
    }
  }

  return (
    <form className="w-full space-y-2 rounded-lg border p-3" onSubmit={onSubmit} noValidate>
      <p className="font-medium">Rate {engagement.ca_name}</p>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((number) => (
          <button
            key={number}
            type="button"
            aria-label={number + (number === 1 ? " star" : " stars")}
            aria-pressed={stars === number}
            className="text-2xl text-amber-500"
            onClick={() => setStars(number)}
          >
            {number <= stars ? "★" : "☆"}
          </button>
        ))}
      </div>
      <Textarea
        aria-label="Review (optional)"
        placeholder="How was working with this CA? (optional)"
        rows={2}
        maxLength={2000}
        value={review}
        onChange={(event) => setReview(event.target.value)}
      />
      <ErrorText>{error}</ErrorText>
      <Button type="submit" disabled={busy}>
        {busy ? "Sending..." : "Send rating"}
      </Button>
    </form>
  );
}
