"""Download public vendor weights; no capture is transmitted."""
from pathlib import Path
import urllib.request
import hashlib,json
p=Path('models/depth_pro.pt');p.parent.mkdir(exist_ok=True)
url='https://ml-site.cdn-apple.com/models/depth-pro/depth_pro.pt'
if not p.exists():
 tmp=p.with_suffix('.partial');urllib.request.urlretrieve(url,tmp);tmp.replace(p)
h=hashlib.sha256()
with p.open('rb') as f:
 for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
if h.hexdigest()!='3eb35ca68168ad3d14cb150f8947a4edf85589941661fdb2686259c80685c0ce':
 raise ValueError('Weights checksum differs from the recorded reproduction checkpoint')
(p.parent/'depth-pro-manifest.json').write_text(json.dumps({'url':url,'sha256':h.hexdigest(),'bytes':p.stat().st_size,'source':'https://github.com/apple/ml-depth-pro','license':'https://github.com/apple/ml-depth-pro/blob/main/LICENSE'},indent=2)+'\n')
print('Local weights ready:',p)
