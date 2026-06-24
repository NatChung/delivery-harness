# feature pipeline CLI

State machine + ticket I/O for the `/feature` delivery pipeline.
Stdlib Python 3 only (no install). Design: `docs/2026-06-17-feature-delivery-pipeline-design.md`.

## Commands (run from repo root)
- `python3 scripts/feature/cli.py new <slug> --track <full|lite|spike|bug> [--severity <P0..P3>]`
- `python3 scripts/feature/cli.py status <id>`
- `python3 scripts/feature/cli.py advance <id> --to <phase>`
- `python3 scripts/feature/cli.py lint <id>`

Tracks: `full|lite|spike` (feature) drive `/feature`; `bug` drives `/bug`
(`0-intake → bug-debug → bug-repro → bug-fix → bug-verify → done`).
Skills: `.claude/skills/feature/SKILL.md`, `.claude/skills/bug/SKILL.md`.

## Tests
`cd scripts/feature && python3 -m unittest -v`

## Modules
- `state_machine.py` — phases, tracks, legal transitions (pure)
- `ticket.py` — frontmatter parse/update, id allocation, history append
- `cli.py` — argparse wiring

State of record: `docs/features/<NNN>-<slug>/ticket.md` + `docs/features/INDEX.md`.
The agent-facing orchestrator is `.claude/skills/feature/SKILL.md`.
