import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

// The "Business activity (NIC code)" card on the Business profile page.

const BUSINESS_URL = "/api/v1/onboarding/business";
const SAVE = "PUT /api/v1/onboarding/business/nic-code";

const MY_BUSINESS = {
  business: {
    id: "3f1c2b4a-5d6e-4f70-8a9b-0c1d2e3f4a5b",
    legal_name: "Asha Bakery",
    entity_type: "proprietorship",
    state: "Maharashtra",
    annual_turnover: "4500000.00",
  },
  profile: {
    msme_tier: "micro",
    gst_scheme: "not_registered",
    gst_registration_suggested: false,
    itr_form: "itr_4",
    presumptive_eligible: true,
    audit_applicable: false,
    files_24q: false,
    files_26q: false,
    roc_not_tracked: false,
    explanations: {},
  },
  nic_code: null,
};

const BISCUITS = {
  code: "10712",
  description: "Manufacture of biscuits, cakes, pastries, rusks etc.",
};
const BREAD = { code: "10711", description: "Manufacture of bread" };

function routes(extra) {
  return {
    "GET /api/v1/onboarding/states": [200, [{ name: "Maharashtra", code: "27" }]],
    [`GET ${BUSINESS_URL}`]: [200, MY_BUSINESS],
    ...extra,
  };
}

function lastBody(fetchMock, key) {
  let body = null;
  for (const [path, init] of fetchMock.mock.calls) {
    const method = init && init.method ? init.method : "GET";
    if (`${method} ${path}` === key) {
      body = JSON.parse(init.body);
    }
  }
  return body;
}

describe("NIC code card", () => {
  it("says the code is not chosen yet", async () => {
    loginAs("business");
    fakeApi(routes({}));
    renderApp("/business/onboarding");

    expect(await screen.findByText("Business activity (NIC code)")).toBeInTheDocument();
    expect(screen.getByText("Not chosen yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("finds a code with the search and saves the one the user confirms", async () => {
    loginAs("business");
    const fetchMock = fakeApi(
      routes({
        "GET /api/v1/onboarding/nic-codes?q=bread": [200, [BREAD]],
        [SAVE]: [200, BREAD],
      }),
    );
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Search the NIC list"), "bread");
    await user.click(await screen.findByLabelText(/10711/));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(lastBody(fetchMock, SAVE)).toEqual({ code: "10711" });
    expect(screen.getByText(/Your code:/)).toHaveTextContent(
      "Your code: 10711 · Manufacture of bread",
    );
  });

  it("has no suggestions, only the search", async () => {
    loginAs("business");
    fakeApi(routes({}));
    renderApp("/business/onboarding");

    expect(await screen.findByLabelText("Search the NIC list")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suggest codes" })).not.toBeInTheDocument();
  });

  it("shows the saved code", async () => {
    loginAs("business");
    fakeApi(routes({ [`GET ${BUSINESS_URL}`]: [200, { ...MY_BUSINESS, nic_code: BISCUITS }] }));
    renderApp("/business/onboarding");

    expect(await screen.findByText("10712")).toBeInTheDocument();
    expect(screen.queryByText("Not chosen yet.")).not.toBeInTheDocument();
  });
});
