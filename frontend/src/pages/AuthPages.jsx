import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  changePassword,
  errorMessage,
  forgotPassword,
  resendVerificationCode,
  resetPassword,
  signup,
  useHealth,
  verifyEmail,
} from "@/api";
import { useAuth } from "@/auth";
import { ErrorText, field, FormCard, FormField, Notice, Section } from "@/components/shared";
import {
  Badge,
  Button,
  buttonClass,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  linkClass,
} from "@/components/ui";
import {
  codeSchema,
  emailSchema,
  label,
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
  ROLE_HOME,
  USER_ROLE_LABELS,
} from "@/lib";

// --- Pieces of the account forms ---------------------------------------------------------------

function EmailField({ form }) {
  return <FormField label="Email" type="email" autoComplete="email" {...field(form, "email")} />;
}

function CodeField({ form }) {
  return (
    <FormField
      label="Code"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      {...field(form, "code")}
    />
  );
}

/** "Password" (or "New password") with the rule under it, and "Confirm ...". */
function NewPasswordFields({ form, title = "Password" }) {
  return (
    <>
      <FormField
        label={title}
        type="password"
        autoComplete="new-password"
        hint={PASSWORD_RULE_TEXT}
        {...field(form, "password")}
      />
      <FormField
        label={"Confirm " + title.toLowerCase()}
        type="password"
        autoComplete="new-password"
        {...field(form, "confirm_password")}
      />
    </>
  );
}

function SubmitButton({ form, busyText, children }) {
  const busy = form.formState.isSubmitting;
  return (
    <Button type="submit" className="w-full" disabled={busy}>
      {busy ? busyText : children}
    </Button>
  );
}

/** The server's error or a notice: message is {}, { error } or { notice }. */
function Messages({ message }) {
  return (
    <>
      <ErrorText>{message.error}</ErrorText>
      <Notice>{message.notice}</Notice>
    </>
  );
}

/** "Send a new code", once the email box holds a valid email. */
function ResendButton({ form, send, setMessage }) {
  const [resending, setResending] = useState(false);

  async function onResend() {
    setMessage({});
    if (!(await form.trigger("email"))) return;
    setResending(true);
    try {
      await send(form.getValues("email"));
      setMessage({ notice: "We sent a new code to this email." });
    } catch (error) {
      setMessage({ error: errorMessage(error) });
    } finally {
      setResending(false);
    }
  }

  return (
    <Button type="button" variant="outline" className="w-full" disabled={resending} onClick={onResend}>
      {resending ? "Sending..." : "Send a new code"}
    </Button>
  );
}

/** A line under a form, e.g. "Already have an account? Log in". */
function FooterLink({ text, to, children }) {
  return (
    <p className="text-sm text-hint">
      {text && text + " "}
      <Link to={to} className={linkClass}>
        {children}
      </Link>
    </p>
  );
}

function useZodForm(schema, defaultValues) {
  return useForm({ resolver: zodResolver(schema), defaultValues });
}

// --- HomePage ----------------------------------------------------------------------------------

// Each card links to where that audience starts: signup with the role chosen, or login.
const AUDIENCES = [
  {
    title: "Businesses",
    text: "Profile, compliance calendar, documents, find a CA.",
    action: "Create a business account",
    to: "/signup",
    state: { role: "business" },
  },
  {
    title: "Chartered Accountants",
    text: "Clients, deadlines and requests.",
    action: "Join as a CA",
    to: "/signup",
    state: { role: "ca" },
  },
  { title: "Admins", text: "Users, CA verification and configuration.", action: "Log in", to: "/login" },
];

/** The API status badge is for developers: shown in development, or when something is down. */
function showApiStatus(health) {
  if (import.meta.env.DEV || health.isError) return true;
  return health.isSuccess && health.data.status !== "ok";
}

function ApiStatus({ health }) {
  if (health.isPending) return <Badge variant="secondary">checking...</Badge>;
  if (health.isError) return <Badge variant="destructive">unreachable</Badge>;
  if (health.data.status === "ok") return <Badge>ok</Badge>;
  return <Badge variant="destructive">API up, database {health.data.database}</Badge>;
}

