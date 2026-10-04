"""Rigid cross-capture alignment and evidence comparison, never ground truth scoring."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import linear_sum_assignment
import cv2


def transform_xz(points,yaw,translation):
    r=np.array([[np.cos(yaw),-np.sin(yaw)],[np.sin(yaw),np.cos(yaw)]])
    return np.asarray(points)@r.T+np.asarray(translation)


def icp2d(source,target,yaw,translation,max_iterations=35):
    q=transform_xz(source,yaw,translation);tree=cKDTree(target)
    total_yaw=yaw;total_t=np.asarray(translation,float)
    for _ in range(max_iterations):
        d,indices=tree.query(q);keep=d<min(.65,np.quantile(d,.75))
        if keep.sum()<50:break
        a,b=q[keep],target[indices[keep]];ac,bc=a.mean(0),b.mean(0)
        u,_,vt=np.linalg.svd((a-ac).T@(b-bc));r=vt.T@u.T
        if np.linalg.det(r)<0:vt[-1]*=-1;r=vt.T@u.T
        t=bc-ac@r.T;q=q@r.T+t;total_t=total_t@r.T+t
        angle=np.arctan2(r[1,0],r[0,0]);total_yaw+=angle
        if np.linalg.norm(t)<.0005 and abs(angle)<.0001:break
    return q,float(total_yaw),total_t


def align_xz(source,target,source_yaw=0,target_yaw=0):
    if len(source)>8000:source=source[::int(np.ceil(len(source)/8000))]
    if len(target)>10000:target=target[::int(np.ceil(len(target)/10000))]
    tree=cKDTree(target);best=[]
    for quarter in range(4):
        # structure.py's rotation uses opposite sign from this standard 2D rotation.
        yaw=target_yaw-source_yaw+quarter*np.pi/2
        rotated=transform_xz(source,yaw,[0,0]);base=np.median(target,axis=0)-np.median(rotated,axis=0)
        for dx in np.arange(-1.2,1.21,.4):
            for dz in np.arange(-1.2,1.21,.4):
                t=base+[dx,dz];q=rotated[::3]+t;d,_=tree.query(q)
                score=float(np.mean(np.minimum(d,.5)))
                best.append((score,yaw,t))
    refined=[]
    for _,yaw,t in sorted(best,key=lambda x:x[0])[:12]:
        q,yaw,t=icp2d(source,target,yaw,t)
        d,_=tree.query(q);reverse,_=cKDTree(q).query(target)
        score=float(np.mean(np.minimum(d,.3)))
        refined.append({'yaw_radians':yaw,'translation_xz_m':t.tolist(),
                        'median_source_to_target_m':float(np.median(d)),
                        'p90_source_to_target_m':float(np.quantile(d,.9)),
                        'source_overlap_within_10cm':float((d<.1).mean()),
                        'target_overlap_within_10cm':float((reverse<.1).mean()),'score':score})
    return min(refined,key=lambda x:x['score']),refined


def load_cloud(path):
    path=Path(path)
    if path.suffix=='.npz':return np.load(path)['points']
    with path.open() as f:
        for line in f:
            if line.strip()=='end_header':break
        return np.loadtxt(f)


def polygon_iou(a,b,grid=.05,a_holes=(),b_holes=()):
    a,b=np.asarray(a),np.asarray(b);lo=np.minimum(a.min(0),b.min(0))-.1;hi=np.maximum(a.max(0),b.max(0))+.1
    shape=np.ceil((hi-lo)/grid).astype(int)+1
    if np.prod(shape)>5_000_000:return 0.
    ma=np.zeros((shape[1],shape[0]),np.uint8);mb=ma.copy()
    cv2.fillPoly(ma,[np.rint((a-lo)/grid).astype(np.int32)],1);cv2.fillPoly(mb,[np.rint((b-lo)/grid).astype(np.int32)],1)
    for mask,holes in [(ma,a_holes),(mb,b_holes)]:
        for hole in holes:cv2.fillPoly(mask,[np.rint((np.asarray(hole)-lo)/grid).astype(np.int32)],0)
    return float(np.logical_and(ma,mb).sum()/max(1,np.logical_or(ma,mb).sum()))


def compare_structures(source,target,alignment):
    yaw=alignment['yaw_radians'];translation=alignment['translation_xz_m']
    roompairs=[]
    if source['rooms'] and target['rooms']:
        costs=np.array([[1-polygon_iou(transform_xz(s['polygon'],yaw,translation),t['polygon'],a_holes=[transform_xz(h,yaw,translation) for h in s.get('polygon_holes',[])],b_holes=t.get('polygon_holes',[])) for t in target['rooms']] for s in source['rooms']])
        si,ti=linear_sum_assignment(costs)
        for i,j in zip(si,ti):
            s,t=source['rooms'][i],target['rooms'][j];iou=1-costs[i,j]
            if iou<.2:continue
            sh,th=s['ceiling_height']['value'],t['ceiling_height']['value']
            roompairs.append({'source_room':s['id'],'target_room':t['id'],'polygon_iou':float(iou),
                              'area_difference_m2':s['floor_area']['value']-t['floor_area']['value'],
                              'ceiling_difference_m':sh-th if sh is not None and th is not None else None,
                              'status':'geometric_correspondence_candidate'})
    wallpairs=[];used=set()
    for wall in source['walls']:
        a,b=transform_xz([wall['start'],wall['end']],yaw,translation);direction=b-a;length=np.linalg.norm(direction)
        direction/=length
        options=[]
        for tw in target['walls']:
            if tw['id'] in used:continue
            c,d=np.asarray(tw['start']),np.asarray(tw['end']);tdir=d-c;tl=np.linalg.norm(tdir);tdir/=tl
            parallel=abs(direction@tdir)
            delta=c-a
            offset=abs(direction[0]*delta[1]-direction[1]*delta[0])
            projected=np.array([(c-a)@direction,(d-a)@direction]);overlap=max(0,min(length,projected.max())-max(0,projected.min()))
            fraction=overlap/min(length,tl)
            if parallel>.98 and offset<.18 and fraction>.45:options.append((offset+(1-fraction)*.1,tw,float(offset),float(fraction)))
        if options:
            _,tw,offset,fraction=min(options,key=lambda x:x[0]);used.add(tw['id'])
            delta=wall['length']['value']-tw['length']['value']
            wallpairs.append({'source_wall':wall['id'],'target_wall':tw['id'],'plane_offset_m':offset,
                              'support_overlap_fraction':fraction,'observed_length_difference_m':delta,
                              'status':'coverage_comparison_not_accuracy'})
    return {'rooms':roompairs,'walls':wallpairs,'unmatched_source_walls':len(source['walls'])-len(wallpairs),
            'unmatched_target_walls':len(target['walls'])-len(used)}


def compare_captures(source_cache,target_cache,source_structure,target_structure,output):
    sc,tc=np.load(Path(source_cache)/'clouds.npz'),np.load(Path(target_cache)/'clouds.npz')
    ss=json.loads(Path(source_structure).read_text());ts=json.loads(Path(target_structure).read_text())
    sf=ss['diagnostics']['horizontal_levels']['floor_y_m'];tf=ts['diagnostics']['horizontal_levels']['floor_y_m']
    s=sc['points'];t=tc['points']
    # Mid-height slabs reduce effects of ceiling coverage and floor texture density.
    s=s[(s[:,1]>sf+.5)&(s[:,1]<sf+1.7)][:,[0,2]]
    t=t[(t[:,1]>tf+.5)&(t[:,1]<tf+1.7)][:,[0,2]]
    alignment,hypotheses=align_xz(s,t,ss['diagnostics']['manhattan_yaw_radians'],ts['diagnostics']['manhattan_yaw_radians'])
    pairs=compare_structures(ss,ts,alignment)
    result={'status':'unverified_geometric_comparison','alignment':alignment,'hypotheses':hypotheses,
            'vertical_translation_m':tf-sf,'comparison':pairs,
            'warnings':['Rigid registration removes arbitrary session origin and yaw; it can also hide global pose error.',
                        'No scale fitting is performed; both LiDAR scans retain metric scale.',
                        'Camera path and furniture differences can affect coverage and segmentation.',
                        'Correspondence is algorithmic, not confirmation of physical room identity.',
                        'No laser/tape ground truth used; no accuracy gate pass is asserted.']}
    output=Path(output);output.mkdir(parents=True,exist_ok=True);(output/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    image=np.full((900,1100,3),247,np.uint8)
    src=transform_xz(s[::max(1,len(s)//30000)],alignment['yaw_radians'],alignment['translation_xz_m']);tgt=t[::max(1,len(t)//30000)]
    lo=np.minimum(np.quantile(src,.005,axis=0),np.quantile(tgt,.005,axis=0));hi=np.maximum(np.quantile(src,.995,axis=0),np.quantile(tgt,.995,axis=0));scale=min(1000/(hi-lo)[0],780/(hi-lo)[1])
    for pts,color in [(tgt,(201,125,40)),(src,(55,170,190))]:
        pix=((pts-lo)*scale+[50,70]).astype(int);valid=(pix[:,0]>=0)&(pix[:,0]<1100)&(pix[:,1]>=0)&(pix[:,1]<900);image[pix[valid,1],pix[valid,0]]=color
    cv2.putText(image,'Aligned wall/furniture slabs: reference blue, source orange',(35,35),cv2.FONT_HERSHEY_SIMPLEX,.6,(30,45,65),1)
    cv2.imwrite(str(output/'overlay.png'),image)
    return result
