# Physical benchmark collection still required

1. Choose a property containing at least three rooms plus a connector. Include a furnished room with removable simulated damage in two labelled classes. Photograph mirrors, glass, wet-look surfaces and dim corners. Record what is simulated versus naturally observed.
2. Capture the same rooms at the photo, video and LiDAR tiers. The photo tier must arrive as per-room folders, including connector views. Record device/app versions and retain all raw data unchanged.
3. Repeat at least one room at the same tier in a separate capture. Establish stable room, wall and opening identifiers independently from the algorithm's segmentation.
4. Take independent laser/tape ground truth for every wall, height, opening and damage extent. Record operator, device resolution, repeated measurement spread and uncertainty. Do not use scan-derived values as truth.
5. Capture two of the rooms with a consumer app such as Polycam or magicplan. Record app version and retain its export. Transcribe shared measurements with explicit ID mappings if a direct adapter is unavailable.
6. Run all captures with the same configuration. Retain command, library lock, source hashes, runtime, output, ground-truth mappings and scoring report. Separate development captures from held-out interval calibration captures.
7. Run drift on/off for the entire multi-room scan. Compare stitched footprint, topology and alignment against truth, not just registration residual. The local ICP implementation does not provide global loop closure and may fall short here.
8. Select the worst measured gate, write the one-page fix declaration before the change, predict a number, ship the fix, and regenerate before/after from raw inputs. Record any shortfall candidly. The included ceiling-coverage software repair is not a substitute for this scored physical fix loop.

Current evidence: one supplied 37.17-second RGB-D export, a video derived from it, and photos sampled from that video for software-path testing. Derived tiers are **not** independent captures and cannot satisfy benchmark composition. No verified accuracy, calibration, repeatability or head-to-head numbers exist yet.
