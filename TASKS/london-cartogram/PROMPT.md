# Prompt

You are running in an automated loop. Read these files before doing anything else:

1. `TASKS/london-cartogram/loop-state.md` — current task and progress (may not exist yet)
2. `TASKS/london-cartogram/run-log.md` — what previous iterations completed
3. `TASKS/london-cartogram/backlog.md` — the full task list
4. `prd-london-cartogram.md` — the authoritative product spec; consult when a task's intent is ambiguous

## Protocol

**If `loop-state.md` doesn't exist, or its `status` is `done`:**

- If `loop-state.md` exists with `status: done`, append a run-log entry for the just-completed task (see "Run-log format" below). Then delete or reset `loop-state.md`.
- If no unchecked `[ ]` tasks remain in `backlog.md` after applying the dependency rules (see "Picking the next task"), print `__PROMISE_RL_DONE__` on its own final line and exit. Do nothing else.
- Otherwise pick the next task (see below) and create `loop-state.md` with `status: in_progress`.

**If `status` is `in_progress` or `verifying`:**

- Resume from the existing checklist in `loop-state.md`. Do not restart the task.
- If the previous iteration crashed mid-edit, inspect the working tree first (`git status`, `git diff`) before making further changes.

**If `status` is `blocked`:**

- Append a `blocked` entry to `run-log.md` with the blocker description from `loop-state.md`.
- Move to `next_task` (also in `loop-state.md`) and reset `status` to `in_progress`. If `next_task` is empty, follow the "pick next task" path above.

## Picking the next task

Tasks have dependencies — see the **Dependency Graph** section in `backlog.md`.

1. Scan `backlog.md` for unchecked `[ ]` tasks in priority order (Phase 1 → Phase 6 as listed under "Priority Order").
2. Skip any task whose declared `Deps:` are not all checked `[x]`.
3. Claim the first eligible unchecked task by writing its ID into `loop-state.md` as `current_task`.
4. Identify the next-eligible task after it and record it as `next_task` (best-effort; can change if a different one unblocks).

## Loop-state format

```markdown
---
current_task: <task-id, e.g. CC-1>
status: in_progress | verifying | done | blocked
last_commit: ""
next_task: <task-id or empty>
blockers: ""
---

## Checklist

- [ ] Read task context (PRD section + files listed in task)
- [ ] Apply changes per "What to do"
- [ ] Run verification commands
- [ ] Backlog checkbox flipped to [x]
- [ ] Commit created (single coherent commit)

## Surprises

- (none yet)
```

## Run-log format

Append one entry to `run-log.md` per completed or blocked task:

```markdown
## <ISO-timestamp> | <task-id> | <done|blocked>

- **Commit:** <sha>
- **Verification:** <one line: what was run and the key observation>
- **Surprises:** <anything unexpected, or "none">
```

## Verification

This project has no automated test suite by design (see PRD non-goals). Verification is manual and structured per task.

**Global rules from the backlog ("How to Use This File"):**

- After build-pipeline changes (CC-2, BUILD-*, SCO-*, RM-*): `python3 build_commute_site_data.py` must run to completion. If the task description explicitly allows an intermediate failing state, the failure must be at the specifically named later point — capture the exact error in `loop-state.md`'s Surprises.
- After Phase 6 SVG-1: `python3 generate_london_rail_cartogram.py` must also run to completion.
- After UI changes (UI-*, CC-1 HTML edits, SCO-2 frontend edits): serve `site/` with `python3 -m http.server 8000` and open `http://localhost:8000/site/` in a browser to confirm the relevant interaction by eye.
- Each task's own "Verification" block in `backlog.md` is mandatory in addition to the above.

**For visual / interactive verification of UI tasks**, use the `playwright-cli` skill: navigate, screenshot, and inspect the running site at `http://localhost:8000/site/`. Pin origins, type postcode searches, and read on-page text via DOM queries. Capture a screenshot into `/tmp/` for inspection — do not commit screenshots.

**Commit rules** (from repo conventions and `~/CLAUDE.md`):

- One coherent commit per task.
- Imperative, lower-case commit messages without trailing punctuation, matching the existing repo style (e.g. `make maximum distance configurable and add outline option`).
- Include the backlog checkbox flip (`[ ]` → `[x]` in `backlog.md`) in the same commit as the task's other changes.
- British English in user-visible copy (titles, OG tags, README, About section, etc.).
- Never use `--no-verify`. If a pre-commit hook fails, fix the underlying issue.

## Completion rule

Only set `status: done` in `loop-state.md` when ALL of these are true:

- Code changes applied and committed (single commit).
- The task's specific "Verification" steps passed.
- The relevant global verification rule (above) passed.
- The backlog checkbox for this task is `[x]` and the change is part of the commit.
- `loop-state.md` has the commit SHA in `last_commit`.

If any one of these fails, do not mark `done`. Either mark `blocked` with a clear blocker, or remain `in_progress` and continue work.

## Surprises

When something unexpected comes up — data file with a different schema than the backlog assumed, a hidden coupling between modules, an off-by-one in coordinates — record it in `loop-state.md` under "Surprises". If it's likely to bite a future iteration or reader, capture it durably:

- Code-level surprises: inline code comment explaining the constraint.
- Process-level surprises: append to the relevant task's notes in `backlog.md`, or add a short ADR-style note at the bottom of `prd-london-cartogram.md` under a "Discovered constraints" heading.

## Reference

These resources are relevant when executing tasks:

- `prd-london-cartogram.md` — authoritative product spec; durable architectural decisions
- `backlog.md` — task list with per-task instructions
- `~/CLAUDE.md` / `~/AGENTS.md` — repo + author conventions (British English, MVP commits, commit style, etc.)
- `playwright-cli` skill — for visual / interactive verification of UI tasks
- Reference table in `backlog.md` — data source URLs (TfL OSI, ONS, Transitland, postcodes.io, Nominatim)
