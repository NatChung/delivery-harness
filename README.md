# delivery-harness

An **agent-native feature/bug delivery pipeline harness** — skills + a state-machine engine for Claude Code.

> **Not affiliated with [Harness.io](https://harness.io)** (the CI/CD platform).
> This is a Claude Code skill harness: it wires Claude into a structured delivery workflow,
> not a CI/CD runner.

---

## What this is

`delivery-harness` is a reference implementation of the **Agent Harness** pattern:
a thin scaffold of markdown skills, a Python state machine, and bash orchestration scripts
that give Claude Code a repeatable, auditable workflow for shipping features and fixing bugs.

The agent doesn't free-form its way through work. Instead:

1. **A ticket** (`docs/features/<NNN>-<slug>/ticket.md`) holds all state — phase, track, acceptance criteria, links.
2. **`scripts/feature/cli.py`** enforces legal phase transitions and refuses illegal ones.
3. **Three skills** (`/feature`, `/bug`, `/orchestrator`) give Claude entry points that read the ticket and drive it forward — never guessing, always verifying.

The result is delivery you can audit: every phase change is recorded in the ticket, every AC is written before implementation, and running Claude a week later on the same ticket picks up exactly where it left off.

---

## Tracks

| Track | Flow |
|-------|------|
| `full` | intake → requirements → UI prototype → spec → plan → implement → UAT → done |
| `lite` | intake → requirements → spec → plan → implement → UAT → done (no UI prototype) |
| `bug` | debug → reproduction test → spec → plan → TDD fix → verify → done |
| `spike` | intake → spike → promote to `full` or `lite` |

---

## Quick start

See **[INSTALL.md](INSTALL.md)** for the three-step fork guide.

```bash
# after install:
python3 scripts/feature/cli.py new my-feature --track full
# then in Claude Code:
# /feature
```

---

## Parallel orchestration

For teams running multiple in-flight CRs simultaneously, `/orchestrator` dispatches
background subagents per feature and coordinates their reports — keeping the main loop
at human timescales (question, decision, delegate) while background agents do the slow work.

---

## Prior art

[`heliohq/ship`](https://github.com/heliohq/ship) is a prior-art project with the same
core concept (structured agent delivery pipeline). `delivery-harness` takes a different
angle — tighter Claude Code skill integration, explicit state-machine enforcement, and
parallel-orchestration primitives — but the conceptual lineage overlaps. Detailed
differentiation write-up TBD.

---

## Relation to Agent Harness course / Harness Notes

This repo is the **reference implementation** accompanying the
**Agent Harness** course and the
[Harness Notes](https://natchung.beehiiv.com) newsletter.
The course teaches the harness pattern from first principles;
this repo is what the pattern looks like in production.

---

## Structure

```
skills/
  feature/      # /feature skill — drives a CR through the full/lite/spike tracks
  bug/          # /bug skill — drives a defect through the bug track
  orchestrator/ # /orchestrator skill — parallel multi-CR coordination
scripts/
  feature/      # cli.py + state_machine.py + tests
  orch/         # wt.sh — worktree management for parallel runs
config/
  pipeline.config.example   # codebase map template (copy → .claude/pipeline.config)
hooks/
  settings.snippet.json     # merge into .claude/settings.json
mcp/
  .mcp.json.example         # optional: Playwright / mobile test MCP
docs/
  2026-06-17-feature-delivery-pipeline-design.md   # full spec
  2026-06-23-parallel-feature-orchestrator-design.md
  2026-06-23-stg-review-bundle-convention.md
```

---

## License

MIT — see [LICENSE](LICENSE).
