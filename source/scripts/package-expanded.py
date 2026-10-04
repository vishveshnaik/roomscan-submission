"""Preserve supplied inputs, Git history, actual experiment evidence and hashes."""
from pathlib import Path
import json,hashlib,zipfile,argparse
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
p=argparse.ArgumentParser();p.add_argument('captures',nargs='+');a=p.parse_args();files=[]
files.append((OUT/'roomscan-history.bundle','roomscan-history.bundle'))
for capture in a.captures:
 path=Path(capture).resolve();files.append((path,'inputs/'+path.name))
folders=['comprehensive-review','improvement-review','pdf']+[f'improved-{name}{suffix}' for name in ['original','floor-only','with-ceiling'] for suffix in ['', '-no-drift']]+[f'full-{name}{suffix}' for name in ['original','floor-only','with-ceiling'] for suffix in ['', '-no-drift']]+[f'alignment-{name}' for name in ['floor-ceiling','original-floor-only','original-with-ceiling']]+[f'damage-{prefix}{name}' for name in ['original','floor-only','with-ceiling'] for prefix in ['', 'filtered-']]+[f'depth-reference-{name}' for name in ['original','floor-only','with-ceiling']]+[f'metric-{tier}-{name}' for name in ['original','floor-only','with-ceiling'] for tier in ['photos','video']]+['metric-property-photos','property-photos','model-evaluation']
for folder in folders:
 for path in sorted((OUT/folder).rglob('*')):
  if path.is_file() and path.suffix.lower() in {'.json','.md','.svg','.html','.pdf','.png','.jpg','.bin','.txt','.npy'}:
   files.append((path,'artifacts/'+str(path.relative_to(OUT))))
for path in [OUT/'anomaly-contact-sheet.jpg',OUT/'anomaly-visual-review.json',ROOT/'models/depth-pro-manifest.json',ROOT/'tmp/depth-pro-source.tar.gz',ROOT/'third_party/ml-depth-pro-main/LICENSE']:
 if path.exists():files.append((path,'model/'+path.name if path.parent.name in ['models','tmp','ml-depth-pro-main'] else 'artifacts/'+path.name))
manifest=[]
for path,name in files:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 manifest.append({'path':name,'bytes':path.stat().st_size,'sha256':h.hexdigest()})
readme='''# Expanded RoomScan reproduction

Raw ZIP inputs are unchanged. This archive includes actual Git history and experiment evidence. No physical accuracy gate has passed; independent ground truth, repeats and competitor exports are absent.

    git clone roomscan-history.bundle source
    cd source
    python3 -m venv .venv
    .venv/bin/python -m pip install -e .
    .venv/bin/python -m roomscan run ../inputs/single_room.zip --out output/full-original

Repeat for the floor-only and ceiling ZIPs; use --no-drift for ablations. Read artifacts/improvement-review/index.html for geometry revision 2, artifacts/comprehensive-review/index.html for the historical broader review, and source/docs/GEOMETRY_IMPROVEMENT.md for implementation notes. The original scan and larger scans have unverified semantic correspondence.

Optional image-only metric path:

    .venv/bin/python -m pip install -r requirements-vision.txt
    mkdir -p third_party
    tar -xzf ../model/depth-pro-source.tar.gz -C third_party
    .venv/bin/python -m pip install --no-deps third_party/ml-depth-pro-main
    .venv/bin/python scripts/fetch-depth-model.py

The vendor source snapshot and full Apple license are included. Vendor weights are not bundled; their URL, size and exact SHA-256 are in model/depth-pro-manifest.json. All inference is local; no API key is required. Use --metric and --rotate-cw on sideways Stray Scanner RGB video. Derived inputs are not independent benchmark captures. Sparse reconstructed components do not establish complete property geometry.

Re-run python scripts/build-improvement-review.py after generating revision 2 outputs; python scripts/build-comprehensive-review.py rebuilds the historical broader dashboard; python scripts/build-report.py recreates the six-page PDF with reportlab. Saved controlled topology fixtures improved from 0/5 to 5/5; these software cases do not measure physical accuracy. Clean-machine setup time, operating-system compatibility and walk-in accuracy are unverified. Requirements/version documentation and actual Git history are included in the source bundle.

manifest.json records every included file hash and byte count. Large database, point-cloud and cache files can be regenerated from inputs and are omitted. Selected model depth predictions and COLMAP reconstruction components are preserved as experiment evidence.
'''
archive=OUT/'roomscan-expanded-reproduction.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
 for path,name in files:z.write(path,name,compress_type=zipfile.ZIP_STORED if name.startswith('inputs/') else zipfile.ZIP_DEFLATED)
 z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n');z.writestr('REPRODUCE.md',readme)
print(archive,archive.stat().st_size,len(files))
