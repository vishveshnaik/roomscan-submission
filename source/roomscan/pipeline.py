from pathlib import Path
import json
import time
import tempfile
import numpy as np
from .ingest import extract_zip,scan_roots,load_scan,provenance
from .drift import correct_clouds,voxel_downsample
from .geometry import rooms_from_cloud
from .vision import photo_room,extract_video,IMAGE_SUFFIXES,VIDEO_SUFFIXES
from .render import write_review,write_ply,cloud_preview
from .evidence import apply_evidence


def run(source, output, tier='auto', drift=True, every=20, evidence=None, geometry='structural', damage=True, metric=False, weights='models/depth_pro.pt', rotate_cw=False,keyframes=240,depth_views=12):
    start = time.perf_counter()
    source,out = Path(source).resolve(),Path(output).resolve()
    if not source.exists():
        raise ValueError('Input does not exist')
    if out == source or (source.is_dir() and out.is_relative_to(source)):
        raise ValueError('Output must be outside input to keep provenance immutable')
    out.mkdir(parents=True,exist_ok=True)
    cv_seed()
    temp_import = tempfile.TemporaryDirectory(prefix='import-', dir=out) if source.suffix.lower()=='.zip' else None
    raw = extract_zip(source,Path(temp_import.name)) if temp_import else source
    roots = scan_roots(raw) if raw.is_dir() else []
    if tier == 'auto':
        tier = 'lidar' if roots else ('video' if raw.is_file() else 'photos')
    result = {'schema_version':'0.1.0','capture_id':source.stem,'tier':tier,
              'status':'needs_review','rooms':[],'adjacency':[],
              'footprint_area':None,'diagnostics':[], 'warnings':[
                  'Prototype output; no benchmark accuracy or calibrated confidence is claimed.',
                  'Openings and RGB anomalies are unverified candidates; human review is required.',
                  'The Round 1 published schema was not supplied; this uses the included provisional schema.'],
              'provenance':provenance(source), 'configuration':{'every':every,'drift':drift,'geometry':geometry,'damage':damage,'metric_visual':metric,'keyframes':keyframes,'depth_views':depth_views,'rotate_cw':rotate_cw}}
    allpoints = []
    result['structural_walls']=[];result['opening_candidates']=[];result['damage_candidates']=[]
    if tier == 'lidar':
        if not roots:
            raise ValueError('No Stray Scanner export found')
        for root in roots:
            clouds,rows,meta = load_scan(root,every=every)
            fixed,driftlog = correct_clouds(clouds,enabled=drift)
            points = np.concatenate(fixed)
            if geometry=='structural':
                from .structure import extract_structure
                cameras=[]
                for original,registered,row in zip(clouds,fixed,rows):
                    ac,bc=original.mean(0),registered.mean(0)
                    u,_,vt=np.linalg.svd((original-ac).T@(registered-bc));rotation=vt.T@u.T
                    camera=np.array([float(row[k]) for k in ['x','y','z']])
                    cameras.append(camera@rotation.T+bc-ac@rotation.T)
                structure=extract_structure(points,fixed,cameras,root.name,out/'structure'/root.name)
                rooms,edges,quality=structure['rooms'],structure['adjacency'],structure['diagnostics']
                result['structural_walls'].extend(structure['walls']);result['opening_candidates'].extend(structure['openings'])
                if damage:
                    from .damage import detect_scan_anomalies
                    proposals=detect_scan_anomalies(root,structure,out/'damage'/root.name)
                    for candidate in proposals['candidates']:
                        candidate['evidence_image']=str(Path('damage')/root.name/candidate['evidence_image'])
                        candidate['mask_image']=str(Path('damage')/root.name/candidate['mask_image'])
                    result['damage_candidates'].extend(proposals['candidates'])
                    quality['damage']=proposals
            else:
                rooms,edges,quality = rooms_from_cloud(points,root.name)
            result['rooms'].extend(rooms)
            result['adjacency'].extend(edges)
            result['diagnostics'].append({'input':meta,'drift':driftlog,'geometry':quality})
            allpoints.append(points)
        if len(roots)>1:
            # Separate AR sessions have unrelated world origins: keep them out of a false stitch.
            result['warnings'].append('Multiple independent LiDAR sessions: world-frame registration is unresolved.')
            result['status']='unresolved'
            for room in result['rooms']:
                room['warnings'].append('Independent session origin; property placement unresolved.')
        result['warnings'].extend(['LiDAR floor segmentation is preliminary and may split or merge semantic rooms.',
                                   'Lens distortion is not applied; IMU is retained as evidence, not fused.'])
    elif tier in {'photos','video'}:
        sampling = {}
        visual_statuses = []
        if tier == 'video':
            videos = [raw] if raw.is_file() else sorted(p for p in raw.rglob('*') if p.suffix.lower() in VIDEO_SUFFIXES)
            if not videos:
                raise ValueError('No supported video found (MOV, MP4, M4V, AVI or MKV)')
            sets = []
            for p in videos:
                files, stats = extract_video(p,out/'frames'/p.stem,count=keyframes,rotate_cw=rotate_cw,return_metadata=True)
                sets.append((p.stem,files)); sampling[p.stem] = stats
        else:
            if not raw.is_dir():
                raise ValueError('Photos require a folder (or ZIP of folders)')
            dirs = sorted({p.parent for p in raw.rglob('*') if p.suffix.lower() in IMAGE_SUFFIXES})
            sets = [(str(d.relative_to(raw)) if d!=raw else raw.name,
                     sorted(p for p in d.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)) for d in dirs]
            if not sets:
                raise ValueError('No photos found')
        for name,files in sets:
            if len(files)<2:
                result['warnings'].append(f'{name}: fewer than two photos; geometry cannot be reconstructed.')
            if metric:
                from .thin import metric_multiview
                structure,cloud=metric_multiview(files,out/'visual'/str(len(result['diagnostics'])),weights,video=tier=='video',max_depth_images=depth_views,capture_id=f'{source.stem}-visual-{len(result["diagnostics"])}')
                if not structure['rooms']:
                    observation,_=photo_room(files,name,tier)
                    observation['warnings'].append('Multi-view metric reconstruction failed; unresolved observation retained.')
                    structure['rooms']=[observation]
                    structure['status']='unresolved'
                result['rooms'].extend(structure['rooms']);result['adjacency'].extend(structure['adjacency'])
                result['structural_walls'].extend(structure['walls']);result['opening_candidates'].extend(structure['openings'])
                visual_statuses.append(structure['status'])
                if name in sampling:structure['diagnostics']['video_sampling']=sampling[name]
                result['diagnostics'].append(structure['diagnostics'])
                if len(cloud):allpoints.append(cloud)
                continue
            room,cloud = photo_room(files,name,tier)
            result['rooms'].append(room)
            if name in sampling:
                result['diagnostics'].append({'video_sampling':sampling[name],
                                              'visual_mode':'relative_two_view',
                                              'reconstruction':room['reconstruction']})
            # Relative two-view clouds have independent origins; never merge as a metric plan.
            write_ply(cloud,out/f'relative-{len(result["rooms"])}.ply')
        result['status']=visual_result_status(visual_statuses) if metric else 'unresolved'
        if not metric:
            result['warnings'].append('Lightweight relative mode cannot produce metric dimensions. Use --metric for experimental multi-view reconstruction and learned scale; metric accuracy remains unverified.')
        result['warnings'].append('Thin-input property stitching is unresolved. Learned metric scale, when enabled, is uncalibrated; disconnected components are excluded.')
    else:
        raise ValueError('Unknown tier')
    if not result['rooms']:
        result['status']='unresolved'
        result['warnings'].append('No supported floor-plan geometry recovered.')
    from .geometry import measurement
    vals=[r['floor_area'] for r in result['rooms']]
    if vals and all(v['value'] is not None for v in vals) and len(roots)<=1 and tier=='lidar':
        result['footprint_area']=measurement(sum(v['value'] for v in vals),sum(v['upper']-v['value'] for v in vals),
                                              'm2','sum_of_floor_candidates','candidate')
    else:
        result['footprint_area']=measurement(unit='m2')
    if evidence:
        apply_evidence(result,Path(evidence))
    if len(allpoints)>1 and tier!='lidar':
        allpoints=[]
        result['warnings'].append('Visual sets have independent coordinate frames; no combined metric cloud or footprint is asserted.')
    if allpoints:
        points=voxel_downsample(np.concatenate(allpoints),.025)
        write_ply(points,out/'cloud.ply')
        cloud_preview(points,out/'cloud.png')
    if temp_import:
        temp_import.cleanup()
    if not allpoints:
        for stale in ('cloud.png','cloud.ply'):
            if (out/stale).exists(): (out/stale).unlink()
    result['timing_seconds']=round(time.perf_counter()-start,3)
    validate(result)
    write_review(result,out)
    return result


