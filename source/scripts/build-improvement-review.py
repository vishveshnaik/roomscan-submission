"""Before/after evidence for geometry revision 2; does not score physical gates."""
from pathlib import Path
import json,html
from roomscan.compare import compare_structures
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output';DEST=OUT/'improvement-review';DEST.mkdir(exist_ok=True)
def load(path):return json.loads((OUT/path).read_text())
def stats(r):
 g=r['diagnostics'][0]['geometry'];walls=[w for room in r['rooms'] for w in room['walls']]
 return {'rooms':len(r['rooms']),'structural_planes':len(r['structural_walls']),'opening_candidates':len(r['opening_candidates']),
         'area_m2':r['footprint_area']['value'],'physical_boundary_lengths':sum(w['length']['value'] is not None for w in walls),
         'unknown_physical_boundaries':sum(w['length']['value'] is None for w in walls),
         'ray_count':g.get('ray_count'),'wall_clipped_rays':g.get('wall_clipped_rays'),
         'observed_area_m2':g.get('directly_observed_area_m2'),'inferred_area_m2':g.get('inferred_area_m2'),
         'local_height_candidates_m':[room['ceiling_height']['value'] for room in r['rooms']]}
summary={'baseline_commit':'92d4f63','geometry_revision':2,'physical_gate_status':'not_evaluated','captures':{},
         'controlled_regressions':{'before':load('topology-regression-before.json'),'after':load('topology-regression-after.json')},
         'drift_ablation_method':'geometry revision 2, same source capture and configuration; bounded ICP enabled/disabled',
         'warnings':['Candidate count reductions do not establish improved physical accuracy or detector recall.',
                     'Area methods differ: previous polygon approximations versus current raster regions with exclusions.',
                     'Upper-plane selection changes ceiling candidates and requires physical verification.',
                     'No supplied opening proposal survives the stronger evidence gates; real doorways may remain undetected.',
                     'Geometry revision is encoded in IDs; old annotations must be explicitly rematched.']}
sections=[];table=[]
for name in ['original','floor-only','with-ceiling']:
    before=load(f'full-{name}/result.json');after=load(f'improved-{name}/result.json');b,a=stats(before),stats(after)
    corrected=load(f'improved-{name}/result.json');uncorrected=load(f'improved-{name}-no-drift/result.json')
    c,u=stats(corrected),stats(uncorrected)
    drift={'enabled':c,'disabled':u,'region_count_change':c['rooms']-u['rooms'],
           'candidate_area_change_m2':round(c['area_m2']-u['area_m2'],4),
           'wall_clipped_ray_change':c['wall_clipped_rays']-u['wall_clipped_rays']}
    matches=compare_structures({'rooms':before['rooms'],'walls':before['structural_walls']},
                            {'rooms':after['rooms'],'walls':after['structural_walls']},{'yaw_radians':0,'translation_xz_m':[0,0]})
    summary['captures'][name]={'before':b,'after':a,'same_frame_geometric_correspondence':matches,'same_revision_drift_ablation':drift}
    table.append(f"<tr><td>{name}</td><td>{b['rooms']} → {a['rooms']}</td><td>{b['structural_planes']} → {a['structural_planes']}</td><td>{b['opening_candidates']} → {a['opening_candidates']}</td><td>{a['physical_boundary_lengths']} measured candidates / {a['unknown_physical_boundaries']} unresolved</td><td>{a['wall_clipped_rays']:,}</td></tr>")
    sections.append(f"<section><h2>{name}</h2><div class='pair'><div><h3>Earlier geometry</h3><object data='../full-{name}/plan.svg' type='image/svg+xml'></object><a href='../full-{name}/review.html'>Earlier review</a></div><div><h3>Revision 2</h3><object data='../improved-{name}/plan.svg' type='image/svg+xml'></object><a href='../improved-{name}/review.html'>Updated review and support evidence</a></div></div><p>Revision 2: {a['rooms']} spaces · {a['structural_planes']} structural planes · {a['opening_candidates']} accepted opening candidates · {a['wall_clipped_rays']:,} rays clipped at candidate walls. Observed free-space extent: {a['observed_area_m2']:.2f} m²; inferred fill: {a['inferred_area_m2']:.2f} m².</p><table><tr><th>ICP setting</th><th>Spaces</th><th>Candidate area</th><th>Accepted boundary lengths</th><th>Wall-clipped rays</th></tr><tr><td>On</td><td>{c['rooms']}</td><td>{c['area_m2']:.2f} m²</td><td>{c['physical_boundary_lengths']}</td><td>{c['wall_clipped_rays']:,}</td></tr><tr><td>Off</td><td>{u['rooms']}</td><td>{u['area_m2']:.2f} m²</td><td>{u['physical_boundary_lengths']}</td><td>{u['wall_clipped_rays']:,}</td></tr></table><p>The area and boundary changes are algorithm outputs, not accuracy improvements. No opening passed the stricter evidence checks in this capture.</p></section>")
