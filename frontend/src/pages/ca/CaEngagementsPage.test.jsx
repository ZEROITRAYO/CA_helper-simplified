import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ENGAGEMENT_ID, engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST_URL = "/api/v1/marketplace/ca-engagements";
const ACTION_URL = `/api/v1/marketplace/engagements/${ENGAGEMENT_ID}`;

describe("CA: My engagements page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    fakeApi({});
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "My engagements" })).toHaveAttribute(
      "href",
      "/ca/engagements",
    );
  });

  it("shows a new request with the business and its filings", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement()]] });
    renderApp("/ca/engagements");

    expect(await screen.findByRole("heading", { name: "New requests" })).toBeInTheDocument();
    expect(screen.getByText("Asha Traders")).toBeInTheDocument();
    expect(screen.getByText("GSTR-3B filing")).toBeInTheDocument();
    expect(screen.getByText("₹1,400")).toBeInTheDocument();
    // The fee is fixed: the CA accepts at the listed prices or declines, no quote.
    expect(screen.getByRole("button", { name: "Accept at listed prices" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send a quote" })).not.toBeInTheDocument();
  });

  it("accepts a request", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/accept`]: [200, engagement({ status: "active" })],
    });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Accept at listed prices" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${ACTION_URL}/accept`);
  });

  it("declines a request and completes an active one", async () => {
    loginAs("ca");
    const active = engagement({ id: "e2", status: "active" });
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement(), active]],
      [`POST ${ACTION_URL}/decline`]: [200, engagement({ status: "declined" })],
      "POST /api/v1/marketplace/engagements/e2/complete": [200, { ...active, status: "completed" }],
    });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Decline" }));
    await user.click(screen.getByRole("button", { name: "Mark as completed" }));

    const paths = fetchMock.mock.calls.map(([path]) => path);
    expect(paths).toContain(`${ACTION_URL}/decline`);
    expect(paths).toContain("/api/v1/marketplace/engagements/e2/complete");
  });

  it("hides the answer buttons once the 48 hours are over", async () => {
    loginAs("ca");
    fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement({ expires_at: "2020-01-01T00:00:00Z" })]],
    });
    renderApp("/ca/engagements");

    expect(
      await screen.findByText(
        "The 48 hours to answer are over. This request will close automatically.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/answer time over/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Accept at listed prices" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Decline" })).not.toBeInTheDocument();
  });
});
