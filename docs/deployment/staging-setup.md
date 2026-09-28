# Staging setup — step by step (M19, D25)

This walks you through putting Deal Intelligence Lab on the internet as a
**private staging site**, using the stack you approved (D25): Railway runs the
app, Neon holds the database, Cloudflare R2 holds documents, Clerk handles
sign-in, Sentry reports errors.

**Before you start**

- Allow about 60–90 minutes. Do the parts in order: later parts need values
  from earlier ones.
- **Keep every secret in a password manager** (1Password, Bitwarden, Apple
  Passwords…) as you go. Never paste secrets into chat, email, documents or
  the repository. The table in Part 0 lists what you'll collect.
- Expected cost: about $20–45/month, plus AI usage capped in Part 1.
- **Synthetic data only.** No real customer documents go on staging until
  there is a separate, formal approval (M19 exit gate).

---

## Part 0 — What you'll collect

Create one entry in your password manager called **"Deal Lab staging"** and
save each value there as you get it.

| # | Value | From | Secret? |
|---|---|---|---|
| A | Anthropic staging API key (`sk-ant-…`) | Part 1 | **Yes** |
| B | Neon direct connection string (`postgresql://…`) | Part 2 | **Yes** |
| C | Cloudflare Account ID | Part 3 | No |
| D | R2 Access Key ID | Part 3 | **Yes** |
| E | R2 Secret Access Key | Part 3 | **Yes** |
| F | Clerk Publishable key (`pk_test_…`) | Part 4 | No (public by design) |
| G | Clerk Frontend API URL (`https://….clerk.accounts.dev`) | Part 4 | No |
| H | Sentry DSN (`https://…@….ingest…sentry.io/…`) | Part 5 | Treat as secret |
| I | Staging web address (`https://….up.railway.app`) | Part 6 | No |

---

## Part 1 — Anthropic: a separate staging key with a spend limit (5 min)

Why: staging gets its own key and budget, so a mistake there can't run up
cost on your main key, and you can switch it off without touching anything
else.

1. Go to **console.anthropic.com** and sign in.
2. Open **Settings → Workspaces** and click **Create workspace**.
   Name it `deal-lab-staging`.
3. Open the new workspace and find its **Limits** (spend limit). Set a
   monthly limit — **$100** is the cap D25 suggested.
4. Go to **API Keys**, click **Create key**, choose the **deal-lab-staging**
   workspace, and name the key `railway-staging`.
