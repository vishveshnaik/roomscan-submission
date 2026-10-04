import json
import sys
from pathlib import Path
before,after=[json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
keys=['status','rooms','footprint_area','timing_seconds']
diff={k:{'before':len(before[k]) if k=='rooms' else before[k],
         'after':len(after[k]) if k=='rooms' else after[k]} for k in keys}
Path(sys.argv[3]).write_text(json.dumps(diff,indent=2)+'\n')
print(json.dumps(diff,indent=2))
