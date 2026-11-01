# Card Notebook deployment guide

[中文版](DEPLOY.zh-CN.md) · [Project home](../README.md)

Card Notebook is designed for one trusted owner. Run it locally with Markdown files, or deploy to Vercel with Neon PostgreSQL. The modes do not synchronize automatically. Markdown downloads remain available when PostgreSQL is the primary store.

The application UI currently uses Chinese text. This guide does not imply an English UI translation.

## 1. Prerequisites

- Python **3.13**, Node.js **24**, npm, and Git.
- For cloud deployment: your own GitHub, Vercel, and Neon accounts. A custom domain is optional.
- Clone or fork this repository. Run commands from the repository root.

No notes or credentials are included. First local startup creates an empty `data/notes`, `data/trash`, and default category configuration. When migrating an existing notebook, locate its actual data first; accidentally starting an empty notebook is not a successful migration.

Accounts, public sharing, attachments, AI features, and automatic synchronization are outside the current scope.

## 2. Local deployment

### Windows

After installing Python and Node.js, run:

```powershell
.\安装.cmd
.\启动卡片本.cmd
```

Open `http://127.0.0.1:8765`. The scripts mean install and start, respectively. `停止卡片本.cmd` stops this project's service; closing the browser does not stop the server. `创建桌面入口.cmd` creates a desktop shortcut.

Repeated startup reuses the same project and data directory. A port owned by another service produces an error rather than terminating that service. After moving the folder or changing computers, rebuild dependencies: rename and retain an old `.venv` before reinstalling. Recreate desktop shortcuts as well.

