import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const PROFILE_URL = "/api/v1/marketplace/ca-profile";
const SERVICES_URL = "/api/v1/marketplace/services";
const MENU_URL = "/api/v1/marketplace/ca-services";

const GST = {
  id: "11111111-1111-4111-8111-111111111111",
  code: "gstr_3b",
  name: "GSTR-3B filing",
  specialization: "gstr_3b",
  description: "Summary GST return.",
  unit: "per_return",
};
const AUDIT = {
  id: "22222222-2222-4222-8222-222222222222",
  code: "tax_audit",
  name: "Tax audit",
  specialization: "tax_audit",
  description: "Audit for one year.",
  unit: "per_year",
};
const PROFILE = {
  id: "p1",
  verification_status: "verified",
  membership_no: "123456",
  cop_number: "COP-1",
  city: "Pune",
  languages: ["english"],
  specializations: ["gstr_3b"],
  capacity: 10,
  years_experience: 5,
  about: "",
};

function api(extra = {}) {
  return fakeApi({
    [`GET ${PROFILE_URL}`]: [200, PROFILE],
    [`GET ${SERVICES_URL}`]: [200, [GST, AUDIT]],
    [`GET ${MENU_URL}`]: [200, { items: [{ service_id: GST.id, price: "750.00" }] }],
    ...extra,
  });
}

describe("CA services & prices page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    api();
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "Services & prices" })).toHaveAttribute(
      "href",
      "/ca/services",
    );
  });

  it("shows the saved prices", async () => {
    loginAs("ca");
    api();
    renderApp("/ca/services");

    expect(await screen.findByLabelText("GSTR-3B filing")).toBeChecked();
    expect(screen.getByLabelText("Price for GSTR-3B filing")).toHaveValue("750");
    expect(screen.getByLabelText("Tax audit")).not.toBeChecked();
    expect(screen.getByLabelText("Price for Tax audit")).toBeDisabled();
  });

  it("saves the ticked services with their prices", async () => {
    loginAs("ca");
    const saved = {
      items: [
        { service_id: GST.id, price: "750.00" },
        { service_id: AUDIT.id, price: "20000.00" },
      ],
    };
    const fetchMock = api({ [`PUT ${MENU_URL}`]: [200, saved] });
    renderApp("/ca/services");

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("Tax audit"));
    await user.type(screen.getByLabelText("Price for Tax audit"), "20000");
    await user.click(screen.getByRole("button", { name: "Save prices" }));

    expect(await screen.findByText("Prices saved.", { exact: false })).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(init.body)).toEqual({
      items: [
        { service_id: GST.id, price: "750" },
        { service_id: AUDIT.id, price: "20000" },
      ],
    });
  });

  it.each(["-100", "0"])("refuses a price of %s next to its field and near Save", async (price) => {
    loginAs("ca");
    const fetchMock = api();
    renderApp("/ca/services");

    const user = userEvent.setup();
    const box = await screen.findByLabelText("Price for GSTR-3B filing");
    await user.clear(box);
    await user.type(box, price);
    await user.click(screen.getByRole("button", { name: "Save prices" }));

    expect(await screen.findByText("Fix 1 price: GSTR-3B filing.", { exact: false })).toBeInTheDocument();
    expect(box).toHaveAccessibleDescription("Enter a price from 1 to 10,00,000.");
    expect(box).toHaveFocus();
    expect(screen.queryByText("Prices saved.")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  });

  it("checks prices before sending anything", async () => {
    loginAs("ca");
    const fetchMock = api();
    renderApp("/ca/services");

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("Tax audit"));
    await user.click(screen.getByRole("button", { name: "Save prices" }));

    expect(await screen.findByText("Enter a price from 1 to 10,00,000.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  });

  it("asks for a profile first", async () => {
    loginAs("ca");
    api({
      [`GET ${PROFILE_URL}`]: [
        404,
        { error: { code: "CA_PROFILE_NOT_FOUND", message: "Not completed." } },
      ],
      [`GET ${MENU_URL}`]: [200, { items: [] }],
    });
    renderApp("/ca/services");

    expect(await screen.findByText("Complete your profile first")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Complete profile" })).toHaveAttribute(
      "href",
      "/ca/profile",
    );
  });

  it("tells an unverified CA when businesses will see the prices", async () => {
    loginAs("ca");
    api({ [`GET ${PROFILE_URL}`]: [200, { ...PROFILE, verification_status: "pending" }] });
    renderApp("/ca/services");

    expect(
      await screen.findByText(
        "Businesses see your prices once an admin has verified your profile.",
      ),
    ).toBeInTheDocument();
  });

  it("warns about a priced service outside the specializations and adds it in one click", async () => {
    loginAs("ca");
    const fetchMock = api({
      [`PUT ${PROFILE_URL}`]: [200, { ...PROFILE, specializations: ["gstr_3b", "tax_audit"] }],
    });
    renderApp("/ca/services");
    const user = userEvent.setup();

    await user.click(await screen.findByLabelText("Tax audit")); // its specialization is missing
    const warning = screen.getByRole("note");
    expect(warning).toHaveTextContent("Tax audit");
    await user.click(screen.getByRole("button", { name: "Add to specializations" }));

    await waitFor(() => expect(screen.queryByRole("note")).not.toBeInTheDocument());
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(init.body).specializations).toEqual(["gstr_3b", "tax_audit"]);
  });
});
