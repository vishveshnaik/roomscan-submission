# RoomScan

A local reconstruction and evidence-review prototype for the Applied AI case study. All three supplied scans are processed. The expanded pipeline extracts structural wall planes, observed free-space room candidates, local floor/ceiling planes, passage and bounded-wall opening candidates, and RGB surface anomaly proposals with depth-supported extent. These outputs require review; case-study accuracy is not established. Image-only COLMAP plus Apple Depth Pro is available as an experimental metric path, with explicit disconnected-view coverage and learned-scale uncertainty. See [the current analysis](docs/EXPANDED_ANALYSIS.md) and [compliance matrix](docs/COMPLIANCE.md).

Start with [the current geometry comparison](output/improvement-review/index.html) for revision 2. The [comprehensive review](output/comprehensive-review/index.html) retains the wider historical experiment set and links to the latest geometry review. Earlier `full-*` output and comparisons are baseline evidence.

## What is single_room.zip?

It is raw sensor input, not application code or a trained model. Inside `c00a170fe1/` are 1,715 depth PNGs (192 × 256, uint16 millimetres), 1,715 confidence PNGs (0/1/2), `rgb.mp4` (1920 × 1440, 1,715 frames), `odometry.csv` (poses and per-frame intrinsics), `camera_matrix.csv` and `imu.csv`. The recording lasts approximately 37.17 seconds and includes views of a living area and a bathroom. Its filename does not establish that it is exactly one semantic room.

Use it to exercise RGB-D import, depth projection, drift correction and floor-coverage reconstruction. It does not contain independent tape/laser ground truth, repeated captures, staged damage labels, competitor exports or the required complete three-tier benchmark.

## Additional datasets

The new floor-only and ceiling captures have also been processed. See [the dataset comparison](docs/ADDITIONAL_DATASETS.md). Local reviews are `output/floor-only/review.html`, `output/with-ceiling/review.html` and `output/dataset-comparison/review.html`. The ceiling scan supports a preliminary scan-wide 2.4486 m height estimate; per-room heights and accuracy remain unverified. The updated technical PDF and comprehensive review cover all three scans. The expanded reproduction ZIP preserves all inputs and current experiment evidence; the original smaller archive remains as historical evidence.

## Start on this computer

From this project directory:

```sh
./scripts/run-local.sh run /path/to/capture.zip --out output/my-capture
```

Open `output/my-capture/review.html` in a browser. It is a standalone local file; no server or account is required. The current example is `output/lidar/review.html`.

## Clean machine setup

Python 3.10+ on macOS/Linux/Windows. The LiDAR pipeline requires no API key or model weights. Optional visual metric reconstruction downloads Apple Depth Pro weights once and then runs locally.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m roomscan run /path/to/single_room.zip --out output/capture
```

On Windows use `.venv\Scripts\python.exe`. Setup under 15 minutes is a target, not a verified install-time result on every platform. Dependency download access is required for setup. Inference is offline. `requirements.txt` allows compatible versions; `requirements-lock.txt` records this run's exact library versions.

## Other input tiers

```sh
# Photos: one folder per room, JPEG/PNG/WebP (convert HEIC to JPEG first)
python -m roomscan run /path/to/property-photos --tier photos --out output/photos
# Walkthrough video
python -m roomscan run /path/to/walkthrough.mp4 --tier video --out output/video
# Drift ablation: same input with corrections disabled
python -m roomscan run /path/to/scan --out output/no-drift --no-drift
```

Without `--metric`, photo/video paths retain the lightweight relative two-view baseline. With `--metric`, COLMAP performs camera calibration, geometric matching and multi-view reconstruction; local Apple Depth Pro estimates a global metric scale. It never receives LiDAR or sensor poses. Fragmented reconstructions exclude unregistered images and do not establish a complete property plan. Metric estimates are uncalibrated and currently outside the required demonstrated accuracy.

The relative baseline always leaves metric dimensions unresolved, even when it recovers 3D points. Video sampling honors `--keyframes` in both modes (default 240); the former eight-frame shortcut could miss overlapping views in long walkthroughs. Metric runs distinguish `partial_reconstruction` from `unresolved` and `needs_review`; none of these statuses is a passed accuracy gate.

```sh
python -m pip install -r requirements-vision.txt
python -m pip install --no-deps git+https://github.com/apple-aiml-research/ml-depth-pro.git
python scripts/fetch-depth-model.py
python -m roomscan run /path/to/photos --tier photos --metric --out output/metric-photos
python -m roomscan run /path/to/video.mp4 --tier video --metric --out output/metric-video
# Stray Scanner RGB rasters in these ZIPs are sideways:
python -m roomscan run /path/to/rgb.mp4 --tier video --metric --rotate-cw --out output/metric-video
```

Weights are approximately 1.82 GB. CPU inference was measured locally; MPS was unavailable on this machine. Torch runs in a separate worker process from COLMAP because their OpenMP libraries conflict. Vendor attribution and model SHA-256 are recorded by the fetch script. These dependencies and fresh-machine setup time have not been verified on every platform.

## Outputs and evidence

- `result.json`: included provisional schema, provenance SHA-256 hashes, measurement status, error budgets, diagnostics and timing.
- `plan.svg` and `review.html`: preliminary observed-floor geometry with visible limitations.
- `cloud.ply` and `cloud.png`: LiDAR reconstruction; thin tiers save independent `relative-N.ply` clouds instead.
- Measurements are metres or square metres. Ranges are **uncalibrated engineering error budgets**, not statistical confidence intervals. Unresolved values and bounds are null.
- `opening_candidates` and `damage_candidates` contain unverified proposals. Damage candidates include masks, evidence frames, structural surface IDs, estimated area and inspection rules. They do not establish a damage diagnosis or authorize repair quantities. Empty candidate output does not establish an undamaged property.
- Optional `--evidence examples/evidence.json` accepts reviewed surface annotations and explicit adjacency. Human evidence is labelled. It cannot turn photo-only geometry into a successful automated stitch.

Independent LiDAR sessions have unrelated origins. The pipeline deliberately withholds a combined plan and footprint rather than treating their origins as aligned. A single continuous capture shares its world frame; morphological regions and touching-region adjacency remain candidates.

## Evaluate and reproduce

Fill `examples/ground_truth.json` from independent tape/laser measurements, following [INPUTS.md](docs/INPUTS.md), then:

```sh
python -m roomscan evaluate output/capture/result.json ground_truth.json --out output/benchmark \
  --repeat output/repeat/result.json --competitor competitor.json
