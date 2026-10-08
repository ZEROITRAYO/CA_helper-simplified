import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  CA_PROFILE_KEY,
  CA_SERVICES_KEY,
  errorMessage,
  saveCaProfile,
  saveCaServices,
  uploadCertificate,
  useCaProfile,
  useCaServices,
  useServices,
} from "@/api";
import { useAuth } from "@/auth";
import {
  caFacts,
  ErrorText,
  field,
  Field,
  FormField,
  Notice,
  PageTitle,
  QueryStatus,
  Section,
  SpecializationBadges,
  useAction,
} from "@/components/shared";
import {
  Badge,
  Button,
  buttonClass,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Textarea,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  label,
  labelList,
  SERVICE_UNIT_LABELS,
} from "@/lib";

// --- CaProfilePage -----------------------------------------------------------------------------

// The same rules as the checks in backend/routes_marketplace.py.
const profileSchema = z.object({
  membership_no: z.string().regex(/^[0-9]{6}$/, "Enter your 6-digit ICAI membership number."),
  cop_number: z.string().trim().min(1, "Enter your Certificate of Practice number.").max(20),
  city: z.string().trim().min(1, "Enter your city.").max(100),
  languages: z.array(z.string()).min(1, "Choose at least one language."),
  specializations: z.array(z.string()).min(1, "Choose at least one specialization."),
  capacity: z.coerce.number().int().min(1, "Enter a number from 1 to 1000.").max(1000),
  years_experience: z.coerce.number().int().min(0, "Enter a number from 0 to 70.").max(70),
  about: z.string().trim().max(500, "Use at most 500 characters."),
});

const EMPTY_FORM = {
  membership_no: "",
  cop_number: "",
  city: "",
  languages: [],
  specializations: [],
  capacity: "",
  years_experience: "",
  about: "",
};

// The form's values: the saved profile's, or empty fields for a new CA.
function formValues(profile) {
  if (!profile) return EMPTY_FORM;
  return Object.fromEntries(Object.keys(EMPTY_FORM).map((key) => [key, profile[key]]));
}

// Badge colour for each verification status: red until verified, then green.
const STATUS_COLORS = {
  pending: "bg-red-100 text-red-700",
  verified: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

/** What each verification status means for the CA. */
const STATUS_TEXT = {
  pending:
    "An admin is checking your membership and CoP numbers. You will appear in the marketplace once verified.",
  verified:
    "Businesses can find you in the marketplace. Changing your membership or CoP number needs a new check.",
  rejected:
    "An admin could not confirm your numbers. Correct your details and save to ask for a new check.",
};

// Changing one of these fields sends a verified profile back for a new check (backend rule).
const IDENTITY_FIELDS = ["membership_no", "cop_number"];

/** /ca/profile: the practice profile; a new one (or new numbers) needs verification. */
export function CaProfilePage() {
  const profile = useCaProfile();

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">My profile</h1>
      <QueryStatus query={profile} />
      {profile.isSuccess && (
        <>
          <StatusCard profile={profile.data} />
          <CertificateCard profile={profile.data} />
          <CaProfileForm profile={profile.data} />
          {profile.data && <PreviewCard profile={profile.data} />}
        </>
      )}
    </div>
  );
}

