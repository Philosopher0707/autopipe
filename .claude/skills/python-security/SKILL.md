# Python Security — Autopipe

## Skill: python-security

## When to Apply
- Before opening a PR.
- When adding LLM integrations, file readers, or data connectors.
- After modifying `credentials/`, `config/`, or `.env.example`.

## Security Checklist

### Secrets
- [ ] No secrets in source code (grep for `api_key`, `token`, `password`, `SECRET`).
- [ ] `.env` is in `.gitignore`.
- [ ] `.env.example` lists all required vars with dummy values.
- [ ] `python-dotenv` loads env vars at startup; no defaults with real values.

### Static Analysis
Run before merge:
```bash
conda run -n pipeline bandit -r autopipe -f json -o bandit-report.json
conda run -n pipeline safety check
conda run -n pipeline ruff check autopipe tests --select E,W,F,N,I,UP,B,C4,SIM,ARG,PIE,RUF,S
```

### Input Validation
- [ ] YAML configs validated against JSON schemas.
- [ ] File paths resolved with `pathlib.Path.resolve()` and checked against allowed roots.
- [ ] LLM prompts escaped or parameterized; no raw `eval()` / `exec()`.
- [ ] SQL queries parameterized (use DuckDB/PostgreSQL placeholders).

### Network
- [ ] URL validation for webhooks or external data sources.
- [ ] Timeouts on all `requests` / `httpx` calls (never default infinite).
- [ ] Rate limiting with `tenacity` or `governor` for LLM providers.

### Deserialization
- [ ] `yaml.safe_load` or `yaml.load(..., Loader=yaml.SafeLoader)` only.
- [ ] Avoid `pickle.loads` on untrusted data; use JSON, msgpack, or Parquet.
- [ ] Avoid `marshal` or `eval` entirely.

### Dashboard Specific
- [ ] CORS configured for known origins in production.
- [ ] No `CORSMiddleware(allow_origins=["*"])` in prod.
- [ ] Authentication tokens use HTTPS‑only cookies or secure headers.

## Remediation Priority
1. **Blocker** — fix immediately, do not merge.
2. **HIGH** — fix in the same PR.
3. **MEDIUM** — open a tracking issue.
4. **LOW** — note in PR description.

## Useful Commands
```bash
# Full security scan
conda run -n pipeline bandit -r autopire
conda run -n pipeline safety check
```
