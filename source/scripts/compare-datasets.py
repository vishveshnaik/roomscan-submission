"""Compare observed coverage and sensor evidence without claiming accuracy gates."""
import argparse
import html
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('runs',nargs='+',help='Directories containing result.json and plan.svg');p.add_argument('--out',required=True);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
records=[];plans=[]
for run in a.runs:
 path=Path(run);r=json.loads((path/'result.json').read_text());d=r['diagnostics'][0];levels=d['geometry']['levels'];height=next((room['ceiling_height'] for room in r['rooms'] if room['ceiling_height']['value'] is not None),None)
 record={'capture_id':r['capture_id'],'provenance':r['provenance'],'configuration':r['configuration'],
         'frames':d['input']['pose_count'],'duration_seconds':d['input']['duration_seconds'],
         'sampled_frames':d['input']['sampled_frames'],'candidate_regions':len(r['rooms']),
         'floor_coverage_area':r['footprint_area'],'global_ceiling_height':height,
         'floor_support_points':levels.get('floor_samples',0),'ceiling_support_points':levels.get('ceiling_samples',0),
         'accepted_drift_corrections':d['drift']['accepted_frames'],'timing_seconds':r['timing_seconds']}
 nodrift=path.with_name(path.name+'-no-drift')/'result.json'
 if nodrift.exists():
  baseline=json.loads(nodrift.read_text());record['floor_coverage_area_without_drift']=baseline['footprint_area']
 records.append(record);plans.append((path/'plan.svg').read_text())
comparison={'status':'descriptive_only','same_property_confirmed':False,
            'warnings':['Capture correspondence has not been confirmed by the user.',
                        'Area is observed coverage, not independently measured property area.',
                        'Ceiling height is a scan-wide plane estimate, not independently fitted per room.',
                        'Regions are morphological candidates; true room adjacency remains unverified.',
                        'Error budgets are uncalibrated; no accuracy or repeatability gate is passed.'],
            'captures':records}
if len(records)==2:
 values=[r['floor_coverage_area']['value'] for r in records]
 if all(v is not None and v>0 for v in values):
  comparison['coverage_area_difference_m2']=round(abs(values[1]-values[0]),4)
  comparison['coverage_area_difference_percent_relative_to_first']=round(abs(values[1]-values[0])/values[0]*100,3)
(out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
lines=['# Additional dataset comparison','', 'Status: descriptive only; no ground truth accuracy claim.','',
       '| Capture | Frames | Duration | Floor coverage | Ceiling estimate | Regions |',
       '| --- | ---: | ---: | ---: | --- | ---: |']
rows=[]
for r in records:
 h=r['global_ceiling_height'];ht=f"{h['value']:.4f} m [{h['lower']:.4f}, {h['upper']:.4f}]" if h else 'Unresolved'
 cells=[r['capture_id'],str(r['frames']),f"{r['duration_seconds']:.2f} s",(f"{r['floor_coverage_area']['value']:.4f} m²" if r['floor_coverage_area']['value'] is not None else "Unresolved"),ht,str(r['candidate_regions'])]
 lines.append('| '+' | '.join(cells)+' |');rows.append('<tr>'+''.join('<td>'+html.escape(c)+'</td>' for c in cells)+'</tr>')
lines+=['','The coverage-area difference is '+str(comparison.get('coverage_area_difference_percent_relative_to_first','unresolved'))+'% relative to the first capture.','']
lines+=['- '+w for w in comparison['warnings']]
(out/'comparison.md').write_text('\n'.join(lines)+'\n')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoomScan dataset comparison</title><style>body{font:15px system-ui;background:#f3f5fa;color:#17243b;margin:0}main{max-width:1200px;margin:auto;padding:32px}article{background:white;border-radius:16px;padding:24px;margin:24px 0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #e2e8f0}.scroll{overflow:auto}.plans{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}svg{width:100%}h1{font-size:30px}li{margin:12px 0}a{color:#235bc0}@media(max-width:800px){.plans{grid-template-columns:1fr}}</style><main><h1>RoomScan · New dataset comparison</h1><p>Observed coverage and ceiling evidence. Preliminary output; ranges are uncalibrated.</p><article class="scroll"><table><thead><tr><th>Capture</th><th>Frames</th><th>Duration</th><th>Coverage area</th><th>Ceiling height</th><th>Regions</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></article><div class="plans">'''
for r,svg in zip(records,plans):page+='<article><h2>'+html.escape(r['capture_id'])+'</h2>'+svg+'</article>'
page+='</div><article><h2>Interpretation</h2><ul>'+''.join('<li>'+html.escape(w)+'</li>' for w in comparison['warnings'])+'</ul><a href="comparison.json">Structured comparison</a></article></main></html>'
(out/'review.html').write_text(page)
print(out/'review.html')
