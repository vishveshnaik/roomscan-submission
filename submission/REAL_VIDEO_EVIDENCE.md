# Real iPhone video evidence supplement

An actual landscape iPhone home walkthrough was processed with the optional multi-view metric pipeline. The result was `partial_reconstruction`: 240 frames were sampled, 24 disconnected reconstruction components were found, and the largest component registered 24 frames. The pipeline produced one local candidate region.

This demonstrates real-video ingestion and partial geometry recovery. It does not demonstrate a complete property plan, accurate dimensions or area, verified ceiling height, or passing the assignment's physical accuracy gates. Independent measurements and the full benchmark remain pending.

Two software defects were corrected: the lightweight video path previously forced eight sampled frames, and the overall visual status previously overwrote successful metric results with `unresolved`. The lightweight two-view mode still has no real-world scale by design. The 45-test suite passed after the fixes, including video sampling and result-status regressions.

`evidence/real-video-summary.json` contains selected nonvisual run statistics extracted from the local result. The private video, extracted frames, camera poses, point clouds, and home geometry are excluded. These aggregate statistics cannot independently reproduce or validate the private run.

The six-page technical report describes the earlier supplied-dataset experiments. Read this supplement for the later real-video test; it does not replace the report's accuracy limitations.