/** Landing page: what the platform is, log in / sign up buttons, and (see above) API status. */
export function HomePage() {
  const health = useHealth();
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">CA Helper</h1>
        <p className="text-hint">
          Know which filings apply to your business and when. File yourself or work with a fairly
          priced CA.
        </p>
        {user ? (
          <Link to={ROLE_HOME[user.role]} className={buttonClass()}>Go to your dashboard</Link>
        ) : (
          <div className="flex gap-2">
            <Link to="/login" className={buttonClass()}>Log in</Link>
            <Link to="/signup" className={buttonClass("outline")}>Create an account</Link>
          </div>
        )}
        {showApiStatus(health) && (
          <p className="text-sm">
            API status: <ApiStatus health={health} />
          </p>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {AUDIENCES.map((audience) => (
          <Link
            key={audience.title}
            to={audience.to}
            state={audience.state}
            className="rounded-xl focus-visible:ring-3 focus-visible:ring-focus/50 focus-visible:outline-none"
          >
            <Card className="h-full transition-colors hover:bg-soft/50">
              <CardHeader>
                <CardTitle>{audience.title}</CardTitle>
                <CardDescription>{audience.text}</CardDescription>
                <span className="text-sm font-medium text-primary">{audience.action} →</span>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

// --- LoginPage ---------------------------------------------------------------------------------

const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
});

/** What to tell the user for each login error code from the API. */
const LOGIN_ERROR_TEXT = {
  INVALID_CREDENTIALS: "Wrong email or password.",
  EMAIL_NOT_VERIFIED: "Your email is not verified yet.",
};

/** After login: back to the page the guard sent the user from, if it is in their area. */
function destination(role, from) {
  const home = ROLE_HOME[role];
  return from && (from === home || from.startsWith(`${home}/`)) ? from : home;
}

/** /login; the location state may carry `from`, `email` and `notice`. */
export function LoginPage() {
  const { user, login } = useAuth();
  const { from, email, notice } = useLocation().state ?? {};
  const [serverError, setServerError] = useState(null);
  // Set when the API says EMAIL_NOT_VERIFIED: the error then links to /verify-email.
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);
  const form = useZodForm(loginSchema, { email: email ?? "" });

  // Logged in (already, or just now by onSubmit): go to the right page.
  if (user) return <Navigate to={destination(user.role, from)} replace />;

  async function onSubmit(values) {
    setServerError(null);
    setUnverifiedEmail(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      const known = error instanceof ApiRequestError && LOGIN_ERROR_TEXT[error.code];
      setServerError(known || errorMessage(error));
      if (error instanceof ApiRequestError && error.code === "EMAIL_NOT_VERIFIED") {
        setUnverifiedEmail(values.email);
      }
    }
  }

  return (
    <FormCard title="Log in" description="Businesses, CAs and admins all log in here.">
      <Notice>{notice}</Notice>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <EmailField form={form} />
        <FormField
          label="Password"
          type="password"
          autoComplete="current-password"
          {...field(form, "password")}
        />
        {serverError && (
          <p role="alert" className="text-sm text-danger">
            {serverError}{" "}
            {unverifiedEmail && (
              <Link to="/verify-email" state={{ email: unverifiedEmail }} className={linkClass}>
                Enter your code
              </Link>
            )}
          </p>
        )}
        <SubmitButton form={form} busyText="Logging in...">
          Log in
        </SubmitButton>
      </form>
      <div className="flex justify-between text-sm">
        <Link to="/forgot-password" className={linkClass}>
          Forgot password?
        </Link>
        <Link to="/signup" className={linkClass}>
          Create an account
        </Link>
      </div>
    </FormCard>
  );
}

// --- SignupPage --------------------------------------------------------------------------------

/** The roles that may sign up (admins are created by the team). */
const SIGNUP_ROLES = ["business", "ca"];

const signupSchema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your name.").max(200, "Use at most 200 characters."),
    email: emailSchema,
    role: z.enum(SIGNUP_ROLES, { error: "Choose how you will use CA Helper." }),
    password: newPasswordSchema,
    confirm_password: z.string(),
    terms_accepted: z.boolean(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR)
  // A check on the whole form (not z.literal on the field), so it is shown together with
  // the other errors.
  .refine((values) => values.terms_accepted, {
    message: "Agree to the Terms and Privacy Policy to sign up.",
    path: ["terms_accepted"],
  });

/** /signup: create a business or CA account, then verify the email with the emailed code. */
export function SignupPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  // The landing page's "Join as a CA" card passes { role: "ca" }.
  const askedRole = useLocation().state?.role;
  const [serverError, setServerError] = useState(null);
  const form = useZodForm(signupSchema, {
    role: SIGNUP_ROLES.includes(askedRole) ? askedRole : "business",
    terms_accepted: false,
  });
  const errors = form.formState.errors;

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  async function onSubmit(values) {
    setServerError(null);
    try {
      await signup(values);
      navigate("/verify-email", { state: { email: values.email } });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <FormCard
      title="Create an account"
      description="For businesses, freelancers and Chartered Accountants."
    >
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <FormField label="Full name" autoComplete="name" {...field(form, "full_name")} />
        <EmailField form={form} />
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">I am signing up as</legend>
          {SIGNUP_ROLES.map((role) => (
            <label key={role} className="flex items-center gap-2 text-sm">
              <input type="radio" value={role} {...form.register("role")} />
              {label(USER_ROLE_LABELS, role)}
            </label>
          ))}
          {errors.role && <p className="text-sm text-danger">{errors.role.message}</p>}
        </fieldset>
        <NewPasswordFields form={form} />
        <div className="space-y-1">
          <label htmlFor="terms_accepted" className="flex items-center gap-2 text-sm">
            <input id="terms_accepted" type="checkbox" {...form.register("terms_accepted")} />
            <span>
              I agree to the{" "}
              <Link to="/terms" target="_blank" className={linkClass}>
                Terms and Privacy Policy
              </Link>
            </span>
          </label>
          {errors.terms_accepted && (
            <p className="text-sm text-danger">{errors.terms_accepted.message}</p>
          )}
        </div>
        <ErrorText>{serverError}</ErrorText>
        <SubmitButton form={form} busyText="Creating account...">
          Create account
        </SubmitButton>
      </form>
      <FooterLink text="Already have an account?" to="/login">
        Log in
      </FooterLink>
    </FormCard>
  );
}

// --- VerifyEmailPage ---------------------------------------------------------------------------

const verifySchema = z.object({ email: emailSchema, code: codeSchema });

/** /verify-email: enter the 6-digit code from the signup email, or get a new one. */
export function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [message, setMessage] = useState({});
  const form = useZodForm(verifySchema, { email: location.state?.email ?? "", code: "" });

  async function onSubmit({ email, code }) {
    setMessage({});
    try {
      await verifyEmail(email, code);
      navigate("/login", {
        state: { email, notice: "Your email is verified. You can log in now." },
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "EMAIL_ALREADY_VERIFIED") {
        navigate("/login", { state: { email, notice: "Your email is already verified. Log in." } });
      } else {
        setMessage({ error: errorMessage(error) });
      }
    }
  }

  return (
    <FormCard
      title="Verify your email"
      description="Enter the 6-digit code we emailed you. You can log in once your email is verified."
    >
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <EmailField form={form} />
        <CodeField form={form} />
        <Messages message={message} />
        <SubmitButton form={form} busyText="Verifying...">
          Verify email
        </SubmitButton>
        <ResendButton form={form} send={resendVerificationCode} setMessage={setMessage} />
      </form>
      <FooterLink text="Already verified?" to="/login">
        Log in
      </FooterLink>
    </FormCard>
  );
}

// --- ForgotPasswordPage ------------------------------------------------------------------------

const forgotSchema = z.object({ email: emailSchema });

/** /forgot-password: ask for a reset code by email, then continue on /reset-password. */
export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const form = useZodForm(forgotSchema);

  async function onSubmit({ email }) {
    setServerError(null);
    try {
      await forgotPassword(email);
      navigate("/reset-password", { state: { email } });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <FormCard
      title="Forgot your password?"
      description="Enter your account's email and we will send you a 6-digit code to reset it."
    >
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <EmailField form={form} />
        <ErrorText>{serverError}</ErrorText>
        <SubmitButton form={form} busyText="Sending...">
          Send code
        </SubmitButton>
      </form>
      <FooterLink text="Remembered it?" to="/login">
        Log in
      </FooterLink>
    </FormCard>
  );
}

// --- ResetPasswordPage -------------------------------------------------------------------------

const resetSchema = z
  .object({
    email: emailSchema,
    code: codeSchema,
    password: newPasswordSchema,
    confirm_password: z.string(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR);

/** /reset-password: the emailed code plus a new password. */
export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [message, setMessage] = useState({});
  const form = useZodForm(resetSchema, { email: location.state?.email ?? "" });

  async function onSubmit({ email, code, password }) {
    setMessage({});
    try {
      await resetPassword(email, code, password);
      navigate("/login", {
        state: { email, notice: "Your password is reset. Log in with your new password." },
      });
    } catch (error) {
      setMessage({ error: errorMessage(error) });
    }
  }

  return (
    <FormCard
      title="Reset your password"
      description="We sent a 6-digit code to your email. Enter it and choose a new password."
    >
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <EmailField form={form} />
        <CodeField form={form} />
        <NewPasswordFields form={form} title="New password" />
        <Messages message={message} />
        <SubmitButton form={form} busyText="Saving...">
          Reset password
        </SubmitButton>
        <ResendButton form={form} send={forgotPassword} setMessage={setMessage} />
      </form>
      <FooterLink to="/login">Back to log in</FooterLink>
    </FormCard>
  );
}

// --- ChangePasswordPage ------------------------------------------------------------------------

const changeSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    password: newPasswordSchema,
    confirm_password: z.string(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR);

const EMPTY_FORM = { current_password: "", password: "", confirm_password: "" };

/** Change password (every role); a wrong current password is 400, so no logout. */
export function ChangePasswordPage() {
  const [message, setMessage] = useState({});
  const form = useZodForm(changeSchema, EMPTY_FORM);

  async function onSubmit({ current_password, password }) {
    setMessage({});
    try {
      await changePassword(current_password, password);
      form.reset(EMPTY_FORM);
      setMessage({ notice: "Your password is changed." });
    } catch (error) {
      setMessage({ error: errorMessage(error) });
    }
  }

  return (
    <FormCard title="Change password" description="We will email you when your password changes.">
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <FormField
          label="Current password"
          type="password"
          autoComplete="current-password"
          {...field(form, "current_password")}
        />
        <NewPasswordFields form={form} title="New password" />
        <Messages message={message} />
        <SubmitButton form={form} busyText="Saving...">
          Change password
        </SubmitButton>
      </form>
    </FormCard>
  );
}

// --- TermsPage ---------------------------------------------------------------------------------

// Plain-language terms: what we store, how it is protected, who sees it, what we do not do.
const SECTIONS = [
  {
    title: "What CA Helper does",
    points: [
      "It tells your business which tax filings apply and when they are due, helps you file them yourself, or connects you with a Chartered Accountant (CA).",
      "It never files a return for you and has no access to the government portals. Filing is done by you or by your CA.",
      "The profile and due dates are a guide. Check anything important with a CA.",
    ],
  },
  {
    title: "What we store",
    points: [
      "Your account: name, email and a hashed password (we never store the password itself).",
      "Your business details: name, type, state, address, turnover, PAN, GSTIN, TAN, phone and the answers you give on the profile form.",
      "Your filings and their status, and the documents you or your CA upload.",
    ],
  },
  {
    title: "How we protect it",
    points: [
      "PAN, GSTIN, TAN and phone numbers are encrypted in our database.",
      "Uploaded documents are encrypted and stored on our server; they are never sent anywhere else.",
      "Nothing you enter is sent to an AI service.",
    ],
  },
  {
    title: "Who sees your data",
    points: [
      "A CA you send a request to sees only a summary (business type, state, size) and the filings in the request, not your PAN, GSTIN, TAN or documents.",
      "Once you and a CA agree, that CA sees your full profile, but only the filings in that engagement and the documents linked to them. When the work ends, their access ends.",
      "Our admins see account and verification details, never the contents of your documents.",
    ],
  },
];

/** /terms: the Terms and Privacy Policy, in plain language. */
export function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Terms and Privacy Policy</h1>
      {SECTIONS.map((section) => (
        <Section key={section.title} title={section.title}>
          <ul className="list-disc space-y-2 pl-5 text-sm">
            {section.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </Section>
      ))}
    </div>
  );
}

// --- NotFoundPage ------------------------------------------------------------------------------

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md space-y-4 p-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="text-sm underline">
        Back to the home page
      </Link>
    </div>
  );
}
