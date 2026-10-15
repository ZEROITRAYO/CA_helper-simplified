import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ENGAGEMENT_ID, engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST_URL = "/api/v1/marketplace/my-engagements";
const ACTION_URL = `/api/v1/marketplace/engagements/${ENGAGEMENT_ID}`;

describe("business: My engagements page", () => {
  it("is linked from the business sidebar", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business");

    expect(await screen.findByRole("link", { name: "My engagements" })).toHaveAttribute(
      "href",
      "/business/engagements",
    );
  });

  it("shows a request with its fixed prices and total", async () => {
    loginAs("business");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement()]] });
    renderApp("/business/engagements");

    const section = (await screen.findByRole("heading", { name: "Waiting for the CA" })).closest(
      "section",
    );
    expect(within(section).getByText("Meera Shah")).toBeInTheDocument();
    expect(within(section).getByText("₹800")).toBeInTheDocument(); // one filing's price
    expect(within(section).getByText("₹1,400")).toBeInTheDocument(); // the total
  });

  it("withdraws an unanswered request", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/withdraw`]: [200, engagement({ status: "cancelled" })],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: "Waiting for the CA" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Withdraw request" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${ACTION_URL}/withdraw`);
  });

  it("shows an action's error", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/withdraw`]: [
        409,
        { error: { code: "INVALID_STATUS", message: "This engagement is active." } },
      ],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Withdraw request" }));

    expect(await screen.findByText("This engagement is active.", { exact: false })).toBeInTheDocument();
  });

  it("shows finished engagements without actions", async () => {
    loginAs("business");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement({ status: "declined" })]] });
    renderApp("/business/engagements");

    expect(await screen.findByRole("heading", { name: "Finished" })).toBeInTheDocument();
    expect(screen.getByText("Declined")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw request" })).not.toBeInTheDocument();
  });
});

describe("engagement card timeline", () => {
  it("shows where a request is, with no expiry and a way to withdraw it", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/marketplace/my-engagements": [200, [engagement()]] });
    renderApp("/business/engagements");

    const progress = await screen.findByRole("list", { name: "Progress" });
    expect(progress).toHaveTextContent("● Requested→ ○ Active→ ○ Completed");
    expect(within(progress).getByText(/Requested/)).toHaveAttribute("aria-current", "step");
    expect(screen.queryByText(/expires in/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Withdraw request" })).toBeInTheDocument();
  });

  it("shows how a declined request ended", async () => {
    loginAs("business");
    fakeApi({
      "GET /api/v1/marketplace/my-engagements": [200, [engagement({ status: "declined" })]],
    });
    renderApp("/business/engagements");

    const progress = await screen.findByRole("list", { name: "Progress" });
    expect(progress).toHaveTextContent("✓ Requested→ ● Declined");
  });

  it("offers to find another CA after withdrawing a request", async () => {
    loginAs("business");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement({ status: "cancelled" })]] });
    renderApp("/business/engagements");

    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Find another CA" })).toHaveAttribute(
      "href",
      "/business/marketplace",
    );
  });

  it("rates a completed engagement", async () => {
    loginAs("business");
    const done = engagement({ status: "completed" });
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [done]],
      [`POST ${ACTION_URL}/rating`]: [
        200,
        { ...done, rating: { stars: 4, review: "Quick", created_at: "2026-09-28T05:00:00Z" } },
      ],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "4 stars" }));
    await user.type(screen.getByLabelText("Review (optional)"), "Quick");
    await user.click(screen.getByRole("button", { name: "Send rating" }));

    const [, init] = fetchMock.mock.calls.find(([path]) => path === `${ACTION_URL}/rating`);
    expect(JSON.parse(init.body)).toEqual({ stars: 4, review: "Quick" });
  });

  it("asks for stars before sending a rating", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement({ status: "completed" })]],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Send rating" }));

    expect(screen.getByText("Choose 1 to 5 stars.", { exact: false })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  });

  it("shows the rating instead of the form once rated", async () => {
    loginAs("business");
    const rated = engagement({
      status: "completed",
      rating: { stars: 5, review: "Great help", created_at: "2026-09-28T05:00:00Z" },
    });
    fakeApi({ [`GET ${LIST_URL}`]: [200, [rated]] });
    renderApp("/business/engagements");

    expect(await screen.findByRole("img", { name: "5 out of 5 stars" })).toBeInTheDocument();
    expect(screen.getByText(/Great help/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send rating" })).not.toBeInTheDocument();
  });
});
