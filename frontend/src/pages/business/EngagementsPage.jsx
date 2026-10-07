import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation } from "react-router";

import {
  engagementAction,
  errorMessage,
  FILINGS_KEY,
  MY_ENGAGEMENTS_KEY,
  useMyEngagements,
} from "@/api";
import { EngagementCard, QueryStatus } from "@/components/shared";
import { Button, buttonClass } from "@/components/ui";

// --- MyEngagementsPage -------------------------------------------------------------------------

// The groups on the page, in order, and which statuses belong to each.
const GROUPS = [
  { title: "Waiting for the CA", statuses: ["requested"] },
  { title: "Active", statuses: ["active"] },
  { title: "Finished", statuses: ["completed", "declined", "expired", "cancelled"] },
];

// /business/engagements: every request the business sent to a CA, grouped by status,
// with the actions it can take (withdraw a request, rate a finished one).
export function MyEngagementsPage() {
  const location = useLocation();
  const engagements = useMyEngagements();
  const justSent = location.state && location.state.sent;

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
        <p className="text-sm">
          <Link to="/business/onboarding" className="underline">
            Register your business
          </Link>{" "}
          first, then request a CA from "Find a CA".
        </p>
      )}
      {engagements.isSuccess && engagements.data !== null && engagements.data.length === 0 && (
        <p className="text-sm">
          You have not requested a CA yet.{" "}
          <Link to="/business/marketplace" className="underline">
            Find a CA
          </Link>
        </p>
      )}
      {engagements.isSuccess &&
        engagements.data !== null &&
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
                  title={engagement.ca_name}
                >
                  <BusinessActions engagement={engagement} />
                </EngagementCard>
              ))}
            </section>
          );
        })}
    </div>
  );
}

// The buttons the business has for one engagement: withdraw a request the CA has not
// answered, or find another CA when one was declined or expired.
function BusinessActions({ engagement }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await engagementAction(engagement.id, action);
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
      queryClient.invalidateQueries({ queryKey: FILINGS_KEY }); // filings may now be "With CA"
    } catch (actionError) {
      setError(errorMessage(actionError));
    }
    setBusy(false);
  }

  let buttons = null;
  if (engagement.status === "requested") {
    buttons = (
      <Button variant="outline" onClick={() => run("withdraw")} disabled={busy}>
        Withdraw request
      </Button>
    );
  } else if (engagement.status === "expired" || engagement.status === "declined") {
    // The CA did not take it: the filings are free, so offer to pick another CA.
    buttons = (
      <Link to="/business/marketplace" className={buttonClass()}>Find another CA</Link>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {buttons}
        {engagement.status === "completed" && !engagement.rating && (
          <RateForm engagement={engagement} />
        )}
        <Link
          to={"/business/marketplace/" + engagement.ca_profile_id}
          className="self-center text-primary underline-offset-4 hover:underline"
        >
          View CA
        </Link>
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

// Rate the CA once the work is completed (1 to 5 stars and an optional review).
function RateForm({ engagement }) {
  const queryClient = useQueryClient();
  const [stars, setStars] = useState(0);
  const [review, setReview] = useState("");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    if (stars === 0) {
      setError("Choose 1 to 5 stars.");
      return;
    }
    setError(null);
    setSending(true);
    try {
      await engagementAction(engagement.id, "rating", { stars: stars, review: review });
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
    } catch (rateError) {
      setError(errorMessage(rateError));
    }
    setSending(false);
  }

  const choices = [1, 2, 3, 4, 5];
  return (
    <form className="w-full space-y-2 rounded-lg border p-3" onSubmit={onSubmit} noValidate>
      <p className="font-medium">Rate {engagement.ca_name}</p>
      <div className="flex gap-1">
        {choices.map((number) => (
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
      <textarea
        aria-label="Review (optional)"
        placeholder="How was working with this CA? (optional)"
        rows={2}
        maxLength={2000}
        className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm"
        value={review}
        onChange={(event) => setReview(event.target.value)}
      />
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={sending}>
        {sending ? "Sending..." : "Send rating"}
      </Button>
    </form>
  );
}
