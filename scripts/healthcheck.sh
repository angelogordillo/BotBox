#!/usr/bin/env bash
# Quick environment sanity check for BotBox tooling.
set -euo pipefail

ok() { printf 'ok  %s\n' "$1"; }
fail() { printf 'fail %s\n' "$1" >&2; exit 1; }

command -v bash >/dev/null 2>&1 || fail "bash not found"
ok "bash $(bash --version | head -n1 | sed 's/^GNU Bash, version //;s/ .*//')"

if command -v python3 >/dev/null 2>&1; then
  ok "python3 $(python3 --version | awk '{print $2}')"
else
  fail "python3 not found"
fi

ok "cwd $(pwd)"
printf '\nBotBox healthcheck passed.\n'