def visual_result_status(statuses):
    """Preserve recovered geometry without implying independent sets are stitched."""
    if not statuses or all(s=='unresolved' for s in statuses):
        return 'unresolved'
    if len(statuses)>1 or any(s!='needs_review' for s in statuses):
        return 'partial_reconstruction'
    return 'needs_review'


def cv_seed():
    import cv2
    cv2.setRNGSeed(0)
    cv2.setNumThreads(1)


def validate(result):
    import jsonschema
    schema=json.loads((Path(__file__).parent/'schema.json').read_text())
    jsonschema.validate(result,schema)
    room_ids=[r['id'] for r in result['rooms']]
    if len(room_ids)!=len(set(room_ids)):
        raise ValueError('Duplicate room IDs')
    validate_topology(result)
    def check(value):
        if isinstance(value,dict):
            if {'value','lower','upper','unit'}.issubset(value):
                triple=[value[k] for k in ('lower','value','upper')]
                if any(v is None for v in triple):
                    if not all(v is None for v in triple):
                        raise ValueError('Unresolved measurement bounds must all be null')
                elif not all(np.isfinite(v) for v in triple) or not triple[0]<=triple[1]<=triple[2]:
                    raise ValueError('Invalid measurement interval')
            for v in value.values(): check(v)
        elif isinstance(value,list):
            for v in value: check(v)
        elif isinstance(value,float) and not np.isfinite(value):
            raise ValueError('Nonfinite result value')
    check(result)


def validate_topology(result):
    room_ids={room['id'] for room in result['rooms']}
    openings={opening['id']:opening for opening in result.get('opening_candidates',[])}
    if len(openings)!=len(result.get('opening_candidates',[])):raise ValueError('Duplicate opening IDs')
    strict=any(item.get('geometry',item).get('geometry_revision',0)>=2 for item in result.get('diagnostics',[]))
    for opening in openings.values():
        for key in ['room_a','room_b']:
            if opening.get(key) and opening[key] not in room_ids:raise ValueError('Opening references unknown room')
        if opening.get('room_a') and opening.get('room_a')==opening.get('room_b'):raise ValueError('Opening connects a room to itself')
    for edge in result['adjacency']:
        if edge['room_a'] not in room_ids or edge['room_b'] not in room_ids:raise ValueError('Adjacency references unknown room')
        if edge['room_a']==edge['room_b']:raise ValueError('Self-adjacency is invalid')
        if strict and edge.get('status')!='human_supplied':
            opening=openings.get(edge.get('opening_id'))
            if opening is None:raise ValueError('Automatic adjacency lacks opening evidence')
            if {opening['room_a'],opening['room_b']}!={edge['room_a'],edge['room_b']}:raise ValueError('Adjacency contradicts opening room sides')
