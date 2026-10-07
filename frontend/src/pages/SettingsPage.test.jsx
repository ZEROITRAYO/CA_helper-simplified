import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST_URL = "GET /api/v1/alerts/notifications?page=1";

const INBOX = {
  items: [
    {
      id: "n1",
      type: "engagement_update",
      title: "Your CA accepted your request",
      body: "Meera Shah accepted your request at their listed prices.",
      link: "/business/engagements",
      read_at: null,
      created_at: "2026-09-27T10:30:00+00:00",
    },
    {
      id: "n2",
      type: "deadline_reminder",
      title: "GSTR-1 (Q2 2026-27) is due in 7 days",
      body: "File it before the due date.",
      link: null,
      read_at: "2026-09-27T11:00:00Z",
      created_at: "2026-09-26T10:30:00+00:00",
    },
  ],
  page: 1,
  page_size: 20,
  total: 2,
};

function open(role, path, answers = {}) {
  loginAs(role);
  const fetchMock = fakeApi({
    "GET /api/v1/auth/settings": [200, { email_notifications: true }],
    "PUT /api/v1/auth/settings": [200, { email_notifications: false }],
    [LIST_URL]: [200, INBOX],
    "POST /api/v1/alerts/notifications/n1/read": [200, { ...INBOX.items[0], read_at: "now" }],
    ...answers,
  });
  const router = renderApp(path);
  return { fetchMock, router };
}

describe("notification settings", () => {
  it("switches off the notification emails", async () => {
    const { fetchMock } = open("business", "/business/settings");
    const box = await screen.findByRole("checkbox", { name: /Email me my notifications/ });
    expect(box).toBeChecked();

    await userEvent.setup().click(box);

    await waitFor(() => expect(box).not.toBeChecked());
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(call[1].body)).toEqual({ email_notifications: false });
  });

  it("says login and password codes are always emailed, with one switch", async () => {
    open("business", "/business/settings");

    expect(
      await screen.findByText(/Login and password codes are always emailed/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });

  it("is in the CA's sidebar too", async () => {
    open("ca", "/ca/settings");

    expect(
      await screen.findByRole("checkbox", { name: /Email me my notifications/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
      "href",
      "/ca/settings",
    );
  });
});

describe("notification inbox", () => {
  it("lists notifications newest first with the unread ones in bold", async () => {
    open("business", "/business/settings");

    const unread = await screen.findByRole("button", { name: /Your CA accepted your request/ });
    const read = screen.getByRole("button", { name: /GSTR-1 \(Q2 2026-27\) is due in 7 days/ });
    expect(unread).toHaveClass("font-bold");
    expect(read).not.toHaveClass("font-bold");
    expect(unread.compareDocumentPosition(read)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("opens a notification in a window, marks it read and stays on the page", async () => {
    const { fetchMock, router } = open("business", "/business/settings");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Your CA accepted your request/ }));

    const view = screen.getByRole("dialog", { name: "Your CA accepted your request" });
    expect(view).toHaveTextContent("Meera Shah accepted your request at their listed prices.");
    expect(router.state.location.pathname).toBe("/business/settings");
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            url === "/api/v1/alerts/notifications/n1/read" && init?.method === "POST",
        ),
      ).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(view).not.toBeInTheDocument();
  });

  it("says when there is nothing yet", async () => {
    open("ca", "/ca/settings", {
      [LIST_URL]: [200, { items: [], page: 1, page_size: 20, total: 0 }],
    });

    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
  });
});
