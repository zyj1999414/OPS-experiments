# OPS portable experiment workspace

This directory contains the OPS implementation, ablation algorithms, experiment runners, and measured results. Large datasets are stored in the sibling `../data/` directory so this repository can be pushed to a private Git host without committing binary data.

## Layout

```text
OPS-portable/
├── repo/                 # Git repository: code, runners, results
│   ├── algorithms/
│   ├── work/
│   ├── outputs/
│   ├── requirements.txt
│   └── DATA_MANIFEST.sha256
└── data/                 # Copy separately or manage with Git LFS
    ├── SDB1/
    ├── ...
    └── SDB8/
```

## Environment

```bash
cd OPS-portable/repo
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

The original measurements were made with Python 3.9.4, NumPy 2.0.2, SciPy 1.13.1, psutil 7.2.2, and memory-profiler 0.61.0.

## Verify datasets

Run from the `OPS-portable` parent directory:

```bash
shasum -a 256 -c repo/DATA_MANIFEST.sha256
```

On Linux, use:

```bash
sha256sum -c repo/DATA_MANIFEST.sha256
```

## Important entry points

- `work/run_all_ops_algorithm.py`: common runner for all OPS ablations.
- `work/run_cached_fusion_ops_miner.py`: current OPS-Miner implementation.
- `work/run_final_compact_sdb1_8_ablation.py`: compact SDB1-SDB8 main experiment.
- `work/run_final_two_scalability_all_ablation.py`: latest two scalability experiments.
- `work/run_original_efo_sopp_first_window.py`: original EFO/SOPP single-window runner.

## Data format

The experiment datasets are little-endian float64 binary files. Read them using:

```python
import numpy as np
data = np.memmap(path, dtype="<f8", mode="r")
```

## New computer

Clone the private repository into `OPS-portable/repo`, restore the separate data directory as `OPS-portable/data`, create the Python environment, and open `OPS-portable/repo` as the Codex project.
