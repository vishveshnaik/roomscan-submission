# Interim RoomScan submission

This package contains the source snapshot, case-study documents, six-page technical report, and selected software evidence. It intentionally excludes Git metadata/history, raw datasets, point clouds, image/video frames, model weights, caches, and the original home video.

## Included

- Portable source snapshot and setup instructions
- Compliance matrix, capture protocol, device matrix, benchmark plan, fix-loop notes, geometry notes
- Six-page technical report
- Geometry comparison data and before/after software fix result JSON
- Real iPhone video evidence supplement and sanitized aggregate run statistics
- Checksummed file manifest

## Known submission gaps

- No independently measured wall, floor-area, doorway, or ceiling-height ground truth for the supplied scans
- No completed same-property benchmark across photo, video, and LiDAR tiers
- No repeat-capture accuracy result, staged-damage benchmark, consumer-app head-to-head, or live walk-in result
- Video sampling and result-status bugs have been fixed and covered by regression tests. A new landscape home video yielded a partial metric reconstruction of a local fragment, with disconnected camera groups and unknown ceiling height. This is not a complete property plan or a verified accuracy result. Private home videos, frames, and derived geometry are excluded.
- The fresh-machine under-15-minute setup and capture protocol have not been field-validated

The PDF report contains derived visuals from the supplied assignment scans. Share it only with the assignment evaluator and according to the data owner's sharing terms. The larger reproduction archive is separate and includes the supplied raw scans and derived scan artifacts; confirm that it may be returned before sharing it. This is an interim prototype submission, not a claim that the physical accuracy gates passed.


## Packaging note

The phone handover guide is maintained separately for the friend lending the device. Protocol, device matrix, benchmark plan, and fix-loop documentation appear once under `source/docs/`; duplicate copies were removed. The full private iPhone result JSON is excluded. Only aggregate nonvisual statistics appear in `evidence/real-video-summary.json`; see `submission/REAL_VIDEO_EVIDENCE.md` for what the run demonstrates and what remains unverified. Generated HTML dashboards are not included; use this report and the included comparison/fix JSON for this interim package. The source README also describes workspace outputs that are not bundled here.