(DEST/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
r=summary['controlled_regressions'];cases=[]
for b,a in zip(r['before']['cases'],r['after']['cases']):cases.append(f"<tr><td>{a['case']}</td><td>{'pass' if b['pass'] else 'fail'}</td><td>{'pass' if a['pass'] else 'fail'}</td></tr>")
page="""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>RoomScan · Geometry improvement</title><style>body{margin:0;background:#edf1f6;color:#17243b;font:16px system-ui}main{max-width:1300px;margin:auto;padding:30px}h1{font-size:36px}p{line-height:1.65}section{background:white;padding:24px;margin:24px 0;border-radius:16px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:22px}object{width:100%;height:560px}table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #dae2ed}a{color:#2259ae}.tag{background:#fff0cf;border-radius:18px;padding:9px 14px;display:inline-block}@media(max-width:750px){.pair{display:block}main{padding:12px}object{height:430px}}</style><main><span class='tag'>Geometry revision 2 · physical accuracy unverified</span><h1>Geometry improvement</h1><p>Wall barriers now constrain free-space rays. Wall candidates need stronger lower-face and vertical support. Openings need supported jambs plus traversal or spanning-head evidence. Watershed contacts are recorded separately from physical doorways. Unsupported boundaries have unresolved physical length and area. Observed space and inferred fill are reported separately.</p><section><h2>Controlled software regressions</h2><p>Five controlled cases improved from 0/5 to 5/5: rejecting unsupported gaps, pose jumps, painted wall gaps and short furniture faces while preserving one real doorway in a synthetic two-room scene. The recorded suite contains 40 software checks. These results do not measure real-world accuracy.</p><table><tr><th>Case</th><th>Before</th><th>After</th></tr>"""+''.join(cases)+"</table></section><section><h2>All supplied scans rerun</h2><table><tr><th>Capture</th><th>Spaces old → revised</th><th>Wall planes old → revised</th><th>Openings old → revised</th><th>Revised supported / unknown lengths</th><th>Rays stopped</th></tr>"+''.join(table)+"</table><p>The revised detector accepted no openings in the supplied scans. That removes unsupported doorway claims; it also shows that real-scene opening recall remains unresolved. A zero-candidate result is not evidence that a property has no doors.</p></section>"+''.join(sections)+"<section><h2>Limits and reproduction</h2><p>Room identity, height accuracy and opening recall remain unverified. The area method changed, so differences between revisions are not accuracy improvements. Geometry revision 2 changes surface IDs; old human annotations require explicit remapping. The earlier six-page report and full-* outputs are retained as the historical baseline.</p><p><a href='comparison.json'>Measured before/after evidence</a> · <a href='../comprehensive-review/index.html'>Full data review</a> · <a href='../../docs/GEOMETRY_IMPROVEMENT.md'>Implementation and reproduction</a></p></section></main></html>"
(DEST/'index.html').write_text(page);print(DEST/'index.html')
