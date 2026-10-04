"""Build a source-only package without supplied scans or scan-derived artifacts."""
from pathlib import Path
import hashlib
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DEST = OUT / "roomscan-shareable.zip"
DOCS = {
    "docs/BENCHMARK_PLAN.md",
    "docs/CAPTURE_PROTOCOL.md",
    "docs/DEVICE_MATRIX.md",
    "docs/FIX_LOOP.md",
    "docs/HANDOVER.md",
    "docs/INPUTS.md",
}
ROOT_FILES = {
    ".gitignore",
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-lock.txt",
    "requirements-vision.txt",
}

tracked = subprocess.check_output(
    ["git", "ls-files", "-z"], cwd=ROOT
).decode().split("\0")
paths = []
for name in filter(None, tracked):
    if name in ROOT_FILES or name in DOCS or name.startswith(
        ("roomscan/", "scripts/", "tests/", "examples/")
    ):
        path = ROOT / name
        if path.is_file():
            paths.append((path, f"RoomScan/{name}"))

history = subprocess.check_output(
    ["git", "log", "--reverse", "--format=%h\t%cs\t%s"], cwd=ROOT
).decode()
notes = """# Shareable RoomScan source package

This package contains the RoomScan source, setup files, selected benchmark/capture
guidance, examples, and tests. It does not contain the ZIP datasets supplied with
the assignment, raw sensor data, scan-derived floor plans/images/point clouds,
generated reports, model weights, caches, or a virtual environment. The datasets
were provided by someone else, so this package avoids redistributing them or
derived views of the properties.

This is a source snapshot plus a commit list, not a complete reproduction bundle.
To reproduce dataset-specific results, obtain authorization and the original input
ZIPs separately. Physical accuracy remains unverified; the included protocol and
benchmark plan describe evidence still needed. No license is granted for code
reuse by this package; share it for assignment review unless a separate license
is agreed.

Setup: use Python 3.10+, create a virtual environment, install `-e .`, and run
`python -m roomscan --help`. See `README.md` and `docs/CAPTURE_PROTOCOL.md`.

## Commit history

""" + "\n".join(f"- `{line.split(chr(9), 1)[0]}` · {line.split(chr(9), 1)[1]}"
                for line in history.splitlines()) + "\n"

files = [(p, n) for p, n in paths]
files.append((None, "RoomScan/SHAREABLE_PACKAGE.md"))
manifest = []
DEST.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(DEST, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path, name in files:
        content = notes.encode() if path is None else path.read_bytes()
        z.writestr(name, content)
        manifest.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
    manifest_text = "\n".join(manifest) + "\n"
    z.writestr("RoomScan/MANIFEST.sha256", manifest_text)
print(f"Created {DEST} ({DEST.stat().st_size:,} bytes; {len(files)} files plus manifest)")
