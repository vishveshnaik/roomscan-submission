# Input and output contracts

LiDAR input accepts a Stray Scanner folder, a parent folder, or a ZIP. Poses use `timestamp,frame,x,y,z,qx,qy,qz,qw` plus optional `fx,fy,cx,cy`. Quaternion ordering is xyzw; poses are camera-to-world in the export's OpenCV camera convention. Intrinsics scale from the actual RGB resolution to the depth resolution, independently in x and y. Depth must be uint16 millimetres and a matching confidence PNG must exist for each sampled frame. Invalid depths, values above 6 m and confidence below 2 are removed. Video/pose frame count mismatch is rejected. Timestamps and indices are retained; count matching does not by itself establish exact sensor exposure synchronization.

Photo inputs are folders containing JPEG/PNG/WebP, with one subfolder per room; two to eight photos is the case-study target. Undecodable HEIC is rejected with conversion guidance. One photo still produces an unresolved result. Video inputs use an MP4 file or a folder with MP4s. The model-free baseline samples eight frames and estimates relative geometry for the best verified two-view pair. It does not integrate all camera poses or establish scale.

`roomscan/schema.json` is a **provisional** schema because the published Round 1 schema was not included in the supplied PDF. All measurement objects contain value, lower/upper bounds, unit, method, status and interval type. Unresolved measurement triples are null; numerical error budgets are explicitly uncalibrated. No nominal confidence level is assigned. `polygon` and wall endpoints are world X/Z metres on the LiDAR path, and absent on thin-input unresolved rooms. `status=candidate` does not certify a structural surface.

Ground truth example:

```json
{
  "independent_measurements": true,
  "measurements": {
    "c00a170fe1-room-1/wall/c00a170fe1-room-1-wall-1": 4.12,
    "c00a170fe1-room-1/ceiling_height": 2.48,
    "c00a170fe1-room-1/opening/door-1": 0.82,
    "property/footprint_area": 26.5
  },
  "adjacency": [["room-a", "room-b"]],
  "no_overlaps_verified": true
}
```

These numbers illustrate syntax only; they are not measurements of the supplied room. Ground truth must cover every real opening. Missed openings and predicted IDs absent from truth are scored as misses. ID matching must be independently reviewed, with stable room/surface IDs across repeated captures. The current extractor's automatically generated IDs are not guaranteed stable across captures.

Competitor input has `app`, `version`, `export_file` and a `measurements` mapping using the same IDs. Retain the original app export and disclose any manual transcription. The evaluator compares shared dimensions only; missing shared dimensions cannot establish the required benchmark composition.

Optional evidence:

```json
{
  "damage": [{
    "id": "damage-1", "room_id": "scan-room-1", "surface_id": "scan-room-1-wall-1",
    "class": "water_stain", "polygon_uv": [[0.1,0.1],[0.3,0.1],[0.3,0.4]],
    "area_m2": 0.15, "uncertainty_m2": 0.05
  }],
  "adjacency": [{"room_a": "scan-room-1", "room_b": "scan-room-2"}]
}
```

UV coordinates are normalized reviewed surface coordinates, not a detected image mask. Classes are `water_stain`, `crack`, `mold_suspected`, `material_loss`. Water staining triggers a moisture-check rule; suspected mold triggers specialist review. Flags are prompts for inspection, not confirmation of concealed damage. Scope actions are inspect/document quantities keyed to surfaces; no automatic repair or cost estimate is asserted. Negative damage inference, trained class recognition and image-to-surface metric projection are not implemented.
