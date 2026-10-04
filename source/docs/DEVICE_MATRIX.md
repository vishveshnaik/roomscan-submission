# Device and accuracy matrix

| Device | Photos | Video | LiDAR | Current accuracy evidence |
| --- | --- | --- | --- | --- |
| iPhone 15 or newer, non-Pro | Native Camera | Native Camera | No supported built-in LiDAR route | No metric accuracy validated; thin-input scale unresolved |
| iPhone 15 Pro / Pro Max, or later LiDAR-equipped Pro device | Native Camera | Native Camera | Stray Scanner raw RGB-D export | One supplied recording processed; no laser/tape truth, no accuracy claim |
| Computer | Python 3.10+ | OpenCV decoding | NumPy/SciPy/Pillow processing | Executed on this Apple Silicon Mac; other platforms unverified |

The case study targets ±8% photo walls/footprint, ±3% video walls, 2 cm opening widths on at least 85%, 1.5 cm ceiling bias and 1 cm height spread, and wall repeatability of 1 cm or 0.5%. These are **requirements**, not delivered accuracy. Ranges in this prototype are broad, uncalibrated error budgets. Actual hardware compatibility, app version and export UI should be verified during field collection.
