# Things to add or tell the team later

My notes for the new project (`~/Desktop/CA-helper`). The finished code to copy is in this
project (`~/Desktop/SL_simple/CA_helper-simplified`).

## 1. Add the request timeout back to `apiFetch()`

**When:** in my PR #27 (Document vault API), which edits `frontend/src/api.js` anyway, or in its
own small PR. Commit message: `feat(api): give up on requests after 20 seconds`.

**Why it was left out:** PR #7 has a simple `apiFetch()` without a timeout. Without it, a
backend that hangs makes the page wait forever.

**What to add in `frontend/src/api.js`:**

1. The constant, after `ApiRequestError`:

   ```js
   // How long a request may take, in milliseconds (20000 ms = 20 seconds), before it fails with code TIMEOUT.
   export const REQUEST_TIMEOUT = 20_000;
   ```

2. In `apiFetch()`, replace the `fetch(...)` and `response.json()` lines with:

   ```js
   const controller = new AbortController();
   const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
   let response;
   let data;
   try {
     response = await fetch(path, {
       method,
       headers,
       body: body === undefined || isForm ? body : JSON.stringify(body),
       signal: controller.signal,
     });
     // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
     data = await response.json().catch(() => null);
   } catch (error) {
     if (!controller.signal.aborted) throw error; // a network failure: see errorMessage()
   } finally {
     clearTimeout(timer);
   }
   if (controller.signal.aborted) {
     throw new ApiRequestError(
       0,
       "TIMEOUT",
       "The server did not answer within 20 seconds. Try again in a moment.",
     );
   }
   ```

3. In the comment at the top of the file, add back the bullet:

   ```
    * - A request with no answer after REQUEST_TIMEOUT fails with code TIMEOUT, so a
    *   hung server shows a clear message instead of a page that never finishes.
   ```

The full version is `apiFetch()` in this project's `frontend/src/api.js`.

**Check:** stop the backend (`docker compose stop backend`), use a page that loads data: after
20 seconds it shows "The server did not answer within 20 seconds".

## 1b. `lib.js` pieces left out of PR #7 (each is added by the PR that first uses it)

In PR #7, `lib.js` only gets the session block (`STORAGE_KEY`, `loadSession`, `saveSession`,
`clearSession`), because `auth.jsx` uses it. `api.js` has the full PR #7 part (`apiFetch`, `fail`,
`errorMessage`, `get`, `useGet`, `sendForm`, `withQuery`, `useRefresh`). Copy the rest of `lib.js`
from this project's `frontend/src/lib.js`:

| Piece | Add it in | Why that PR |
|---|---|---|
| `ROLE_HOME` (with its comment) | my PR #11 (log in page) | after login the user goes to their role's home |
| `USER_ROLE_LABELS`, `label()` | my PR #14 (sign up page) | the role choice shows "Business" / "Chartered Accountant" |

## 2. `apiDownload()` in `frontend/src/api.js`

**When:** my PR #27 (Document vault API), as the plan says (lines 83-92 of the finished file).
It uses `fail()`, which is already there from PR #7.

## 3. Names that differ from the zip (tell the team when they copy)

Code copied from `CA_helper_production.zip` uses the old names. In our project:

| In the zip | Use instead | Where |
|---|---|---|
| `from models import ... now`, `now()` | `db_now`, `db_now()` | everything that imports `now` from `models.py` |
| `user.email_verified_at` | `user.email_verified` (true/false) | reset password (Person 3), admin users page |
| `terms_accepted_at` | (removed) | signup |
| `code_problem`, `problem` | `check_otp`, `otp_error` | reset password (Person 3) |
| `send_code` | `send_otp` | forgot password (Person 3) |
| `{{ code }}` in email templates | `{{ otp }}` | any new email template with a code |
| `me()` | `my_account()` | `routes_auth.py` |
| `ALL_ROLES` | `"business", "ca", "admin"` written out | `routes_auth.py` |
| `loggedOutOnPurpose` (from `useAuth()`) | `clickedLogout` | `RequireRole` in `frontend/src/routes.jsx` (Person 3, PR #20) |
| `post(path, body)`, `put(path, body)`, `remove(path)` | `apiFetch(path, { method: "POST", body })`, `"PUT"`, `"DELETE"` | every new function in `frontend/src/api.js` |

## 4. Change password was removed

The plan's PR #20 (Person 3, sidebar layout) still adds the change-password page and
`changePassword()` in `api.js`. We removed that feature: tell Person 3 to leave out
`ChangePasswordPage`, `changePassword()`, the `change-password` route and the sidebar link.
A logged-in user who wants a new password uses "Forgot password".

## 5. Colour names (team decision still open)

`index.css` on `main` uses `ink`, `hint`, `soft`, `danger`, `focus`, but `ui.jsx` from the zip uses
`foreground`, `muted-foreground`, `muted`, `destructive`, `ring`, `primary-foreground`. Either put
the original names back in `index.css`, or rename the classes when copying (`text-foreground` ->
`text-ink`, `text-muted-foreground` -> `text-hint`, `bg-muted` -> `bg-soft`, `destructive` ->
`danger`, `ring` -> `focus`, `text-primary-foreground` -> `text-white`). This project's
`frontend/src/components/ui.jsx` already uses the new names.

## 6. Small things for Person 1

- `http_error` in `backend/app.py` sends `error.name` ("Not Found"); the zip uppercases it
  (`code = error.name.upper().replace(" ", "_")`, giving "NOT_FOUND").
- `MAIL_SUPPRESS_SEND` in `backend/app.py` is no longer used (no `outbox` in `helpers.py`).
