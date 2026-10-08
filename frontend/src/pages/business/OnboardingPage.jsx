import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import {
  errorMessage,
  FILINGS_KEY,
  MY_BUSINESS_KEY,
  readRegistrationDocument,
  registerBusiness,
  saveNicCode,
  updateBusiness,
  useGstStates,
  useMyBusiness,
  useNicSearch,
  useRefresh,
} from "@/api";
import {
  Choice,
  ErrorText,
  field,
  Field,
  FormField,
  Options,
  QueryStatus,
  Section,
  useAction,
} from "@/components/shared";
import {
  Badge,
  Button,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
} from "@/components/ui";
import {
  ENTITY_TYPE_LABELS,
  formatRupees,
  GST_SCHEME_LABELS,
  gstinError,
  ITR_FORM_LABELS,
  label,
  MSME_TIER_LABELS,
} from "@/lib";

// --- OnboardingPage ----------------------------------------------------------------------------

/** /business/onboarding: the registration form, or the profile with its reasons. */
export function OnboardingPage() {
  const myBusiness = useMyBusiness();
  const states = useGstStates();
  const [editing, setEditing] = useState(false);
  const [changes, setChanges] = useState(null);

  let content;
  if (!myBusiness.isSuccess || !states.isSuccess) {
    content = <QueryStatus query={[myBusiness, states]} />;
  } else if (myBusiness.data === null) {
    content = <BusinessForm states={states.data} />;
  } else if (editing) {
    content = (
      <BusinessForm
        states={states.data}
        business={myBusiness.data.business}
        onSaved={(saved) => {
          setChanges(saved.changes);
          setEditing(false);
        }}
        onCancel={() => setEditing(false)}
      />
    );
  } else {
    content = (
      <>
        {changes && <WhatChanged changes={changes} />}
        <ProfileView
          business={myBusiness.data.business}
          profile={myBusiness.data.profile}
          nicCode={myBusiness.data.nic_code}
          onEdit={() => {
            setChanges(null);
            setEditing(true);
          }}
        />
      </>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Business profile</h1>
      {content}
    </div>
  );
}

// ----------------------------------------------------------------------------
// The registration / edit form
// ----------------------------------------------------------------------------

const AMOUNT = /^[0-9]+(\.[0-9]{1,2})?$/; // rupees, e.g. 4500000 or 4500000.50
const GSTIN_FORMAT = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$/;
const COMPANY_TYPES = ["llp", "private_limited"];

// The same rules as the checks in backend/routes_business.py.
// `states` is [{name, code}]: the state must be one of them, and a GSTIN must fit it.
function makeSchema(states) {
  const codeOf = Object.fromEntries(states.map((state) => [state.name, state.code]));
  const code = () => z.string().trim().toUpperCase();
  return (
    z
      .object({
        legal_name: z.string().trim().min(1, "Enter the business name.").max(200),
        entity_type: z.string().min(1, "Choose the type of business."),
        state: z.string().refine((name) => name in codeOf, "Choose your state from the list."),
        address: z.string().trim().min(1, "Enter the address.").max(500),
        description: z.string().trim().min(1, "Describe what the business does.").max(1000),
        annual_turnover: z.string().regex(AMOUNT, "Enter an amount in rupees, e.g. 4500000."),
        investment_amount: z.string().regex(AMOUNT, "Enter an amount in rupees, e.g. 800000."),
        pan: code().regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/, "Enter a valid PAN, e.g. ABCDE1234F."),
        phone: z.string().regex(/^[6-9][0-9]{9}$/, "Enter a 10-digit mobile number."),
        gst_registered: z.boolean(),
        gstin: code(),
        gst_composition: z.boolean(),
        gst_returns: z.enum(["monthly", "quarterly"]),
        accounts_audited_other_law: z.boolean(),
        deducts_tds: z.boolean(),
        tan: code(),
        pays_salary_above_limit: z.boolean(),
        cin_llpin: code(),
        udyam_number: code(),
      })
      // Fields that are needed only for some businesses.
      .superRefine((form, ctx) => {
        const problem = (path, message) => ctx.addIssue({ code: "custom", path: [path], message });
        if (form.gst_registered) {
          const gstinProblem = GSTIN_FORMAT.test(form.gstin)
            ? gstinError(form.gstin, form.pan, form.state, codeOf[form.state])
            : "Enter a valid 15-character GSTIN.";
          if (gstinProblem) problem("gstin", gstinProblem);
        }
        if (form.deducts_tds && !/^[A-Z]{4}[0-9]{5}[A-Z]$/.test(form.tan)) {
          problem("tan", "Enter a valid TAN, e.g. MUMA12345B.");
        }
        if (COMPANY_TYPES.includes(form.entity_type) && !form.cin_llpin) {
          problem("cin_llpin", "Enter the CIN or LLPIN.");
        }
        if (form.udyam_number && !/^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/.test(form.udyam_number)) {
          problem("udyam_number", "Enter it like UDYAM-MH-01-0000001, or leave it empty.");
        }
      })
  );
}

