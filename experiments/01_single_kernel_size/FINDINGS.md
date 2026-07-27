# Phase 1 Findings — Single-Kernel Memory-Hierarchy Characterization

Generated 2026-07-27T04:31:35Z from `experiments/01_single_kernel_size/results/phase1_results.csv`. All numbers below
are computed directly from that CSV by `scripts/derive_findings.py` — re-run it (do not
hand-edit) if the CSV is regenerated.

## Cache-tier bandwidth steps

- **L2-resident** up to read-footprint **1,048,576 bytes** (~1.00 MB)
- **L2+SLC-served** up to read-footprint **2,097,152 bytes** (~2.00 MB)
- **DRAM-bound** from read-footprint **4,194,304 bytes** (~4.00 MB) onward
- **Measured DRAM peak:** 179.2 GB/s

## Reuse crossover

Reuse stops lifting achieved BW above DRAM peak once read_footprint_bytes >= 4194304 (~4.0 MB); below that, higher reuse_N pushes BW above the 179 GB/s measured DRAM peak via cache hits.

## Saturation (minimum blocks to reach plateau, threads/block=256, reuse N=1)

- 32,768 bytes/buffer -> 32 blocks
- 65,536 bytes/buffer -> 64 blocks
- 131,072 bytes/buffer -> 64 blocks
- 262,144 bytes/buffer -> 64 blocks
- 524,288 bytes/buffer -> 64 blocks
- 1,048,576 bytes/buffer -> 64 blocks
- 2,097,152 bytes/buffer -> 256 blocks
- 3,145,728 bytes/buffer -> 256 blocks
- 4,194,304 bytes/buffer -> 1024 blocks
- 6,291,456 bytes/buffer -> 256 blocks
- 8,388,608 bytes/buffer -> 256 blocks
- 12,582,912 bytes/buffer -> 256 blocks
- 16,777,216 bytes/buffer -> 256 blocks
- 25,165,824 bytes/buffer -> 256 blocks
- 50,331,648 bytes/buffer -> 256 blocks
- 100,663,296 bytes/buffer -> 1024 blocks

## Threads-per-block check

256 threads/block confirmed near-optimal at the mid-size check (values: {128: 151.762, 256: 266.407, 512: 166.089})

## Compute-bound crossover observed?

No (as expected for AI ~= 0.08 flop/byte).

## Tier-boundary sanity (00_conventions.md / prompt Verification section)

Re-check these by eye against `results/plots/bw_vs_footprint.png`:
- Largest size (footprint >> 8 MB) should show ~no BW gain from reuse, BW ~= DRAM peak.
- Small size (footprint <= 4 MB) should show reuse pushing BW *above* DRAM peak (cache hits).
If either does not hold, treat this findings.json as suspect and STOP before Phase 2 consumes it.
