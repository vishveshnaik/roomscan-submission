"""Standalone review HTML, dimensioned SVG, and point cloud previews."""
import html
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def plan_svg(result):
    rooms=result['rooms'];polys=[np.asarray(r['polygon']) for r in rooms if r['polygon']]
    if len(result.get('diagnostics',[]))>1:polys=[]
    if not polys:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640"><rect width="960" height="640" fill="#f4f6fa"/><text x="55" y="260" font-family="sans-serif" font-size="25">Geometry unresolved</text><text x="55" y="305" font-family="sans-serif" font-size="17">A complete metric plan is not established.</text></svg>'
    points=np.concatenate(polys);lo,hi=points.min(0),points.max(0);extent=np.maximum(hi-lo,.5);scale=min(740/extent[0],470/extent[1])
    def xy(p):return (np.asarray(p)-lo)*scale+[100,115]
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 740">','<rect width="960" height="740" fill="#f4f6fa"/>','<text x="36" y="42" font-family="sans-serif" font-size="23" font-weight="bold" fill="#17243b">Observed floor plan</text>','<text x="36" y="70" font-family="sans-serif" font-size="13" fill="#78591b">PRELIMINARY · candidates · intervals uncalibrated</text>']
    palette=['#dce9fb','#dbeee9','#e9e0f8','#f6e8d8','#dfe7ef'];occupied=[];texts=[]
    for i,room in enumerate(rooms):
        if not room['polygon']:continue
        pp=np.array([xy(p) for p in room['polygon']]);coords=' '.join(f'{x:.1f},{y:.1f}' for x,y in pp)
        parts.append(f'<polygon points="{coords}" fill="{palette[i%len(palette)]}" stroke="#91a3bb" stroke-width="1.5" stroke-dasharray="4 3"/>')
        if room.get('polygon_holes'):
            paths=[]
            for ring in [room['polygon']]+room['polygon_holes']:
                values=[xy(point) for point in ring];paths.append('M '+' L '.join(f'{x:.1f},{y:.1f}' for x,y in values)+' Z')
            parts[-1]=f'<path d="{" ".join(paths)}" fill="{palette[i%len(palette)]}" fill-rule="evenodd" stroke="#91a3bb" stroke-width="1.5" stroke-dasharray="4 3"/>'
        center=xy(room['label_position']) if room.get('label_position') else pp.mean(0);x,y=center
        occupied.append([x-45,y-13,x+45,y+23]);val=room['floor_area']['value'];area='unresolved' if val is None else f'{val:.2f} m²'
        texts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" stroke="#f4f6fa" stroke-width="3" paint-order="stroke">{html.escape(room["name"])}</text><text x="{x:.1f}" y="{y+17:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" stroke="#f4f6fa" stroke-width="3" paint-order="stroke">{area}</text>')
    walls=result.get('structural_walls',[]) or [w for r in rooms for w in r['walls']]
    for wall in result.get('structural_walls',[]):
        a,b=xy(wall['start']),xy(wall['end']);parts.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#17243b" stroke-width="4"><title>{html.escape(wall["id"])}</title></line>')
    for wall in sorted(walls,key=lambda w:w['length']['value'] or 0,reverse=True):
        length=wall['length']['value']
        if length is None or length<1.2:continue
        a,b=xy(wall['start']),xy(wall['end']);mid=(a+b)/2;direction=b-a;norm=np.linalg.norm(direction)
        if norm<1:continue
        normal=np.array([-direction[1],direction[0]])/norm
        for offset in [12,-12,24,-24]:
            x,y=mid+normal*offset;box=[x-23,y-10,x+23,y+3]
            if any(box[0]<q[2] and box[2]>q[0] and box[1]<q[3] and box[3]>q[1] for q in occupied):continue
            occupied.append(box);texts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#233c60" stroke="#f4f6fa" stroke-width="3" paint-order="stroke">{length:.2f} m</text>');break
    for opening in result.get('opening_candidates',[]):
        if opening.get('center'):
            x,y=xy(opening['center']);parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#e99825" stroke="white" stroke-width="2"><title>{html.escape(opening["id"])}: unverified opening</title></circle>')
    parts+=texts
    parts+=[f'<line x1="40" y1="660" x2="{40+scale:.1f}" y2="660" stroke="#33486c" stroke-width="3"/>','<text x="40" y="685" font-family="sans-serif" font-size="12">1 metre · dark = supported plane · dashed = inferred extent · orange = opening candidate</text>','<text x="40" y="712" font-family="sans-serif" font-size="11">Displayed dimensions are supported segment extents. Full measurements and uncertainty are in JSON.</text>','</svg>']
    return ''.join(parts)


def cloud_preview(points, output):
    if len(points) == 0:
        return
    pts = points[:, [0,2]]
    lo,hi = np.quantile(pts,[.002,.998],axis=0)
    size = np.maximum(hi-lo, .1)
    scale = min(900/size[0],650/size[1])
    image = Image.new('RGB',(1000,760),'#101d31')
    draw = ImageDraw.Draw(image)
    for p,y in zip(pts[::2],points[::2,1]):
        xy = (p-lo)*scale + [40,60]
        color = (int(np.clip(90+y*45,20,220)),170,int(np.clip(220-y*20,70,250)))
        draw.point(tuple(xy),fill=color)
    draw.text((35,20),'Reconstructed depth samples / top view',fill='white')
    image.save(output)