const EMPTY_FORM = {
  legal_name: "",
  entity_type: "",
  state: "",
  address: "",
  description: "",
  annual_turnover: "",
  investment_amount: "",
  pan: "",
  phone: "",
  gst_registered: false,
  gstin: "",
  gst_composition: false,
  gst_returns: "monthly",
  accounts_audited_other_law: false,
  deducts_tds: false,
  tan: "",
  pays_salary_above_limit: false,
  cin_llpin: "",
  udyam_number: "",
};

// The saved business as form values: only the form's own fields (the API refuses
// others), amounts as typed, empty codes as "".
function formValues(business) {
  const values = {};
  for (const key of Object.keys(EMPTY_FORM)) {
    values[key] = business[key] ?? EMPTY_FORM[key];
  }
  values.state = business.state_needs_review ? "" : business.state;
  values.annual_turnover = String(Number(business.annual_turnover));
  values.investment_amount = String(Number(business.investment_amount));
  values.gst_returns = business.gst_qrmp ? "quarterly" : "monthly";
  return values;
}

// A field filled by "Fill in from a document" is purple until the form is saved.
const OCR_CLASS = "border-purple-500 bg-purple-50 text-purple-900";

/** Registers a business (no `business`) or edits the saved one. */
function BusinessForm({ states, business, onSaved, onCancel }) {
  const queryClient = useQueryClient();
  const refresh = useRefresh();
  const [serverError, setServerError] = useState(null);
  const [ocrFields, setOcrFields] = useState([]); // the fields read from a document
  const form = useForm({
    resolver: zodResolver(makeSchema(states)),
    defaultValues: business ? formValues(business) : EMPTY_FORM,
  });
  const { errors, isSubmitting } = form.formState;

  // Some fields appear only after a tick or a choice.
  const [gstRegistered, composition, deductsTds, entityType] = useWatch({
    control: form.control,
    name: ["gst_registered", "gst_composition", "deducts_tds", "entity_type"],
  });
  const needsCin = COMPANY_TYPES.includes(entityType);
  const asksOtherAudit = entityType === "partnership" || entityType === "llp";

  // Purple for a field that was read from a document.
  function ocr(name) {
    return ocrFields.includes(name) ? OCR_CLASS : "";
  }

  function input(name) {
    return { ...field(form, name), className: ocr(name) };
  }

  async function onSubmit(values) {
    setServerError(null);
    const { gst_returns, ...rest } = values;
    // Send empty codes as null, and only the ones that apply.
    const sent = {
      ...rest,
      gstin: values.gst_registered ? values.gstin : null,
      gst_composition: values.gst_registered && values.gst_composition,
      gst_qrmp: values.gst_registered && !values.gst_composition && gst_returns === "quarterly",
      accounts_audited_other_law: asksOtherAudit && values.accounts_audited_other_law,
      tan: values.deducts_tds ? values.tan : null,
      pays_salary_above_limit: values.deducts_tds && values.pays_salary_above_limit,
      cin_llpin: needsCin ? values.cin_llpin : null,
      udyam_number: values.udyam_number || null,
    };
    try {
      const saved = business ? await updateBusiness(sent) : await registerBusiness(sent);
      queryClient.setQueryData(MY_BUSINESS_KEY, {
        business: saved.business,
        profile: saved.profile,
        nic_code: saved.nic_code,
      });
      refresh(FILINGS_KEY); // the filings may have changed
      onSaved?.(saved);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Section
      title={business ? "Edit your business details" : "Register your business"}
      description="We use these details to work out which filings apply to you and when they are due. PAN, GSTIN, TAN and phone are stored encrypted."
    >
      {!business && <FillFromDocument setValue={form.setValue} onFilled={setOcrFields} />}
      {ocrFields.length > 0 && (
        <p role="note" className="mb-4 rounded-lg bg-purple-100 p-3 text-sm text-purple-900">
          The fields in purple were read from your document. Check them before you register, as
          scanning can be wrong.
        </p>
      )}
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Business name" {...input("legal_name")} />
          <Field id="entity_type" label="Type of business" error={errors.entity_type}>
            <Select id="entity_type" className={ocr("entity_type")} {...form.register("entity_type")}>
              <Options labels={ENTITY_TYPE_LABELS} empty="Choose..." />
            </Select>
          </Field>
          <Field id="state" label="State" error={errors.state}>
            <Select id="state" className={ocr("state")} {...form.register("state")}>
              <option value="">Choose...</option>
              {states.map((state) => (
                <option key={state.code} value={state.name}>
                  {state.name}
                </option>
              ))}
            </Select>
            {business?.state_needs_review && !errors.state && (
              <p className="text-xs text-muted-foreground">
                You typed "{business.state}" before this list existed: please choose it again.
              </p>
            )}
          </Field>
          <FormField label="Mobile number" inputMode="numeric" {...field(form, "phone")} />
          <FormField
            label="Annual turnover (₹)"
            inputMode="decimal"
            {...field(form, "annual_turnover")}
          />
          <FormField
            label="Investment in plant & machinery (₹)"
            inputMode="decimal"
            {...field(form, "investment_amount")}
          />
          <FormField label="PAN" {...input("pan")} />
          <FormField label="Udyam number (optional)" {...field(form, "udyam_number")} />
          {needsCin && <FormField label="CIN (company) or LLPIN (LLP)" {...field(form, "cin_llpin")} />}
        </div>
        <FormField label="Address" {...field(form, "address")} />
        <FormField
          label="What does the business do?"
          hint="In your own words, e.g. 'We bake biscuits and cakes'."
          {...field(form, "description")}
        />

        {asksOtherAudit && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Audit</legend>
            <Choice
              id="accounts_audited_other_law"
              text="Our accounts are audited under another law (for example the LLP Act or our partnership deed)"
              {...form.register("accounts_audited_other_law")}
            />
            <p className="text-xs text-muted-foreground">
              LLPs above certain limits, and firms whose deed requires it, have their accounts
              audited every year. Ask your CA if you are not sure. An audit moves the income tax
              return's due date.
            </p>
          </fieldset>
        )}

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">GST</legend>
          <Choice id="gst_registered" text="GST registered" {...form.register("gst_registered")} />
          {gstRegistered && (
            <>
              <FormField label="GSTIN" {...input("gstin")} />
              <Choice
                id="gst_composition"
                text="I chose the composition scheme"
                {...form.register("gst_composition")}
              />
              {!composition && (
                <div className="space-y-1">
                  <p className="text-sm">How do you file GST returns?</p>
                  <div className="flex gap-4">
                    <Choice
                      id="gst_monthly"
                      type="radio"
                      value="monthly"
                      text="Monthly"
                      {...form.register("gst_returns")}
                    />
                    <Choice
                      id="gst_quarterly"
                      type="radio"
                      value="quarterly"
                      text="Quarterly (QRMP)"
                      {...form.register("gst_returns")}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Quarterly returns (QRMP) are allowed up to a turnover limit; above it, returns
                    are monthly and your profile will say so.
                  </p>
                </div>
              )}
            </>
          )}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">TDS</legend>
          <Choice id="deducts_tds" text="I deduct TDS" {...form.register("deducts_tds")} />
          {deductsTds && (
            <>
              <FormField label="TAN" {...field(form, "tan")} />
              <Choice
                id="pays_salary_above_limit"
                text="I pay salaries above the taxable limit"
                {...form.register("pays_salary_above_limit")}
              />
            </>
          )}
        </fieldset>

        <ErrorText>{serverError}</ErrorText>
        <div className="flex gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : business ? "Save changes" : "Register business"}
          </Button>
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </form>
    </Section>
  );
}

