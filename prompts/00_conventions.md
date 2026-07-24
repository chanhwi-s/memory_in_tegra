# Shared Conventions — read before implementing ANY phase

> Every work-prompt (`prompts/NN_*.md`) assumes these conventions. They exist so that
> separate analyses stay isolated **and** can safely reference each other's results.
> Read this together with `../OVERVIEW.md`.

---

## 1. Directory-per-phase

Each analysis gets its own directory under `experiments/`, zero-padded and incrementally
numbered, with a short descriptive name (you choose the name):

```
experiments/
  01_single_kernel_size/
  02_two_kernel_symmetric/
  ...
```

Standard contents of each phase directory:
```
experiments/NN_name/
  src/            # CUDA/C++ sources for this phase only
  scripts/        # run + plot scripts (self-contained; runnable from repo root)
  results/        # CSVs + generated plots (committed)
  README.md       # how to build/run this phase + short prose summary of observations
  FINDINGS.md     # human-readable distilled conclusions (the numbers that matter downstream)
  findings.json   # machine-readable handoff (schema below)
```

**Isolation rules**
- A phase writes **only** inside its own `experiments/NN_name/` directory (plus `shared/env.md`, append-only).
- Never modify another phase's directory. If you need its numbers, **read** its `findings.json`.

---

## 2. Cross-phase handoff (so later analyses can build on earlier ones)

Later phases depend on earlier results (e.g. Phase 2 needs Phase 1's cache-tier boundaries
and per-size saturation block counts). Handoff happens through a **stable, versioned
`findings.json`** — never by hard-coding numbers or re-deriving them.

### Rules
1. Each phase, when finished, **must** write `experiments/NN_name/findings.json` and a matching human `FINDINGS.md`.
2. A phase that needs upstream results **reads** the specific `findings.json` it depends on and **echoes the values it consumed** into its own README (so provenance is traceable).
3. `findings.json` must include a `schema_version`, the `phase` id, a `generated_utc` timestamp, and a `source_csv` path. Downstream code should tolerate missing optional keys gracefully and **fail loudly** if a required upstream key is absent (do not silently substitute a guess).
4. If a later phase's measurements contradict an upstream finding, **do not overwrite** the upstream file — record the discrepancy in the current phase's `FINDINGS.md` and flag it.

### `findings.json` common envelope (all phases)
```json
{
  "schema_version": "1.0",
  "phase": "01_single_kernel_size",
  "generated_utc": "YYYY-MM-DDThh:mm:ssZ",
  "source_csv": "experiments/01_single_kernel_size/results/phase1_results.csv",
  "env_ref": "shared/env.md",
  "results": { "...phase-specific keys..." },
  "consumed": [ ]   // list of upstream findings.json paths this phase read, if any
}
```
Phase-specific `results` keys are defined in that phase's prompt.

---

## 3. Environment logging (reproducibility)

- On first run, write `shared/env.md` capturing: device model, L4T/JetPack version, CUDA version,
  driver version, `nvpmodel` mode, `jetson_clocks` state, locked GPU clock (MHz), SoC temperature,
  and any thermal notes. Later phases append their own run-time env block (append-only; never rewrite).
- Every results CSV row also carries `gpu_clock_mhz, power_mode, soc_temp_c, cuda_version, driver_version`
  so each measurement is self-describing.

---

## 4. Measurement discipline (applies to every phase)

- Fix power/clocks before measuring: `sudo nvpmodel -m 0` then `sudo jetson_clocks`.
- CPU idle, single GPU process, no concurrent GPU work unless that concurrency IS the experiment.
- Warm-up (≥3 untimed launches) before every measured cell.
- Time with CUDA events; ≥10 trials per cell; report median/min/max/stddev.
- Flag any cell with stddev/median > 5% for re-measurement.
- Report **plateau (saturated)** throughput: sweep block count until throughput flattens; block count is a knob, not a reported axis (unless a phase explicitly makes it one).
- Achieved bandwidth = bytes moved / time; cache residency legitimately pushes it above DRAM peak — that is signal, not error.

## 5. Worklog — session handoff (mandatory)

Independent Claude Code sessions do not share memory; the `worklog/` directory is the shared
state. See `../worklog/README.md` for the format.

- **At session start:** read the most recent `worklog/` entries (files sort chronologically) plus
  `../OVERVIEW.md` and this file, so you know what is done / in-progress / blocked before acting.
- **At session end:** create a **new** `worklog/YYYY-MM-DD-HHMM_<scope>.md` from `worklog/_TEMPLATE.md`.
  Never edit another session's entry (append-only history). Record: what you did, files touched,
  key decisions, findings produced (link the `findings.json`), blockers, and explicit next-steps.
- Numbers go in `findings.json`; narrative state + handoff goes in the worklog. Use both.
- **At session end, also print a suggested one-line git commit message in the chat** — English,
  imperative mood, ≤ 72 chars, summarizing the session's change (e.g.
  `Add Phase 1 A+B sweep harness and cache-tier plots`). Do not commit automatically; just recommend it.

## 6. Scope guards

- Do only what the current phase's prompt specifies. Do not pre-implement future phases
  (e.g. no zero copy in Phase 1, no green context before Phase 3).
- If a hardware assumption in `OVERVIEW.md` doesn't match measurements, document the
  discrepancy in the phase `README.md`; do not silently work around it.
