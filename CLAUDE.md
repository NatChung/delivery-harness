# delivery-harness — repo instructions for Claude

This repo is the **public upstream** of an agent-native feature/bug delivery
pipeline (skills + a Python state machine + worktree orchestration). What it is
and how to install it live in [README.md](README.md) and [INSTALL.md](INSTALL.md)
— read those first. The pipeline's design rationale is in `docs/*-design.md` and
`docs/*-convention.md`; read the relevant spec before changing pipeline behavior,
not this file.

## Two audiences, two modes

- **Upstream (this repo):** keep everything **generic and public-safe**. This is
  the template others fork.
- **A vendored fork (a "hub" that copied this in):** free to specialize —
  prefix the skills (`acme-feature`), fill in real codebases, accumulate
  project war-stories. Forks diverge on purpose; that's the model.

Improvements flow **fork → upstream by manual cherry-pick only** (low frequency,
sanitized). Upstream never auto-pushes into forks.

## Public-repo rules (non-negotiable here)

- **Never commit client identifiers, secrets, or machine paths.** No real
  company/product names, no `/Users/...`, no API keys, no internal hostnames or
  deploy-script behavior. This repo was extracted from a private codebase and
  sanitized; keep it that way. When adding examples, use neutral placeholders
  (`app`/`api`/`cms`/`chat`, `dark-mode`, `<your test runner>`).
- Before committing anything that could carry a leak (specs, skill bodies, test
  fixtures), grep the diff for obvious fingerprints.

## Layout is load-bearing — don't move it

The skills' bodies hardcode `python3 scripts/feature/cli.py` and
`scripts/orch/wt.sh`. Keep the engine at `scripts/feature/` and the worktree
helper at `scripts/orch/` so a fork can vendor `skills/` + `scripts/` unchanged.
Renaming a skill means rewriting its in-body cross-references too (feature/bug
point at `orchestrator`; orchestrator points at `feature`/`bug` and the
`/feature`, `/bug` slash invocations).

## Config seam

`scripts/orch/wt.sh` is the **only** consumer of `.claude/pipeline.config` (a
bash-sourceable file with `CODEBASE_DIR`, `CODEBASE_BRANCH`, `WT_CACHE_ROOT`).
Don't hardcode codebase paths or branch names in `wt.sh` or the skills — add
them to `pipeline.config`. The real config is gitignored (per-clone);
`config/pipeline.config.example` is the template that ships.

## Engine

`scripts/feature/{cli.py,state_machine.py,ticket.py}` — stdlib Python 3, no deps.
The state machine refuses illegal phase transitions; treat the CLI as the only
way to mutate a ticket's phase/track/id (don't hand-edit those fields).

Tests:
```bash
cd scripts/feature && python3 -m unittest -v
```
`cli.py new` also reads `docs/features/{INDEX.md,_template.md,_template_bug.md}`
at runtime — keep those present, and keep `INDEX.md` an empty registry in the
repo (header + separator, no data rows). Run a real `cli.py new` (not just the
unit suite — it self-fixtures) when changing scaffold-dependent behavior.

## Provenance:.harness-version

每個 fork install 時在 `.claude/skills/.harness-version` 戳裝自哪個 upstream commit(格式見 `config/harness-version.example`)。將來要把上游改善流進 fork,以此 commit 為 baseline:`git -C <upstream> log <commit>..HEAD -- skills/ scripts/` 看 fork 落後哪些改動。同步機制本身尚未自動化(手動 / AI 輔助)。

## Commits

Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). One logical change per
commit. Tests green before committing engine changes.