def write_review(result, out):
    out = Path(out)
    svg = plan_svg(result)
    (out/'plan.svg').write_text(svg)
    data = json.dumps(result,indent=2,allow_nan=False)
    (out/'result.json').write_text(data+'\n')
    rows = []
    def fmt(m):
        return 'Unresolved' if m['value'] is None else f"{m['value']:.2f} {m['unit']} [{m['lower']:.2f}, {m['upper']:.2f}]"
    for r in result['rooms']:
        rows.append('<tr><td>'+html.escape(r['name'])+'</td><td>'+html.escape(r['tier'])+'</td><td>'+fmt(r['floor_area'])+'</td><td>'+fmt(r['ceiling_height'])+'</td><td>'+html.escape(r['status'])+'</td></tr>')
    gallery=''
    for candidate in result.get('damage_candidates',[]):
        gallery+=f'<figure><img src="{html.escape(candidate["evidence_image"],quote=True)}" alt="Unverified surface anomaly"><figcaption>{html.escape(candidate["class"])} · {html.escape(candidate["surface_id"])} · requires review</figcaption></figure>'
    if gallery:gallery='<div class="card"><h2>Unverified anomaly evidence</h2>'+gallery+'</div>'
    geometry_evidence=''
    for room in result['rooms']:
        evidence=room.get('surface_evidence',{})
        if 'inferred_extent_m2' not in evidence:continue
        geometry_evidence+=f'<tr><td>{html.escape(room["name"])}</td><td>{evidence["directly_observed_extent_m2"]:.2f} m²</td><td>{evidence["inferred_extent_m2"]:.2f} m²</td><td>{evidence["supported_boundary_fraction"]:.0%}</td></tr>'
    if geometry_evidence:
        geometry_evidence='<div class="card"><h2>Geometry support</h2><p>Dark lines show candidate wall-plane support. Dashed outlines are inferred coverage limits. Unknown boundary surfaces have no asserted wall area. Room contacts alone do not establish doorways or physical adjacency.</p><table><tr><th>Space</th><th>Observed extent</th><th>Inferred extent</th><th>Boundary plane support</th></tr>'+geometry_evidence+'</table></div>'
    warnings = ''.join('<li>'+html.escape(w)+'</li>' for w in result['warnings'])
    visual_summary=''
    if result['tier'] in {'photos','video'}:
        mode='Experimental multi-view geometry with learned metric scale' if result.get('configuration',{}).get('metric_visual') else 'Relative two-view geometry; metric measurements unavailable'
        details=[]
        for item in result.get('diagnostics',[]):
            sampling=item.get('video_sampling',{});sfm=item.get('sfm',{});relative=item.get('reconstruction',{})
            if sampling:
                details.append(f"{sampling['decoded_keyframes']} sampled frames out of {sampling['source_frames']} video frames.")
            if sfm:
                details.append(f"Largest component: {sfm['registered_images']} of {sfm['input_images']} images; {sfm['component_count']} disconnected components.")
            elif relative:
                details.append(f"Relative reconstruction: {relative.get('successful_pairs',0)} usable pairs from {relative.get('attempted_pairs',0)} comparisons. Recovered points have arbitrary scale.")
        visual_summary='<div class="card"><h2>Visual reconstruction</h2><p>'+html.escape(mode)+'. Capture status: '+html.escape(result['status'])+'.</p><ul>'+''.join('<li>'+html.escape(d)+'</li>' for d in details)+'</ul></div>'
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoomScan capture review</title>
<style>body{margin:0;background:#f3f5fa;color:#17243b;font:15px system-ui}main{max-width:1150px;margin:auto;padding:36px}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:32px;margin-bottom:8px}.tag{background:#fff0d5;padding:10px 16px;border-radius:24px;color:#805807}.card{background:white;padding:24px;border-radius:16px;margin-top:24px;box-shadow:0 4px 20px #17243b08}svg{width:100%;max-height:740px}table{width:100%;border-collapse:collapse}td,th{padding:13px;text-align:left;border-bottom:1px solid #e5eaf3}.scroll{overflow:auto}a{color:#235bc0}li{margin:10px 0}pre{overflow:auto;background:#101d31;color:#d7e4fa;padding:20px;border-radius:12px}img{max-width:100%}</style>
<main><header><div><h1>RoomScan</h1><p>Local capture reconstruction &amp; evidence review</p></div><span class="tag">Needs verification</span></header>
'''+visual_summary+'''<div class="card">'''+svg+'''</div><div class="card scroll"><h2>Measurements</h2><p>Ranges are engineering error budgets. Coverage has not been calibrated against ground truth.</p><table><tr><th>Space</th><th>Input</th><th>Floor area</th><th>Ceiling height</th><th>Status</th></tr>'''+''.join(rows)+'''</table></div>
<div class="card"><h2>Evidence and limitations</h2><ul>'''+warnings+'''</ul><p><a href="result.json">Download JSON</a> · <a href="plan.svg">Open SVG plan</a> · <a href="cloud.ply">Download reconstructed cloud</a></p></div>
'''+('<div class="card"><h2>Reconstruction</h2><img src="cloud.png" alt="Top view of reconstructed candidate geometry"></div>' if (out/'cloud.png').exists() else '')+geometry_evidence+gallery+'''<details class="card"><summary>Full structured output</summary><pre>'''+html.escape(data)+'''</pre></details></main></html>'''
    (out/'review.html').write_text(document)


def write_ply(points,path):
    with open(path,'w') as f:
        f.write(f'ply\nformat ascii 1.0\nelement vertex {len(points)}\nproperty float x\nproperty float y\nproperty float z\nend_header\n')
        np.savetxt(f,points,fmt='%.5f')
