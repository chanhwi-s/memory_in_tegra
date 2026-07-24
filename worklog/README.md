# Worklog — cross-session handoff

This directory is how independent Claude Code sessions stay aware of each other's work.
Different sessions do not share memory, so this log is the shared understanding.

## Rules

**At the START of every session:**
1. Read `../OVERVIEW.md` (study context) and `../prompts/00_conventions.md` (rules).
2. Read the **most recent worklog entries** here (files sort chronologically by name) to learn
   current state: what's done, what's in progress, what's blocked, and any handoff notes.
3. Read any `findings.json` referenced by those entries if you will build on that work.

**At the END of every session:**
- Copy `_TEMPLATE.md` to a new file and fill it in. **Do not edit another session's entry** —
  always create a new file (append-only history).
- Filename: `YYYY-MM-DD-HHMM_<scope>.md`
  - `<scope>` = short slug of what you worked on, e.g. `phase1-impl`, `phase1-fix-timing`,
    `phase2-design`.
  - Example: `2026-07-24-1530_phase1-impl.md`
- Keep it factual and focused on **state + handoff**, not narration. The next session should be
  able to continue safely from your entry alone.

## Why one file per session
A single shared log would cause merge conflicts when sessions run in parallel or on different
machines. One timestamped file per session avoids that and still gives a clean chronological
history (`ls worklog/` = the project timeline).

## Relationship to `findings.json`
- `findings.json` = **structured numeric results** a phase produces for downstream phases to consume.
- worklog entry = **narrative state + handoff** ("I implemented X, decided Y, this is broken, do Z next").
Use both: put numbers in `findings.json`, put context and next-steps in the worklog.
