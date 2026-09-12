# OPS experiment workspace

- Use `work/run_all_ops_algorithm.py` as the common ablation runner.
- The current OPS-Miner implementation is `work/run_cached_fusion_ops_miner.py` (`ScanAndFusionReuseMiner`).
- Ablation sources are in `algorithms/OPS-ablation/`.
- Large float64 datasets are stored outside the Git repository in sibling directory `../data/SDB1` through `../data/SDB8`.
- Dataset files use little-endian float64 (`<f8`) unless a script explicitly states otherwise.
- Do not overwrite existing JSON results. Create a new output directory for changed parameters.
- Report running time, Peak RSS, total frequent patterns, average patterns per window, and whether a value is measured or estimated.
- OPST-OPS reports maximal frequent patterns; do not compare its count directly with the full frequent-pattern count of other algorithms.
- Prefer five independent runs and the median for short scalability timings.
