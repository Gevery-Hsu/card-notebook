# Contributor entry point

Read README.md and docs/DEPLOY.en.md or docs/DEPLOY.zh-CN.md before changing deployment behavior.

- This is the public source tree. Never commit data/, .env files, .vercel/, .runtime/, browser profiles, logs, archives, notes, or real deployment IDs/domains. `.env.cloud.example` contains placeholders only.
- Local Markdown and cloud PostgreSQL are separate modes; they do not synchronize. Test with isolated data and preserve originals, unknown frontmatter, stable IDs/filenames, and conflict drafts.
- Keep Vercel fail-closed: require PostgreSQL and an access-key hash. Enforce authorization on reads and exports as well as writes. Do not expose credentials through VITE_ variables.
- Use transactions for cloud mutations; file mode requires one writer process. Do not silently overwrite stale versions.
- All categories share editor and reader. Book excerpts only add source information. Preserve editable calendar dates, Asia/Shanghai date semantics, date validation, and draft recovery.
- Preserve design/theme.original.css. Application layout belongs in src/styles.css. Do not add accounts, public sharing, attachments, AI, or synchronization without a scoped request.
- Test Python behavior with `python -m pytest tests -q`, dates with `node --test tests/dates.test.mjs`, and frontend builds with `npm run build`. Use real browser validation for rendered UI changes.
- Database tests only accept a loopback database named notebook_qa, and clear its application tables. Never point them at a real notebook.
- Deploy or publish only when explicitly requested. Verify target account, repository/project, environment, and sanitized Git contents before publishing.
