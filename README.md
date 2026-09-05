# BotBox

Tooling and scripts home for **Bot Box** — Angelo’s Grok Bot for tech work, scripts, and ops helpers.

Ship small, useful utilities. Prefer clarity over ceremony.

## Layout

```
scripts/   # runnable one-offs and ops helpers (shell / python)
tools/     # slightly larger utilities or CLIs
docs/      # short notes when a README section isn’t enough
```

## Quick start

```bash
# health check example
./scripts/healthcheck.sh

# python hello example
python3 scripts/hello.py
```

## Adding a tool

1. Put it under `scripts/` (simple) or `tools/` (multi-file / CLI).
2. Prefer portable shell or Python 3 — no heavy frameworks unless needed.
3. Make it executable when it’s a shell entrypoint: `chmod +x scripts/your-tool.sh`
4. Document the one-liner to run it in this README (or a short `docs/` note).
5. No secrets in the repo. Use env vars; keep examples in `.env.example` if needed.

### Naming

- Shell: `kebab-case.sh`
- Python: `snake_case.py`
- Keep names boring and searchable (`sync-calendar.py`, not `magic.py`)

## Conventions

- Fail loud: non-zero exit on error (`set -euo pipefail` in bash).
- Print usage on bad args.
- Prefer stdout for data, stderr for logs.
- Keep each script self-contained when possible.

## License

MIT — see `LICENSE`.

## Design notes

- [Secure bot communication sandbox](docs/secure-bot-sandbox.md) — multi-user bot messaging with web access (design v0)
