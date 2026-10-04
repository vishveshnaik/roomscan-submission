# Compliance matrix

Status refers to demonstrated behavior, not the existence of a field or placeholder.

| Requirement | File path | Artifact/evidence | Status |
| --- | --- | --- | --- |
| Stock capture route | docs/CAPTURE_PROTOCOL.md | Stray Scanner + native Camera draft | Written; field install/export verification pending |
| Device and accuracy matrix | docs/DEVICE_MATRIX.md | Hardware/tier table with disclosed unknowns | Written; accuracy unverified |
| One command per capture | roomscan/cli.py | output/lidar/result.json, review.html | Working locally |
| Fresh-machine setup <15 min | README.md, requirements-lock.txt | Installation commands | Not timed on a clean machine |
| LiDAR depth/poses/intrinsics | roomscan/ingest.py | 1,715-frame export imported | Implemented and tested |
| Floor area and dimensioned surfaces | roomscan/structure.py | output/improvement-review/index.html; revision 2 yields 3/4/5 region candidates | Wall-constrained observed-space candidates; 9/22/27 supported-length boundaries and 182/334/374 unresolved; accuracy unverified |
| Ceiling height | roomscan/geometry.py | Unresolved on supplied capture | Plane estimate exists when supported; real accuracy unverified |
| Openings and 2 cm gate | roomscan/evaluate.py | Missed/phantom scoring tests | Passage and bounded-wall-gap candidates implemented; jamb accuracy gate not measured |
| Multi-room stitching | roomscan/geometry.py | Shared-world floor regions | Partial; semantic adjacency unverified |
| Photo folders to metric whole-property plan | roomscan/vision.py | Relative geometry or unresolved results | Experimental image-only SfM + learned metric depth implemented; incomplete coverage and contract accuracy unverified |
| Video metric plan | roomscan/vision.py, roomscan/thin.py | Configurable temporal sampling, adjacent-pair relative reconstruction, optional multi-view learned metric path | Real iPhone walkthrough demonstrated partial reconstruction: 24/240 frames in largest connected component, 24 disconnected components, one local candidate region. See submission/REAL_VIDEO_EVIDENCE.md and evidence/real-video-summary.json. Complete property plan and metric accuracy unverified |
| Damage class and metric extent | roomscan/evidence.py | Optional reviewed annotation | Classical anomaly proposals, masks and planar depth projection implemented; damage classes unvalidated |
| Concealed damage rule disclosure | roomscan/evidence.py | Inspection flags with rule IDs | Inspection rule IDs implemented for reviewed evidence and unverified anomaly candidates |
| Surface-keyed scope items | roomscan/evidence.py | Inspection quantities | Partial; complete remediation scope not implemented |
| Confidence interval on every measurement | roomscan/geometry.py | Explicit unknowns / uncalibrated ranges | Calibrated confidence intervals not implemented |
| Published schema | roomscan/schema.json | Provisional JSON schema | Blocked by missing published Round 1 schema |
| Rendered plan | roomscan/render.py | output/comprehensive-review/index.html and per-capture SVG/HTML | Implemented preliminary visualization |
| Drift handling on/off | roomscan/drift.py | output/improved-{capture} vs output/improved-{capture}-no-drift | Bounded ICP implemented and ablated within geometry revision 2; no global loop closure or footprint gate proof |
| Mandatory physical benchmark | docs/BENCHMARK_PLAN.md | Collection protocol | Not collected |
| Repeatability and height bias | roomscan/evaluate.py | Synthetic regression tests | Evaluator exists; physical results absent |
| Head-to-head >=70% on two rooms | examples/competitor.json | Input adapter format | App exports and measurements absent |
| Worst-gate fix declaration | docs/FIX_LOOP.md | Software missing-ceiling repair | Demonstrated software fix; scored physical gate loop absent |
| Regenerable before/after | scripts/fix-loop.sh | output/fix-before, fix-after, fix-diff.json | Working from actual baseline commit |
| Technical report <=6 pages | output/pdf/technical-report.pdf | Updated report with three-capture comparisons | Written with measured software experiments and limitations |
| Reproduction bundle | README.md, scripts/, requirements-lock.txt | Raw ZIP preserved in Downloads; source hashes | Working for current software runs; physical benchmark missing |
| Process evidence | Git history | Incremental implementation commits | Actual work history recorded; no fabricated history |
| Reflective/low-light failure modes | docs/TECHNICAL_REPORT.md | Failure-mode analysis | Discussed; not benchmarked |
| Cold walk-in test, all tiers | roomscan/pipeline.py | Ingest paths execute | Not ready for required metric/topology accuracy |

The PDF refers to additional Round 1 gates and a published schema without including them. These external specifications are needed for complete conformance. Physical evidence cannot be manufactured from this ZIP.

The expanded analysis and baseline result index are in docs/EXPANDED_ANALYSIS.md and output/comprehensive-review/summary.json. Current geometry evidence is in docs/GEOMETRY_IMPROVEMENT.md and output/improvement-review/comparison.json. Cross-capture consistency and paired sensor comparison are not physical accuracy gates. The anomaly fixture filter is a software repair, not a scored damage benchmark.