// The form fields "Fill in from a document" can fill, with the names people see.
const FILLABLE = {
  legal_name: "business name",
  entity_type: "type of business",
  state: "state",
  pan: "PAN",
  gstin: "GSTIN",
};

/** Fill the form from a GST certificate or PAN card (read on the server, not stored). */
function FillFromDocument({ setValue, onFilled }) {
  const [message, setMessage] = useState(null);
  const { busy, error, run } = useAction();

  async function onFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    setMessage(null);
    await run(async () => {
      const { found } = await readRegistrationDocument(file);
      const filled = Object.keys(FILLABLE).filter((name) => found[name]);
      for (const name of filled) setValue(name, found[name], { shouldValidate: true });
      if (found.gstin) setValue("gst_registered", true);
      onFilled(filled);
      setMessage(
        filled.length
          ? `Filled in: ${filled.map((name) => FILLABLE[name]).join(", ")}.`
          : "We could not find any details in this file. Please type them in.",
      );
    });
    event.target.value = ""; // the same file can be chosen again
  }

  return (
    <div className="mb-6 space-y-2 rounded-lg border border-dashed p-4">
      <Label htmlFor="autofill_file">Fill in from your GST certificate or PAN card (optional)</Label>
      <input
        id="autofill_file"
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        className="block text-sm"
        disabled={busy}
        onChange={onFile}
      />
      <p className="text-xs text-muted-foreground">
        {busy
          ? "Reading the file..."
          : "The file is read on our server and not kept. Nothing is saved until you register."}
      </p>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

// ----------------------------------------------------------------------------
// The regulatory profile
// ----------------------------------------------------------------------------

const yesNo = (value) => (value ? "Yes" : "No");

// Every profile line: [code in the profile, title, how to show its value].
const LINES = [
  ["msme_tier", "MSME tier", (value) => label(MSME_TIER_LABELS, value)],
  ["gst_scheme", "GST scheme", (value) => label(GST_SCHEME_LABELS, value)],
  ["itr_form", "Income tax return form", (value) => label(ITR_FORM_LABELS, value)],
  ["presumptive_eligible", "Presumptive scheme", yesNo],
  ["audit_applicable", "Tax audit (s.44AB; s.63 from tax year 2026-27)", yesNo],
  ["other_audit_applicable", "Accounts audited under another law", yesNo],
  ["files_24q", "TDS return, salary (Form 138, earlier 24Q)", yesNo],
  ["files_26q", "TDS return, other payments (Form 140, earlier 26Q)", yesNo],
];

// The short GST chip of each scheme ("No GST" when not registered).
const GST_CHIPS = { regular_qrmp: "QRMP", regular_monthly: "GST monthly", composition: "Composition" };

// The short summary at the top of the profile, e.g. Micro · QRMP · ITR-4 · 26Q.
function summaryChips(profile) {
  const chips = [
    label(MSME_TIER_LABELS, profile.msme_tier),
    GST_CHIPS[profile.gst_scheme] ?? "No GST",
    label(ITR_FORM_LABELS, profile.itr_form),
  ];
  if (profile.presumptive_eligible) chips.push("Presumptive");
  if (profile.audit_applicable || profile.other_audit_applicable) chips.push("Audit");
  if (profile.files_24q) chips.push("24Q");
  if (profile.files_26q) chips.push("26Q");
  return chips;
}

const WARNING = "rounded-lg bg-amber-100 p-3 text-sm text-amber-900";

function ProfileView({ business, profile, nicCode, onEdit }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{business.legal_name}</CardTitle>
          <CardDescription>
            {label(ENTITY_TYPE_LABELS, business.entity_type)} · {business.state} · turnover{" "}
            {formatRupees(business.annual_turnover)}
          </CardDescription>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
            <ul className="flex flex-wrap gap-2" aria-label="Profile summary">
              {summaryChips(profile).map((chip) => (
                <li key={chip}>
                  <Badge variant="secondary">{chip}</Badge>
                </li>
              ))}
            </ul>
            <Link to="/business/compliance" className="text-sm underline">
              See your filings in the compliance calendar
            </Link>
          </div>
          <div className="pt-2">
            <Button variant="outline" size="sm" onClick={onEdit}>
              Edit details
            </Button>
          </div>
        </CardHeader>
      </Card>

      {business.state_needs_review && (
        <p role="alert" className={WARNING}>
          Your state "{business.state}" is not in our list. Choose it again with Edit details.
        </p>
      )}
      {profile.gst_registration_suggested && (
        <p role="alert" className={WARNING}>
          {profile.explanations.gst_scheme}
        </p>
      )}
      {profile.roc_not_tracked && (
        <p className="rounded-lg bg-muted p-3 text-sm">{profile.explanations.roc_not_tracked}</p>
      )}

      <NicCodeCard nicCode={nicCode} />

      <p className="text-xs text-muted-foreground">
        The legal limits behind this profile are still being verified. Check with a CA before
        relying on it.
      </p>
    </>
  );
}