function StatusCard({ profile }) {
  const status = profile?.verification_status; // no profile yet (null) -> no status
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Verification
          {status && (
            <Badge className={STATUS_COLORS[status]}>
              {label(CA_VERIFICATION_STATUS_LABELS, status)}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          {status
            ? STATUS_TEXT[status]
            : "Complete your profile. An admin checks your membership and CoP numbers before businesses can see you."}
        </CardDescription>
        {status === "rejected" && profile.rejection_reason && (
          <p className="text-sm">
            <span className="font-medium">The admin's reason: </span>
            {profile.rejection_reason}
          </p>
        )}
      </CardHeader>
    </Card>
  );
}

/** Upload the Certificate of Practice: an admin checks it before verifying the CA. */
function CertificateCard({ profile }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState(null);
  const [done, setDone] = useState(false);
  const { busy, error, run } = useAction();

  async function onUpload(event) {
    event.preventDefault();
    setDone(false);
    await run(async () => {
      queryClient.setQueryData(CA_PROFILE_KEY, await uploadCertificate(file));
      setDone(true);
    });
  }

  let description = "Save your profile first, then upload your certificate.";
  if (profile?.has_certificate) {
    description = "Uploaded. Uploading a new one sends your profile back for verification.";
  } else if (profile) {
    description =
      "Upload your Certificate of Practice (PDF, JPG or PNG, up to 5 MB). An admin checks it before verifying you.";
  }

  return (
    <Section title="Certificate of Practice" description={description}>
      {profile && (
        <>
          <form className="flex flex-wrap items-center gap-3" onSubmit={onUpload}>
            <Label htmlFor="certificate" className="sr-only">
              Certificate file
            </Label>
            <Input
              id="certificate"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              className="w-auto"
              onChange={(event) => setFile(event.target.files[0] || null)}
            />
            <Button type="submit" disabled={!file || busy}>
              {busy ? "Uploading..." : "Upload certificate"}
            </Button>
          </form>
          <ErrorText className="mt-2">{error}</ErrorText>
          {done && (
            <p className="mt-2 text-sm text-muted-foreground">
              Certificate uploaded. An admin will check it.
            </p>
          )}
        </>
      )}
    </Section>
  );
}

/** How the saved profile looks on the businesses' "Find a CA" page. */
function PreviewCard({ profile }) {
  const { user } = useAuth();
  return (
    <Card>
      <CardHeader>
        <CardDescription>Preview: how businesses see you</CardDescription>
        <CardTitle>{user ? user.full_name : ""}</CardTitle>
        <CardDescription>{caFacts(profile)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <SpecializationBadges codes={profile.specializations} />
        <p>
          <span className="text-muted-foreground">Languages: </span>
          {labelList(CA_LANGUAGE_LABELS, profile.languages)}
        </p>
        {profile.about && <p>{profile.about}</p>}
        {profile.verification_status !== "verified" && (
          <p className="text-xs text-muted-foreground">
            Businesses see this once an admin has verified you.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** `profile` is the saved profile, or null for a CA who has not saved one yet. */
function CaProfileForm({ profile }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState(null);
  const [saved, setSaved] = useState(false);
  const form = useForm({ resolver: zodResolver(profileSchema), defaultValues: formValues(profile) });
  const { errors, isSubmitting } = form.formState;
  // A verified CA changing a number is told before saving that it needs a new check.
  const typed = useWatch({ control: form.control, name: IDENTITY_FIELDS });
  const needsNewCheck =
    profile?.verification_status === "verified" &&
    IDENTITY_FIELDS.some((name, index) => typed[index] !== profile[name]);

  async function onSubmit(values) {
    setServerError(null);
    setSaved(false);
    try {
      queryClient.setQueryData(CA_PROFILE_KEY, await saveCaProfile(values));
      setSaved(true);
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "DUPLICATE_MEMBERSHIP_NO") {
        // Show it on the field it is about, not at the bottom of the form.
        form.setError("membership_no", { message: error.message }, { shouldFocus: true });
      } else {
        setServerError(errorMessage(error));
      }
    }
  }

  return (
    <Section title="Practice details" description="Businesses see everything here except your CoP number.">
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label="ICAI membership number"
            inputMode="numeric"
            {...field(form, "membership_no")}
          />
          <FormField label="Certificate of Practice number" {...field(form, "cop_number")} />
          <FormField label="City" {...field(form, "city")} />
          <FormField
            label="Years of experience"
            type="number"
            min={0}
            {...field(form, "years_experience")}
          />
          <FormField
            label="Capacity (clients at a time)"
            type="number"
            min={1}
            {...field(form, "capacity")}
          />
        </div>
        {needsNewCheck && (
          <p className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
            You changed your membership or CoP number: after saving, your profile goes back to an
            admin for verification and you leave the marketplace until then.
          </p>
        )}
        <CheckboxGroup
          legend="Specializations"
          labels={CA_SPECIALIZATION_LABELS}
          error={errors.specializations}
          {...form.register("specializations")}
        />
        <CheckboxGroup
          legend="Languages"
          labels={CA_LANGUAGE_LABELS}
          error={errors.languages}
          {...form.register("languages")}
        />
        <Field id="about" label="About your practice (optional)" error={errors.about}>
          <Textarea id="about" rows={3} aria-invalid={!!errors.about} {...form.register("about")} />
        </Field>
        <ErrorText>{serverError}</ErrorText>
        <Notice>{saved && "Profile saved."}</Notice>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Save profile"}
        </Button>
      </form>
    </Section>
  );
}

/** One checkbox per code in `labels`; React Hook Form collects the ticked codes in an array. */
function CheckboxGroup({ legend, labels, error, ...inputProps }) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {Object.entries(labels).map(([code, text]) => (
          <label
            key={code}
            htmlFor={inputProps.name + "-" + code}
            className="flex items-center gap-2 text-sm"
          >
            <input id={inputProps.name + "-" + code} type="checkbox" value={code} {...inputProps} />
            {text}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-destructive">{error.message}</p>}
    </fieldset>
  );
}

// --- CaServicesPage ----------------------------------------------------------------------------

// The same limits as the checks in backend/routes_marketplace.py.
const MIN_PRICE = 1;
const MAX_PRICE = 1000000;
const PRICE_ERROR = "Enter a price from 1 to 10,00,000.";

// /ca/services: the CA ticks the catalog services they offer and sets a price for
// each. That price is the CA's fixed fee.
export function CaServicesPage() {
  const profile = useCaProfile();
  const services = useServices();
  const menu = useCaServices();

  let content = <QueryStatus query={[profile, services, menu]} />;
  if (profile.isSuccess && services.isSuccess && menu.isSuccess) {
    content = profile.data ? (
      <PriceMenu services={services.data} menu={menu.data} profile={profile.data} />
    ) : (
      <Card>
        <CardHeader>
          <CardTitle>Complete your profile first</CardTitle>
          <CardDescription>You can set your prices once your profile is saved.</CardDescription>
          <div>
            <Link to="/ca/profile" className={buttonClass()}>Complete profile</Link>
          </div>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageTitle title="Services & prices">
        Tick the services you offer and enter your fee. Businesses pay exactly this fee.
      </PageTitle>
      {content}
    </div>
  );
}

// The form's starting rows: { serviceId: { offered, price } } for every catalog service.
function startingRows(services, menu) {
  const rows = {};
  for (const service of services) {
    rows[service.id] = { offered: false, price: "" };
  }
  for (const item of menu.items) {
    // "750.00" -> "750", so the box shows what the CA typed.
    rows[item.service_id] = { offered: true, price: String(Number(item.price)) };
  }
  return rows;
}

function PriceMenu({ services, menu, profile }) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState(startingRows(services, menu));
  const [errors, setErrors] = useState({});
  // Shown next to Save: the rows above may be far up the page (13 services).
  const [errorSummary, setErrorSummary] = useState(null);
  const [saved, setSaved] = useState(false);
  const { busy, error, setError, run } = useAction();

  function updateRow(serviceId, changes) {
    setRows({ ...rows, [serviceId]: { ...rows[serviceId], ...changes } });
    setSaved(false);
  }

  async function onSave(event) {
    event.preventDefault();
    setError(null);
    setErrorSummary(null);
    setSaved(false);

    // Check every ticked row and collect what to send.
    const items = [];
    const newErrors = {};
    const wrongNames = [];
    for (const service of services) {
      const row = rows[service.id];
      if (!row.offered) continue;
      const price = Number(row.price);
      if (row.price === "" || isNaN(price) || price < MIN_PRICE || price > MAX_PRICE) {
        newErrors[service.id] = PRICE_ERROR;
        wrongNames.push(service.name);
      } else {
        items.push({ service_id: service.id, price: row.price });
      }
    }
    setErrors(newErrors);
    if (wrongNames.length > 0) {
      const count = wrongNames.length === 1 ? "1 price" : wrongNames.length + " prices";
      setErrorSummary("Fix " + count + ": " + wrongNames.join(", ") + ".");
      // Move to the first wrong price, which may be out of view.
      document.getElementById(priceId(Object.keys(newErrors)[0]))?.focus();
      return;
    }

    await run(async () => {
      queryClient.setQueryData(CA_SERVICES_KEY, await saveCaServices(items));
      setSaved(true);
    });
  }

  return (
    <form className="space-y-4" onSubmit={onSave} noValidate>
      {profile.verification_status !== "verified" && (
        <p className="text-sm text-muted-foreground">
          Businesses see your prices once an admin has verified your profile.
        </p>
      )}
      <SpecializationWarning services={services} rows={rows} profile={profile} />
      <ul className="space-y-3">
        {services.map((service) => (
          <ServiceRow
            key={service.id}
            service={service}
            row={rows[service.id]}
            error={errors[service.id]}
            onChange={(changes) => updateRow(service.id, changes)}
          />
        ))}
      </ul>
      <ErrorText>{errorSummary}</ErrorText>
      <ErrorText>{error}</ErrorText>
      <Notice>{saved && "Prices saved."}</Notice>
      <Button type="submit" disabled={busy}>
        {busy ? "Saving..." : "Save prices"}
      </Button>
    </form>
  );
}

/** Lists priced services whose specialization the profile lacks, with an add button. */
function SpecializationWarning({ services, rows, profile }) {
  const queryClient = useQueryClient();
  const { busy, error, run } = useAction();

  const missing = [];
  for (const service of services) {
    const code = service.specialization;
    if (rows[service.id].offered && code && !profile.specializations.includes(code)) {
      if (!missing.includes(code)) missing.push(code);
    }
  }
  if (missing.length === 0) return null;

  function onAdd() {
    run(async () => {
      const specializations = profile.specializations.concat(missing);
      const updated = await saveCaProfile({ ...formValues(profile), specializations });
      queryClient.setQueryData(CA_PROFILE_KEY, updated);
    });
  }

  return (
    <div role="note" className="space-y-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
      <p>
        You price services that are not among your specializations:{" "}
        {labelList(CA_SPECIALIZATION_LABELS, missing)}. Businesses filtering by specialization will
        not find you for them.
      </p>
      <Button type="button" size="sm" variant="outline" onClick={onAdd} disabled={busy}>
        {busy ? "Adding..." : "Add to specializations"}
      </Button>
      {error && <p className="text-destructive">{error}</p>}
    </div>
  );
}

// The id of a service's price box (the error summary moves the focus there).
function priceId(serviceId) {
  return "price-" + serviceId;
}

function ServiceRow({ service, row, error, onChange }) {
  const id = priceId(service.id);
  return (
    <li className="space-y-2 rounded-lg border p-3">
      <label htmlFor={"offer-" + service.id} className="flex items-center gap-2 font-medium">
        <input
          id={"offer-" + service.id}
          type="checkbox"
          checked={row.offered}
          onChange={(event) => onChange({ offered: event.target.checked })}
        />
        {service.name}
      </label>
      <p className="text-xs text-muted-foreground">{service.description}</p>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span>₹</span>
        <Input
          id={id}
          aria-label={"Price for " + service.name}
          aria-describedby={error ? id + "-error" : undefined}
          inputMode="decimal"
          className="w-32"
          value={row.price}
          disabled={!row.offered}
          aria-invalid={!!error}
          onChange={(event) => onChange({ price: event.target.value })}
        />
        <span>{label(SERVICE_UNIT_LABELS, service.unit)}</span>
      </div>
      {error && (
        <p id={id + "-error"} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </li>
  );
}
