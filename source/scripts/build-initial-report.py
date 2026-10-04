"""Create the four-page technical report using actual run metadata."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/technical-report.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
r=json.loads((ROOT/'output/lidar/result.json').read_text())
a=json.loads((ROOT/'output/lidar-no-drift/result.json').read_text())
meta=r['diagnostics'][0]['input']; drift=r['diagnostics'][0]['drift']
pages=[('Architecture and delivered behavior',[
('Purpose and status','RoomScan is a local, auditable software prototype for the supplied Applied AI case study. It is not a compliant finished submission. It runs the supplied RGB-D capture and produces preliminary floor-coverage regions, surface candidates, a dimensioned SVG, structured JSON and an HTML review. Metric photo/video plans, semantic whole-property stitching, opening detection, automatic damage detection and interval calibration remain incomplete.'),
('Sensor pipeline','The importer reads Stray Scanner uint16 millimetre depth and confidence 0/1/2, removes low-confidence points, scales each frame\'s intrinsics using actual RGB/depth dimensions and transforms camera-space points using xyzw camera-to-world poses. It rejects missing depth/confidence pairs, duplicate frame IDs and video/pose count mismatches. Provenance includes SHA-256 hashes. No pretrained weights, remote APIs or cloud infrastructure are used.'),
('Geometry and contract','A sampled point cloud is registered to an accumulated model with bounded ICP. Horizontal plane modes find the floor and ceiling where visible. Observed floor points are rasterized at 5 cm, small gaps closed and narrow connector cores segmented morphologically. Contours become candidate surface boundaries. These boundaries may represent furniture or coverage gaps rather than true walls. The missing Round 1 published schema prevents external schema conformance; an included provisional schema and semantic interval checks validate output.'),
('Modules and output','ingest.py handles raw input; drift.py registration; geometry.py surfaces and explicit unresolved measurements; vision.py relative two-view geometry; evidence.py reviewed annotations and rules; evaluate.py gate scoring; render.py offline artifacts. The single capture command is python -m roomscan run INPUT --out OUTPUT. Any unsupported measurement is null with an explicit reason.')]),
('Tiers, capture and device support',[
('Capture route','Route 2 uses Stray Scanner on LiDAR-equipped Pro-class iPhones and native Camera for photos/video. The draft field protocol specifies slow perimeter coverage, both jambs at openings, full floor/ceiling views and a return loop. Raw files must be transferred without depth resizing or video re-encoding. App installation/export workflow and protocol usability still require in-person verification.'),
('Photos and video','Photos are grouped by room; video yields eight sampled frames. SIFT feature matching, essential-matrix recovery and triangulation recover the best supported two-view relative point cloud when enough parallax exists. Approximate focal length is disclosed. Relative scale is not converted to metres. There is no pretrained metric-depth model, full structure-from-motion integration, structural plane inference or automatic photo-property alignment yet. The paths execute but do not meet the case study\'s output floor.'),
('Device matrix and requirements','Any iPhone 15 or newer can provide native photos/video. A compatible Pro-class iPhone with LiDAR provides the raw depth route. Hardware accuracy is unverified. The document targets +/-8% photo walls/footprint, +/-3% video walls, <=2 cm opening widths on >=85%, <=1.5 cm ceiling bias, <=1 cm ceiling spread, and wall repeatability within 1 cm or 0.5%. These are targets, not delivered results.'),
('Damage and scope','Automatic damage classes, image masks and metric surface projection are not implemented. Explicit human annotations can supply normalized surface regions and metric extent with uncertainty. Water staining triggers moisture inspection; suspected mold triggers specialist review. Rules generate inspect/document scope items keyed to surfaces. They are not a diagnosis of concealed damage or a complete repair estimate. Empty damage arrays mean not assessed.')]),
('Evidence, drift and uncertainty',[
('Supplied capture',f"The ZIP contains {meta['pose_count']:,} depth frames and matching confidence frames, RGB video, camera poses with per-frame intrinsics, a camera matrix and IMU. The sequence spans {meta['duration_seconds']:.2f} seconds. This run sampled {meta['sampled_frames']} frames. The clip shows a living area and a bathroom. Two preliminary floor regions were returned, not two verified semantic rooms. Ceiling height could not be supported."),
('Drift ablation',f"Bounded frame-to-model ICP accepted corrections on {drift['accepted_frames']} sampled frames. Acceptance requires improved median residual, <20 cm translation and <4 degrees rotation. Corrected observed coverage area was {r['footprint_area']['value']:.4f} m²; without correction it was {a['footprint_area']['value']:.4f} m². Both outputs are retained. This is an on/off software ablation, not an accuracy comparison. There is no global pose graph or loop closure. ICP can align repeated structures incorrectly or accumulate its own bias."),
('Error budget and calibration','Wall-candidate ranges use a 15 cm or 6% floor; area budgets depend on perimeter times 15 cm; supported ceiling pairs use an 8 cm engineering budget. They are deliberately uncalibrated, with no nominal statistical confidence level. Their coverage has not been measured. Occlusion and unseen extent are not fully captured by these heuristics. The held-out calibration gate is not implemented. No 95% confidence claim or accuracy pass is made.'),
('Benchmark and timing',f"The corrected run took {r['timing_seconds']:.3f} seconds on this local machine; actual timing varies. Twelve meaningful unit regressions passed for projection, units, confidence, ICP, safe ZIP extraction, ceiling absence and evaluator behavior. LiDAR, derived video and derived photo inputs have been exercised; derived inputs do not replace independent three-tier captures. No tape/laser truth, repeat capture or consumer-app export was supplied. Accuracy, repeatability and head-to-head gates therefore remain unverified.")]),
('Fix loop, failure modes and completion plan',[
('Regenerable software fix','The initial implementation rejected the entire floor plan whenever a ceiling pair was absent. The hypothesis was that ceiling-dependent floor detection discarded valid low horizontal floor points. The predicted fix retained at least one floor region while leaving ceiling height unresolved. Baseline commit 503a331 produced zero regions; shipped fix 8f53ffe produced two with drift disabled. scripts/fix-loop.sh regenerates both versions from raw input and creates a readable JSON diff. This is a real software repair, not the required measured worst-gate fix loop.'),
('Failure modes','Sparse floor coverage and furniture create irregular boundary estimates; narrow-space segmentation can merge rooms or create fragments. Mirrors, glass and wet-look surfaces can corrupt depth; confidence filtering cannot guarantee their removal. Low light and motion blur reduce visual matches. Pure rotation lacks triangulation baseline. Repeated texture creates false matches. Missing ceiling views leave height unobservable. Independent LiDAR sessions have unrelated origins and cannot be treated as aligned. Lens distortion and IMU fusion are not applied.'),
('Work still required','Implement metric thin-input reconstruction, structural surfaces, verified topology and openings; train or integrate disclosed damage models with metric projection; implement global drift correction and calibration. Collect the specified property with three rooms plus connector, a furnished damaged room, all three independent tiers, same-tier repeats, complete tape/laser truth, and competitor exports for two rooms. Evaluate the real worst gate, predict and ship its fix, and reproduce before/after without inventing evidence.'),
('Reproduction and references','The original ZIP stays in Downloads; source code, requirements-lock.txt, schema, protocol, matrix and reproducible scripts are in this repository. README gives clean-machine setup and one command per capture. Setup time and walk-in readiness are not certified. Format reference: github.com/strayrobots/scanner/blob/main/docs/format.md. Pose/projection reference: github.com/kekeblom/StrayVisualizer/blob/main/stray_visualize.py. Additional Round 1 schema/gates must be supplied.')])]
styles=getSampleStyleSheet();styles['BodyText'].fontName='Helvetica';styles['BodyText'].fontSize=10.5;styles['BodyText'].leading=15;styles['BodyText'].spaceAfter=12
styles['Heading2'].fontName='Helvetica-Bold';styles['Heading2'].fontSize=12;styles['Heading2'].leading=16
c=canvas.Canvas(str(OUT),pagesize=A4)
md=['# RoomScan technical report','', 'Status: prototype; case-study compliance incomplete.','']
for num,(title,sections) in enumerate(pages,1):
    c.setFillColorRGB(.09,.14,.23);c.rect(0,A4[1]-95,A4[0],95,fill=1,stroke=0)
    c.setFillColorRGB(1,1,1);c.setFont('Helvetica-Bold',20);c.drawString(42,A4[1]-43,'RoomScan | Technical report')
    c.setFont('Helvetica',12);c.drawString(42,A4[1]-69,title)
    y=A4[1]-119;md+=['## '+title,'']
    for head,text in sections:
        md+=['### '+head,'',text,'']
        for content,style in [(head,styles['Heading2']),(text,styles['BodyText'])]:
            p=Paragraph(escape(content),style);w,h=p.wrap(A4[0]-84,y-45)
            if y-h<55:raise RuntimeError('Report content overflows page')
            p.drawOn(c,42,y-h);y-=h+10
    c.setFillColorRGB(.35,.4,.5);c.setFont('Helvetica',9);c.drawString(42,30,'Prototype evidence | 4 October 2026 | No verified accuracy claim')
    c.drawRightString(A4[0]-42,30,f'{num} / 4');c.showPage()
c.save()
(ROOT/'docs/TECHNICAL_REPORT.md').write_text('\n'.join(md)+'\n')
print(OUT)
