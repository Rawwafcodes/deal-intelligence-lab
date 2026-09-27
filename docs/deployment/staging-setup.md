# Staging setup checklist (M19, D25)

Everything in this checklist needs the founder: creating accounts and handling
credentials. The code is ready for it (Tasks 19.2-19.6). Approved budget:
≈ $20-45/month infrastructure, AI testing capped (D25). **Synthetic data only
until a separate formal approval for real customer data** (M19 exit gate).

## 1. Accounts (founder)

| Service | Plan to start | Region / setting |
|---|---|---|
| Railway | Hobby ($5/month) | Region: EU West (Amsterdam) |
| Neon | Free, then Launch when needed | Region: AWS Europe (Frankfurt) |
| Cloudflare R2 | Free tier | Bucket with **EU jurisdiction**, private |
| Clerk | Free (Hobby) | Application for staging |
| Sentry | Developer (free) | One Python project |
| Anthropic | Existing | A **separate workspace-scoped key for staging**, with a spend limit set in the Console |

## 2. Settings in each service

**Neon**
- Create project `deal-lab-staging` in Frankfurt.
- Copy the **direct** connection string, **not** the pooled one. The app
  relies on per-connection settings (schema search path, a start-up advisory
  lock) that a transaction pooler breaks.

**Cloudflare R2**
- Create bucket `deal-lab-staging` with EU jurisdiction. Leave public access
  **off**.
- Create an R2 API token scoped to that bucket only (Object Read & Write).
- Endpoint: `https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com`.

**Clerk**
- Create an application. Sign-in method: email (magic link or code). Turn
  **off** public sign-up (the app is invite-only anyway).
- Sessions → Customize session token → add the claim
  `"email": "{{user.primary_email_address}}"` (the app links an invited person
  by this email on first sign-in).
- Add the staging domain to allowed origins once Railway gives you one.

**Sentry**: create a Python project and copy its DSN.

## 3. Railway: two services from this repository (same Dockerfile)

| | Web service | Worker service |
|---|---|---|
| Start command | (default) `python server.py` | `python worker.py` |
| Health check path | `/api/health` | - |
| Public domain | yes | **no** |
| `DEAL_LAB_RUN_WORKER` | `0` | (unset) |

Environment variables for **both** services (Railway "shared variables"):

```
DEAL_LAB_ENVIRONMENT=staging
DATABASE_URL=<Neon direct connection string>
ANTHROPIC_API_KEY=<staging key>
ANTHROPIC_MODEL=claude-sonnet-5
DEAL_LAB_STORAGE=object
DEAL_LAB_S3_BUCKET=deal-lab-staging
DEAL_LAB_S3_ENDPOINT=https://<ACCOUNT_ID>.eu.r2.cloudflarestorage.com
DEAL_LAB_S3_PREFIX=staging
AWS_ACCESS_KEY_ID=<R2 token access key>
AWS_SECRET_ACCESS_KEY=<R2 token secret>
SENTRY_DSN=<Sentry DSN>
```

Web service only:

```
DEAL_LAB_AUTH_MODE=clerk
DEAL_LAB_AUTH_ISSUER=<Clerk Frontend API URL>
DEAL_LAB_AUTH_JWKS_URL=<Clerk Frontend API URL>/.well-known/jwks.json
DEAL_LAB_AUTH_AUTHORIZED_PARTIES=https://<staging domain>
DEAL_LAB_ALLOWED_ORIGINS=https://<staging domain>
```

Build argument (web service): `VITE_CLERK_PUBLISHABLE_KEY=<Clerk publishable key>`.
It's public by design and baked into the React build.

## 4. First run

1. Deploy both services. CI (`.github/workflows/ci.yml`) already builds and
   starts this exact image on every push.
2. The first start creates the database schema automatically.
3. Invite yourself: the database starts with the local seed identities. Sign
   in once with your Clerk account and you'll see "not invited". Then run the
   one-off invite command below from Railway's shell on the web service, sign
   in again, and invite everyone else from the **Team** page.

   ```bash
   python -c "import identity; org=identity.list_organizations()[0].id; identity.invite_to_organization(org, 'YOU@EXAMPLE.COM', 'Your Name', 'admin')"
   ```

## 5. Before any real customer data

Out of scope for this checklist, and each needs its own sign-off (M19 exit
gate): two users completing the workflow, tenant-isolation and
document-access tests on staging, a long job surviving browser closure and a
worker restart, a backup-restore drill (Neon point-in-time restore), logs and
alerts working, and a security review.
