# delivery-harness

[繁體中文](README.md) | **English**

An **agent-native feature/bug delivery pipeline harness** — skills + a state-machine engine for Claude Code.

---

## What this is

`delivery-harness` gives Claude Code a **repeatable, auditable workflow** for shipping features and fixing bugs, instead of letting the agent free-form its way through the work.

The problem it solves: an agent that improvises keeps its state in the conversation, leaves no record of *why* it did what it did, and has nothing stopping it from skipping steps. This harness moves the workflow's state **out of the model and onto disk**, on three load-bearing pieces:

- **The ticket is the single source of truth.** Each CR or bug is a markdown file at `docs/features/<NNN>-<slug>/ticket.md` whose frontmatter holds the phase, track, and acceptance criteria, and whose body accumulates gates, links, and a phase-change history. The agent reads the ticket first and acts from it — so a session run a week later picks up exactly where the last one stopped, on any machine.
- **The CLI is an enforced state machine.** `scripts/feature/cli.py` (`new` / `status` / `advance` / `lint`) is the *only* sanctioned way to change a ticket's phase or track. `advance` refuses illegal transitions and prints the legal set, so the agent can't quietly skip spec, plan, or UAT — the rules live in code, not in a prompt the model can talk itself out of.
- **The skills are phase-aware entry points.** `/feature` and `/bug` drive one ticket through its track; `/orchestrator` runs several in parallel. Beyond routing, the skills encode the operating discipline the pipeline depends on: read the ticket before acting, map existing code with a code graph before editing, gate each artifact (spec, plan, diff) through a fresh-context review subagent, and decide-and-proceed on reversible choices instead of stalling.

The payoff is delivery you can audit: every phase change is recorded in the ticket, every acceptance criterion is written before implementation, and the same ticket is resumable across sessions and machines.

The per-phase work is done by the generic development skills from [superpowers](https://github.com/obra/superpowers) (brainstorming, TDD, writing-plans, code review, …); delivery-harness adds the shell that wires them into a delivery pipeline with a state machine, tickets, prototype-first custom phases, and parallel orchestration. **superpowers is a required prerequisite** (see [INSTALL.md](INSTALL.md)).

---

## Tracks

| Track | Flow |
|-------|------|
| `full` | intake → requirements → UI prototype → spec → plan → implement → UAT → done |
| `lite` | intake → requirements → spec → plan → implement → UAT → done (no UI prototype) |
| `bug` | debug → reproduction test → spec → plan → TDD fix → verify → done |
| `spike` | intake → spike → promote to `full` or `lite` |

The table shows the forward "happy path." The state machine also models the messier reality: **rework loops** (a failed UAT routes back to spec or implement), **reopen edges** (a `lite` CR that turns out to need a prototype converts to `full`), **spike resolution** (`spike` promotes into `full` or `lite` once feasibility is known), plus **`on-hold`** parking and **`done` / `rejected`** terminal states. Illegal jumps are refused.

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
at human timescales (question, decision, delegate) while background agents do the slow work,
with `scripts/orch/wt.sh` giving each parallel implement its own isolated worktree.

---

## Structure

```
skills/
  feature/      # /feature skill — drives a CR through the full/lite/spike tracks
  bug/          # /bug skill — drives a bug through the bug track
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
  2026-06-23-integration-bundle-convention.md
```

---

## License

MIT — see [LICENSE](LICENSE).
