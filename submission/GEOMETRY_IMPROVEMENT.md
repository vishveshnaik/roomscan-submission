# Geometry revision 2: implementation and evidence

Revision 2 tightens how the LiDAR pipeline turns sensor samples into room, wall and opening candidates. It is a software-quality improvement whose physical accuracy has not been measured.

## Changes

- `roomscan/topology.py` adds ray clipping at candidate wall rasters, camera-trajectory crossing checks that reject large pose jumps, and boundary/height support helpers.
- `roomscan/structure.py` separates observed free-space extent from inferred fill, retains holes in room polygons, requires stronger lower-face and vertical wall support, and leaves boundary lengths unresolved unless candidate wall geometry supports them. Unsupported watershed contacts are recorded as partition interfaces rather than openings.
- `roomscan/openings.py` requires supported jambs plus traversal or spanning-head evidence, and rejects occupied gaps.
- `roomscan/pipeline.py` validates that automatic adjacency has accepted opening evidence. Revision-tagged geometry IDs require explicit remapping of older annotations.
- `roomscan/render.py` distinguishes inferred boundaries and presents the support evidence and unresolved values in the review.

## Supplied-scan results

The source ZIPs were rerun with the current pipeline. Counts below describe algorithm candidates; they do not identify ground-truth rooms or walls.

| Capture | Space regions, earlier → current | Structural plane candidates, earlier → current | Opening candidates, earlier → current | Current boundaries with supported length / unresolved | Rays clipped at candidate walls |
|---|---:|---:|---:|---:|---:|
| Original | 3 → 3 | 12 → 7 | 2 → 0 | 9 / 182 | 2,315 |
| Floor only | 6 → 4 | 23 → 18 | 8 → 0 | 22 / 334 | 5,820 |
| With ceiling | 5 → 5 | 27 → 18 | 6 → 0 | 27 / 374 | 5,599 |

The new gates eliminate the earlier unsupported opening proposals, but none of the three supplied scans has an accepted opening candidate after the change. Real doorways may therefore be missed. Zero candidates does not mean a property has no doors. Likewise, more unresolved boundary lengths is explicit uncertainty, not evidence of better dimensional accuracy. The area method changed between versions, so area differences are not an accuracy comparison.

The same-revision drift ablation is in [`output/improvement-review/comparison.json`](../output/improvement-review/comparison.json). With ICP correction on/off, the candidate region counts are 3/2 (original), 4/4 (floor only), and 5/4 (with ceiling). These changes show sensitivity to drift handling, not correctness. The revised per-region ceiling candidates for the ceiling scan also moved materially upward for several regions; they remain uncalibrated and need physical measurement.

The recorded controlled software fixtures changed from 0/5 to 5/5 for rejecting unsupported gaps, pose jumps, painted gaps and short furniture faces while retaining a synthetic traversed doorway. Those fixtures exercise code behavior only; they do not establish performance on real buildings. The full visual review is [`output/improvement-review/index.html`](../output/improvement-review/index.html).

## Reproduction

Run the installed project from its root, substituting the path to each supplied ZIP:

```sh
python -m roomscan run /path/to/single_room.zip --out output/improved-original
python -m roomscan run /path/to/single_scan_floor_only.zip --out output/improved-floor-only
python -m roomscan run /path/to/single_scan_with_ceiling.zip --out output/improved-with-ceiling
```

For the same-version drift ablation, add `--no-drift`. Generated output includes the candidate plan, review page, machine-readable result and structural support diagnostics. Run `python scripts/build-improvement-review.py` after regenerating all three sets to refresh the comparison page.

## Still required

Independent tape/laser wall, opening, room-area and height measurements; repeated captures; reviewed doorway labels; capture-to-capture identity matching; and competitor exports are not present in these inputs. The case-study accuracy gates therefore remain unevaluated. Before using these candidates for decisions, measure representative spaces and openings, compare false positives and misses, calibrate error intervals, and revise the thresholds against that evidence.
