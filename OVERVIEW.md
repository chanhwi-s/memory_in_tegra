# Research Overview — Green Context & Zero-Copy Efficiency on Jetson AGX Orin

> Master context document. Single source of truth for the study's goals, hypotheses,
> axes, and phased roadmap. Every work prompt and experiment references this file.

---

## 0. Platform

- **Device:** NVIDIA Jetson AGX Orin 64GB — iGPU with **unified memory** (CPU/GPU share physical DRAM).
- **GPU:** Ampere, `sm_87`. 16 SMs × 128 CUDA cores = 2048 cores, max ~1.3 GHz.
- **Memory hierarchy (GPU read path): L1 → L2 → SLC → DRAM**
  - L1 / shared (unified): **192 KB per SM**, private per-SM.
  - L2: **4 MB**, shared across all 16 SMs.
  - SLC (system-level cache): **4 MB**, shared between CPU and GPU, sits between DRAM and L2/L3.
  - DRAM: 64 GB LPDDR5, 256-bit, ~204.8 GB/s theoretical peak.
- Tier boundaries used throughout: read working set ≤ 4 MB (L2-resident), ≤ ~8 MB (L2+SLC), > ~8 MB (DRAM-bound).

---

## 1. What we are studying

Two GPU optimization mechanisms on the Orin iGPU, and how their benefit depends on workload:

### Green context
CUDA green contexts let us **partition SMs** between concurrent kernels (e.g. kernel A → SMs 0–7, kernel B → SMs 8–15) so no SM is shared. What this actually isolates:
- **L1 / shared memory** (per-SM) — no cross-kernel L1 pollution.
- **Occupancy / registers** — kernels don't compete for warp slots on a shared SM.
- **Scheduling contention + predictability** — each kernel gets a fixed SM pool instead of the block scheduler interleaving both.

**Important:** green context does **NOT** partition L2 or SLC (both are globally shared). So green context is an **L1 + scheduling** tool. L1 inter-launch reuse is normally fragile (the scheduler shuffles blocks across SMs between launches); green context stabilizes it.

### Zero copy
Route a kernel's reads **around the GPU cache**, straight to DRAM. This targets the **L2 / SLC** shared-cache level that green context cannot touch. Rationale: when the combined working set of two kernels exceeds cache, forcing the large/streaming kernel to bypass cache removes its **cache pollution / SLC contention**, potentially freeing cache for the other kernel.

### The key interaction: reuse
Zero copy avoids pollution but forgoes cache reuse. So its benefit **flips with the reuse level**:
- Low/no reuse → each byte read once → cache gave little → bypass is neutral or a win.
- High reuse → cache would have served repeat reads → bypass loses.
The study maps **where that crossover sits** across working-set size and reuse.

---

## 2. Analysis axes (kept strictly separated — this is the whole point)

| Axis | Meaning | Notes |
|---|---|---|
| **working-set size** | per-buffer bytes S; read footprint = 2·S | swept to cross L1/L2/SLC/DRAM tiers |
| **reuse N** | **full-buffer reuse via N repeated launches** over the identical buffers | inter-launch reuse; nothing changes between launches |
| **kernel count** | 1 kernel (Phases 1) → 2 kernels (Phases 2+) | |
| **symmetry** | equal-size vs asymmetric (one fixed small, other grown) | Phase 2b |
| **green context** | SM partition on/off | Phases 3+ |
| **zero copy** | cache-bypass on one kernel | Phases 4+ |

**Fixed/controlled across the study (unless it is the swept axis):**
- Access pattern = **uniform / fully coalesced** (thread i → element i). (Strided/scatter are a possible later extension, not now.)
- Power: `nvpmodel -m 0` (MAXN) + `jetson_clocks`, locked GPU clock.
- CPU idle; single GPU process; no concurrent GPU work.
- Reuse always means "same buffers, N launches, no re-init between launches."

### Definitions pinned down
- **Reuse = inter-launch, full-buffer.** Not intra-kernel loops, not ML-style partial reuse (same weights / new activations). Everything is re-read identically each launch.
- **Kernel = element-wise `C = A + B`, float.** Deliberately memory-bound (arithmetic intensity ≈ 0.08 flop/byte) → **no compute-bound crossover expected.** The "roofline" is the **bandwidth ceiling of each cache tier**, not compute-vs-memory. (A high-intensity matmul is kept as an *optional* later compute-bound contrast workload only.)
- **Block count is a saturation knob, not a reported axis.** For each cell, grid is swept until throughput plateaus; the plateau is reported. Grid-stride loop decouples block count from data size. Per-SM working set (relevant to L1 / green context) is engineered later via block granularity + partitioned slices.

---

## 3. Phased roadmap

Each phase lives in its own `experiments/NN_shortname/` directory and hands results to later phases via a `findings.json` + `FINDINGS.md` (see `prompts/00_conventions.md`).

- **Phase 1 — Single-kernel memory-hierarchy characterization.** A+B, size × reuse sweep, zero copy OFF, green context OFF. Find the cache-tier bandwidth steps (L1/L2/SLC/DRAM), measured DRAM peak, and per-size saturation block counts. Foundation for everything.
- **Phase 2 — Two kernels, size sweep.**
  - 2a symmetric: grow both equally, find the throughput roofline / contention onset.
  - 2b asymmetric: one fixed at 1 MB, grow the other to k MB (k chosen at the cache-overflow / bound-crossover point found in Phase 1).
- **Phase 3 — Green context on the Phase 2 roofline points.** Compare partitioned vs shared SMs at (and just below, ~90%) the contention onset. Expect gains where per-SM working set is near L1 and where scheduling/L1 contention was hurting.
- **Phase 4 — Add zero copy on one kernel** (on top of Phase 2/3 configs). If bypassing cache on the large/streaming kernel helps, the bottleneck was memory (L2/SLC) bound, not compute. Sweep reuse to locate the crossover where zero copy stops helping.

---

## 4. Why this rewrite exists

The prior version mixed axes (size / count / symmetry / green context / zero copy / reuse) simultaneously, so effects couldn't be attributed. This study **isolates one axis at a time**, carries clean baselines forward, and records every environment parameter for reproducibility.

## 5. Repository layout

```
memoryintegra/
  OVERVIEW.md                 # this file
  prompts/                    # English work-prompts handed to Claude Code, one per phase
    00_conventions.md         # shared rules every phase follows (layout, findings handoff, env logging)
    01_single_kernel_size.md
    02_...                    # added as each phase is designed
  experiments/                # Claude Code creates one dir per phase
    01_single_kernel_size/
      src/ scripts/ results/ README.md
      FINDINGS.md             # human-readable distilled results
      findings.json           # machine-readable handoff for later phases
  shared/
    env.md                    # environment log (hardware, CUDA/driver, clocks) — written once, referenced by all
```
