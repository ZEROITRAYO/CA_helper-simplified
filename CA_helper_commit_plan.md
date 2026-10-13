# CA Helper: commit plan (small features, 3 people in parallel, 20 days)

Every feature belongs to **one person, from the database to the page**: for example the person who builds the log in page also builds the log in API, the tokens and the saved session. Features are small (2 to 6 PRs of about 200 lines), and **the three of you work at the same time, one PR each per day** (sometimes two small ones), about 150-300 lines a day. Day 1 (PRs #1-#3) is done.

## Every day

1. Morning: `git switch main && git pull` (yesterday's PRs are merged).
2. If your PR says **wait for #N today**, wait until #N is merged and pull again; otherwise start right away.
3. `git switch -c <the branch in the PR>`, write the code under **Files** (line numbers are those of the finished project in `CA_helper_production.zip`), add an import only when the code uses it (**Top of the files** shows the result), run `docker compose up` and do **See it work before you push**.
4. Push and open the pull request. **Merge the day's PRs in number order.** Before you merge, run `git pull origin main` on your branch: if git reports a conflict in the lines named under **Merging**, keep both sides (each PR adds its own lines).

Every PR was checked twice: on its own branch (earlier days plus only what it waits for) and in the merge order. Each time the frontend builds, the backend starts and seeds, the API works on a copy of the shared Neon database, and the commands below give the output shown (copied from those runs). After the last PR the project is exactly `CA_helper_production.zip`.

## Day 2, first thing: fix-up PR (Person 1)

Your repo after PRs #1-#3 matches the plan except for three things that would break later PRs. Merge this before the day-2 PRs (branch `p1/03-fix-ups`):

1. **`frontend/src/index.css`**: replace it with the finished project's `frontend/src/index.css`. The UI kit (`ui.jsx`) uses colour names like `primary-foreground`, `muted-foreground` and `destructive`, which your file doesn't define (it has `ink`, `hint`, `soft`, `danger`). Without them, button text is invisible and later pages lose their colours.
2. **`backend/helpers.py`**: rename `now()` back to `today_in_india()` and `date()` back to `india_date()`. Later files import `now` from `models.py` together with these helpers, so a helper called `now` would clash with it, and `date` clashes with Python's `date`.
3. **`.env.example`**: in `.gitignore`, add `!.env.example` under `.env.*` (without it git ignores the file), then add `.env.example` back from the zip.

```bash
git check-ignore .env.example        # prints nothing: the file can be committed
docker compose exec backend python -c "from helpers import today_in_india, india_date; print(today_in_india())"
```

Open http://localhost:5173/terms: the page has its colours. Commit: `fix: theme colours, helper names and .env.example`.

## The 20 days

| Day | Person 1 | Person 2 | Person 3 |
|---|---|---|---|
| 1 | #1 (done) | #2 (done) | #3 (done) |
| 2 | fix-up, #6 (205) | #4 (243) | #5 (259) |
| 3 | #9 (178) | #7 (278) | #8 + #10 (280) |
| 4 | #13 (227) | #11 (288) | #12 (164) |
| 5 | #15 + #17 (292) | #14 (195) | #16 (200) |
| 6 | #19 (209) | - | #18 (219) |
| 7 | #21 (277) | #22 (220) | #20 + #23 (291) |
| 8 | #26 (150) | #25 (183) | #24 (204) |
| 9 | #28 (172) | #27 (190) | #29 (210) |
| 10 | #30 (245) | #31 + #34 (294) | #32 + #33 (271) |
| 11 | #36 (198) | #37 + #38 (283) | #35 (130) |
| 12 | #40 (224) | #41 (225) | #39 (206) |
| 13 | #43 (216) | #42 (275) | #44 (173) |
| 14 | #47 (168) | #45 + #48 (293) | #46 (181) |
| 15 | - | #49 (210) | #50 (162) |
| 16 | #54 (217) | #51 + #53 (291) | #52 (192) |
| 17 | #55 (242) | - | #56 (180) |
| 18 | #57 (214) | - | #58 (151) |
| 19 | #59 (198) | - | #60 (95) |
| 20 | - | - | - |

The numbers in brackets are that day's lines. Day 20 is spare.

## Who does what

| Feature | Owner | PRs | Lines |
|---|---|---|---|
| [Sign up, log in and the home page](#sign-up-log-in-and-the-home-page) | Person 2 | #4, #7, #11, #14 | 1004 |
| [Passwords, sidebar and notifications](#passwords-sidebar-and-notifications) | Person 3 | #8, #18, #20, #29 | 738 |
| [Guides: income tax and TDS](#guides-income-tax-and-tds) | Person 3 | #12, #16 | 364 |
| [Guides: GST](#guides-gst) | Person 1 | #6, #9 | 383 |
| [Database tables and legal rules](#database-tables-and-legal-rules) | Person 3 | #5, #10 | 397 |
| [Register a business and its regulatory profile](#register-a-business-and-its-regulatory-profile) | Person 1 | #13, #15, #17, #19, #21, #26 | 1155 |
| [Fill the form by OCR and the NIC code](#fill-the-form-by-ocr-and-the-nic-code) | Person 2 | #22, #37 | 365 |
| [Compliance calendar, dashboard and filing page](#compliance-calendar-dashboard-and-filing-page) | Person 3 | #24, #32, #33, #35, #39 | 811 |
| [Document vault and proof of filing](#document-vault-and-proof-of-filing) | Person 2 | #25, #27, #34, #42, #51 | 1000 |
| [Penalties and peer insights](#penalties-and-peer-insights) | Person 2 | #38, #48 | 301 |
| [CA profile and admin verification](#ca-profile-and-admin-verification) | Person 1 | #28, #30, #36, #40, #43 | 1055 |
| [CA marketplace](#ca-marketplace) | Person 2 | #31, #41, #45, #49, #53 | 798 |
| [Engagements](#engagements) | Person 1 | #47, #54, #55, #57, #59 | 1039 |
| [CA workspace](#ca-workspace) | Person 3 | #44, #46, #50, #52, #56, #58 | 1039 |
| [Reminders and README](#reminders-and-readme) | Person 3 | #23, #60 | 219 |

| | Person 1 | Person 2 | Person 3 |
|---|---|---|---|
| PRs (with the done ones) | 19 | 19 | 22 |
| **Lines** | 3884 | 3734 | 3804 |
| of which backend | 1176 | 1287 | 1118 |
| of which frontend | 2241 | 2434 | 2222 |
| of which guide content | 383 | 0 | 364 |

11422 lines in the whole project. Nothing generated is committed. One data file is copied, not counted: `content/reference/nic_2008.csv`, the official NIC list.

## Your test account (each person, once)

- After PR #4 is merged, create it with the commands in its check (or, after PR #18, on /signup): `p1-test@example.com`, `p2-test@example.com` or `p3-test@example.com`, password `Test#2026`, role Business.
- After PR #21 is merged, log in with it and register its business on **Business profile**: State Maharashtra, PAN `ABCDE1234F`, tick **GST registered**, GSTIN `27ABCDE1234F1Z0`, quarterly returns, anything for the rest. Later checks use its filings, so the demo data stays clean.
- The demo accounts are already in the shared Neon database: `business@demo.local` / `DemoBusiness#2026`, `ca@demo.local` / `DemoCA#2026`, `admin@demo.local` / `DemoAdmin#2026`. Emails go to Mailpit: http://localhost:8025.

## API helpers for the checks

Paste these in the terminal where you run the checks (set `ME` to your test account):

```bash
api()   { curl -s -w '  [HTTP %{http_code}]\n' "http://localhost:8000/api/v1$1" "${@:2}"; }
login() { curl -s http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
            -d "{\"email\":\"$1\",\"password\":\"$2\"}" | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'; }
bapi()  { api "$1" -H "Authorization: Bearer $(login business@demo.local 'DemoBusiness#2026')" "${@:2}"; }
capi()  { api "$1" -H "Authorization: Bearer $(login ca@demo.local 'DemoCA#2026')" "${@:2}"; }
aapi()  { api "$1" -H "Authorization: Bearer $(login admin@demo.local 'DemoAdmin#2026')" "${@:2}"; }
tapi()  { api "$1" -H "Authorization: Bearer $(login "$ME" 'Test#2026')" "${@:2}"; }
J='Content-Type: application/json'
ME=p1-test@example.com    # YOUR test account: p1-test, p2-test or p3-test
```

---

# Sign up, log in and the home page

**Person 2** · PRs #4, #7, #11, #14 · **1004 lines**

The accounts: the users table, sign up with an emailed code, log in with a token the browser keeps, the API client, and the home, log in and sign up pages.

## 4 Accounts backend: sign up, email code, log in

**Person 2** · **day 2** · **243 lines** · branch `p2/04-accounts-backend-sign-up` · start in the morning

### What this PR builds

- The `users` and `email_otps` tables.
- Sign up (`POST /auth/signup`), a 6-digit code emailed to verify the address (`POST /auth/verify-email`, `.../resend`), log in with a token (`POST /auth/login`) and `GET /auth/me`.
- Passwords stored only as argon2 hashes; emails sent through Mailpit (`verify_email`, `reset_password` templates).
- Login tokens in `app.py`: a bad or missing token answers 401, so the frontend logs out.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 36-56, 70 | load_user, token_error, part of http_error | 23 |
| `backend/helpers.py` | 114-151 | hasher, hash_password, check_password, outbox, send_email | 41 |
| `backend/models.py` | 45-69 | User, EmailOtp | 25 |
| `backend/routes_auth.py` (new file) | 1-3, 16-126, 175-180 | top of file, ALL_ROLES, PASSWORD_RULE, CODE_MINUTES, user_to_dict, find_user, good_password, send_code ... | 132 |
| `backend/templates/email/reset_password.txt` (new file) | all |  | 11 |
| `backend/templates/email/verify_email.txt` (new file) | all |  | 11 |
| **Total** | | | **243** |

### Top of the files after this PR

`backend/app.py`

```python
# CA Helper backend: the Flask app. Start it with
#     flask --app app run --host 0.0.0.0 --port 8000 --debug     (docker compose does this)
# The routes are in the routes_*.py files, imported at the bottom of this file.

import os
import uuid

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException

from models import User, db
```

`backend/helpers.py`

```python
# Small helpers the route files share: errors, the logged-in user, money, passwords,
# email, notifications, GSTIN checks and storing uploaded files.

import smtplib
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from flask import current_app, jsonify, render_template
from flask_jwt_extended import get_current_user, jwt_required
```

`backend/routes_auth.py`

```python
# Accounts: sign up with an emailed 6-digit code, log in, passwords, the email switch and
# the notification inbox.

import re
import secrets
from datetime import timedelta

from flask import jsonify, request
from flask_jwt_extended import create_access_token

from app import app
from helpers import (
    check_password, current_user, error, hash_password, role_required, send_email,
)
from models import EmailOtp, User, db, now
```

### See it work before you push

- Paste the API helpers (top of this file), then sign up your test account:

```bash
api /auth/signup -H "$J" -d '{"full_name":"Test Owner","email":"'$ME'","password":"Test#2026","role":"business","terms_accepted":true}'
# open http://localhost:8025 (Mailpit): an email with a 6-digit code arrived
CODE=123456    # put the code from that email here
api /auth/verify-email -H "$J" -d '{"email":"'$ME'","code":"'$CODE'"}'
login $ME 'Test#2026'
login business@demo.local 'DemoBusiness#2026'
```

You should see something like (shortened):

```text
{
  "email": "new4-test@example.com",
  "full_name": "Test Owner",
  "id": "1cc8a2f4-4a97-4b9d-bc86-b71108f6dbf0",
  "role": "business"
}
  [HTTP 201]
  [HTTP 204]
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc5MTg3MzU5MSwianRpIjoiOGEyYjAwZTEtNDFlMy00Z ...
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc5MTg3MzU5MSwianRpIjoiM2M4Njc4NjQtOTM4OC00M ...
```

### Commit message

`feat(accounts): sign up with an emailed code and log in`

## 7 Log in session in the app: API client and saved login

**Person 2** · **day 3** · **278 lines** · branch `p2/07-log-in-session-in-the-app` · start in the morning

### What this PR builds

- `api.js` part 1: `apiFetch()` (adds the login token, a 20 s timeout, JSON errors as `ApiRequestError`, logs out on a 401), `errorMessage()`, and the helpers every API call uses (`useGet`, `post`, `put`, `remove`, `sendForm`, `withQuery`, `useRefresh`).
- `lib.js`: the saved login session (localStorage), each role's home page, role labels and `label()`.
- `auth.jsx`: the AuthProvider that holds the session and logs in through `POST /auth/login`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/api.js` (new file) | 2-82, 93-165 | top of file, ApiRequestError, REQUEST_TIMEOUT_MS, accessToken, logout, setAuth, apiFetch, fail ... | 155 |
| `frontend/src/auth.jsx` (new file) | all | top of file, AuthProvider, AuthContext, useAuth | 59 |
| `frontend/src/lib.js` | 12-21, 156-160, 291-336 | USER_ROLE_LABELS, label, ROLE_HOME, STORAGE_KEY, loadSession, saveSession, clearSession | 61 |
| `frontend/src/main.jsx` | 24, 26 | part of router | 3 |
| **Total** | | | **278** |

### Top of the files after this PR

`frontend/src/api.js`

```js
import { useQuery, useQueryClient } from "@tanstack/react-query";
```

`frontend/src/auth.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useLayoutEffect, useState } from "react";

import { apiFetch, setAuth } from "@/api";
import { clearSession, loadSession, saveSession } from "@/lib";
```

`frontend/src/main.jsx`

```js
import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";

import { AuthProvider } from "@/auth";
import { appRoutes } from "@/routes";
```

### See it work before you push

- Nothing new on screen yet (the log in page comes in PR #11). Check that the frontend still builds:

```bash
docker compose exec frontend npm run build
```

You should see something like (shortened):

```text
vite v8.3.1 building client environment for production...
transforming...
✓ 150 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                              0.39 kB │ gzip:   0.26 kB
dist/assets/geist-cyrillic-ext-wght-normal-DjL33-gN.woff2    7.42 kB
dist/assets/geist-vietnamese-wght-normal-6IgcOCM7.woff2      8.00 kB
dist/assets/geist-cyrillic-wght-normal-BEAKL7Jp.woff2       15.08 kB
dist/assets/geist-latin-ext-wght-normal-DC-KSUi6.woff2      16.51 kB
dist/assets/geist-latin-wght-normal-BgDaEnEv.woff2          29.40 kB
dist/assets/index-o5YIdBd8.css                              21.11 kB │ gzip:   4.82 kB
dist/assets/index-BLQqwENo.js                              369.61 kB │ gzip: 116.37 kB
✓ built in 251ms
```

### Commit message

`feat(auth): API client and session provider`

## 11 Log in page

**Person 2** · **day 4** · **288 lines** · branch `p2/11-log-in-page` · start in the morning

### What this PR builds

- `shared.jsx` form pieces: `useAction()` (busy + error for a button), ErrorText, Notice, QueryStatus, Field, FormField, `field()`, FormCard.
- Account form pieces: email field, new password + confirm fields, submit button, footer link, `useZodForm()`; the email rule in `lib.js`.
- The log in page: messages for a wrong email or password and an unverified email; afterwards the user goes to their role's home page (or back to the page they wanted).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/components/shared.jsx` | 31-57, 65-96, 205-244, 290-306 | useAction, ErrorText, Notice, QueryStatus, Field, FormField, field, FormCard | 124 |
| `frontend/src/lib.js` | 337-343, 358-359 | PASSWORD_RULE_TEXT, emailSchema | 10 |
| `frontend/src/pages/AuthPages.jsx` | 40-45, 58-87, 123-138, 203-284 | EmailField, NewPasswordFields, SubmitButton, FooterLink, useZodForm, loginSchema, LOGIN_ERROR_TEXT, destination ... | 152 |
| `frontend/src/routes.jsx` | 88 | part of appRoutes | 2 |
| **Total** | | | **288** |

### Top of the files after this PR

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useState } from "react";

import { errorMessage } from "@/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  cn,
} from "@/lib";
```

`frontend/src/lib.js`

```js
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { z } from "zod";
```

`frontend/src/pages/AuthPages.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  errorMessage,
} from "@/api";
import { useAuth } from "@/auth";
import { field, FormCard, FormField, Notice, Section } from "@/components/shared";
import {
  Button,
  linkClass,
} from "@/components/ui";
import {
  emailSchema,
  PASSWORD_RULE_TEXT,
  ROLE_HOME,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Outlet } from "react-router";

import {
  LoginPage,
  NotFoundPage,
  TermsPage,
} from "@/pages/AuthPages";
```

### See it work before you push

- Open http://localhost:5173/login and log in with `business@demo.local` / `DemoBusiness#2026`: you are sent to /business (still the 404 page until PR #20 adds the business area).
- Try a wrong password: **Wrong email or password.**

### Commit message

`feat(auth): log in page`

## 14 Home page and sign up page

**Person 2** · **day 5** · **195 lines** · branch `p2/14-home-page-and-sign-up-page` · start in the morning

### What this PR builds

- The home page: what the platform is, for whom, Log in / Create an account (or 'Go to your dashboard').
- `signup()` in `api.js` and the password rules in `lib.js`.
- The sign up page: name, email, password, role (business or CA), the Terms tick; then on to verify the email.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/api.js` | 166-172 | signup | 7 |
| `frontend/src/lib.js` | 344-351, 360-368 | newPasswordSchema, passwordsMatch, PASSWORDS_MATCH_ERROR | 17 |
| `frontend/src/pages/AuthPages.jsx` | 139-202, 285-376 | AUDIENCES, HomePage, SIGNUP_ROLES, signupSchema, SignupPage | 167 |
| `frontend/src/routes.jsx` | 87, 89 | part of appRoutes | 4 |
| **Total** | | | **195** |

### Top of the files after this PR

`frontend/src/pages/AuthPages.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  errorMessage,
  signup,
} from "@/api";
import { useAuth } from "@/auth";
import { ErrorText, field, FormCard, FormField, Notice, Section } from "@/components/shared";
import {
  Button,
  buttonClass,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  linkClass,
} from "@/components/ui";
import {
  emailSchema,
  label,
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
  ROLE_HOME,
  USER_ROLE_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Outlet } from "react-router";

import {
  HomePage,
  LoginPage,
  NotFoundPage,
  SignupPage,
  TermsPage,
} from "@/pages/AuthPages";
```

### See it work before you push

- Open http://localhost:5173: the home page with **Log in** and **Create an account**.
- Open http://localhost:5173/signup, sign up as a Business with a new email (for example `p1-signup@example.com`) and tick the Terms.
- You are sent to /verify-email (404 until PR #18) and Mailpit (http://localhost:8025) has the code email.

### Commit message

`feat(auth): home page and sign up page`

---

# Passwords, sidebar and notifications

**Person 3** · PRs #8, #18, #20, #29 · **738 lines**

Forgot / reset / change password (API and pages), the logged-in layout with the sidebar, and the notification inbox with the email switch.

## 8 Accounts backend: passwords, email switch, notification inbox

**Person 3** · **day 3** · **142 lines** · branch `p3/08-accounts-backend-passwords` · start in the morning

### What this PR builds

- The `notifications` table; `notify()` saves a notification and emails it when the user wants emails.
- Forgot password (emails a code), reset password with the code, change password while logged in (with a 'password changed' email).
- The email switch (`GET/PUT /auth/settings`) and the inbox API (`GET /alerts/notifications`, `POST .../read`).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/helpers.py` | 95-103, 152-164 | page_of, notify, email_notice | 24 |
| `backend/models.py` | 206-215 | Notification | 10 |
| `backend/routes_auth.py` | 127-174, 181-222 | forgot_password, save_new_password, reset_password, change_password, settings, notification_to_dict, list_notifications, mark_read | 90 |
| `backend/templates/email/notification.txt` (new file) | all |  | 10 |
| `backend/templates/email/password_changed.txt` (new file) | all |  | 8 |
| **Total** | | | **142** |

### Top of the files after this PR

`backend/helpers.py`

```python
# Small helpers the route files share: errors, the logged-in user, money, passwords,
# email, notifications, GSTIN checks and storing uploaded files.

import smtplib
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from flask import current_app, jsonify, render_template, request
from flask_jwt_extended import get_current_user, jwt_required

from models import Notification, db
```

`backend/routes_auth.py`

```python
# Accounts: sign up with an emailed 6-digit code, log in, passwords, the email switch and
# the notification inbox.

import re
import secrets
from datetime import timedelta

from flask import jsonify, request
from flask_jwt_extended import create_access_token

from app import app
from helpers import (
    check_password, current_user, error, hash_password, iso, page_of, role_required, send_email,
)
from models import EmailOtp, Notification, User, db, now
```

### See it work before you push

- With the API helpers pasted:

```bash
api /auth/forgot-password -H "$J" -d '{"email":"'$ME'"}'
tapi /auth/settings
bapi "/alerts/notifications?page=1"
```

You should see something like (shortened):

```text
  [HTTP 204]
{
  "email_notifications": true
}
  [HTTP 200]
{
  "items": [
    {
      "body": "From: Demo CA (your CA)\nTo: Asha Traders\n\nMessage: Please download GSTR-2B for the period fr ...
      "created_at": "2026-10-08T02:35:30.117319+00:00",
      "id": "bd1a6aab-f5e5-48e4-9459-4e8f67171c5f",
      "link": "/business/compliance/f4e7e7b8-371c-402f-ad03-985f5ca78cff",
      "read_at": null,
      "title": "Demo CA asked you for a document for GSTR-3B (Sep 2026)",
      "type": "document_request"
    },
...
```

### Commit message

`feat(accounts): password reset, email switch and notification inbox API`

## 18 Verify email, forgot and reset password pages

**Person 3** · **day 6** · **219 lines** · branch `p3/18-verify-email-forgot` · start in the morning

### What this PR builds

- The 6-digit code field, messages, and 'send the code again'.
- Verify email page, forgot password page (emails a code) and reset password page (code + new password).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/api.js` | 173-190 | verifyEmail, resendVerificationCode, forgotPassword, resetPassword | 18 |
| `frontend/src/lib.js` | 352-357 | codeSchema | 6 |
| `frontend/src/pages/AuthPages.jsx` | 46-57, 88-122, 377-513 | CodeField, Messages, ResendButton, verifySchema, VerifyEmailPage, forgotSchema, ForgotPasswordPage, resetSchema ... | 189 |
| `frontend/src/routes.jsx` | 91-93 | part of appRoutes | 6 |
| **Total** | | | **219** |

### Top of the files after this PR

`frontend/src/pages/AuthPages.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  errorMessage,
  forgotPassword,
  resendVerificationCode,
  resetPassword,
  signup,
  verifyEmail,
} from "@/api";
import { useAuth } from "@/auth";
import { ErrorText, field, FormCard, FormField, Notice, Section } from "@/components/shared";
import {
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
```

`frontend/src/routes.jsx`

```js
import { Link, Outlet } from "react-router";

import {
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
```

### See it work before you push

- Open http://localhost:5173/verify-email, enter the email and the code from the check of PR #14: the email is verified and /login works with it.
- Open http://localhost:5173/forgot-password, enter the email: Mailpit gets a reset code email; http://localhost:5173/reset-password sets a new password with that code.

### Commit message

`feat(auth): verify email, forgot and reset password pages`

## 20 Logged-in layout (sidebar) and change password page

**Person 3** · **day 7** · **167 lines** · branch `p3/20-logged-in-layout-sidebar` · start in the morning

### What this PR builds

- The logged-in layout: a sidebar with the role's links, the user's name, Change password and Log out; `RequireRole` sends visitors to /login and other roles to their own home.
- The three role areas in `routes.jsx`: /business, /ca and /admin, and the Change password page.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/api.js` | 191-198 | changePassword | 8 |
| `frontend/src/pages/AuthPages.jsx` | 514-560 | changeSchema, EMPTY_FORM, ChangePasswordPage | 48 |
| `frontend/src/routes.jsx` | 43-45, 53-54, 62-63, 66-81, 96, 107-108, 117-118, 122, 126-203 | part of NAV, roleArea, part of appRoutes, AppShell, RequireRole | 111 |
| **Total** | | | **167** |

### Top of the files after this PR

`frontend/src/pages/AuthPages.jsx`

```js
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
  verifyEmail,
} from "@/api";
import { useAuth } from "@/auth";
import { ErrorText, field, FormCard, FormField, Notice, Section } from "@/components/shared";
import {
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
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
```

### See it work before you push

- Log in: you see the sidebar (CA Helper, your role, your name, **Change password**, **Log out**; page links come with later PRs).
- **Change password** in the sidebar changes it (Mailpit gets a 'password changed' email).

### Commit message

`feat(layout): sidebar layout and change password page`

## 29 Settings page: notification inbox and email switch

**Person 3** · **day 9** · **210 lines** · branch `p3/29-settings-page-notification` · start in the morning

### What this PR builds

- The settings page for businesses and CAs: the inbox (newest first, unread in bold, click to open and mark read, pages) and the 'Email me my notifications' switch.
- `Pager` and `formatDateTime()`; 'Notification settings' in both sidebars.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/api.js` | 199-210, 369-381 | SETTINGS_KEY, useSettings, saveSettings, NOTIFICATIONS_KEY, useNotifications, markNotificationRead | 25 |
| `frontend/src/components/shared.jsx` | 269-289 | Pager | 22 |
| `frontend/src/lib.js` | 195-206 | formatDateTime | 12 |
| `frontend/src/pages/SettingsPage.jsx` (new file) | all | top of file, SettingsPage, NotificationList, NotificationView, EmailSwitch | 146 |
| `frontend/src/routes.jsx` | 52, 61, 106, 116 | part of NAV, part of appRoutes | 5 |
| **Total** | | | **210** |

### Top of the files after this PR

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  cn,
  COMPLIANCE_STATUS_LABELS,
  label,
} from "@/lib";
```

`frontend/src/pages/SettingsPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  markNotificationRead,
  NOTIFICATIONS_KEY,
  saveSettings,
  SETTINGS_KEY,
  useNotifications,
  useRefresh,
  useSettings,
} from "@/api";
import { ErrorText, Pager, QueryStatus, Section, useAction } from "@/components/shared";
import { Button } from "@/components/ui";
import { formatDateTime } from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
```

### Merging

Merged after #27 today. When you pull `main` before merging, git may show a conflict in `frontend/src/api.js`: keep both sides (yours and theirs).

### See it work before you push

- Log in as `business@demo.local`: the sidebar has **Notification settings**. Open it: the inbox (click a notification to open it, unread ones are bold) and the email switch.

### Commit message

`feat(settings): notification inbox and email switch page`

---

# Guides: income tax and TDS

**Person 3** · PRs #12, #16 · **364 lines**

The guides (checklist, explanation, instructions) of the income tax return and the TDS returns 24Q / 26Q, and the GST state list.

## 12 Guide content: income tax return (ITR) and the GST state list

**Person 3** · **day 4** · **164 lines** · branch `p3/12-guide-content-income-tax` · start in the morning

### What this PR builds

- `content/README.md`, `content/reference/gst_states.json` (each state and its GST code), and the ITR guide: checklist (YAML), explanation and instructions (Markdown).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `content/README.md` (new file) | all |  | 19 |
| `content/forms/ITR/checklist.yaml` (new file) | all |  | 38 |
| `content/forms/ITR/explanation.md` (new file) | all |  | 30 |
| `content/forms/ITR/instructions.md` (new file) | all |  | 36 |
| `content/reference/gst_states.json` (new file) | all |  | 41 |
| **Total** | | | **164** |

### See it work before you push

- Open `content/forms/ITR/explanation.md` in VS Code and press Ctrl+Shift+V (Markdown preview). And run:

```bash
docker compose exec backend python -c "import json, yaml; print('ITR:', len(yaml.safe_load(open('../content/forms/ITR/checklist.yaml'))['items']), 'checklist items'); print(len(json.load(open('../content/reference/gst_states.json'))['states']), 'states')"
```

You should see something like (shortened):

```text
ITR: 7 checklist items
36 states
```

### Commit message

`docs(content): ITR guide and the GST state list`

## 16 Guide content: TDS returns 24Q and 26Q

**Person 3** · **day 5** · **200 lines** · branch `p3/16-guide-content-tds-returns` · start in the morning

### What this PR builds

- The 24Q and 26Q guides.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `content/forms/24Q/checklist.yaml` (new file) | all |  | 30 |
| `content/forms/24Q/explanation.md` (new file) | all |  | 32 |
| `content/forms/24Q/instructions.md` (new file) | all |  | 38 |
| `content/forms/26Q/checklist.yaml` (new file) | all |  | 30 |
| `content/forms/26Q/explanation.md` (new file) | all |  | 32 |
| `content/forms/26Q/instructions.md` (new file) | all |  | 38 |
| **Total** | | | **200** |

### See it work before you push

- Open the new `.md` files with Ctrl+Shift+V. And run:

```bash
docker compose exec backend python -c "import yaml; [print(f, len(yaml.safe_load(open(f'../content/forms/{f}/checklist.yaml'))['items']), 'checklist items') for f in ('24Q', '26Q',)]"
```

You should see something like (shortened):

```text
24Q 5 checklist items
26Q 5 checklist items
```

### Commit message

`docs(content): 24Q and 26Q guides`

---

# Guides: GST

**Person 1** · PRs #6, #9 · **383 lines**

The guides of GSTR-1, GSTR-3B, CMP-08 and GSTR-4.

## 6 Guide content: GSTR-1 and GSTR-3B

**Person 1** · **day 2** · **205 lines** · branch `p1/06-guide-content-gstr-1` · start in the morning

### What this PR builds

- The GSTR-1 and GSTR-3B guides.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `content/forms/GSTR-1/checklist.yaml` (new file) | all |  | 32 |
| `content/forms/GSTR-1/explanation.md` (new file) | all |  | 30 |
| `content/forms/GSTR-1/instructions.md` (new file) | all |  | 39 |
| `content/forms/GSTR-3B/checklist.yaml` (new file) | all |  | 35 |
| `content/forms/GSTR-3B/explanation.md` (new file) | all |  | 30 |
| `content/forms/GSTR-3B/instructions.md` (new file) | all |  | 39 |
| **Total** | | | **205** |

### See it work before you push

- Open the new `.md` files with Ctrl+Shift+V. And run:

```bash
docker compose exec backend python -c "import yaml; [print(f, len(yaml.safe_load(open(f'../content/forms/{f}/checklist.yaml'))['items']), 'checklist items') for f in ('GSTR-1', 'GSTR-3B',)]"
```

You should see something like (shortened):

```text
GSTR-1 5 checklist items
GSTR-3B 6 checklist items
```

### Commit message

`docs(content): GSTR-1 and GSTR-3B guides`

## 9 Guide content: CMP-08 and GSTR-4

**Person 1** · **day 3** · **178 lines** · branch `p1/09-guide-content-cmp-08` · start in the morning

### What this PR builds

- The CMP-08 and GSTR-4 guides.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `content/forms/CMP-08/checklist.yaml` (new file) | all |  | 27 |
| `content/forms/CMP-08/explanation.md` (new file) | all |  | 29 |
| `content/forms/CMP-08/instructions.md` (new file) | all |  | 33 |
| `content/forms/GSTR-4/checklist.yaml` (new file) | all |  | 27 |
| `content/forms/GSTR-4/explanation.md` (new file) | all |  | 29 |
| `content/forms/GSTR-4/instructions.md` (new file) | all |  | 33 |
| **Total** | | | **178** |

### See it work before you push

- Open the new `.md` files with Ctrl+Shift+V. And run:

```bash
docker compose exec backend python -c "import yaml; [print(f, len(yaml.safe_load(open(f'../content/forms/{f}/checklist.yaml'))['items']), 'checklist items') for f in ('CMP-08', 'GSTR-4',)]"
```

You should see something like (shortened):

```text
CMP-08 4 checklist items
GSTR-4 4 checklist items
```

### Commit message

`docs(content): CMP-08 and GSTR-4 guides`

---

# Database tables and legal rules

**Person 3** · PRs #5, #10 · **397 lines**

The database tables of the whole app, and the legal limits and due-date rules (seed.py) that the business pages use.

## 5 Database tables for businesses, filings, documents and CAs

**Person 3** · **day 2** · **259 lines** · branch `p3/05-database-tables-for` · **wait for #4 today**

### What this PR builds

- Every remaining table: NIC codes, businesses, regulatory profiles, rule thresholds, obligation templates, filings, checklist ticks, penalty rules, reminder log, documents and their links, CA profiles, the service catalog, CA prices, engagements and their filings, ratings, document requests. PAN, GSTIN, TAN and phone are encrypted.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/models.py` | 70-205, 216-337 | NicCode, Business, RegulatoryProfile, RuleThreshold, ObligationTemplate, ComplianceItem, ChecklistTick, PenaltyRule ... | 259 |
| **Total** | | | **259** |

### Top of the files after this PR

`backend/models.py`

```python
# The database tables. Every table has an id (UUID), created_at and updated_at.
# PAN, GSTIN, TAN and phone numbers are stored encrypted (EncryptedText below).

import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
```

### See it work before you push

- Restart the backend, then:

```bash
docker compose exec backend python -c "from app import app; from models import db; print(len(db.metadata.tables), 'tables:', ', '.join(sorted(db.metadata.tables)))"
```

You should see something like (shortened):

```text
20 tables: businesses, ca_profiles, ca_services, checklist_ticks, compliance_item_documents, compliance_items, ...
```

### Commit message

`feat(db): tables for businesses, filings, documents and CAs`

## 10 Legal rule tables: limits and due-date rules (seed.py)

**Person 3** · **day 3** · **138 lines** · branch `p3/10-legal-rule-tables-limits` · start in the morning

### What this PR builds

- `seed.py`: the legal limits (MSME tiers, GST registration, composition, QRMP, presumptive scheme, tax audit) and the due-date rules of every form, from official sources. Safe to run again.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/seed.py` (new file) | 1-8, 18, 40-132, 175-185, 195-200, 219-231 | top of file, RULES_FROM, MSME_SOURCE, RULE_THRESHOLDS, GST_FAQ, OBLIGATION_TEMPLATES, save, part of seed | 138 |
| **Total** | | | **138** |

### Top of the files after this PR

`backend/seed.py`

```python
# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in the shared Neon database.

import sys
from datetime import date
from decimal import Decimal

from app import app
from models import ObligationTemplate, RuleThreshold, db
```

### See it work before you push


```bash
docker compose exec backend python seed.py
```

You should see something like (shortened):

```text
Seeded: service catalog, rule thresholds, obligation templates, penalty rules, NIC codes, filings synced to th ...
```

### Commit message

`feat(rules): legal limits and due-date rules in seed.py`

---

# Register a business and its regulatory profile

**Person 1** · PRs #13, #15, #17, #19, #21, #26 · **1155 lines**

Registering and editing a business, working out its regulatory profile from the legal limits, and making its filings for the year: API, form and profile page.

## 13 Business registration logic: form checks, GSTIN check, regulatory profile

**Person 1** · **day 4** · **227 lines** · branch `p1/13-business-registration-logic` · **wait for #12 today**

### What this PR builds

- Reading the registration form safely: required fields, PAN / GSTIN / TAN / Udyam / CIN formats, amounts, the state list, the GSTIN check (state code, PAN inside it, check character).
- `compute_profile()`: MSME tier, GST scheme, ITR form, presumptive scheme, audits and TDS returns, from the limits in the rule tables only.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/helpers.py` | 52-56, 79-94, 104-113, 165-201 | my_business, money, read_amount, format_inr, GST_STATES, state_code, gstin_check_character, gstin_error | 70 |
| `backend/routes_business.py` (new file) | 1-4, 23-166 | top of file, ENTITY_TYPES, COMPANY_TYPES, PROFILE_LINES, CODES, read_business_form, limit, compute_profile | 157 |
| **Total** | | | **227** |

### Top of the files after this PR

`backend/helpers.py`

```python
# Small helpers the route files share: errors, the logged-in user, money, passwords,
# email, notifications, GSTIN checks and storing uploaded files.

import json
import smtplib
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from flask import current_app, jsonify, render_template, request
from flask_jwt_extended import get_current_user, jwt_required

from models import Business, Notification, db
```

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from helpers import (
    error, format_inr, gstin_error, read_amount,
    state_code, today_in_india,
)
from models import (
    RuleThreshold, now,
)
```

### See it work before you push

- Work out the profile of a made-up business (MSME tier, GST scheme, ITR form, files 26Q) and check a GSTIN:

```bash
docker compose exec backend python -c "
from app import app
from models import Business
from routes_business import compute_profile
from helpers import gstin_error
with app.app_context():
    b = Business(entity_type='proprietorship', annual_turnover=4000000, investment_amount=500000,
                 gst_registered=True, gst_composition=False, gst_qrmp=True,
                 accounts_audited_other_law=False, deducts_tds=True, pays_salary_above_limit=False)
    p = compute_profile(b)
    print(p['msme_tier'], p['gst_scheme'], p['itr_form'], p['files_26q'])
    print(gstin_error('27AAPFU0939F1ZV', 'AAPFU0939F', 'Maharashtra'))
"
```

You should see something like (shortened):

```text
micro regular_qrmp itr_4 True
None
```

### Commit message

`feat(onboarding): registration form checks and regulatory profile`

## 15 Filing calendar engine: periods, due dates, making a business's filings

**Person 1** · **day 5** · **172 lines** · branch `p1/15-filing-calendar-engine` · start in the morning

### What this PR builds

- `filings.py` part 1: financial years, periods, due dates from the obligation templates, form names (24Q/26Q become Form 138/140 from 2026-27).
- `sync_filings()`: makes a business's filings for the year match its profile.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/filings.py` (new file) | 1-4, 17-171 | top of file, DONE, NOT_STARTED, FORM_FOLDERS, RENAMED_FORMS, form_name, filing_name, filing_to_dict ... | 167 |
| `backend/seed.py` | 216-218 | part of seed | 5 |
| **Total** | | | **172** |

### Top of the files after this PR

`backend/filings.py`

```python
# Everything about filings that several route files need: periods and due dates, making a
# business's calendar, the checklists and texts of each form, the filing page, and checking
# an uploaded acknowledgement. The legal dates come from obligation_templates (seed.py).

import calendar
from datetime import date

from helpers import iso
from models import (
    ChecklistTick, ComplianceItem, ComplianceItemDocument, DocumentRequest, Engagement,
    EngagementItem, ObligationTemplate, ReminderLog, db,
)
```

`backend/seed.py`

```python
# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in the shared Neon database.

import sys
from datetime import date
from decimal import Decimal

from app import app
from filings import sync_filings
from helpers import today_in_india
from models import ObligationTemplate, RegulatoryProfile, RuleThreshold, db
```

### See it work before you push

- The financial year of a day and its quarters (label, start, end):

```bash
docker compose exec backend python -c "
from datetime import date
from filings import financial_year_start, fy_label, periods_of_year
start = financial_year_start(date(2026, 10, 12))
print(fy_label(start))
for period in periods_of_year('quarterly', start):
    print(period[0], period[1], period[2])
"
```

You should see something like (shortened):

```text
2026-27
Q1 2026-27 2026-04-01 2026-06-30
Q2 2026-27 2026-07-01 2026-09-30
Q3 2026-27 2026-10-01 2026-12-31
Q4 2026-27 2027-01-01 2027-03-31
```

### Commit message

`feat(filings): periods, due dates and the filing calendar engine`

## 17 Register and edit the business (API)

**Person 1** · **day 5** · **120 lines** · branch `p1/17-register-and-edit` · **wait for #15 today**

### What this PR builds

- `POST /onboarding/business` registers the business, works out its profile and makes this year's filings; `GET` returns it; `PUT` edits it and returns what changed. `GET /onboarding/states`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 71 | part of http_error | 1 |
| `backend/routes_business.py` | 167-252 | business_page, register_business, get_business, update_business, list_states | 92 |
| `frontend/src/api.js` | 211-229, 242-246, 252-254 | MY_BUSINESS_KEY, useMyBusiness, registerBusiness, updateBusiness, useGstStates, FILINGS_KEY | 27 |
| **Total** | | | **120** |

### Top of the files after this PR

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from flask import jsonify, request

from app import app
from filings import (
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    role_required, state_code, today_in_india,
)
from models import (
    Business, NicCode, RegulatoryProfile, RuleThreshold, db, now,
)
```

### See it work before you push

- With the API helpers pasted:

```bash
bapi /onboarding/business
bapi /onboarding/states
```

You should see something like (shortened):

```text
{
  "business": {
    "accounts_audited_other_law": false,
    "address": "12 Demo Road, Maharashtra",
    "annual_turnover": "4500000.00",
    "cin_llpin": null,
    "deducts_tds": false,
    "description": "Fictional business for the CA Helper demo",
    "entity_type": "proprietorship",
    "gst_composition": false,
    "gst_qrmp": false,
    "gst_registered": true,
    "gstin": "27DMAPA1000Z1ZY",
    "id": "3d32b668-d325-4811-8143-5b17d827be85",
    "investment_amount": "800000.00",
    "legal_name": "Asha Traders",
...
```

### Commit message

`feat(onboarding): register and edit the business API`

## 19 Onboarding form rules and labels

**Person 1** · **day 6** · **209 lines** · branch `p1/19-onboarding-form-rules` · start in the morning

### What this PR builds

- The business labels (entity types, MSME tiers, GST schemes, ITR forms), `formatRupees()`, the GSTIN check in the browser, and the registration form's schema and values; `Options` and `Choice` in `shared.jsx`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/components/shared.jsx` | 245-268 | Options, Choice | 25 |
| `frontend/src/lib.js` | 76-106, 166-180, 253-290 | ENTITY_TYPE_LABELS, MSME_TIER_LABELS, GST_SCHEME_LABELS, ITR_FORM_LABELS, formatRupees, CHARACTERS, gstinCheckCharacter, gstinError | 84 |
| `frontend/src/pages/business/OnboardingPage.jsx` (new file) | 52, 104-197 | top of file, AMOUNT, GSTIN_FORMAT, COMPANY_TYPES, makeSchema, EMPTY_FORM, formValues | 100 |
| **Total** | | | **209** |

### Top of the files after this PR

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useState } from "react";

import { errorMessage } from "@/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  cn,
  label,
} from "@/lib";
```

`frontend/src/pages/business/OnboardingPage.jsx`

```js
import { z } from "zod";

import {
  gstinError,
} from "@/lib";
```

### See it work before you push

- Try the new labels and the GSTIN check in the frontend container:

```bash
docker compose exec frontend node --input-type=module -e "
import { gstinError, label, ENTITY_TYPE_LABELS, formatRupees } from './src/lib.js';
console.log(label(ENTITY_TYPE_LABELS, 'llp'), formatRupees(4500000));
console.log(gstinError('27AAPFU0939F1ZV', 'AAPFU0939F', 'Maharashtra', '27'));
console.log(gstinError('27AAPFU0939F1ZX', 'AAPFU0939F', 'Maharashtra', '27'));
"
```

You should see something like (shortened):

```text
LLP ₹45,00,000
null
This GSTIN is not valid: its last character does not match. Check for a typo.
```

### Commit message

`feat(onboarding): form rules and labels`

## 21 Business registration page

**Person 1** · **day 7** · **277 lines** · branch `p1/21-business-registration-page` · **wait for #20 today**

### What this PR builds

- The Business profile page with the registration form (business details, PAN, phone, turnover, investment, address, audit question, GST, TDS; fields appear only when they apply). 'Business profile' in the sidebar.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/business/OnboardingPage.jsx` | 53-81, 92-103, 198-263, 265-402 | part of OnboardingPage, OCR_CLASS, part of BusinessForm | 274 |
| `frontend/src/routes.jsx` | 47, 98 | part of NAV, part of appRoutes | 3 |
| **Total** | | | **277** |

### Top of the files after this PR

`frontend/src/pages/business/OnboardingPage.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import {
  errorMessage,
  FILINGS_KEY,
  MY_BUSINESS_KEY,
  registerBusiness,
  updateBusiness,
  useGstStates,
  useMyBusiness,
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
} from "@/components/shared";
import {
  Button,
  Select,
} from "@/components/ui";
import {
  ENTITY_TYPE_LABELS,
  gstinError,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
```

### See it work before you push

- Log in with your test account. The sidebar has **Business profile**: the registration form. Register your test business (details in 'Your test account' at the top) with **Register business**.
- The profile view comes in the next PR; check it was saved:

```bash
tapi /onboarding/business
```

You should see something like (shortened):

```text
{
  "business": {
    "accounts_audited_other_law": false,
    "address": "1 Test Road, Pune",
    "annual_turnover": "4000000.00",
    "cin_llpin": null,
    "deducts_tds": false,
    "description": "We sell test goods",
    "entity_type": "proprietorship",
    "gst_composition": false,
    "gst_qrmp": true,
    "gst_registered": true,
    "gstin": "27ABCDE1234F1Z0",
    "id": "ae520a03-4ee0-4bc2-b0dd-4927e6a6fde4",
    "investment_amount": "500000.00",
    "legal_name": "Test Traders",
...
```

### Commit message

`feat(onboarding): business registration page`

## 26 Business profile view and what changed

**Person 1** · **day 8** · **150 lines** · branch `p1/26-business-profile-view` · start in the morning

### What this PR builds

- After registering: the profile with its reasons, warnings and Edit; after an edit, 'What changed'.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/business/OnboardingPage.jsx` | 82-91, 462-542, 544-591 | part of OnboardingPage, yesNo, LINES, GST_CHIPS, summaryChips, WARNING, part of ProfileView, plural ... | 150 |
| **Total** | | | **150** |

### Top of the files after this PR

`frontend/src/pages/business/OnboardingPage.jsx`

```js
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
  updateBusiness,
  useGstStates,
  useMyBusiness,
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
```

### See it work before you push

- Log in with your test account and open **Business profile**: the profile with its reasons. Press **Edit**, change the turnover, save: **What changed** lists the changes.

### Commit message

`feat(onboarding): profile view and what changed`

---

# Fill the form by OCR and the NIC code

**Person 2** · PRs #22, #37 · **365 lines**

Reading a GST certificate or PAN card on our own server to fill the form, and the official NIC activity code.

## 22 Fill the form from a GST certificate or PAN card (local OCR)

**Person 2** · **day 7** · **220 lines** · branch `p2/22-fill-the-form-from-a-gst` · **wait for #21 today**

### What this PR builds

- `ocr.py` part 1: the text of a PDF or photo (PyMuPDF + Tesseract, never sent anywhere) and the registration values in it; `POST /onboarding/autofill`; 'Fill in from a document' on the form (filled fields turn purple).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/helpers.py` | 202-223 | FILE_STARTS, read_upload | 22 |
| `backend/ocr.py` (new file) | 1-5, 14-65, 108-110, 125-138, 219-252 | top of file, STATES_FILE, GST_STATES, MAX_PAGES, MIN_PAGE_TEXT, RENDER_DPI, TESSERACT_TIMEOUT_SECONDS, _read_picture ... | 115 |
| `backend/routes_business.py` | 281-294 | autofill | 15 |
| `frontend/src/api.js` | 247-251 | readRegistrationDocument | 5 |
| `frontend/src/pages/business/OnboardingPage.jsx` | 264, 403-461 | part of BusinessForm, FILLABLE, FillFromDocument | 63 |
| **Total** | | | **220** |

### Top of the files after this PR

`backend/ocr.py`

```python
# Reading documents on our own server (never sent anywhere): the text of a PDF or photo
# (PyMuPDF + Tesseract) and the facts in it (acknowledgement number, date, form, period,
# document type, and the values to fill the registration form). A file that cannot be read
# raises ValueError with a message that says why.

import json
import re
import shutil
import subprocess
from pathlib import Path

import pymupdf
```

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from flask import jsonify, request

import ocr
from app import app
from filings import (
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, NicCode, RegulatoryProfile, RuleThreshold, db, now,
)
```

`frontend/src/pages/business/OnboardingPage.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import {
  errorMessage,
  FILINGS_KEY,
  MY_BUSINESS_KEY,
  readRegistrationDocument,
  registerBusiness,
  updateBusiness,
  useGstStates,
  useMyBusiness,
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
  Button,
  Label,
  Select,
} from "@/components/ui";
import {
  ENTITY_TYPE_LABELS,
  gstinError,
} from "@/lib";
```

### See it work before you push

- Read the registration values from the text of a GST certificate:

```bash
docker compose exec backend python -c "
import ocr
print(ocr.read_registration('Legal Name of Business ASHA TRADERS Registration Number 27AAPFU0939F1ZV Constitution of Business Proprietorship Address Pune Maharashtra'))
"
```

You should see something like (shortened):

```text
{'gstin': '27AAPFU0939F1ZV', 'pan': 'AAPFU0939F', 'state': 'Maharashtra', 'legal_name': 'of Business ASHA TRAD ...
```

### Commit message

`feat(onboarding): fill the form from a GST certificate or PAN card`

## 37 NIC activity code: search and save

**Person 2** · **day 11** · **145 lines** · branch `p2/37-nic-activity-code-search` · start in the morning

### What this PR builds

- Searching the official NIC 2008 codes and saving the business's code; `seed.py` loads `nic_2008.csv`; the NIC card on the profile.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_business.py` | 253-280 | search_nic_codes, set_nic_code | 28 |
| `backend/seed.py` | 206-215 | part of seed | 11 |
| `content/reference/nic_2008.csv` (new file) | all | the official NIC list: copy it | not counted |
| `frontend/src/api.js` | 230-241 | useNicSearch, saveNicCode | 12 |
| `frontend/src/pages/business/OnboardingPage.jsx` | 543, 592-681 | part of ProfileView, NicCodeCard | 94 |
| **Total** | | | **145** |

### Top of the files after this PR

`backend/seed.py`

```python
# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in the shared Neon database.

import csv
import sys
from datetime import date
from decimal import Decimal

from app import app
from filings import sync_filings
from helpers import REPO, today_in_india
from models import CatalogService, NicCode, ObligationTemplate, RegulatoryProfile, RuleThreshold, db
```

`frontend/src/pages/business/OnboardingPage.jsx`

```js
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
```

### See it work before you push

- Load the NIC codes (`seed.py` now reads `nic_2008.csv`) and search them:

```bash
docker compose exec backend python seed.py
bapi "/onboarding/nic-codes?q=bread"
```

You should see something like (shortened):

```text
Seeded: service catalog, rule thresholds, obligation templates, penalty rules, NIC codes, filings synced to th ...
[
  {
    "code": "10617",
    "description": "Manufacture of flour mixes and prepared blended flour and dough for bread, cakes, biscuits ...
  },
  {
    "code": "10711",
    "description": "Manufacture of bread"
  }
]
  [HTTP 200]
```

### Commit message

`feat(onboarding): NIC activity code search`

---

# Compliance calendar, dashboard and filing page

**Person 3** · PRs #24, #32, #33, #35, #39 · **811 lines**

The filings list, the calendar, the dashboard, and each filing's page with its checklist and guide.

## 24 Filing labels, dates, status badges and the filings list API

**Person 3** · **day 8** · **204 lines** · branch `p3/24-filing-labels-dates-status` · start in the morning

### What this PR builds

- Form and status labels, dates and days left in `lib.js`; `StatusBadge`, `RegisterFirst`, `Table`, `Row`, `PageTitle`, `BackLink`; `GET /compliance/items`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_business.py` | 334-344 | list_filings | 12 |
| `frontend/src/api.js` | 261-265 | useFilings | 5 |
| `frontend/src/components/shared.jsx` | 97-108, 151-204, 307-327 | PageTitle, BackLink, RegisterFirst, Table, Row, COLOURS, StatusBadge | 91 |
| `frontend/src/lib.js` | 29-39, 107-131, 181-194, 207-252 | FORM_LABELS, RENAMED_FORMS, filingFormLabel, COMPLIANCE_STATUS_LABELS, formatDate, MILLISECONDS_PER_MINUTE, MILLISECONDS_PER_DAY, todayIso ... | 96 |
| **Total** | | | **204** |

### Top of the files after this PR

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from flask import jsonify, request

import ocr
from app import app
from filings import (
    filing_to_dict,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, NicCode, RegulatoryProfile, RuleThreshold, db, now,
)
```

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  cn,
  COMPLIANCE_STATUS_LABELS,
  label,
} from "@/lib";
```

### See it work before you push


```bash
bapi /compliance/items
```

You should see something like (shortened):

```text
[
  {
    "acknowledgement_no": "AA0000150526DEMO",
    "due_date": "2026-05-11",
    "filed_at": "2026-05-15T05:30:00+00:00",
    "filing_path": "self",
    "form_code": "gstr_1",
    "fy": "2026-27",
    "id": "ba978a27-2f77-43f4-8fba-02dae4ee49fd",
    "period_end": "2026-04-30",
    "period_label": "Apr 2026",
    "period_start": "2026-04-01",
    "status": "filed"
  },
  {
    "acknowledgement_no": "AA0001180526DEMO",
...
```

### Commit message

`feat(filings): filing labels, status badges and the filings list API`

## 32 Compliance calendar page

**Person 3** · **day 10** · **159 lines** · branch `p3/32-compliance-calendar-page` · start in the morning

### What this PR builds

- The calendar (/business/compliance): this year's filings, overdue first, then by month; Form and Status chips.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/business/CalendarPage.jsx` (new file) | all | top of file, FORM_FILTERS, DONE, STATUS_FILTERS, CompliancePage, Chips, FilingSections, FilingTable | 156 |
| `frontend/src/routes.jsx` | 48, 99 | part of NAV, part of appRoutes | 3 |
| **Total** | | | **159** |

### Top of the files after this PR

`frontend/src/pages/business/CalendarPage.jsx`

```js
import { useState } from "react";
import { Link } from "react-router";

import { useFilings } from "@/api";
import { QueryStatus, RegisterFirst, Row, StatusBadge, Table } from "@/components/shared";
import { linkClass } from "@/components/ui";
import { daysLeftText, daysUntil, filingFormLabel, formatDate, monthLabel } from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
```

### Merging

Merged after #30 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- Log in as `business@demo.local`: the sidebar has **Compliance calendar**: this year's filings with the Form and Status chips (a filing's own page comes in PR #39).

### Commit message

`feat(filings): compliance calendar page`

## 33 Business dashboard

**Person 3** · **day 10** · **112 lines** · branch `p3/33-business-dashboard` · start in the morning

### What this PR builds

- /business: welcome and four cards (next deadline, due this month, overdue, with a CA); `GET /compliance/dashboard`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_business.py` | 309-333 | dashboard | 25 |
| `frontend/src/api.js` | 255-260 | DASHBOARD_KEY, useComplianceDashboard | 6 |
| `frontend/src/components/shared.jsx` | 109-137 | Welcome, NumberCard | 29 |
| `frontend/src/pages/business/DashboardPage.jsx` (new file) | 12-18, 20-25, 28-57 | top of file, DONE, part of BusinessDashboardPage, Numbers | 49 |
| `frontend/src/routes.jsx` | 46, 97 | part of NAV, part of appRoutes | 3 |
| **Total** | | | **112** |

### Top of the files after this PR

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, filing_to_dict,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, NicCode, RegulatoryProfile, RuleThreshold, db, now,
)
```

`frontend/src/pages/business/DashboardPage.jsx`

```js
import {
  useComplianceDashboard,
  useFilings,
} from "@/api";
import { NumberCard, RegisterFirst, Welcome } from "@/components/shared";
import { daysLeftText, filingFormLabel, formatDate } from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
```

### Merging

Merged after #30, #32 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- Log in as `business@demo.local`: /business shows the welcome and the four cards (next deadline, due this month, overdue, with a CA).

### Commit message

`feat(dashboard): business dashboard numbers`

## 35 Filing page API: checklist, guide texts, ticks

**Person 3** · **day 11** · **130 lines** · branch `p3/35-filing-page-api-checklist` · start in the morning

### What this PR builds

- `filings.py` part 2: each form's checklist and texts, ticks, the status from the ticks, the filing page data; `GET /compliance/items/<id>` and `POST .../checklist`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/filings.py` | 172-238, 243-251 | checklist, form_content, checklist_with_ticks, missing_documents, refresh_status, set_tick, part of filing_page | 79 |
| `backend/routes_business.py` | 295-308, 345-351, 369-384 | find_filing, get_filing, tick_checklist | 37 |
| `frontend/src/api.js` | 266-275, 281-284 | filingKey, useFiling, tickChecklist | 14 |
| **Total** | | | **130** |

### Top of the files after this PR

`backend/filings.py`

```python
# Everything about filings that several route files need: periods and due dates, making a
# business's calendar, the checklists and texts of each form, the filing page, and checking
# an uploaded acknowledgement. The legal dates come from obligation_templates (seed.py).

import calendar
import re
from datetime import date

import yaml

from helpers import REPO, iso, today_in_india
from models import (
    ChecklistTick, ComplianceItem, ComplianceItemDocument, DocumentRequest, Engagement,
    EngagementItem, ObligationTemplate, ReminderLog, db,
)
```

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, checklist, filing_page, filing_to_dict, set_tick,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, NicCode, RegulatoryProfile, RuleThreshold, db, now,
)
```

### See it work before you push

- Take the `id` of one of your test business's filings, load its page and tick a checklist entry:

```bash
tapi /compliance/items
ID=paste-an-id-here    # an "id" from the list above
tapi /compliance/items/$ID
KEY=paste-a-key    # the "key" of an entry in its "checklist" above
tapi /compliance/items/$ID/checklist -H "$J" -d '{"key":"'$KEY'","ticked":true}'
```

You should see something like (shortened):

```text
[
  {
    "acknowledgement_no": null,
    "due_date": "2026-07-13",
    "filed_at": null,
    "filing_path": null,
    "form_code": "gstr_1",
    "fy": "2026-27",
    "id": "c3b80bb2-8bfe-4dee-a10a-dd102fcd77b8",
    "period_end": "2026-06-30",
    "period_label": "Q1 2026-27",
    "period_start": "2026-04-01",
    "status": "overdue"
  },
  {
    "acknowledgement_no": null,
...
```

### Commit message

`feat(filings): filing page API with checklist ticks`

## 39 Filing page: header, checklist and the form guide

**Person 3** · **day 12** · **206 lines** · branch `p3/39-filing-page-header-checklist` · start in the morning

### What this PR builds

- The filing page: name, period, status, due date; the checklist with ticks; the form's explanation and instructions (Markdown).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/components/shared.jsx` | 376-408 | STYLES, Markdown | 34 |
| `frontend/src/pages/business/FilingPage.jsx` (new file) | 57-84, 90-113, 357-360, 362-364, 367-375, 393-418, 420-421, 427-431, 693-734 | top of file, OPEN_FOR_BUSINESS, FILED, OPEN_ENGAGEMENTS, FILE_TYPES, part of FilingPage, Header, part of Checklist ... | 170 |
| `frontend/src/routes.jsx` | 100 | part of appRoutes | 2 |
| **Total** | | | **206** |

### Top of the files after this PR

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  cn,
  COMPLIANCE_STATUS_LABELS,
  label,
} from "@/lib";
```

`frontend/src/pages/business/FilingPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import {
  DASHBOARD_KEY,
  filingKey,
  FILINGS_KEY,
  tickChecklist,
  useFiling,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Markdown,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui";
import {
  daysLeftText,
  filingFormLabel,
  formatDate,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaProfilePage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- Log in with your test account, open **Compliance calendar** and click a filing: its page with the checklist (tick one: the status changes) and the form's explanation and instructions.

### Commit message

`feat(filings): filing page with checklist and guide`

---

# Document vault and proof of filing

**Person 2** · PRs #25, #27, #34, #42, #51 · **1000 lines**

Files stored encrypted and read by OCR, the vault, linking files to checklist entries, and marking a filing filed with its acknowledgement.

## 25 Reading uploaded files: stored encrypted, facts read by OCR

**Person 2** · **day 8** · **183 lines** · branch `p2/25-reading-uploaded-files` · start in the morning

### What this PR builds

- Files stored encrypted in the database; OCR part 2: an acknowledgement's number, date, form and period, and a document's type.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/helpers.py` | 57-64, 224-256 | as_uuid, save_document, send_document, remove_document | 46 |
| `backend/ocr.py` | 66-107, 111-124, 139-218 | MONTHS, FORM_PATTERNS, ACK_NUMBER, BARE_ARN, DAY_MONTH_YEAR, YEAR_MONTH_DAY, FINANCIAL_YEAR, QUARTER ... | 137 |
| **Total** | | | **183** |

### Top of the files after this PR

`backend/helpers.py`

```python
# Small helpers the route files share: errors, the logged-in user, money, passwords,
# email, notifications, GSTIN checks and storing uploaded files.

import hashlib
import io
import json
import smtplib
import uuid
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from flask import current_app, jsonify, render_template, request, send_file
from flask_jwt_extended import get_current_user, jwt_required

import ocr
from models import Business, ComplianceItemDocument, Document, DocumentRequest, Notification, db
```

`backend/ocr.py`

```python
# Reading documents on our own server (never sent anywhere): the text of a PDF or photo
# (PyMuPDF + Tesseract) and the facts in it (acknowledgement number, date, form, period,
# document type, and the values to fill the registration form). A file that cannot be read
# raises ValueError with a message that says why.

import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pymupdf
```

### See it work before you push

- Guess a document's type and read an acknowledgement's facts from text:

```bash
docker compose exec backend python -c "
from datetime import date
import ocr
print(ocr.guess_document_type('INCOME TAX DEPARTMENT Permanent Account Number Card ABCDE1234F'))
print(ocr.read_proof_fields('GSTR-3B Acknowledgement ARN AA270726123456X Date 18/07/2026 Return Period Jun 2026', date(2026, 10, 12)))
"
```

You should see something like (shortened):

```text
pan_card
{'acknowledgement_no': 'AA270726123456X', 'filing_date': '2026-07-18', 'form_codes': ['gstr_3b'], 'months': [6 ...
```

### Commit message

`feat(documents): encrypted file storage and OCR facts`

## 27 Document vault API: upload, list, open, delete

**Person 2** · **day 9** · **190 lines** · branch `p2/27-document-vault-api-upload` · start in the morning

### What this PR builds

- Upload with a type (with a warning when OCR thinks it is another type), list, open, delete (not the proof of a filed filing).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 73 | part of http_error | 1 |
| `backend/routes_documents.py` (new file) | 1-4, 17-36, 72-92, 94-97, 106-137, 146-171 | top of file, DOCUMENT_TYPES, document_to_dict, my_document, part of upload_document, list_documents, part of open_document, delete_document | 119 |
| `frontend/src/api.js` | 83-92, 311-344, 358-368 | apiDownload, UPLOAD_TYPES, DOCUMENTS_KEY, useDocuments, uploadDocument, deleteDocument, downloadDocument | 55 |
| `frontend/src/lib.js` | 141-155 | DOCUMENT_TYPE_LABELS | 15 |
| **Total** | | | **190** |

### Top of the files after this PR

`backend/routes_documents.py`

```python
# The document vault: upload, list, open and delete files, link them to filings (ticking the
# checklist), and answer a CA's document request with a file. A filed filing's documents are
# fixed: they are the proof of what was filed. Admins never open documents.

from flask import jsonify, request

from app import app
from filings import DONE, filing_name
from helpers import (
    as_uuid, current_user, error, iso, my_business, page_of, read_upload,
    remove_document, role_required, save_document, send_document,
)
from models import (
    ComplianceItem, ComplianceItemDocument, Document,
    db,
)
```

### See it work before you push

- Upload a small PDF to your test business's vault, then list the vault:

```bash
printf '%%PDF-1.4\n%%test\n' > /tmp/test.pdf
tapi /documents -F doc_type=other -F "file=@/tmp/test.pdf;type=application/pdf"
tapi "/documents?page=1"
```

You should see something like (shortened):

```text
{
  "created_at": "2026-10-13T06:40:10.350413+00:00",
  "doc_type": "other",
  "fy": null,
  "id": "b7074934-f1c2-4586-b181-f9089fe15b00",
  "links": [],
  "mime_type": "application/pdf",
  "ocr_status": "failed",
  "original_filename": "test.pdf",
  "period_label": null,
  "size_bytes": 15,
  "type_warning": null
}
  [HTTP 201]
{
  "items": [
...
```

### Commit message

`feat(documents): document vault API`

## 34 Document vault page

**Person 2** · **day 10** · **180 lines** · branch `p2/34-document-vault-page` · start in the morning

### What this PR builds

- The Document vault page: upload, list, open, delete.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/components/shared.jsx` | 58-64 | useObjectUrl | 7 |
| `frontend/src/pages/business/DocumentsPage.jsx` (new file) | all | top of file, PAGE_SIZE, DocumentsPage, UploadCard, DocumentTable, DocumentRow | 170 |
| `frontend/src/routes.jsx` | 49, 101 | part of NAV, part of appRoutes | 3 |
| **Total** | | | **180** |

### Top of the files after this PR

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  cn,
  COMPLIANCE_STATUS_LABELS,
  label,
} from "@/lib";
```

`frontend/src/pages/business/DocumentsPage.jsx`

```js
import { useState } from "react";

import {
  deleteDocument,
  DOCUMENTS_KEY,
  downloadDocument,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useRefresh,
} from "@/api";
import {
  ErrorText,
  Field,
  Options,
  PageTitle,
  Pager,
  QueryStatus,
  Row,
  Section,
  Table,
  useAction,
} from "@/components/shared";
import { Button, Input, Select } from "@/components/ui";
import { DOCUMENT_TYPE_LABELS, formatDateTime, label } from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
```

### Merging

Merged after #30, #32, #33 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- Log in with your test account: **Document vault** in the sidebar. Upload a file with a type (a PAN card uploaded as 'Other' shows a warning), open it, delete it.

### Commit message

`feat(documents): document vault page`

## 42 Link vault files to checklist entries

**Person 2** · **day 13** · **275 lines** · branch `p2/42-link-vault-files` · start in the morning

### What this PR builds

- Linking files to a filing's checklist entries (linking ticks the entry); on the filing page each entry shows its files: add from the vault or upload, open, remove.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_documents.py` | 37-71, 93, 98-105, 172-202 | documents_by_filing, link_to_filing, part of upload_document, link_document, unlink_document | 75 |
| `frontend/src/api.js` | 345-357 | linkDocument, unlinkDocument | 13 |
| `frontend/src/pages/business/FilingPage.jsx` | 361, 365-366, 376-392, 419, 422-426, 432-580 | part of Checklist, linksByKey, EntryDocuments, VaultSelect, AddDocument | 187 |
| **Total** | | | **275** |

### Top of the files after this PR

`backend/routes_documents.py`

```python
# The document vault: upload, list, open and delete files, link them to filings (ticking the
# checklist), and answer a CA's document request with a file. A filed filing's documents are
# fixed: they are the proof of what was filed. Admins never open documents.

from flask import jsonify, request

from app import app
from filings import DONE, checklist, filing_name, set_tick
from helpers import (
    as_uuid, current_user, error, iso, my_business, page_of, read_upload,
    remove_document, role_required, save_document, send_document,
)
from models import (
    ComplianceItem, ComplianceItemDocument, Document,
    db,
)
```

`frontend/src/pages/business/FilingPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import {
  DASHBOARD_KEY,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  filingKey,
  FILINGS_KEY,
  linkDocument,
  tickChecklist,
  unlinkDocument,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useFiling,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  Markdown,
  Options,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, Input, Select } from "@/components/ui";
import {
  daysLeftText,
  DOCUMENT_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  label,
} from "@/lib";
```

### See it work before you push

- Log in with your test account, open a filing: each checklist entry has its files. Add one from the vault or upload a new one: the entry is ticked. Remove it again.

### Commit message

`feat(documents): link vault files to checklist entries`

## 51 Mark filed: acknowledgement check and API

**Person 2** · **day 16** · **172 lines** · branch `p2/51-mark-filed-acknowledgement` · start in the morning

### What this PR builds

- Choose how a filing is done (myself / with a CA); mark filed with the acknowledgement number and file (checked by OCR: 'filed_verified'); undo; download the acknowledgement.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/filings.py` | 239-242, 252-326 | part of filing_page, record_filed, period_shown, verify_acknowledgement | 80 |
| `backend/routes_business.py` | 352-368, 385-434 | choose_path, mark_filed, unmark_filed, download_acknowledgement | 67 |
| `frontend/src/api.js` | 276-280, 285-304 | chooseFilingPath, markFiled, unmarkFiled, useAcknowledgementFile | 25 |
| **Total** | | | **172** |

### Top of the files after this PR

`backend/filings.py`

```python
# Everything about filings that several route files need: periods and due dates, making a
# business's calendar, the checklists and texts of each form, the filing page, and checking
# an uploaded acknowledgement. The legal dates come from obligation_templates (seed.py).

import calendar
import re
from datetime import date

import yaml
from flask import request

from helpers import REPO, error, iso, read_upload, save_document, today_in_india
from models import (
    ChecklistTick, ComplianceItem, ComplianceItemDocument, Document, DocumentRequest, Engagement,
    EngagementItem, ObligationTemplate, ReminderLog, db, now,
)
```

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re
from decimal import Decimal

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, NOT_STARTED, checklist, filing_page, filing_to_dict, record_filed, refresh_status, set_tick,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, india_date, iso, money, my_business, read_amount,
    read_upload, remove_document, role_required, send_document, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, Document, NicCode, PenaltyRule, RegulatoryProfile, RuleThreshold, db, now,
)
```

### See it work before you push

- Mark one of your test business's filings as filed, then undo it:

```bash
tapi /compliance/items
ID=paste-an-id-here    # an "id" from the list above (not filed, not with a CA)
tapi /compliance/items/$ID/mark-filed -X POST -F acknowledgement_no=TEST123
tapi /compliance/items/$ID/unmark-filed -X POST
```

You should see something like (shortened):

```text
[
  {
    "acknowledgement_no": null,
    "due_date": "2026-07-13",
    "filed_at": null,
    "filing_path": null,
    "form_code": "gstr_1",
    "fy": "2026-27",
    "id": "c3b80bb2-8bfe-4dee-a10a-dd102fcd77b8",
    "period_end": "2026-06-30",
    "period_label": "Q1 2026-27",
    "period_start": "2026-04-01",
    "status": "overdue"
  },
  {
    "acknowledgement_no": null,
...
```

### Commit message

`feat(filings): mark filed with acknowledgement check`

---

# Penalties and peer insights

**Person 2** · PRs #38, #48 · **301 lines**

Late fee and interest rules, the penalty boxes, and how similar businesses file.

## 38 Penalties: late fee rules and the estimate API

**Person 2** · **day 11** · **138 lines** · branch `p2/38-penalties-late-fee-rules` · **wait for #35 today**

### What this PR builds

- Late fee and interest rules in `seed.py`; the late fees of overdue filings and one filing's estimate.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_business.py` | 470-547 | estimate, penalty_exposure, penalty_estimate | 79 |
| `backend/seed.py` | 133-174, 201-205 | GST_LATE_FEE, GST_INTEREST, PENALTY_RULES, part of seed | 47 |
| `frontend/src/api.js` | 382-393 | usePenaltyEstimate, usePenaltyExposure | 12 |
| **Total** | | | **138** |

### Top of the files after this PR

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re
from decimal import Decimal

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, checklist, filing_page, filing_to_dict, set_tick,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, NicCode, PenaltyRule, RegulatoryProfile, RuleThreshold, db, now,
)
```

`backend/seed.py`

```python
# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in the shared Neon database.

import sys
from datetime import date
from decimal import Decimal

from app import app
from filings import sync_filings
from helpers import today_in_india
from models import CatalogService, ObligationTemplate, PenaltyRule, RegulatoryProfile, RuleThreshold, db
```

### Merging

Merged after #37 today. When you pull `main` before merging, git may show a conflict in `backend/seed.py`: keep both sides (yours and theirs).

### See it work before you push

- Load the late fee rules (`seed.py` now has them), then ask for the demo business's late fees:

```bash
docker compose exec backend python seed.py
bapi /alerts/penalties
```

You should see something like (shortened):

```text
Seeded: service catalog, rule thresholds, obligation templates, penalty rules, NIC codes, filings synced to th ...
{
  "estimated_count": 2,
  "items": [
    {
      "compliance_item_id": "d64abd2e-1897-44ca-9ce7-961eb10a59be",
      "days_late": 23,
      "due_date": "2026-09-20",
      "form_code": "gstr_3b",
      "interest": null,
      "label": "Estimate (rules pending verification)",
      "late_fee": "1150.00",
      "notes": [
        "Enter the tax due to estimate the interest."
      ],
      "period_label": "Aug 2026",
...
```

### Commit message

`feat(penalties): late fee rules and estimate API`

## 48 Penalty boxes and peer insights on the filing page

**Person 2** · **day 14** · **163 lines** · branch `p2/48-penalty-boxes-and-peer` · start in the morning

### What this PR builds

- What being late may cost (filing page) and the penalty exposure card (dashboard); how similar businesses file a form (peer insights).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_business.py` | 435-469 | peer_insights | 35 |
| `frontend/src/api.js` | 305-310 | usePeerInsights | 6 |
| `frontend/src/pages/business/DashboardPage.jsx` | 26, 58-70 | part of BusinessDashboardPage, PenaltyExposure | 15 |
| `frontend/src/pages/business/FilingPage.jsx` | 85-86, 88, 114-166, 581-624 | part of FilingPage, Penalty, PeerInsights, PeerPath | 107 |
| **Total** | | | **163** |

### Top of the files after this PR

`backend/routes_business.py`

```python
# The business side: registering the business, its regulatory profile (which filings
# apply), the NIC code, the filing calendar and filing page, peer insights and penalties.
# Legal limits come from the rule_thresholds table (seed.py), never from this file.

import re
from decimal import Decimal

from flask import jsonify, request

import ocr
from app import app
from filings import (
    DONE, checklist, filing_page, filing_to_dict, set_tick,
    sync_filings,
)
from helpers import (
    GST_STATES, current_user, error, format_inr, gstin_error, india_date, iso, money, my_business, read_amount,
    read_upload, role_required, state_code, today_in_india,
)
from models import (
    Business, ComplianceItem, NicCode, PenaltyRule, RegulatoryProfile, RuleThreshold, db, now,
)
```

`frontend/src/pages/business/DashboardPage.jsx`

```js
import {
  useComplianceDashboard,
  useFilings,
  usePenaltyExposure,
} from "@/api";
import { NumberCard, RegisterFirst, Welcome } from "@/components/shared";
import { daysLeftText, filingFormLabel, formatDate, formatRupees } from "@/lib";
```

`frontend/src/pages/business/FilingPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import {
  DASHBOARD_KEY,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  filingKey,
  FILINGS_KEY,
  linkDocument,
  tickChecklist,
  unlinkDocument,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useFiling,
  usePeerInsights,
  usePenaltyEstimate,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  FormField,
  Markdown,
  Options,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, Input, Select } from "@/components/ui";
import {
  daysLeftText,
  daysUntil,
  DOCUMENT_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

### See it work before you push

- Log in as `business@demo.local`: the dashboard has the **Penalty exposure** card; an overdue filing's page shows what being late may cost; an upcoming GSTR-3B shows **How similar businesses file it**.

### Commit message

`feat(filings): penalty boxes and peer insights`

---

# CA profile and admin verification

**Person 1** · PRs #28, #30, #36, #40, #43 · **1055 lines**

A CA's profile and certificate, and the admin pages that verify CAs.

## 28 CA profile API and certificate upload

**Person 1** · **day 9** · **172 lines** · branch `p1/28-ca-profile-api` · start in the morning

### What this PR builds

- `GET/PUT /marketplace/ca-profile` (numbers, city, languages, specializations, capacity, experience, about; new numbers need a new check) and the Certificate of Practice upload; CA labels.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 74 | part of http_error | 1 |
| `backend/routes_marketplace.py` (new file) | 1-6, 21-26, 40-52, 110-183 | top of file, LANGUAGES, SPECIALIZATIONS, profile_to_dict, my_profile, get_ca_profile, save_ca_profile, upload_certificate | 112 |
| `frontend/src/api.js` | 394-413 | CA_PROFILE_KEY, useCaProfile, saveCaProfile, uploadCertificate | 20 |
| `frontend/src/lib.js` | 22-28, 40-66, 161-165 | CA_VERIFICATION_STATUS_LABELS, CA_SPECIALIZATION_LABELS, CA_LANGUAGE_LABELS, labelList | 39 |
| **Total** | | | **172** |

### Top of the files after this PR

`backend/routes_marketplace.py`

```python
# The CA marketplace: a CA's profile and prices, Find a CA, requests between a business and a
# CA, and ratings. A request is "requested" until the CA accepts (at their listed, fixed
# prices) or declines it, or the business withdraws it ("cancelled"); it never expires.
# Accepted work is "active" until it is "completed". A CA is listed only once an admin has
# verified their profile; changing the membership or CoP number needs a new check.

import re

from flask import jsonify, request

from app import app
from helpers import (
    current_user, error, iso, read_upload, remove_document,
    role_required, save_document,
)
from models import (
    CaProfile,
    db,
)
```

### Merging

Merged after #27 today. When you pull `main` before merging, git may show a conflict in `backend/app.py`: keep both sides (yours and theirs).

### See it work before you push


```bash
capi /marketplace/ca-profile
```

You should see something like (shortened):

```text
{
  "about": "Demo practice for small traders and freelancers in Mumbai.",
  "capacity": 25,
  "city": "Mumbai",
  "cop_number": "COP-900000",
  "has_certificate": false,
  "id": "362fc34d-ed26-4d7e-88c7-94d73fbfd582",
  "languages": [
    "english",
    "hindi",
    "marathi"
  ],
  "membership_no": "900000",
  "rejection_reason": null,
  "specializations": [
    "itr",
...
```

### Commit message

`feat(marketplace): CA profile API and certificate upload`

## 30 CA profile page

**Person 1** · **day 10** · **245 lines** · branch `p1/30-ca-profile-page` · start in the morning

### What this PR builds

- The CA's My profile page: verification status and the profile form.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/ca/ProfilePage.jsx` (new file) | 55-117, 119, 121-155, 238-343 | top of file, profileSchema, EMPTY_FORM, formValues, STATUS_COLORS, STATUS_TEXT, IDENTITY_FIELDS, part of CaProfilePage ... | 242 |
| `frontend/src/routes.jsx` | 56, 110 | part of NAV, part of appRoutes | 3 |
| **Total** | | | **245** |

### Top of the files after this PR

`frontend/src/pages/ca/ProfilePage.jsx`

```js
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import {
  ApiRequestError,
  CA_PROFILE_KEY,
  errorMessage,
  saveCaProfile,
  useCaProfile,
} from "@/api";
import {
  ErrorText,
  field,
  Field,
  FormField,
  Notice,
  QueryStatus,
  Section,
} from "@/components/shared";
import {
  Badge,
  Button,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  Textarea,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  label,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaProfilePage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- Log in as `ca@demo.local` / `DemoCA#2026`: **My profile** shows the verification status and the profile form.

### Commit message

`feat(marketplace): CA profile page`

## 36 Admin API: stats, users, checking CAs

**Person 1** · **day 11** · **198 lines** · branch `p1/36-admin-api-stats-users` · start in the morning

### What this PR builds

- Home numbers, platform stats, all users (search, role, pages), CAs to check, one CA with the certificate, verify or reject (emails `ca_verified` / `ca_rejected`).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 69 | part of http_error | 1 |
| `backend/routes_admin.py` (new file) | all | top of file, ca_to_dict, admin_dashboard, admin_stats, admin_users, admin_cas, admin_ca, admin_ca_certificate ... | 131 |
| `backend/templates/email/ca_rejected.txt` (new file) | all |  | 10 |
| `backend/templates/email/ca_verified.txt` (new file) | all |  | 6 |
| `frontend/src/api.js` | 537-586 | ADMIN_CAS_KEY, ADMIN_STATS_KEY, useAdminDashboard, useAdminStats, useAdminUsers, useAdminCas, adminCaKey, useAdminCa ... | 50 |
| **Total** | | | **198** |

### Top of the files after this PR

`backend/routes_admin.py`

```python
# Admin pages: the numbers on the home page, every account, and checking CAs (verify or reject
# them after looking at their Certificate of Practice). Admins never open other documents.

from flask import jsonify, request

from app import app
from filings import DONE
from helpers import (
    current_user, error, india_date, iso, page_of, role_required, send_document, send_email, today_in_india,
)
from models import Business, CaProfile, ComplianceItem, Document, Engagement, User, db, now
from routes_marketplace import profile_to_dict
```

### See it work before you push


```bash
aapi /admin/stats
aapi "/admin/cas?status=pending"
```

You should see something like (shortened):

```text
{
  "businesses": 15,
  "cas_by_status": {
    "pending": 1,
    "rejected": 0,
    "verified": 5
  },
  "filings_by_status": {
    "docs_pending": 1,
    "filed": 42,
    "filed_verified": 28,
    "overdue": 4,
    "ready": 1,
    "upcoming": 143,
    "with_ca": 9
  },
...
```

### Commit message

`feat(admin): admin API`

## 40 Admin dashboard and users pages

**Person 1** · **day 12** · **224 lines** · branch `p1/40-admin-dashboard-and-users` · start in the morning

### What this PR builds

- The admin dashboard and Users & CAs pages.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/admin/AdminPages.jsx` (new file) | 60-239 | top of file, AdminDashboardPage, Counts, Filings, USER_TABS, AdminUsersPage, PendingCas, AllUsers | 216 |
| `frontend/src/routes.jsx` | 64-65, 119-120 | part of NAV, part of appRoutes | 8 |
| **Total** | | | **224** |

### Top of the files after this PR

`frontend/src/pages/admin/AdminPages.jsx`

```js
import { useState } from "react";
import { Link } from "react-router";

import {
  useAdminCas,
  useAdminDashboard,
  useAdminStats,
  useAdminUsers,
} from "@/api";
import {
  Field,
  NumberCard,
  Options,
  Pager,
  QueryStatus,
  Row,
  Table,
  Welcome,
} from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  linkClass,
  Select,
} from "@/components/ui";
import {
  COMPLIANCE_STATUS_LABELS,
  formatDateTime,
  label,
  USER_ROLE_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaProfilePage } from "@/pages/ca/ProfilePage";
```

### Merging

Merged after #39 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- Log in as `admin@demo.local` / `DemoAdmin#2026`: the dashboard numbers, and **Users & CAs** (the CAs waiting for verification, and all users with search).

### Commit message

`feat(admin): admin dashboard and users pages`

## 43 Admin: one CA's details and certificate; CA certificate upload card

**Person 1** · **day 13** · **216 lines** · branch `p1/43-admin-one-ca-s-details` · start in the morning

### What this PR builds

- The admin's CA page (details, certificate, verify / reject) and the CA's certificate upload card.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/admin/AdminPages.jsx` | 240-372 | AdminCaDetailPage, Details, Certificate, Decision | 156 |
| `frontend/src/pages/ca/ProfilePage.jsx` | 118, 156-210 | part of CaProfilePage, CertificateCard | 58 |
| `frontend/src/routes.jsx` | 121 | part of appRoutes | 2 |
| **Total** | | | **216** |

### Top of the files after this PR

`frontend/src/pages/admin/AdminPages.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  ADMIN_CAS_KEY,
  ADMIN_STATS_KEY,
  adminCaKey,
  errorMessage,
  rejectCa,
  useAdminCa,
  useAdminCas,
  useAdminDashboard,
  useAdminStats,
  useAdminUsers,
  useCertificateFile,
  useRefresh,
  verifyCa,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  Notice,
  NumberCard,
  Options,
  Pager,
  QueryStatus,
  Row,
  Section,
  Table,
  useAction,
  useObjectUrl,
  Welcome,
} from "@/components/shared";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
  Select,
  Textarea,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  COMPLIANCE_STATUS_LABELS,
  formatDateTime,
  label,
  labelList,
  USER_ROLE_LABELS,
} from "@/lib";
```

`frontend/src/pages/ca/ProfilePage.jsx`

```js
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
import {
  ErrorText,
  field,
  Field,
  FormField,
  Notice,
  PageTitle,
  QueryStatus,
  Section,
  useAction,
} from "@/components/shared";
import {
  Badge,
  Button,
  buttonClass,
  Card,
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
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- Log in as `admin@demo.local`, **Users & CAs**, open the pending CA: details, the certificate, **Verify** and **Reject**. (Don't press them on the shared database.)
- As `ca@demo.local`, **My profile** now has the certificate card.

### Commit message

`feat(admin): CA details, certificate and verification`

---

# CA marketplace

**Person 2** · PRs #31, #41, #45, #49, #53 · **798 lines**

The service catalog, a CA's fixed prices, Find a CA and a CA's page.

## 31 Service catalog and a CA's prices (API)

**Person 2** · **day 10** · **114 lines** · branch `p2/31-service-catalog-and-a-ca` · start in the morning

### What this PR builds

- The service catalog in `seed.py`; `GET /marketplace/services`; a CA's prices (`GET/PUT .../ca-services`).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 27-33, 67-80, 184-220 | SERVICE_SPECIALIZATIONS, prices_of, catalog, ca_services, list_services | 58 |
| `backend/seed.py` | 19-39, 186-194 | SERVICE_CATALOG, part of seed | 30 |
| `frontend/src/api.js` | 431-447 | useServices, CA_SERVICES_KEY, useCaServices, saveCaServices | 17 |
| `frontend/src/lib.js` | 67-75 | SERVICE_UNIT_LABELS | 9 |
| **Total** | | | **114** |

### Top of the files after this PR

`backend/routes_marketplace.py`

```python
# The CA marketplace: a CA's profile and prices, Find a CA, requests between a business and a
# CA, and ratings. A request is "requested" until the CA accepts (at their listed, fixed
# prices) or declines it, or the business withdraws it ("cancelled"); it never expires.
# Accepted work is "active" until it is "completed". A CA is listed only once an admin has
# verified their profile; changing the membership or CoP number needs a new check.

import re

from flask import jsonify, request

from app import app
from helpers import (
    as_uuid, current_user, error, iso, money, read_amount, read_upload, remove_document,
    role_required, save_document,
)
from models import (
    CaProfile, CaService, CatalogService,
    db,
)
```

`backend/seed.py`

```python
# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in the shared Neon database.

import sys
from datetime import date
from decimal import Decimal

from app import app
from filings import sync_filings
from helpers import today_in_india
from models import CatalogService, ObligationTemplate, RegulatoryProfile, RuleThreshold, db
```

### See it work before you push

- Load the service catalog (`seed.py` now has it), then:

```bash
docker compose exec backend python seed.py
capi /marketplace/services
capi /marketplace/ca-services
```

You should see something like (shortened):

```text
Seeded: service catalog, rule thresholds, obligation templates, penalty rules, NIC codes, filings synced to th ...
[
  {
    "code": "itr_presumptive",
    "description": "Income tax return for a business or profession on presumptive income.",
    "id": "f46c7b11-fa88-4481-bcfe-72eb855b40bb",
    "name": "ITR filing: presumptive income (ITR-4)",
    "specialization": "itr",
    "unit": "per_return"
  },
  {
    "code": "itr_business",
    "description": "Income tax return for a proprietor or professional with business income.",
    "id": "33633bb2-1e18-49c1-87f9-689ccca525a8",
    "name": "ITR filing: business or profession (ITR-3)",
    "specialization": "itr",
...
```

### Commit message

`feat(marketplace): service catalog and CA prices API`

## 41 CA services and prices page

**Person 2** · **day 12** · **225 lines** · branch `p2/41-ca-services-and-prices-page` · start in the morning

### What this PR builds

- Services & prices for the CA, with a warning for missing specializations.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/ca/ProfilePage.jsx` | 344-555 | MIN_PRICE, MAX_PRICE, PRICE_ERROR, CaServicesPage, startingRows, PriceMenu, SpecializationWarning, priceId ... | 223 |
| `frontend/src/routes.jsx` | 57, 111 | part of NAV, part of appRoutes | 2 |
| **Total** | | | **225** |

### Top of the files after this PR

`frontend/src/pages/ca/ProfilePage.jsx`

```js
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
  useCaProfile,
  useCaServices,
  useServices,
} from "@/api";
import {
  ErrorText,
  field,
  Field,
  FormField,
  Notice,
  PageTitle,
  QueryStatus,
  Section,
  useAction,
} from "@/components/shared";
import {
  Badge,
  Button,
  buttonClass,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
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
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### Merging

Merged after #39, #40 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- Log in as `ca@demo.local`: **Services & prices**: change a price and save.

### Commit message

`feat(marketplace): CA services and prices page`

## 45 Find a CA API and the CA's public card preview

**Person 2** · **day 14** · **130 lines** · branch `p2/45-find-a-ca-api-and-the-ca` · start in the morning

### What this PR builds

- Verified CAs with filters, pages, ratings and prices; 'Preview: how businesses see you' on the CA profile.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 34-35, 53-66, 81-93, 221-255 | FULL_MESSAGE, ratings_of, public_ca, is_full, listed_ca, list_cas | 64 |
| `frontend/src/api.js` | 414-425 | useVerifiedCas | 12 |
| `frontend/src/components/shared.jsx` | 328-348 | caFacts, SpecializationBadges | 22 |
| `frontend/src/pages/ca/ProfilePage.jsx` | 120, 211-237 | part of CaProfilePage, PreviewCard | 32 |
| **Total** | | | **130** |

### Top of the files after this PR

`backend/routes_marketplace.py`

```python
# The CA marketplace: a CA's profile and prices, Find a CA, requests between a business and a
# CA, and ratings. A request is "requested" until the CA accepts (at their listed, fixed
# prices) or declines it, or the business withdraws it ("cancelled"); it never expires.
# Accepted work is "active" until it is "completed". A CA is listed only once an admin has
# verified their profile; changing the membership or CoP number needs a new check.

import re

from flask import jsonify, request

from app import app
from helpers import (
    as_uuid, current_user, error, iso, money, read_amount, read_upload, remove_document,
    role_required, save_document,
)
from models import (
    CaProfile, CaService, CatalogService, Engagement, Rating,
    db,
)
```

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  CA_SPECIALIZATION_LABELS,
  cn,
  COMPLIANCE_STATUS_LABELS,
  label,
} from "@/lib";
```

`frontend/src/pages/ca/ProfilePage.jsx`

```js
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
```

### See it work before you push

- Log in as `ca@demo.local`: **My profile** ends with **Preview: how businesses see you**. And:

```bash
bapi /marketplace/cas
```

You should see something like (shortened):

```text
{
  "items": [
    {
      "about": "Income tax and TDS for salaried professionals and small employers.",
      "city": "Chennai",
      "full_name": "Priya Iyer",
      "id": "aa215daf-ce67-44fd-9052-d9f17c307df8",
      "languages": [
        "english",
        "tamil"
      ],
      "membership_no": "900001",
      "price": null,
      "rating_average": 5.0,
      "rating_count": 1,
      "specializations": [
...
```

### Commit message

`feat(marketplace): find a CA API and card preview`

## 49 Find a CA page: search verified CAs

**Person 2** · **day 15** · **210 lines** · branch `p2/49-find-a-ca-page-search` · start in the morning

### What this PR builds

- Find a CA: filters in the URL, CA cards, pages.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/components/shared.jsx` | 349-375 | VerifiedBadge, Stars, RatingSummary | 27 |
| `frontend/src/pages/business/FindCaPage.jsx` (new file) | 55-197 | top of file, FILTERS, MarketplacePage, CaCard | 178 |
| `frontend/src/routes.jsx` | 50, 102 | part of NAV, part of appRoutes | 5 |
| **Total** | | | **210** |

### Top of the files after this PR

`frontend/src/pages/business/FindCaPage.jsx`

```js
import { Link, useSearchParams } from "react-router";

import {
  useServices,
  useVerifiedCas,
} from "@/api";
import {
  caFacts,
  Field,
  Options,
  PageTitle,
  Pager,
  QueryStatus,
  RatingSummary,
  SpecializationBadges,
  VerifiedBadge,
} from "@/components/shared";
import {
  Button,
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
  formatRupees,
  label,
  labelList,
  SERVICE_UNIT_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  MarketplacePage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- Log in with your test account: **Find a CA** lists the verified CAs; try the filters.

### Commit message

`feat(marketplace): find a CA page`

## 53 A CA's details page

**Person 2** · **day 16** · **119 lines** · branch `p2/53-a-ca-s-details-page` · start in the morning

### What this PR builds

- `GET /marketplace/cas/<id>` and the CA's page: facts, prices, reviews, 'Request this CA'.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 256-270 | get_ca | 15 |
| `frontend/src/api.js` | 426-430 | useVerifiedCa | 5 |
| `frontend/src/pages/business/FindCaPage.jsx` | 198-286 | CaDetailPage, CaDetails | 97 |
| `frontend/src/routes.jsx` | 103 | part of appRoutes | 2 |
| **Total** | | | **119** |

### Top of the files after this PR

`frontend/src/pages/business/FindCaPage.jsx`

```js
import { Link, useLocation, useParams, useSearchParams } from "react-router";

import {
  useServices,
  useVerifiedCa,
  useVerifiedCas,
} from "@/api";
import {
  BackLink,
  caFacts,
  Field,
  Options,
  PageTitle,
  Pager,
  QueryStatus,
  RatingSummary,
  Row,
  Section,
  SpecializationBadges,
  Stars,
  Table,
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
  formatDateTime,
  formatRupees,
  label,
  labelList,
  SERVICE_UNIT_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  CaDetailPage,
  MarketplacePage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- On **Find a CA**, click a CA: their facts, prices and reviews, and **Request this CA** (its page comes in PR #54).

### Commit message

`feat(marketplace): CA details page`

---

# Engagements

**Person 1** · PRs #47, #54, #55, #57, #59 · **1039 lines**

Requesting a CA, accepting / declining / withdrawing / completing, ratings, and 'How to file' on the filing page.

## 47 Requesting a CA (API)

**Person 1** · **day 14** · **168 lines** · branch `p1/47-requesting-a-ca-api` · **wait for #45 today**

### What this PR builds

- Which filings a business can ask a CA for (with prices), sending a request (the CA is emailed), and the engagement lists of both sides.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 36-39, 94-109, 271-382 | ITR_SERVICES, engagement_to_dict, services_for, requestable_filings, send_request, my_engagements, ca_engagements | 133 |
| `backend/templates/email/engagement_requested.txt` (new file) | all |  | 8 |
| `frontend/src/api.js` | 448-474 | MY_ENGAGEMENTS_KEY, CA_ENGAGEMENTS_KEY, REQUESTABLE_KEY, useRequestableFilings, sendRequest, useMyEngagements, useCaEngagements | 27 |
| **Total** | | | **168** |

### Top of the files after this PR

`backend/routes_marketplace.py`

```python
# The CA marketplace: a CA's profile and prices, Find a CA, requests between a business and a
# CA, and ratings. A request is "requested" until the CA accepts (at their listed, fixed
# prices) or declines it, or the business withdraws it ("cancelled"); it never expires.
# Accepted work is "active" until it is "completed". A CA is listed only once an admin has
# verified their profile; changing the membership or CoP number needs a new check.

import re

from flask import jsonify, request

from app import app
from helpers import (
    as_uuid, current_user, error, iso, money, my_business, read_amount, read_upload, remove_document,
    role_required, save_document, send_email, notify,
)
from models import (
    CaProfile, CaService, CatalogService, ComplianceItem, Engagement, EngagementItem, Rating,
    RegulatoryProfile, db, now,
)
from filings import open_filing_ids
```

### See it work before you push

- What your test business could ask the CA Rahul Mehta for (a demo CA with GST prices):

```bash
bapi /marketplace/cas
CA=paste-the-ca-id    # the "id" of "Rahul Mehta" above
tapi /marketplace/cas/$CA/requestable-filings
capi /marketplace/ca-engagements
```

You should see something like (shortened):

```text
{
  "items": [
    {
      "about": "Income tax and TDS for salaried professionals and small employers.",
      "city": "Chennai",
      "full_name": "Priya Iyer",
      "id": "aa215daf-ce67-44fd-9052-d9f17c307df8",
      "languages": [
        "english",
        "tamil"
      ],
      "membership_no": "900001",
      "price": null,
      "rating_average": 5.0,
      "rating_count": 1,
      "specializations": [
...
```

### Commit message

`feat(engagements): request a CA API`

## 54 Request a CA page

**Person 1** · **day 16** · **217 lines** · branch `p1/54-request-a-ca-page` · **wait for #53 today**

### What this PR builds

- Ticking filings by quarter with the service and price, the total, and Send.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/business/FindCaPage.jsx` | 287-490 | RequestCaPage, priceOf, RequestForm, quarterOf, groupByQuarter, FilingPrice | 215 |
| `frontend/src/routes.jsx` | 104 | part of appRoutes | 2 |
| **Total** | | | **217** |

### Top of the files after this PR

`frontend/src/pages/business/FindCaPage.jsx`

```js
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
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  CaDetailPage,
  MarketplacePage,
  RequestCaPage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- Log in with your test account: **Find a CA**, open Rahul Mehta, **Request this CA**, tick a GST filing and send. (You withdraw it in the check of PR #55.)

### Commit message

`feat(engagements): request a CA page`

## 55 Answering a request: accept, decline, withdraw, complete (API, engagement cards)

**Person 1** · **day 17** · **242 lines** · branch `p1/55-answering-a-request-accept` · start in the morning

### What this PR builds

- Accept, decline, withdraw (never expires), complete; the business is notified. Engagement cards with a status timeline in `shared.jsx`.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 383-464 | find_engagement, tell_business, accept_request, decline_request, complete_engagement, withdraw_request | 82 |
| `backend/templates/email/engagement_accepted.txt` (new file) | all |  | 8 |
| `backend/templates/email/engagement_declined.txt` (new file) | all |  | 6 |
| `frontend/src/api.js` | 475-479 | engagementAction | 5 |
| `frontend/src/components/shared.jsx` | 409-535 | STATUS_COLORS, Timeline, EngagementCard, EngagementGroups | 132 |
| `frontend/src/lib.js` | 132-140 | ENGAGEMENT_STATUS_LABELS | 9 |
| **Total** | | | **242** |

### Top of the files after this PR

`backend/routes_marketplace.py`

```python
# The CA marketplace: a CA's profile and prices, Find a CA, requests between a business and a
# CA, and ratings. A request is "requested" until the CA accepts (at their listed, fixed
# prices) or declines it, or the business withdraws it ("cancelled"); it never expires.
# Accepted work is "active" until it is "completed". A CA is listed only once an admin has
# verified their profile; changing the membership or CoP number needs a new check.

import re

from flask import jsonify, request

from app import app
from helpers import (
    as_uuid, current_user, error, iso, money, my_business, read_amount, read_upload, remove_document,
    role_required, save_document, send_email, notify,
)
from models import (
    CaProfile, CaService, CatalogService, ComplianceItem, Engagement, EngagementItem, Rating,
    RegulatoryProfile, User, db, now,
)
from filings import open_filing_ids
```

`frontend/src/components/shared.jsx`

```js
// Pieces several pages use: query status, errors, cards, fields, tables, CA facts, engagements.
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router";

import { errorMessage } from "@/api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  linkClass,
} from "@/components/ui";
import {
  CA_SPECIALIZATION_LABELS,
  cn,
  COMPLIANCE_STATUS_LABELS,
  ENGAGEMENT_STATUS_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
} from "@/lib";
```

### See it work before you push

- Withdraw the request you sent in the check of PR #54:

```bash
tapi /marketplace/my-engagements
E=paste-the-request-id    # the "id" of your request above
tapi /marketplace/engagements/$E/withdraw -X POST
```

You should see something like (shortened):

```text
[
  {
    "activated_at": null,
    "business_name": "Test Traders",
    "ca_name": "Rahul Mehta",
    "ca_profile_id": "1077d906-221b-492a-8af3-a57cd21dcd68",
    "completed_at": null,
    "id": "77c75a30-8af2-40de-8697-3db1e25dda88",
    "items": [
      {
        "agreed_price": null,
        "compliance_item_id": "c3b80bb2-8bfe-4dee-a10a-dd102fcd77b8",
        "due_date": "2026-07-13",
        "form_code": "gstr_1",
        "id": "cd2ff9c5-b925-42e7-be67-728c070d66ea",
        "listed_price": "500.00",
...
```

### Commit message

`feat(engagements): accept, decline, withdraw, complete`

## 57 My engagements pages (business and CA) and rating a CA

**Person 1** · **day 18** · **214 lines** · branch `p1/57-my-engagements-pages` · start in the morning

### What this PR builds

- My engagements for both sides (withdraw, find another CA, accept / decline / complete) and rating a finished engagement.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_marketplace.py` | 465-482 | rate_engagement | 18 |
| `frontend/src/pages/business/EngagementsPage.jsx` (new file) | all | top of file, MyEngagementsPage, BusinessActions, RateForm | 128 |
| `frontend/src/pages/ca/EngagementsPage.jsx` (new file) | all | top of file, CaEngagementsPage, CaActions | 62 |
| `frontend/src/routes.jsx` | 51, 58, 105, 112 | part of NAV, part of appRoutes | 6 |
| **Total** | | | **214** |

### Top of the files after this PR

`frontend/src/pages/business/EngagementsPage.jsx`

```js
import { useState } from "react";
import { Link, useLocation } from "react-router";

import { engagementAction, FILINGS_KEY, MY_ENGAGEMENTS_KEY, useMyEngagements, useRefresh } from "@/api";
import { EngagementGroups, ErrorText, QueryStatus, RegisterFirst, useAction } from "@/components/shared";
import { Button, buttonClass, linkClass, Textarea } from "@/components/ui";
```

`frontend/src/pages/ca/EngagementsPage.jsx`

```js
import { CA_ENGAGEMENTS_KEY, engagementAction, useCaEngagements, useRefresh } from "@/api";
import { EngagementGroups, ErrorText, QueryStatus, useAction } from "@/components/shared";
import { Button } from "@/components/ui";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { MyEngagementsPage } from "@/pages/business/EngagementsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  CaDetailPage,
  MarketplacePage,
  RequestCaPage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaEngagementsPage } from "@/pages/ca/EngagementsPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- As `business@demo.local`: **My engagements** (requests, active and completed work, ratings).
- As `ca@demo.local`: **My engagements** with Accept / Decline on new requests.

### Commit message

`feat(engagements): engagements pages and ratings`

## 59 How to file: choose a path, mark filed, see the proof

**Person 1** · **day 19** · **198 lines** · branch `p1/59-how-to-file-choose-a-path` · start in the morning

### What this PR builds

- On the filing page: myself or with a CA, mark filed with the acknowledgement, the check result, undo.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/business/FilingPage.jsx` | 87, 167-356 | part of FilingPage, HowToFile, ChoosePath, MarkFiledForm, Verification, Filed | 198 |
| **Total** | | | **198** |

### Top of the files after this PR

`frontend/src/pages/business/FilingPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  chooseFilingPath,
  DASHBOARD_KEY,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  filingKey,
  FILINGS_KEY,
  fulfilDocumentRequest,
  linkDocument,
  markFiled,
  tickChecklist,
  unlinkDocument,
  unmarkFiled,
  UPLOAD_TYPES,
  uploadDocument,
  useAcknowledgementFile,
  useDocuments,
  useFiling,
  useMyDocumentRequests,
  useMyEngagements,
  usePeerInsights,
  usePenaltyEstimate,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  FormField,
  Markdown,
  Options,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
  useObjectUrl,
} from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, Input, Select } from "@/components/ui";
import {
  daysLeftText,
  daysUntil,
  DOCUMENT_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

### See it work before you push

- Log in with your test account, open a filing: **How to file**: choose 'myself', mark it filed with an acknowledgement number, see the result, then **Undo**.

### Commit message

`feat(filings): choose a path and mark filed on the filing page`

---

# CA workspace

**Person 3** · PRs #44, #46, #50, #52, #56, #58 · **1039 lines**

The CA's clients by urgency, a client's page, document requests, filing for clients, deadline batches and the business's to-do list.

## 44 CA workspace API: clients by urgency, one client

**Person 3** · **day 13** · **173 lines** · branch `p3/44-ca-workspace-api-clients-by` · **wait for #42 today**

### What this PR builds

- The CA's clients from active engagements, sorted by urgency with the reasons; one client with the filings and files; the CA can open those files.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/app.py` | 72 | part of http_error | 1 |
| `backend/routes_ca.py` (new file) | 1-4, 13-132 | top of file, POINTS_PER_OVERDUE_FILING, POINTS_DUE_IN_3_DAYS, POINTS_DUE_IN_7_DAYS, POINTS_PER_MISSING_DOCUMENT, POINTS_PER_OPEN_REQUEST, my_work, open_requests ... | 132 |
| `backend/routes_documents.py` | 138-145, 203-214 | part of open_document, request_to_dict | 20 |
| `frontend/src/api.js` | 480-499 | CA_WORKSPACE_KEY, useCaDashboard, useCaClients, useCaClient | 20 |
| **Total** | | | **173** |

### Top of the files after this PR

`backend/routes_ca.py`

```python
# The CA's workspace: their clients sorted by urgency, one client's page, asking a client for
# a document, marking a filing as filed, and batches of the same filing across clients.
# A CA only ever sees the filings of their ACTIVE engagements.

from flask import jsonify

from app import app
from filings import DONE, checklist_with_ticks, filing_to_dict, missing_documents
from helpers import current_user, error, iso, role_required, today_in_india
from models import Business, CaProfile, DocumentRequest, Engagement, EngagementItem, db
from routes_business import business_page
from routes_documents import documents_by_filing, request_to_dict
```

`backend/routes_documents.py`

```python
# The document vault: upload, list, open and delete files, link them to filings (ticking the
# checklist), and answer a CA's document request with a file. A filed filing's documents are
# fixed: they are the proof of what was filed. Admins never open documents.

from flask import jsonify, request

from app import app
from filings import DONE, checklist, filing_name, set_tick
from helpers import (
    as_uuid, current_user, error, iso, my_business, page_of, read_upload,
    remove_document, role_required, save_document, send_document,
)
from models import (
    CaProfile, ComplianceItem, ComplianceItemDocument, Document, Engagement,
    EngagementItem, db,
)
```

### See it work before you push


```bash
capi /ca-workspace/clients
```

You should see something like (shortened):

```text
[
  {
    "business_id": "883a28ea-7a4b-4fbf-8ad1-39f56f2974d1",
    "business_name": "Singh Auto Parts",
    "filing_count": 3,
    "missing_documents": 14,
    "next_deadline": "2026-10-20",
    "open_filing_count": 3,
    "open_request_count": 1,
    "overdue_count": 2,
    "reasons": [
      {
        "points": 80,
        "reason": "2 filing(s) overdue"
      },
      {
...
```

### Commit message

`feat(ca): CA workspace API`

## 46 CA dashboard and the my clients page

**Person 3** · **day 14** · **181 lines** · branch `p3/46-ca-dashboard-and-the-my` · start in the morning

### What this PR builds

- The CA dashboard (setup reminders) and My clients.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/ca/ClientsPage.jsx` (new file) | 48-120 | top of file, CaWorkspacePage, ClientCard | 93 |
| `frontend/src/pages/ca/DashboardPage.jsx` (new file) | all | top of file, CaDashboardPage, REMINDERS, ProfileReminder, SetupChecklist | 82 |
| `frontend/src/routes.jsx` | 55, 59, 109, 113 | part of NAV, part of appRoutes | 6 |
| **Total** | | | **181** |

### Top of the files after this PR

`frontend/src/pages/ca/ClientsPage.jsx`

```js
import { Link } from "react-router";

import {
  useCaClients,
} from "@/api";
import {
  PageTitle,
  QueryStatus,
} from "@/components/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui";
import {
  daysLeftText,
  formatDate,
} from "@/lib";
```

`frontend/src/pages/ca/DashboardPage.jsx`

```js
import { Link } from "react-router";

import { useCaDashboard, useCaProfile, useCaServices } from "@/api";
import { Welcome } from "@/components/shared";
import { buttonClass, Card, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { CA_VERIFICATION_STATUS_LABELS, label } from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### See it work before you push

- As `ca@demo.local`: the dashboard (welcome and setup reminders) and **My clients** (most urgent first, with the reasons).

### Commit message

`feat(ca): CA dashboard and my clients page`

## 50 One client's page for the CA

**Person 3** · **day 15** · **162 lines** · branch `p3/50-one-client-s-page-for-the-ca` · start in the morning

### What this PR builds

- A client's profile and a card per filing with checklist and files.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `frontend/src/pages/ca/ClientsPage.jsx` | 121-224, 232-271 | FILED, CaClientPage, Profile, part of FilingCard, Files | 161 |
| `frontend/src/routes.jsx` | 114 | part of appRoutes | 1 |
| **Total** | | | **162** |

### Top of the files after this PR

`frontend/src/pages/ca/ClientsPage.jsx`

```js
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  downloadDocument,
  useCaClient,
  useCaClients,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  PageTitle,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui";
import {
  daysLeftText,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### Merging

Merged after #49 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- As `ca@demo.local`, **My clients**, open a client: the profile and a card per filing with its checklist and files.

### Commit message

`feat(ca): client page`

## 52 Document requests: the CA asks, the business answers

**Person 3** · **day 16** · **192 lines** · branch `p3/52-document-requests-the-ca` · start in the morning

### What this PR builds

- The CA asks for a document; the business is notified and answers with a vault file (linked and ticked).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_ca.py` | 133-178 | ask_for_document, cancel_document_request | 46 |
| `backend/routes_documents.py` | 215-262 | list_document_requests, fulfil_document_request | 48 |
| `frontend/src/api.js` | 505-517, 524-536 | createDocumentRequest, cancelDocumentRequest, useMyDocumentRequests, fulfilDocumentRequest | 26 |
| `frontend/src/pages/business/FilingPage.jsx` | 89, 625-692 | part of FilingPage, CaRequests, AnswerRequest | 72 |
| **Total** | | | **192** |

### Top of the files after this PR

`backend/routes_ca.py`

```python
# The CA's workspace: their clients sorted by urgency, one client's page, asking a client for
# a document, marking a filing as filed, and batches of the same filing across clients.
# A CA only ever sees the filings of their ACTIVE engagements.

from flask import jsonify, request

from app import app
from filings import DONE, checklist, checklist_with_ticks, filing_name, filing_to_dict, missing_documents
from helpers import as_uuid, current_user, email_notice, error, iso, notify, role_required, today_in_india
from models import Business, CaProfile, DocumentRequest, Engagement, EngagementItem, User, db
from routes_business import business_page
from routes_documents import documents_by_filing, request_to_dict
```

`backend/routes_documents.py`

```python
# The document vault: upload, list, open and delete files, link them to filings (ticking the
# checklist), and answer a CA's document request with a file. A filed filing's documents are
# fixed: they are the proof of what was filed. Admins never open documents.

from flask import jsonify, request

from app import app
from filings import DONE, checklist, filing_name, set_tick
from helpers import (
    as_uuid, current_user, email_notice, error, iso, my_business, notify, page_of, read_upload,
    remove_document, role_required, save_document, send_document,
)
from models import (
    CaProfile, ComplianceItem, ComplianceItemDocument, Document, DocumentRequest, Engagement,
    EngagementItem, User, db, now,
)
```

`frontend/src/pages/business/FilingPage.jsx`

```js
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  DASHBOARD_KEY,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  filingKey,
  FILINGS_KEY,
  fulfilDocumentRequest,
  linkDocument,
  tickChecklist,
  unlinkDocument,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useFiling,
  useMyDocumentRequests,
  usePeerInsights,
  usePenaltyEstimate,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  FormField,
  Markdown,
  Options,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, Input, Select } from "@/components/ui";
import {
  daysLeftText,
  daysUntil,
  DOCUMENT_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

### See it work before you push

- The demo business's open document requests:

```bash
bapi /ca-workspace/document-requests
```

You should see something like (shortened):

```text
[
  {
    "ca_name": "Demo CA",
    "checklist_key": "gstr_2b",
    "compliance_item_id": "f4e7e7b8-371c-402f-ad03-985f5ca78cff",
    "created_at": "2026-10-08T02:35:30.035345+00:00",
    "document_id": null,
    "form_code": "gstr_3b",
    "fulfilled_at": null,
    "id": "fe72c24a-0856-43cd-a331-214fd884fd91",
    "message": "Please download GSTR-2B for the period from the GST portal and upload it.",
    "period_label": "Sep 2026",
    "status": "open"
  }
]
  [HTTP 200]
```

### Commit message

`feat(ca): document requests`

## 56 CA: ask for documents and mark filed from the client page

**Person 3** · **day 17** · **180 lines** · branch `p3/56-ca-ask-for-documents` · start in the morning

### What this PR builds

- On the client page: open requests, ask for a document, Mark as filed (the engagement completes when all its filings are filed).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_ca.py` | 179-213 | ca_mark_filed | 35 |
| `frontend/src/api.js` | 518-523 | caMarkFiled | 6 |
| `frontend/src/pages/ca/ClientsPage.jsx` | 225-231, 272-396 | part of FilingCard, Requests, RequestForm, MarkFiledForm | 139 |
| **Total** | | | **180** |

### Top of the files after this PR

`backend/routes_ca.py`

```python
# The CA's workspace: their clients sorted by urgency, one client's page, asking a client for
# a document, marking a filing as filed, and batches of the same filing across clients.
# A CA only ever sees the filings of their ACTIVE engagements.

from flask import jsonify, request

from app import app
from filings import DONE, checklist, checklist_with_ticks, filing_name, filing_to_dict, missing_documents, record_filed
from helpers import as_uuid, current_user, email_notice, error, iso, notify, role_required, today_in_india
from models import Business, CaProfile, DocumentRequest, Engagement, EngagementItem, User, db, now
from routes_business import business_page
from routes_documents import documents_by_filing, request_to_dict
```

`frontend/src/pages/ca/ClientsPage.jsx`

```js
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  caMarkFiled,
  cancelDocumentRequest,
  createDocumentRequest,
  downloadDocument,
  useCaClient,
  useCaClients,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  PageTitle,
  QueryStatus,
  Section,
  StatusBadge,
  useAction,
} from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
} from "@/components/ui";
import {
  daysLeftText,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

### See it work before you push

- As `ca@demo.local`, open a client: the open requests, **Ask for a document**, and **Mark as filed** on a filing that is with you.

### Commit message

`feat(ca): ask for documents and mark filed`

## 58 Deadline batches page and the business to-do list

**Person 3** · **day 18** · **151 lines** · branch `p3/58-deadline-batches-page` · start in the morning

### What this PR builds

- Deadline batches for the CA and the business dashboard's To do list.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/routes_ca.py` | 214-238 | list_batches | 25 |
| `frontend/src/api.js` | 500-504 | useCaBatches | 5 |
| `frontend/src/pages/business/DashboardPage.jsx` | 19, 27, 71-136 | part of BusinessDashboardPage, ToDo | 72 |
| `frontend/src/pages/ca/ClientsPage.jsx` | 397-440 | CaBatchesPage | 47 |
| `frontend/src/routes.jsx` | 60, 115 | part of NAV, part of appRoutes | 2 |
| **Total** | | | **151** |

### Top of the files after this PR

`frontend/src/pages/business/DashboardPage.jsx`

```js
import { Link } from "react-router";

import {
  useComplianceDashboard,
  useFilings,
  useMyDocumentRequests,
  useMyEngagements,
  usePenaltyExposure,
} from "@/api";
import { NumberCard, RegisterFirst, Welcome } from "@/components/shared";
import { daysLeftText, daysUntil, filingFormLabel, formatDate, formatRupees } from "@/lib";
```

`frontend/src/pages/ca/ClientsPage.jsx`

```js
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  caMarkFiled,
  cancelDocumentRequest,
  createDocumentRequest,
  downloadDocument,
  useCaBatches,
  useCaClient,
  useCaClients,
  useRefresh,
} from "@/api";
import {
  BackLink,
  ErrorText,
  Field,
  PageTitle,
  QueryStatus,
  Row,
  Section,
  StatusBadge,
  Table,
  useAction,
} from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
} from "@/components/ui";
import {
  daysLeftText,
  ENTITY_TYPE_LABELS,
  filingFormLabel,
  formatDate,
  formatRupees,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  label,
  MSME_TIER_LABELS,
} from "@/lib";
```

`frontend/src/routes.jsx`

```js
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "@/auth";
import { Button, buttonClass } from "@/components/ui";
import { cn, ROLE_HOME, USER_ROLE_LABELS } from "@/lib";
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  HomePage,
  LoginPage,
  NotFoundPage,
  ResetPasswordPage,
  SignupPage,
  TermsPage,
  VerifyEmailPage,
} from "@/pages/AuthPages";
import { SettingsPage } from "@/pages/SettingsPage";
import {
  AdminCaDetailPage,
  AdminDashboardPage,
  AdminUsersPage,
} from "@/pages/admin/AdminPages";
import { CompliancePage } from "@/pages/business/CalendarPage";
import { BusinessDashboardPage } from "@/pages/business/DashboardPage";
import { DocumentsPage } from "@/pages/business/DocumentsPage";
import { FilingPage } from "@/pages/business/FilingPage";
import {
  CaDetailPage,
  MarketplacePage,
  RequestCaPage,
} from "@/pages/business/FindCaPage";
import { OnboardingPage } from "@/pages/business/OnboardingPage";
import { CaBatchesPage, CaClientPage, CaWorkspacePage } from "@/pages/ca/ClientsPage";
import { CaDashboardPage } from "@/pages/ca/DashboardPage";
import { CaProfilePage, CaServicesPage } from "@/pages/ca/ProfilePage";
```

### Merging

Merged after #57 today. When you pull `main` before merging, git may show a conflict in `frontend/src/routes.jsx`: keep both sides (yours and theirs).

### See it work before you push

- As `ca@demo.local`: **Deadline batches**. As `business@demo.local`: the dashboard's **To do** list.

### Commit message

`feat(ca): deadline batches; feat(dashboard): to-do list`

---

# Reminders and README

**Person 3** · PRs #23, #60 · **219 lines**

The worker that marks late filings and emails reminders, and the README.

## 23 Deadline reminders and overdue marking (worker)

**Person 3** · **day 7** · **124 lines** · branch `p3/23-deadline-reminders` · start in the morning

### What this PR builds

- `reminders.py`: late filings become overdue; reminders 7, 3 and 1 day before and once when overdue, never twice; the worker service (only ONE teammate runs it).

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `backend/reminders.py` (new file) | all | top of file, mark_overdue, reminder_kind, reminder_title, send_reminders | 108 |
| `backend/templates/email/reminders.txt` (new file) | all |  | 11 |
| `docker-compose.yml` | 29-33 |  | 5 |
| **Total** | | | **124** |

### Top of the files after this PR

`backend/reminders.py`

```python
# The background jobs. Only ONE teammate runs this (docker compose --profile worker up):
#   - every 15 minutes: filings past their due date that were not started become "overdue"
#   - every morning after 8:15 (Indian time): deadline reminders 7, 3 and 1 day before the
#     due date, and once when a filing is overdue, to the business and the CA working on it.
#
#     python reminders.py                       keep running (the worker)
#     python reminders.py --once [2026-10-06]   run both jobs now (as if on that day), then stop

import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import app
from filings import DONE, filing_name
from helpers import india_date, notify, send_email, today_in_india
from models import Business, CaProfile, ComplianceItem, Engagement, EngagementItem, ReminderLog, User, db, now
```

### See it work before you push

- Run both jobs once:

```bash
docker compose exec backend python reminders.py --once
```

You should see something like (shortened):

```text
Overdue: 3 - reminders recorded: 20
```

### Commit message

`feat(reminders): deadline reminders worker`

## 60 README

**Person 3** · **day 19** · **95 lines** · branch `p3/60-readme` · start in the morning

### What this PR builds

- How to run the project, the shared Neon database, Mailpit, the worker, the demo accounts.

### Files

| File | Lines of the finished file | What | Lines |
|---|---|---|---|
| `README.md` (new file) | all |  | 95 |
| **Total** | | | **95** |

### See it work before you push

- Open `README.md` with Ctrl+Shift+V: every link and command in it works.

### Commit message

`docs: README`