5. Copy the key immediately (it's shown once) → save as **A**.

✅ You should see the new key listed under the `deal-lab-staging` workspace.

---

## Part 2 — Neon: the staging database (10 min)

1. Go to **neon.tech** and sign up (GitHub or Google sign-in is fine).
2. Create a project:
   - **Project name:** `deal-lab-staging`
   - **Postgres version:** the default (16 or newer)
   - **Cloud provider:** AWS
   - **Region:** **Europe (Frankfurt)**
   - Click **Create project**.
3. On the project dashboard, click **Connect**.
4. In the connection dialog:
   - Branch: `main` (the default). Database: `neondb` (the default).
   - **Turn "Connection pooling" OFF.** This matters: the app relies on
     per-connection settings that the pooled connection breaks. The address
     must **not** contain `-pooler`.
   - Copy the connection string. It looks like
     `postgresql://neondb_owner:…@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`
5. Save it as **B**.

✅ The string you saved contains `sslmode=require` and does **not** contain
`-pooler`.

---

## Part 3 — Cloudflare R2: private document storage (15 min)

1. Go to **dash.cloudflare.com** and sign up / sign in.
2. In the left menu open **R2 Object Storage**. If asked, accept the R2 terms
   and add a payment method (the free tier covers staging; the card is only
   for going over it).
3. On the R2 overview page, find your **Account ID** (right-hand side,
   "Account Details") → save as **C**.
4. Create the bucket:
   - Click **Create bucket**.
   - **Bucket name:** `deal-lab-staging`
   - **Location:** choose **Specify jurisdiction** → **European Union (EU)**.
     This can't be changed later.
   - Click **Create bucket**.
5. Keep it private: open the bucket → **Settings** → make sure **Public
   access** (public development URL / custom domains) is **disabled**. It is
   by default — just check.
6. Create the access key the app will use:
   - Back on the **R2 Object Storage** page, under **Account Details**, click
     **Manage** next to **API Tokens**.
   - Click **Create Account API token**.
   - **Name:** `deal-lab-staging-app`
   - **Permissions:** **Object Read & Write**
   - **Specify bucket(s):** **Apply to specific buckets only** →
     `deal-lab-staging`
   - Click **Create Account API token**.
7. The next page shows the credentials **once**:
   - **Access Key ID** → save as **D**
   - **Secret Access Key** → save as **E**

✅ You have C, D and E saved. The storage address the app uses will be
`https://C.eu.r2.cloudflarestorage.com` (with your Account ID in place of C —
note the `.eu.`, because the bucket is in the EU jurisdiction).

---

## Part 4 — Clerk: sign-in (15 min)

Staging uses a Clerk **development instance**. It works on Railway's free web
address; a production instance would need a domain you own with DNS records —
that comes later, for the pilot.

1. Go to **dashboard.clerk.com** and sign up.
2. Create an application:
   - **Application name:** `Deal Lab Staging`
   - **Sign-in options:** tick **Email** only (untick Google/phone/etc. —
     pilots sign in with the email address you invite).
   - Click **Create application**.
3. Get the keys: open **Configure → API keys** (or the "API Keys" page shown
   after creation).
   - **Publishable key** (`pk_test_…`) → save as **F**
   - Find the **Frontend API URL** on the same page (it looks like
     `https://something-something-12.clerk.accounts.dev`) → save as **G**.
   - You do **not** need the Secret key for this app.
4. Add the email to the sign-in token (the app uses it to recognise invited
   people on their first sign-in):
   - Open **Configure → Sessions**.
   - Under **Customize session token**, click **Edit** and enter exactly:
     ```json
     {
       "email": "{{user.primary_email_address}}"
     }
     ```
   - Click **Save**.
5. Make sign-up invite-only (recommended second lock — the app itself already
   refuses anyone you haven't invited on its Team page):
   - Open **Configure → Restrictions → Access mode** (or go to
     `dashboard.clerk.com/~/user-authentication/access-mode`).
   - Choose **Invite-only** and save.
   - Consequence: each new person must be invited **twice** — in Clerk
     (**Users → Invite**) so they can create a login, and on the app's
     **Team** page so they can get in. If you'd rather invite only once,
     leave Access mode on **Open**; the app still blocks anyone not on its
     Team page.

✅ You have F and G saved, and the session token shows the `email` claim.

---

## Part 5 — Sentry: error reports (5 min, optional but recommended)

1. Go to **sentry.io/signup**. When asked for a **data storage location**,
   choose **European Union** (keeps error data in the EU with the rest).
2. Create a project: platform **Python**, alert setting "Alert me on every
   new issue", project name `deal-lab-staging`, then **Create Project**.
3. Copy the **DSN** from the setup page (also under **Settings → Projects →
   deal-lab-staging → Client Keys (DSN)**) → save as **H**.

The app sends Sentry no document text, no request contents and no personal
data (only error type and where it happened).

---

## Part 6 — Railway: run the app (25 min)

The app runs as **two services from the same code**: **web** (the website and
API) and **worker** (runs the long AI analyses in the background).

### 6.1 Account and project

1. Go to **railway.com** and sign up **with GitHub** (the same GitHub account
   that owns the `deal-intelligence-lab` repository).
2. Choose the **Hobby** plan ($5/month) under your account's **Plans**.
3. Click **New Project** → **Deploy from GitHub repo**. If asked, **Configure
   GitHub App** and give Railway access to the `deal-intelligence-lab`
   repository only.
4. Pick `deal-intelligence-lab`. Railway creates a service and starts a first
   build — **let it fail or cancel it**; it isn't configured yet.

### 6.2 The web service

Click the new service, then:

1. **Rename it:** Settings → service name → `web`.
2. **Code branch:** Settings → **Source** → **Branch** → choose
   `claude/gifted-turing-79cs5r` (the work is on this branch, not `main`).
   Optional but good: turn on **Wait for CI**, so Railway only deploys a
   commit after GitHub's tests pass.
3. **Region:** Settings → **Deploy** → **Region** → **EU West (Amsterdam)**.
4. **Health check:** Settings → **Deploy** → **Healthcheck Path** →
   `/api/health`.
5. **Variables:** open the **Variables** tab → **Raw Editor**, paste the
   block below, replace every `<…>` with your saved values, then **Update
   Variables**. Leave the two lines that mention I (the web address) for 6.4.

   ```
   DEAL_LAB_ENVIRONMENT=staging
   DEAL_LAB_RUN_WORKER=0
   DATABASE_URL=<B>
   ANTHROPIC_API_KEY=<A>
   ANTHROPIC_MODEL=claude-sonnet-5
   DEAL_LAB_STORAGE=object
   DEAL_LAB_S3_BUCKET=deal-lab-staging
   DEAL_LAB_S3_ENDPOINT=https://<C>.eu.r2.cloudflarestorage.com
   DEAL_LAB_S3_PREFIX=staging
   AWS_ACCESS_KEY_ID=<D>
   AWS_SECRET_ACCESS_KEY=<E>
   SENTRY_DSN=<H>
   DEAL_LAB_AUTH_MODE=clerk
   DEAL_LAB_AUTH_ISSUER=<G>
   DEAL_LAB_AUTH_JWKS_URL=<G>/.well-known/jwks.json
   VITE_CLERK_PUBLISHABLE_KEY=<F>
   DEAL_LAB_BOOTSTRAP_ADMIN_EMAIL=<the email you will sign in with>
   ```

   (Leave out `SENTRY_DSN` if you skipped Part 5.)

### 6.3 The worker service

1. In the project canvas click **+ Create** (or **New**) → **GitHub Repo** →
   `deal-intelligence-lab` again. A second service appears.
2. Rename it `worker`.
3. **Branch:** same as web — `claude/gifted-turing-79cs5r` (and **Wait for
   CI** if you turned it on for web).
4. **Region:** **EU West (Amsterdam)**.
5. **Start command:** Settings → **Deploy** → **Custom Start Command** →
   `python worker.py`
6. **No health check and no public domain** for the worker (it doesn't serve
   web pages).
7. **Variables** → **Raw Editor**, paste, fill in, **Update Variables**:

   ```
   DEAL_LAB_ENVIRONMENT=staging
   DATABASE_URL=<B>
   ANTHROPIC_API_KEY=<A>
   ANTHROPIC_MODEL=claude-sonnet-5
   DEAL_LAB_STORAGE=object
   DEAL_LAB_S3_BUCKET=deal-lab-staging
   DEAL_LAB_S3_ENDPOINT=https://<C>.eu.r2.cloudflarestorage.com
   DEAL_LAB_S3_PREFIX=staging
   AWS_ACCESS_KEY_ID=<D>
   AWS_SECRET_ACCESS_KEY=<E>
   SENTRY_DSN=<H>
   ```

### 6.4 Web address, then finish the web settings

1. Open the **web** service → Settings → **Networking** → **Generate
   Domain**. Railway shows an address like
   `https://deal-lab-web-production.up.railway.app` → save as **I**.
2. Back in **web → Variables → Raw Editor**, add these two lines (the address
   exactly as shown, starting `https://`, no trailing `/`):

   ```
   DEAL_LAB_AUTH_AUTHORIZED_PARTIES=<I>
   DEAL_LAB_ALLOWED_ORIGINS=<I>
   ```

3. Click **Deploy** (or **Apply changes**) on the project so both services
   build with the new settings. The first build takes a few minutes.

✅ Both services show **Active / Deployed**. Opening `<I>/api/health` in a
browser shows `{"ok": true}`.

---

## Part 7 — First sign-in and inviting people (10 min)

1. If you chose **Invite-only** in Clerk (Part 4, step 5): in the Clerk
   dashboard open **Users → Invite**, and invite **yourself** with the email
   you put in `DEAL_LAB_BOOTSTRAP_ADMIN_EMAIL`. Accept the invitation email.
2. Open the web address **I**. You should see the **Deal Intelligence Lab**
   sign-in screen. Sign in with that email.
3. You land in the app as an **admin**. Open **Team** in the sidebar:
   - Under **Organization settings**, rename "Local Organization" (for
     example to your firm's name) and **Save**.
   - Under **Invite someone**, add each staging tester's email and name.
     (If Clerk is Invite-only, also invite them under Clerk **Users →
     Invite**.)
4. Give people access to a deal from that deal's **Overview → People on this
   deal**.
5. Tidy-up (optional, recommended): once you're in, remove
   `DEAL_LAB_BOOTSTRAP_ADMIN_EMAIL` from the web service's variables. It's
   harmless to keep, but it isn't needed any more.

✅ You're signed in, you see yourself on the Team page as **Admin**, and a
test person you invited can sign in and sees only the deals you gave them.

**If something goes wrong**

| You see | Likely cause | Fix |
|---|---|---|
| "This account hasn't been invited" | The email you signed in with isn't on the Team page, or differs from `DEAL_LAB_BOOTSTRAP_ADMIN_EMAIL` | Check the spelling of the variable; redeploy web |
| Sign-in loops or "We couldn't start your session" | `DEAL_LAB_AUTH_AUTHORIZED_PARTIES` doesn't exactly match the web address, or the `email` session claim is missing | Re-check 6.4 and Part 4 step 4 |
| Build fails | Branch not set, or a variable pasted with quotes/spaces | Re-check 6.2 step 2; values go in without quotes |
| Deploy fails its health check | `DATABASE_URL` wrong or pooled | Use the **direct** Neon string (no `-pooler`) |
| Upload fails | R2 values wrong, or endpoint missing `.eu.` | Re-check Part 3 and `DEAL_LAB_S3_ENDPOINT` |

Railway's **Deployments → View logs** on each service shows the exact error;
Sentry (if set up) shows it too.

---

## Part 8 — Tell Claude the web address

Send the web address **I** (not any secret). The next step is the M19 exit
gate on staging, with synthetic data only: two users completing the workflow,
tenant-isolation and document-access tests, a long analysis surviving a closed
browser and a worker restart, a backup-restore drill (Neon **Restore**), and
checking logs and alerts.
