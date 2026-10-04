# Missing-ceiling fix declaration and outcome

**Observed failure.** The supplied scan's initial software run returned zero floor regions and an unresolved plan. It contained strong floor evidence but no well-supported floor/ceiling pair. Independent measurement gates could not be ranked because laser/tape truth was absent; this is a software failure declaration, not the case study's scored worst-gate declaration.

**Root-cause hypothesis.** `horizontal_levels()` returned no floor whenever it could not find a ceiling 1.8-4.5 m above a supported low plane. The floor-coverage extractor consequently discarded usable floor points. Evidence: the uncorrected cloud had a strong floor mode near -1.48 m world Y, while the camera clip mostly saw furniture, walls and floor, not a full ceiling.

**Predicted repair.** Keep a supported low horizontal plane even without a ceiling; produce at least one observed-floor polygon and leave ceiling height null. Do not widen a guessed ceiling interval to imply observation.

**Shipped change.** Baseline commit `503a331` contains the ceiling-coupled behavior. Commit `8f53ffe` decouples floor recovery from ceiling recovery and adds a synthetic missing-ceiling regression test. `scripts/fix-loop.sh` exports the actual baseline code and runs both versions with drift disabled to isolate the change.

**Result.** On the supplied raw scan: zero floor regions before, two coverage regions after. After-fix uncorrected coverage area was 15.4888 m² with a deliberately broad, uncalibrated range [10.2373, 20.7403]. Ceiling height remained unresolved. The small second region may be a fragment rather than a semantic room. A readable machine diff is `output/fix-diff.json`.

**Limits.** This repairs lost floor output. It does not demonstrate that the wall, ceiling, opening or whole-property accuracy gate moves from fail to pass. The resulting outline follows visible floor coverage and occlusions. Semantic-room segmentation and wall fitting remain work to do. The real worst-gate fix loop must follow independently measured physical benchmarking.
