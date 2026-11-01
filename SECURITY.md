# Security

This application is intended for one trusted owner. Cloud access uses a shared access key and revocable browser sessions, not multiple user accounts or per-user permissions.

- Local file mode binds to loopback by default and has no access key unless configured. Do not expose it publicly without appropriate HTTPS, host/origin restrictions, and authentication.
- Vercel mode requires PostgreSQL and `NOTEBOOK_KEY_HASH`; missing configuration must fail closed. All content endpoints, including backups and exports, require an authenticated session.
- Password verification uses scrypt. Sessions use random tokens, store only token hashes, and use HttpOnly, SameSite=Strict cookies; cloud cookies require HTTPS. Sessions expire after one year.
- Login throttling is global: 30 attempts per 15 minutes. A hostile client can temporarily exhaust the owner's login budget. This is not a general-purpose identity platform.
- Browser drafts are unencrypted localStorage data and survive logout. Treat the browser profile as private. Drafts and theme preferences are scoped to the origin.
- Rotation requires replacing the key hash and redeploying. Revoke sessions and retire historical deployments that still contain the old configuration; changing the latest deployment does not rewrite old immutable deployments.
- Do not share production credentials with preview environments, cache authenticated API responses, or publish data directories. Backups contain private note content.

For suspected vulnerabilities, use GitHub's **Report a vulnerability** feature if enabled. Otherwise, open a minimal issue asking for a private reporting channel; do not publish working exploits, secrets, or private notes in a public issue.