python -m roomscan validate output/capture/result.json
python -m unittest discover -s tests -v
```

Evaluation counts missed and phantom openings, distinguishes repeatable height bias, checks wall and height thresholds, and compares shared competitor dimensions. Missing truth never passes; unknown Round 1 gates and uncalibrated intervals remain unevaluated. Capture IDs/surface IDs must be matched consistently before comparing independent sessions.

```sh
# Original failure versus shipped fix, from actual Git history
ROOMSCAN_PYTHON=.venv/bin/python ./scripts/fix-loop.sh /absolute/path/to/raw-scan
# On this Codex workspace use the bundled interpreter:
ROOMSCAN_PYTHON=.venv/bin/python ./scripts/fix-loop.sh /path/to/single_room.zip
```

The fix loop is a demonstrated software regression repair, **not** a proven benchmark gate improvement. Timing is excluded from determinism expectations; it varies by machine. Retain the original input ZIP alongside the repo to regenerate the recorded results.

## Architecture and next implementation work

`ingest.py` → `drift.py` → `geometry.py` → schema validation → `render.py`. The thin-input path is in `vision.py`; annotation rules are in `evidence.py`; scoring is in `evaluate.py`.

The current revision strengthens wall and opening evidence, but its room identities, boundary dimensions, ceiling heights and opening recall remain unverified. See [the implementation and comparison](docs/GEOMETRY_IMPROVEMENT.md). Next, collect tape/laser ground truth, repeat captures, and reviewed doorway labels following [CAPTURE_PROTOCOL.md](docs/CAPTURE_PROTOCOL.md) and [BENCHMARK_PLAN.md](docs/BENCHMARK_PLAN.md). Global pose-graph closure, damage models, calibrated intervals, and the missing published Round 1 schema and thresholds also remain outstanding.

References: [Stray Scanner format](https://github.com/strayrobots/scanner/blob/main/docs/format.md), [official capture app repository](https://github.com/strayrobots/scanner), [author's visualizer](https://github.com/kekeblom/StrayVisualizer/blob/main/stray_visualize.py). No source code from these projects is vendored. No pretrained models used.

## Expanded reproducible experiments

```sh
python scripts/cache-scans.py /path/to/scan --out output/cache
python scripts/run-structure-cache.py output/cache --out output/structure
python scripts/evaluate-metric-depth.py /path/to/scan --out output/depth-reference --count 8
python -m roomscan compare output/cache-source output/cache-target \
  --source-structure output/structure-source/structure.json \
  --target-structure output/structure-target/structure.json --out output/alignment
python scripts/run-visual-suite.py
python scripts/build-comprehensive-review.py
```

`--geometry baseline` preserves the original coverage-based geometry; `--no-damage` skips RGB anomaly processing. `--no-drift` supplies the correction ablation. Cross-capture comparison removes origin/yaw using rigid alignment and preserves sensor scale. Its discrepancy is consistency, not tape/laser accuracy.

The current six-page report is `output/pdf/technical-report.pdf`; `output/roomscan-expanded-reproduction.zip` contains all three unchanged input ZIPs, Git history and measured experiment evidence. `scripts/package-expanded.py` rebuilds the archive after `git bundle create output/roomscan-history.bundle --all`.