### macOS / Linux

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock.txt
npm ci
npm run build
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8765 --workers 1
```

Press Ctrl+C to stop the foreground server. File mode requires a single writer process per data directory; do not increase the worker count.

### Data and drafts

```text
data/
  categories.json   Categories, order, and icons
  notes/*.md        Active notes
  trash/*.md        Recoverable deleted notes
```

Set `NOTEBOOK_DATA_DIR` to use a different directory. Local startup binds to loopback by default. Without an access key, its health endpoint includes the actual data directory to help identify the running instance.

Unsaved drafts live in browser localStorage, not in the data directory. Storage is isolated by origin: changing browser, port, hostname, or HTTP/HTTPS does not migrate drafts. Save drafts before moving. Do not clear browser storage to troubleshoot a blank page.

## 3. Local Docker deployment

Install Docker and Compose, then run:

```sh
docker compose up -d --build
docker compose logs --tail 50
# Stop the service
docker compose down
```

Open `http://127.0.0.1:8765`. Compose mounts `./data` at `/data` and binds the port only to host loopback. Do not change the port mapping to expose unauthenticated file mode publicly. For remote access, use the cloud setup or an appropriately managed private access channel and HTTPS.

## 4. Vercel + Neon deployment

### 4.1 Create your own resources

1. Fork the repository to your GitHub account, or create a repository from your own clean copy.
2. Import it into Vercel. Use the **Vite** preset, `npm run build`, output directory `dist`, and Node.js 24. `.python-version` selects Python 3.13.
3. Under Storage / Marketplace, create **Neon PostgreSQL** and connect it to the project's **Production** environment. Leave Neon Auth disabled: the application already provides a single-owner access key. Keep the database near the function. The default function region in `vercel.json` is Singapore, `sin1`; change `regions` if choosing another database region.
4. Complete provider terms yourself if prompted. Plan limits, free-tier availability, and regions depend on the current provider offering; do not assume paid upgrades are necessary.
5. The integration normally injects `DATABASE_URL` and related variables. Use separate databases or branches for Preview / Development. Verify which database a connection string targets before initialization or migration.

If an automatic deployment starts before setup is complete, the API will refuse to start with missing cloud configuration. Finish the following steps and redeploy. Do not disable authentication or fall back to temporary filesystem storage to make startup pass.

### 4.2 Generate an access-key hash

After installing Python dependencies locally, run:

```sh
python -m scripts.cloud key
```

Enter an access key of at least 16 characters twice. Input is hidden. The command prints `NOTEBOOK_KEY_HASH=scrypt:...`. Store the **entire value after the equals sign** in Vercel as the `NOTEBOOK_KEY_HASH` Secret. Keep the original key in your password manager. Never put it in frontend code, Git, or a `VITE_` variable.

### 4.3 Configure Production environment variables

Use `.env.cloud.example` as a placeholder reference:

| Variable | Value |
| --- | --- |
| `NOTEBOOK_STORAGE` | `postgres` |
| `DATABASE_URL` | Neon's pooled connection string with the required TLS parameters; backend only |
| `NOTEBOOK_KEY_HASH` | Generated scrypt hash; store as a Secret |
| `NOTEBOOK_ALLOWED_HOSTS` | Your custom hostname, e.g. `notes.example.com`; comma-separated, without schemes |
| `NOTEBOOK_ALLOWED_ORIGINS` | Your HTTPS origin, e.g. `https://notes.example.com`; comma-separated |

The current Vercel deployment and primary production host are added from system environment variables. Explicitly list any additional aliases you use. If only using Vercel's default address for now, the two custom-domain variables may be omitted. Same-origin write checks allow the request's current origin.

Redeploy after changing environment variables. Database credentials, access-key hashes, and other secrets must not use `VITE_` prefixes.

### 4.4 Initialize the database

Install the Python dependencies locally and set the correct Neon connection string in your current terminal. These examples hide input and avoid putting the credential in command history.

Windows PowerShell:

```powershell
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', (Read-Host 'Neon connection string' -AsSecureString)).Password
python -m scripts.cloud init
Remove-Item Env:DATABASE_URL
```

macOS / Linux (Bash):

```bash
read -r -s -p 'Neon connection string: ' DATABASE_URL
printf '\n'
export DATABASE_URL
python -m scripts.cloud init
unset DATABASE_URL
```

`init` creates this application's tables and default categories without deleting notes. Runtime uses the pooled URL; setup and import may instead use `DATABASE_URL_UNPOOLED`, which the script prefers when set.

Scripts **do not automatically load `.env.local`**. If using `vercel env pull`, securely load the intended environment yourself and never commit the resulting file.

For a new notebook, run only `init`. Do not run `import` without an existing local notebook.

### 4.5 Optional: import a Markdown notebook

1. Save browser drafts, stop writes to the original directory, and copy the whole directory as a backup.
2. Confirm it contains `notes/`, `trash/`, and `categories.json`. Set the intended database connection as described above.
3. Run these commands from the project root, replacing the example path with the source directory. Keep quotes around paths with spaces.

```sh
python -m scripts.cloud inspect --source "path/to/notebook-data"
python -m scripts.cloud import --source "path/to/notebook-data"
python -m scripts.cloud verify --source "path/to/notebook-data"
```

Import is transactional. IDs, filenames, dates, tags, sources, unknown frontmatter, categories, and trash are preserved. It verifies original file-byte hashes. Identical imports can be repeated; differing existing notes or category configuration cause an explicit stop. Malformed files and duplicate IDs prevent import. Editing the old local copy afterward does not synchronize those edits to the cloud.

### 4.6 Deploy and verify

Redeploy Production in the Vercel dashboard. Alternatively, from your own clone with the Vercel CLI:

```sh
npx vercel link
npx vercel deploy --prod --skip-domain
# Verify the exact returned deployment URL, then promote that deployment
npx vercel promote <tested-deployment-url>
```

Check account, team, project, and environment before publishing. Keep `data/`, `.env*`, `.vercel/`, `.runtime/`, archives, and caches out of Git and deployment uploads. Ignore rules are included. Clone the public source rather than copying an entire private installation.

Acceptance checks:

- The page shows the access-key form. `/api/auth/status` reports `required: true`; notes, metadata, exports, and backup endpoints return 401 without a session.
- Unlock, save, refresh, search, backdate, and export a note. Multiple keywords and tags must all match.
- Updating the same note in another window makes an older version conflict without discarding the draft.
- Logout and revoking all devices require re-entry of the key. Drafts survive session expiration and re-authentication.
- Full backup includes active notes, trash, and category configuration. For migrations, check note counts and the `verify` result.
- Inspect runtime logs and an actual mobile browser; a successful build alone is not end-to-end verification.

Vercel Deployment Protection is separate from the application's key. Depending on account settings, default deployment URLs may also require Vercel login, and custom domains may be protected too. Manage that setting according to your needs; do not automatically remove it as a debugging step.

## 5. Custom domains and Cloudflare DNS

1. Add your hostname, such as `notes.example.com`, in Vercel Settings → Domains.
2. Read the **actual CNAME target** shown for your project. Do not reuse another installation's target.
3. In Cloudflare, add a CNAME named `notes` pointing to that target, with automatic TTL and **DNS only (gray cloud)** initially. Inspect any existing record before replacing it.
4. A subdomain does not require transferring the domain's nameservers. Add a TXT ownership challenge only if Vercel requests one, using its actual returned value.
5. Wait for DNS propagation, valid Vercel configuration, and a successfully issued HTTPS certificate. Add the hostname/origin to the allowlists and redeploy.

If the connection closes during the TLS handshake, check certificate issuance. Correct DNS does not guarantee a certificate has already been issued. Review Vercel certificate status, CAA records, and validation challenges; reissue through the official workflow if needed. Do not disable browser certificate verification, clear drafts, or rebuild the database to fix a network issue.

Preserve API `Cache-Control: no-store`. Do not apply Cloudflare Cache Everything to note endpoints.

## 6. Backups, updates, and key rotation

- Ordinary ZIP exports omit trash. **Full backup** includes `notes/`, `trash/`, and `categories.json`.
- Extract a full backup into a new empty directory to return to local mode. Do not overwrite an existing notebook. Browser drafts and device sessions are not included.
- For file mode, stopping the service and copying its actual data directory is another complete backup. Respect `NOTEBOOK_DATA_DIR` overrides.
- Before updating, download a backup, review changes, install locked dependencies, and rebuild. Redeploying the application does not require rebuilding the cloud database. Do not automatically re-import old local data on every deployment.
- To rotate the access key, generate a new hash, replace the Production Secret, and redeploy. Revoke sessions and retire historical deployments containing old configuration. Updating the latest deployment does not rewrite immutable older ones.
- Browser authorization lasts one year and identifies a browser profile, not hardware. Incognito mode, cookie deletion, or switching browsers requires re-entry. Logout does not delete unencrypted local drafts.

## 7. Development and tests

```sh
python -m pytest tests -q
node --test tests/dates.test.mjs
npm run build
```

Real PostgreSQL tests require a **disposable loopback database** named `notebook_qa`. Set `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/notebook_qa` before running them. They truncate application tables in that test database. Without the variable, database tests explicitly skip; skipped tests are not database acceptance. GitHub Actions supplies an isolated PostgreSQL service for them.

For frontend development, run `npm run dev` and set `NOTEBOOK_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173` on the backend. Use a separate `NOTEBOOK_DATA_DIR` for synthetic test content.

## 8. Current limits

This version targets a small personal text notebook. Matching notes and batch exports can be read into memory in a single request; larger collections need SQL pagination and streaming backups. Global login throttling allows 30 attempts per 15 minutes and can temporarily exhaust the owner's login budget. Drafts are not encrypted. End-to-end encryption, public sharing, offline cloud writes, and automatic multi-store synchronization are not included.