// ----------------------------------------------------------------------------
// After an edit: what changed
// ----------------------------------------------------------------------------

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function WhatChanged({ changes }) {
  const filings = changes.filings;
  const lines = changes.profile.map((change) => {
    const [, title, show] = LINES.find(([key]) => key === change.line);
    return `${title}: ${show(change.old)} → ${show(change.new)}`;
  });
  if (filings.added) lines.push(`${plural(filings.added, "filing")} added`);
  if (filings.removed) lines.push(`${plural(filings.removed, "filing")} no longer needed`);
  if (filings.kept_with_ca) {
    lines.push(
      `${plural(filings.kept_with_ca, "filing")} kept although no longer needed, because a CA has it`,
    );
  }

  return (
    <Section
      role="status"
      title="Saved. What changed"
      description={lines.length === 0 && "Nothing in your profile or filings changed."}
    >
      {lines.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// --- NicCodeCard -------------------------------------------------------------------------------

/** The business's NIC code: found with a search, saved only after Confirm. */
export function NicCodeCard({ nicCode }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState("");
  const [saved, setSaved] = useState(false);
  const { busy, error, run } = useAction();
  const results = useNicSearch(search);
  const rows = results.data ?? [];

  function onConfirm() {
    run(async () => {
      const code = await saveNicCode(chosen);
      // Show the new code on the page without loading the whole business again.
      const cached = queryClient.getQueryData(MY_BUSINESS_KEY);
      if (cached) queryClient.setQueryData(MY_BUSINESS_KEY, { ...cached, nic_code: code });
      setSearch("");
      setChosen("");
      setSaved(true);
    });
  }

  return (
    <Section
      title="Business activity (NIC code)"
      description="The official code for what your business does. Forms like Udyam and GST registration ask for it."
      contentClassName="space-y-4"
    >
      <p className="text-sm">
        {nicCode ? (
          <>
            Your code: <span className="font-semibold">{nicCode.code}</span> · {nicCode.description}
          </>
        ) : (
          "Not chosen yet."
        )}
      </p>
      {saved && (
        <p role="status" className="text-sm text-green-700">
          Saved.
        </p>
      )}

      <div className="space-y-2">
        <Label htmlFor="nic-search">Search the NIC list</Label>
        <Input
          id="nic-search"
          placeholder="e.g. bakery, tailoring or 10712"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {rows.length > 0 && (
          <fieldset className="space-y-2">
            <legend className="sr-only">Search results</legend>
            {rows.map((nic) => (
              <label
                key={nic.code}
                htmlFor={"nic-" + nic.code}
                className="flex items-start gap-2 rounded-lg border p-2 text-sm"
              >
                <input
                  id={"nic-" + nic.code}
                  type="radio"
                  name="nic-code"
                  value={nic.code}
                  checked={chosen === nic.code}
                  onChange={() => setChosen(nic.code)}
                  className="mt-1"
                />
                <span>
                  <span className="font-semibold">{nic.code}</span> · {nic.description}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        {search.trim().length >= 2 && results.data && rows.length === 0 && (
          <p className="text-sm text-muted-foreground">No code found.</p>
        )}
      </div>

      <ErrorText>{error}</ErrorText>
      <Button type="button" onClick={onConfirm} disabled={busy || chosen === ""}>
        Confirm
      </Button>
    </Section>
  );
}
