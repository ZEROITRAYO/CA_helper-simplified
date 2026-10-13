import { useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import {
  MY_ENGAGEMENTS_KEY,
  REQUESTABLE_KEY,
  sendRequest,
  useRefresh,
  useRequestableFilings,
  useServices,
  useVerifiedCa,
  useVerifiedCas,
} from "@/api";
import {
  BackLink,
  caFacts,
  ErrorText,
  Field,
  Options,
  PageTitle,
  Pager,
  QueryStatus,
  RatingSummary,
  RegisterFirst,
  Row,
  Section,
  SpecializationBadges,
  Stars,
  Table,
  useAction,
  VerifiedBadge,
} from "@/components/shared";
import {
  Button,
  buttonClass,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
  labelList,
  SERVICE_UNIT_LABELS,
} from "@/lib";

// --- MarketplacePage ---------------------------------------------------------------------------

const FILTERS = ["service", "specialization", "language", "city"];

/** /business/marketplace: verified CAs; the filters live in the URL (?service=...). */
export function MarketplacePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = {
    specialization: searchParams.get("specialization") ?? "",
    language: searchParams.get("language") ?? "",
    city: searchParams.get("city") ?? "",
    service: searchParams.get("service") ?? "",
    page: Number(searchParams.get("page") || 1),
  };
  const cas = useVerifiedCas(filters);
  const services = useServices();
  // The catalog service picked in the "Service" filter, if any.
  const chosenService = (services.data ?? []).find((service) => service.code === filters.service);

  /** Show `changes` (a new filter goes back to page 1); empty values leave the URL. */
  function show(changes) {
    const next = { ...filters, page: 1, ...changes };
    const params = {};
    for (const name in next) {
      // Leave out empty filters, and page 1 (the default).
      if (next[name] && !(name === "page" && next[name] === 1)) params[name] = next[name];
    }
    setSearchParams(params);
  }

  function onSearch(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    show(Object.fromEntries(FILTERS.map((name) => [name, form.get(name)])));
  }

  return (
    <div className="space-y-6">
      <PageTitle title="Find a CA">Every CA listed here has been verified by our team.</PageTitle>

      {/* key: the inputs show the URL's filters again after "Clear" or back/forward,
          and once the services have loaded (so the Service box can show its choice). */}
      <form
        key={searchParams.toString() + (services.isSuccess ? " loaded" : "")}
        className="grid gap-3 sm:grid-cols-2 sm:items-end lg:grid-cols-5"
        onSubmit={onSearch}
      >
        <Field id="service" label="Service">
          <Select id="service" name="service" defaultValue={filters.service}>
            <option value="">Any</option>
            {(services.data ?? []).map((service) => (
              <option key={service.id} value={service.code}>
                {service.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="specialization" label="Specialization">
          <Select id="specialization" name="specialization" defaultValue={filters.specialization}>
            <Options labels={CA_SPECIALIZATION_LABELS} empty="Any" />
          </Select>
        </Field>
        <Field id="language" label="Language">
          <Select id="language" name="language" defaultValue={filters.language}>
            <Options labels={CA_LANGUAGE_LABELS} empty="Any" />
          </Select>
        </Field>
        <Field id="city" label="City">
          <Input id="city" name="city" defaultValue={filters.city} placeholder="Any" />
        </Field>
        <div className="flex gap-2">
          <Button type="submit">Search</Button>
          <Button type="button" variant="outline" onClick={() => setSearchParams({})}>
            Clear
          </Button>
        </div>
      </form>

      <QueryStatus query={cas} />
      {cas.isSuccess && (
        <>
          <p className="text-sm text-hint">
            {cas.data.total === 1 ? "1 CA found" : `${cas.data.total} CAs found`}
          </p>
          {cas.data.items.length === 0 ? (
            <p className="text-sm">No verified CAs match these filters.</p>
          ) : (
            <ul className="grid gap-4 lg:grid-cols-2">
              {cas.data.items.map((ca) => (
                <li key={ca.id}>
                  <CaCard ca={ca} service={chosenService} search={searchParams.toString()} />
                </li>
              ))}
            </ul>
          )}
          <Pager data={cas.data} onPage={(page) => show({ ...filters, page })} />
        </>
      )}
    </div>
  );
}

// The whole card is a link to the CA's page. `service` is the catalog service chosen in
// the filter (or none); the card then shows this CA's price for it. `search` is the
// current filters, handed to the CA's page so its "Back to results" link keeps them.
function CaCard({ ca, service, search }) {
  return (
    <Link to={"/business/marketplace/" + ca.id} state={{ search }} className="block h-full">
      <Card className="h-full cursor-pointer transition hover:shadow-md hover:ring-2 hover:ring-primary/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <h2>{ca.full_name}</h2>
            <VerifiedBadge />
            {ca.rating_count > 0 && (
              <span className="text-sm font-normal">
                <RatingSummary average={ca.rating_average} count={ca.rating_count} />
              </span>
            )}
          </CardTitle>
          <CardDescription>{caFacts(ca)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <SpecializationBadges codes={ca.specializations} />
          <p>
            <span className="text-hint">Languages: </span>
            {labelList(CA_LANGUAGE_LABELS, ca.languages)}
          </p>
          {ca.about && <p>{ca.about}</p>}
          {service && ca.price !== null && (
            <p>
              <span className="text-hint">Fee for {service.name}: </span>
              <span className="font-medium">
                {formatRupees(ca.price) + " " + label(SERVICE_UNIT_LABELS, service.unit)}
              </span>
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

// --- CaDetailPage ------------------------------------------------------------------------------

// /business/marketplace/:caId: everything about one verified CA, opened from a card
// on "Find a CA". The card passes its search (the filters) so "Back" keeps them.
export function CaDetailPage() {
  const { caId } = useParams();
  const search = useLocation().state?.search;
  const ca = useVerifiedCa(caId);

  return (
    <div className="max-w-3xl space-y-6">
      <BackLink to={"/business/marketplace" + (search ? "?" + search : "")}>Back to results</BackLink>
      <QueryStatus query={ca} />
      {ca.isSuccess && <CaDetails ca={ca.data} />}
    </div>
  );
}

function CaDetails({ ca }) {
  return (
    <>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{ca.full_name}</h1>
          <VerifiedBadge />
        </div>
        <p className="text-sm text-hint">{caFacts(ca)}</p>
      </div>

      <Link to={"/business/marketplace/" + ca.id + "/request"} className={buttonClass()}>
        Request this CA
      </Link>

      <Section
        title="About"
        description={ca.about || "This CA has not written anything about their practice."}
        contentClassName="space-y-3 text-sm"
      >
        <div className="space-y-1">
          <p className="font-medium">Specializations</p>
          <SpecializationBadges codes={ca.specializations} />
        </div>
        <p>
          <span className="font-medium">Languages: </span>
          {labelList(CA_LANGUAGE_LABELS, ca.languages)}
        </p>
      </Section>

      <Section title="Services & fees" description="The CA's fixed fee for each service.">
        {ca.services.length === 0 ? (
          <p className="text-sm">This CA has not listed any prices yet.</p>
        ) : (
          <Table headers={["Service", "Fee"]}>
            {ca.services.map((service) => (
              <Row
                key={service.id}
                cells={[
                  service.name,
                  <>
                    <span className="font-medium">{formatRupees(service.price)}</span>{" "}
                    {label(SERVICE_UNIT_LABELS, service.unit)}
                  </>,
                ]}
              />
            ))}
          </Table>
        )}
      </Section>

      <Section
        title="Ratings"
        description={<RatingSummary average={ca.rating_average} count={ca.rating_count} />}
      >
        {ca.reviews?.length > 0 && (
          <ul className="space-y-3 text-sm">
            {ca.reviews.map((review) => (
              <li key={review.created_at}>
                <Stars stars={review.stars} />{" "}
                <span className="text-hint">{formatDateTime(review.created_at)}</span>
                {review.review && <p>{review.review}</p>}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}

// --- RequestCaPage -----------------------------------------------------------------------------

// /business/marketplace/:caId/request: the business ticks the filings it wants this
// CA to do and sends the request. Filings that cannot be picked say why.
export function RequestCaPage() {
  const { caId } = useParams();
  const ca = useVerifiedCa(caId);
  const filings = useRequestableFilings(caId);

  let content = <QueryStatus query={[ca, filings]} />;
  if (ca.isSuccess && filings.isSuccess) {
    if (filings.data === null) {
      content = <RegisterFirst>first, so we know which filings you have.</RegisterFirst>;
    } else if (filings.data.length === 0) {
      content = <p className="text-sm">You have no filings due for the rest of this year.</p>;
    } else {
      content = <RequestForm caId={caId} filings={filings.data} />;
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <BackLink to={"/business/marketplace/" + caId}>Back to the CA</BackLink>
      <PageTitle title={"Request " + (ca.isSuccess ? ca.data.full_name : "this CA")}>
        Tick the filings you want this CA to do. The CA can accept at these fixed prices or
        decline.
      </PageTitle>
      {content}
    </div>
  );
}

// The price of the chosen service of one filing.
function priceOf(filing, serviceId) {
  const option = filing.options.find((one) => one.service_id === serviceId);
  return option ? Number(option.price) : 0;
}

function RequestForm({ caId, filings }) {
  const navigate = useNavigate();
  const refresh = useRefresh();
  // { filing id: the chosen service id } for every ticked filing.
  const [chosen, setChosen] = useState({});
  const { busy, error, run } = useAction();
  const ticked = filings.filter((filing) => chosen[filing.id]);
  const total = ticked.reduce((sum, filing) => sum + priceOf(filing, chosen[filing.id]), 0);

  function toggle(filing) {
    const next = { ...chosen };
    if (next[filing.id]) {
      delete next[filing.id];
    } else {
      next[filing.id] = filing.options[0].service_id; // the first service by default
    }
    setChosen(next);
  }

  // Tick every filing of a quarter that can be picked (keeping choices already made).
  function selectAll(group) {
    const next = { ...chosen };
    for (const filing of group) {
      if (filing.blocked_reason === null && !next[filing.id]) {
        next[filing.id] = filing.options[0].service_id;
      }
    }
    setChosen(next);
  }

  async function onSend() {
    const items = ticked.map((filing) => ({ compliance_item_id: filing.id, service_id: chosen[filing.id] }));
    const sent = await run(() => sendRequest(caId, items));
    if (sent) {
      refresh(MY_ENGAGEMENTS_KEY, REQUESTABLE_KEY);
      navigate("/business/engagements", { state: { sent: true } });
    }
  }

  // Filings this CA has not priced are listed apart, folded away.
  const offered = filings.filter((filing) => filing.options.length > 0);
  const notOffered = filings.filter((filing) => filing.options.length === 0);

  function filingRow(filing) {
    return (
      <li key={filing.id} className="rounded-lg border p-3 text-sm">
        <label htmlFor={"filing-" + filing.id} className="flex items-center gap-2 font-medium">
          <input
            id={"filing-" + filing.id}
            type="checkbox"
            value={filing.id}
            checked={Boolean(chosen[filing.id])}
            disabled={filing.blocked_reason !== null}
            onChange={() => toggle(filing)}
          />
          {filingFormLabel(filing.form_code, filing.period_label)} {filing.period_label}
          <span className="font-normal text-hint">· due {formatDate(filing.due_date)}</span>
        </label>
        {filing.blocked_reason ? (
          <p className="mt-1 text-hint">{filing.blocked_reason}</p>
        ) : (
          <FilingPrice
            filing={filing}
            serviceId={chosen[filing.id] || filing.options[0].service_id}
            onChoose={(serviceId) => setChosen({ ...chosen, [filing.id]: serviceId })}
          />
        )}
      </li>
    );
  }

  return (
    <div className="space-y-4">
      {groupByQuarter(offered).map((group) => (
        <section key={group.quarter} className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">Due in {group.quarter}</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => selectAll(group.filings)}
              disabled={group.filings.every((filing) => filing.blocked_reason !== null)}
            >
              Select all in {group.quarter.split(" ")[0]}
            </Button>
          </div>
          <ul className="space-y-2">{group.filings.map(filingRow)}</ul>
        </section>
      ))}
      {notOffered.length > 0 && (
        <details className="rounded-lg border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            Not offered by this CA ({notOffered.length})
          </summary>
          <ul className="mt-2 space-y-2">{notOffered.map(filingRow)}</ul>
        </details>
      )}

      <p className="text-sm font-medium">Total at the listed prices: {formatRupees(total)}</p>
      <ErrorText>{error}</ErrorText>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSend} disabled={busy || ticked.length === 0}>
          {busy ? "Sending..." : "Send request"}
        </Button>
        <p className="text-sm text-hint">
          {ticked.length === 0 ? "Tick at least one filing. " : ""}The CA accepts or declines it;
          you can withdraw it until then.
        </p>
      </div>
    </div>
  );
}

// The financial-year quarter a date falls in, e.g. "Q3 (Oct–Dec 2026)".
function quarterOf(isoDate) {
  const year = isoDate.slice(0, 4); // "2026-09-20" -> "2026"
  const month = Number(isoDate.slice(5, 7)); // -> 9
  if (month >= 4 && month <= 6) return "Q1 (Apr–Jun " + year + ")";
  if (month >= 7 && month <= 9) return "Q2 (Jul–Sep " + year + ")";
  if (month >= 10) return "Q3 (Oct–Dec " + year + ")";
  return "Q4 (Jan–Mar " + year + ")";
}

// Groups filings by the quarter of their due date: [{ quarter: "Q2 (Jul–Sep 2026)",
// filings: [...] }, ...] in due-date order (the API sends the filings soonest first).
function groupByQuarter(filings) {
  const groups = [];
  for (const filing of filings) {
    const quarter = quarterOf(filing.due_date);
    const last = groups[groups.length - 1];
    if (last && last.quarter === quarter) {
      last.filings.push(filing);
    } else {
      groups.push({ quarter, filings: [filing] });
    }
  }
  return groups;
}

// The CA's price for a filing. If the CA offers several services for it (ITR),
// the business picks one.
function FilingPrice({ filing, serviceId, onChoose }) {
  if (filing.options.length === 1) {
    const option = filing.options[0];
    return (
      <p className="mt-1">
        {option.name}: <span className="font-medium">{formatRupees(option.price)}</span>
      </p>
    );
  }
  return (
    <select
      aria-label={"Service for " + filing.period_label}
      className="mt-1 h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
      value={serviceId}
      onChange={(event) => onChoose(event.target.value)}
    >
      {filing.options.map((option) => (
        <option key={option.service_id} value={option.service_id}>
          {option.name}: {formatRupees(option.price)}
        </option>
      ))}
    </select>
  );
}
