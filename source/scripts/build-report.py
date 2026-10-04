"""Six-page technical report from actual expanded-run artifacts."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output';summary=json.loads((OUT/'comprehensive-review/summary.json').read_text());improvement=json.loads((OUT/'improvement-review/comparison.json').read_text()) if (OUT/'improvement-review/comparison.json').exists() else None;styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Body',fontName='Helvetica',fontSize=10,leading=15,spaceAfter=10,textColor=colors.HexColor('#27384d')))
styles.add(ParagraphStyle(name='Note',fontName='Helvetica',fontSize=8,leading=12,spaceAfter=8,textColor=colors.HexColor('#58677d')))
story=[]
def p(text,style='Body'):story.append(Paragraph(escape(text),styles[style]))
def heading(title,subtitle):p(title,'Heading1');p(subtitle,'Note');story.append(Spacer(1,10))
def table(rows,widths=None):
 rows=[[Paragraph(escape(str(x)),styles['Note']) for x in row] for row in rows]
 t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eff7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dce3ec'))]));story.append(t);story.append(Spacer(1,12))
def image(path,width=460,maxheight=260):
 from PIL import Image as PILImage
 w,h=PILImage.open(path).size;scale=min(width/w,maxheight/h);story.append(Image(str(path),w*scale,h*scale));story.append(Spacer(1,8))
def new():story.append(PageBreak())
heading('RoomScan: expanded implementation','Applied AI case study | 4 October 2026 | Actual local experiments; physical gates unverified')
p('The three supplied ZIPs are raw sensor captures, not application source or pretrained models. RoomScan now imports them, performs bounded drift correction, extracts structural geometry and observed free-space partitions, proposes openings, projects RGB anomaly masks onto candidate surfaces, and exports structured JSON, dimensioned SVG, point clouds and a local review dashboard.')
p('An optional image-only engine runs COLMAP multi-view reconstruction and Apple Depth Pro locally to estimate metric scale. Derived photos and videos exercise this engine without LiDAR depth or camera poses as inference inputs. The current results are fragmented and uncalibrated; they do not establish complete metric property plans.')
table([['Capture','Pose/depth frames','Duration'],['single_room / c00a170fe1','1,715','37.17 s'],['floor-only / 1a8384c3f6','5,251','114.78 s'],['with-ceiling / c7d28f72c6','9,745','214.93 s']],[235,130,120])
p('The case study asks for dimensioned room/property plans, correct topology and openings, damage classes and metric extent, concealed-inspection rules, surface-keyed scope, calibrated intervals, all three tiers, drift ablations, a physical benchmark, competitor comparison and a regenerable worst-gate fix. The stock-capture protocol, device matrix and benchmark collection plan are documented.')
p('Missing independent tape/laser truth, verified room inventory, repeats, labelled staged damage, independent three-tier captures, competitor exports and the Round 1 published schema prevent conformance claims. Existing candidate measurements are useful engineering evidence, not passed accuracy gates.')
new();heading('Structural LiDAR reconstruction','Sensor projection, observed free space and per-region surface evidence')
p('High-confidence uint16 depth is converted from millimetres. Intrinsics are scaled to the depth raster using actual RGB/depth dimensions; per-frame calibration and xyzw OpenCV camera-to-world poses are used. Sampled clouds undergo bounded frame-to-model ICP. Accepted rigid transforms also update camera origins for ray carving.')
p('Voxel normals support a dominant Manhattan orientation. Robust horizontal fits estimate floor and supported ceilings. Vertical-plane histograms retain tall wall candidates. Mid-height camera rays stop at candidate wall barriers; observed free space and inferred fill are recorded separately. Watershed contacts no longer count as physical openings. Wall lengths and wall area stay unresolved unless a candidate plane supports the boundary. Room polygons and furniture rejection remain imperfect.')
if improvement:
 rows=[['Capture','Spaces before → after','Planes before → after','Opening candidates','Supported / unresolved boundary lengths']]
 for name,item in improvement['captures'].items():
  b,a=item['before'],item['after'];rows.append([name,f"{b['rooms']} → {a['rooms']}",f"{b['structural_planes']} → {a['structural_planes']}",f"{b['opening_candidates']} → {a['opening_candidates']}",f"{a['physical_boundary_lengths']} / {a['unknown_physical_boundaries']}"])
else:
 rows=[['Capture','Regions','Wall planes','Openings','Area m²']]
 for name,r in summary['captures'].items():rows.append([name,r['rooms'],r['walls'],r['openings'],f"{r['candidate_area_m2']:.2f}"])
table(rows,[145,105,105,95,105]);image(OUT/'improved-structure-with-ceiling/structural-raster.png' if (OUT/'improved-structure-with-ceiling/structural-raster.png').exists() else OUT/'structure-with-ceiling/structural-raster.png',maxheight=230)
if improvement:
 p('Revision 2 reports supported extent separately from inferred fill. No opening candidate survives on any supplied capture. A controlled two-room doorway fixture still preserves one door, but synthetic acceptance is not evidence of real-scene recall. In the ceiling scan, revised local height candidates are '+', '.join(f'{h:.3f} m' for h in improvement['captures']['with-ceiling']['after']['local_height_candidates_m'])+'. Floor-only and original heights remain unresolved. The changed estimates have no independent check.','Note')
else:
 p('Ceiling-scan local height candidates are '+', '.join(f'{h:.3f} m' for h in summary['captures']['with-ceiling']['local_heights_m'])+'. Floor-only and original heights remain unresolved. Height variation can reflect scene details, drift or surface-model error; it is not a measured ceiling-bias result.','Note')
new();heading('Comparison and drift ablation','All capture pairings retain their sensor scale; consistency is not physical accuracy')
rows=[['Pair','Median / p90 discrepancy','Overlap within 10 cm','Region / wall matches']]
for name,r in summary['alignments'].items():
 a=r['alignment'];rows.append([name,f"{a['median_source_to_target_m']*100:.1f} / {a['p90_source_to_target_m']*100:.1f} cm",f"{a['source_overlap_within_10cm']:.0%} / {a['target_overlap_within_10cm']:.0%}",f"{len(r['comparison']['rooms'])} / {len(r['comparison']['walls'])}"])
table(rows,[125,130,110,120]);image(OUT/'alignment-floor-ceiling/overlay.png',maxheight=245)
p('Cross-capture ICP removes arbitrary origin and yaw using mid-height slabs. It does not fit scale. Room polygons are matched by overlap and walls by parallelism, offset and shared support. Original-to-larger-capture correspondences have weaker overlap; scan identity is algorithmic and unconfirmed.')
if improvement:
 rows=[['Capture','Regions off / on','Candidate area off / on m²','Supported boundaries off / on','Rays clipped off / on']]
 for name,item in improvement['captures'].items():
  d=item['same_revision_drift_ablation'];u,c=d['disabled'],d['enabled'];rows.append([name,f"{u['rooms']} / {c['rooms']}",f"{u['area_m2']:.2f} / {c['area_m2']:.2f}",f"{u['physical_boundary_lengths']} / {c['physical_boundary_lengths']}",f"{u['wall_clipped_rays']:,} / {c['wall_clipped_rays']:,}"])
else:
 rows=[['Capture','Regions off / on','Area off / on m²','Difference m²']]
 for name,r in summary['captures'].items():
  a=json.loads((OUT/f'full-{name}-no-drift/result.json').read_text());before=a['footprint_area']['value'];rows.append([name,f"{len(a['rooms'])} / {r['rooms']}",f"{before:.2f} / {r['candidate_area_m2']:.2f}",f"{r['candidate_area_m2']-before:+.2f}"])
table(rows,[110,95,120,110,100] if improvement else [125,120,135,105]);p('These are same-revision, same-input software ablations. They show how bounded ICP changes candidate geometry and the number of wall-blocked rays, not whether accuracy improves. No globally optimized pose graph or sensor-fused IMU correction is implemented.','Note')
new();heading('Photos, video and learned metric scale','Image-only inference; derived inputs are not an independent three-tier benchmark')
p('COLMAP estimates camera calibration, geometrically verifies SIFT matches and builds disconnected multi-view components. Dense video uses sequential matching plus input-trained visual loop retrieval. Sparse 2-8-photo sets and a 40-photo property experiment are retained with failures and coverage counts.')
rows=[['Input','Registered / total','Components','Status']]
for name,r in summary['visual'].items():rows.append([name,f"{r['registered_images']} / {r['input_images']}",r['components'],r['status']])
table(rows,[125,125,85,150]);p('For supported triangulated tracks, per-image ratios of predicted metric depth to SfM depth estimate one global scale. Images receive equal weight. Predicted depths are fused using recovered camera poses, then aligned to estimated gravity from upright camera up vectors. Unregistered views and other components remain excluded.')
p('Depth Pro runs in a separate process from COLMAP because their bundled OpenMP runtimes conflict. No bypass of the runtime check is used. All inference runs locally; sensor captures are not transmitted. Vendor weights are approximately 1.90 billion bytes and their SHA-256 is recorded in the reproduction manifest.')
rows=[['RGB/LiDAR sensor-reference comparison','Frames','Median frame relative depth error']]
for name,r in summary['depth_reference'].items():rows.append([name,len(r['frames']),f"{r['median_frame_abs_relative_error']:.1%}"])
table(rows,[220,65,200]);p('These are median absolute relative depth errors against paired high-confidence LiDAR, not independently measured wall/footprint errors. A separate orientation check improved one frame from 48.4% error sideways to 16.6% upright. The model still shows substantial error across 24 sampled frames. Photo ±8% and video ±3% accuracy gates are unverified.','Note')
p('Metric scale budgets include a 20% minimum systematic term and between-view dispersion; areas carry doubled relative scale budgets. These are conservative engineering ranges, not held-out calibrated confidence intervals.','Note')
new();heading('Damage evidence and the software fix','Masks and metric projection are implemented; damage diagnosis remains unvalidated')
p('Classical LAB discoloration and irregular linear-mark proposals produce image masks. High-confidence depth supports a planar patch fit, surface-normal area correction and raw-pose world projection. Proposals near candidate vertical planes receive structural surface IDs, support-frame IDs, estimated metric area and evidence images. Inspection rules generate document/inspect scope items; they do not authorize repairs or diagnose concealed damage.')
rows=[['Capture','Initial proposals','After straight-edge filter']]
for name,r in summary['damage_filter'].items():rows.append([name,r['before'],r['after']])
table(rows,[170,145,170]);image(OUT/'anomaly-contact-sheet.jpg',maxheight=235)
p('Visual review showed that the initial seven proposals marked fixtures and trim. Hypothesis: fragmented straight edges survived the irregular-line test. Shipped fix: reject crack candidates overlapping long Hough edges. Sixty sampled frames per capture produced one remaining proposal; it also appears fixture-confounded in visual review. Initial masks and evidence are preserved. This is a software false-positive reduction, not a labelled damage benchmark.','Note')
p('The earlier missing-ceiling software fix remains regenerable from actual baseline and fix commits: valid floor geometry is retained while unsupported ceiling height stays null. Neither repair constitutes the required measured worst-physical-gate loop. No positive/negative staged damage ground truth exists in these ZIPs.','Note')
new();heading('Reproduction, validation and remaining gates','Auditable local artifacts and actual incremental Git history')
p('The comprehensive review is output/comprehensive-review/index.html. Per-capture full-* folders contain schema-validated JSON, dimensioned SVG, review HTML and clouds; full-*-no-drift provides the correction ablation. Alignment folders preserve every pair. Metric video/photo folders preserve sparse components, image manifests and learned-depth outputs. Damage folders preserve before/after masks and extent evidence.')
p('Run: ./scripts/run-local.sh run /path/to/scan.zip --out output/capture. Disable correction with --no-drift; preserve the initial geometry with --geometry baseline; skip anomaly proposals with --no-damage. Optional --metric enables COLMAP and local model depth; --rotate-cw normalizes the sideways Stray Scanner RGB raster. README documents vendor-source installation, weights, hashes and suite scripts.')
p('The recorded software suite contains 40 regression cases covering projection, ZIP safety, ICP, absent ceilings, rigid alignment, false opening evidence, doorway preservation, walls and surface area. The geometry revision passes 5/5 focused control cases; its historical geometry baseline passed 0/5. These are software checks, not physical accuracy. LiDAR, derived visual and learned-depth experiments executed locally. A clean-machine setup under 15 minutes and unseen walk-in readiness are not certified.')
table([['Required evidence / capability','Current state'],['Tape/laser dimensions and 3 rooms + connector','Not supplied; semantic inventory unverified'],['Independent tiers, repeatability, competitor >=70%','Not supplied; no pass claims'],['Damage labels and calibrated confidence coverage','Not supplied; proposals/ranges unvalidated'],['Published schema / extra Round 1 gates','Not supplied; provisional schema included'],['Global loop correction and full visual property plan','Incomplete; bounded ICP and fragmented visual maps'],['Physical worst-gate fix and cold walk-in test','Not demonstrated']],[265,220])
p('Primary references: Stray Scanner export format (github.com/strayrobots/scanner/blob/main/docs/format.md); COLMAP Python API (github.com/colmap/colmap/tree/main/python); Apple Depth Pro source and license (github.com/apple-aiml-research/ml-depth-pro). Vendor weights and implementation are attributed and kept outside Git. Reproduction artifacts preserve input and output hashes.','Note')
p('Next evidence collection: verify room identities and measure wall endpoints, floor areas, ceiling heights and openings; collect independent photos/video and same-tier repeats; stage and label two damage classes; export competitor results for two rooms. Only those observations can support physical gate scoring and interval calibration.','Note')
def footer(canvas,doc):
 canvas.setStrokeColor(colors.HexColor('#dce3ec'));canvas.line(48,40,A4[0]-48,40);canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#58677d'));canvas.drawString(48,25,'RoomScan | Prototype results; physical accuracy unverified');canvas.drawRightString(A4[0]-48,25,str(doc.page))
out=OUT/'pdf/technical-report.pdf';out.parent.mkdir(exist_ok=True);doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=55);doc.title='RoomScan Expanded Technical Report';doc.author='RoomScan';doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(out)
