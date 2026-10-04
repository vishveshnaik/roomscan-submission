"""Bundle local Git history, original input and actual reported outputs."""
import argparse
from pathlib import Path
import zipfile
import hashlib
import json

p=argparse.ArgumentParser();p.add_argument('input');args=p.parse_args()
root=Path(__file__).resolve().parents[1];out=root/'output';source=Path(args.input).resolve()
bundle=out/'roomscan-history.bundle'
if not bundle.exists():raise ValueError('First run: git bundle create output/roomscan-history.bundle --all')
files=[(bundle,'roomscan-history.bundle'),(source,'inputs/'+source.name)]
for folder in ['lidar','lidar-no-drift','fix-before','fix-after','photos','video','benchmark','pdf']:
    for file in sorted((out/folder).glob('*')):
        if file.is_file() and file.suffix in {'.json','.md','.svg','.html','.pdf','.png'}:
            files.append((file,'artifacts/'+folder+'/'+file.name))
if (out/'fix-diff.json').exists():files.append((out/'fix-diff.json','artifacts/fix-diff.json'))
manifest=[]
for file,name in files:
    h=hashlib.sha256()
    with file.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    manifest.append({'path':name,'bytes':file.stat().st_size,'sha256':h.hexdigest()})
readme='''# RoomScan reproduction bundle

Prototype: required case-study accuracy and benchmark evidence are incomplete.
No tape/laser truth, competitor export or independent three-tier benchmark is included.
The contained input is the user's original supplied scan, unchanged.

Extract this ZIP, then run:

    git clone roomscan-history.bundle source
    cd source
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements-lock.txt
    .venv/bin/python -m pip install --no-deps -e .
    .venv/bin/python -m roomscan run ../inputs/single_room.zip --out output/lidar
    .venv/bin/python -m roomscan run ../inputs/single_room.zip --out output/lidar-no-drift --no-drift
    ROOMSCAN_PYTHON=.venv/bin/python ./scripts/fix-loop.sh ../inputs/single_room.zip

The fix loop resolves input paths before switching checkouts. Windows uses .venv/Scripts/python.exe; fix-loop.sh needs a POSIX shell.

The artifacts folder contains actual reported runs and the technical report.
Capture hashes and library lock support reproduction; timings vary by machine.
No model downloads, API keys or remote inference are required. The build-report
script additionally needs reportlab if regenerating the PDF presentation.

To make derived photo smoke inputs (not physical benchmark evidence), run:

    .venv/bin/python scripts/make-derived-inputs.py ../inputs/single_room.zip --out derived-photos
    .venv/bin/python -m roomscan run derived-photos --tier photos --out output/photos

See source/docs/COMPLIANCE.md for unfinished work.
'''
with zipfile.ZipFile(out/'roomscan-reproduction.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for file,name in files:z.write(file,name)
    z.writestr('REPRODUCE.md',readme)
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
print(out/'roomscan-reproduction.zip')
