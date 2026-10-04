"""Conservative RGB surface anomaly proposals, not verified damage diagnoses.

Candidates carry image masks, raw-frame IDs, geometric surface assignment and
metric support only where depth is valid. Texture/grout/shadows remain confounders.
"""
from pathlib import Path
import json
import numpy as np
import cv2
from PIL import Image
from scipy.spatial.transform import Rotation
from .geometry import measurement
from .ingest import read_poses


def anomaly_masks(image):
    lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(float)
    l=lab[:,:,0];background=cv2.GaussianBlur(l.astype(np.float32),(0,0),15)
    dark=background-l
    chroma=np.linalg.norm(lab[:,:,1:]-128,axis=2)
    stain=(dark>18)&(chroma>18)&(l>25)&(l<230)
    stain=cv2.morphologyEx(stain.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    stain=cv2.morphologyEx(stain,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    blackhat=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(11,11)))
    crack=(blackhat>35).astype(np.uint8)
    # Fixtures and grout are often long straight edges. Suppress proposals that
    # overlap such edges, including fragmented connected components.
    lines=cv2.HoughLinesP(cv2.Canny(gray,60,150),1,np.pi/180,70,minLineLength=70,maxLineGap=18)
    straight=np.zeros_like(gray)
    if lines is not None:
        for x1,y1,x2,y2 in lines.reshape(-1,4):cv2.line(straight,(x1,y1),(x2,y2),255,7)
    results=[]
    for kind,mask in [('discoloration_candidate',stain),('crack_candidate',crack)]:
        n,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
        for label in range(1,n):
            x,y,w,h,pixels=stats[label]
            if pixels<90 or pixels>image.shape[0]*image.shape[1]*.08:continue
            component=(labels==label).astype(np.uint8)
            contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            contour=max(contours,key=cv2.contourArea)
            if kind=='crack_candidate':
                if np.mean(straight[component>0]>0)>.35:continue
                length=cv2.arcLength(contour,False)/2
                width=pixels/max(length,1)
                if length<65 or width>4.5 or max(w,h)/max(1,min(w,h))<3:continue
                # Reject nearly straight long components (grout, fixtures, panel edges).
                vx,vy,cx,cy=cv2.fitLine(contour,cv2.DIST_L2,0,.01,.01).ravel()
                coords=np.column_stack(np.nonzero(component))[:,::-1]
                residual=np.abs((coords[:,0]-cx)*vy-(coords[:,1]-cy)*vx)
                if np.quantile(residual,.9)<2:continue
            elif w<10 or h<10:continue
            results.append({'class':kind,'mask':component,'bbox':[int(x),int(y),int(w),int(h)],'pixels':int(pixels)})
    return sorted(results,key=lambda x:x['pixels'],reverse=True)[:12]


def project_region(mask,depth,confidence,row,matrix,rgb_shape):
    h,w=depth.shape
    small=cv2.resize(mask,(w,h),interpolation=cv2.INTER_NEAREST)>0
    valid=small&(confidence==2)&(depth>.2)&(depth<6)
    vv,uu=np.nonzero(valid)
    if len(uu)<12:return None
    sx,sy=w/rgb_shape[1],h/rgb_shape[0]
    fx=float(row.get('fx') or matrix[0,0])*sx;fy=float(row.get('fy') or matrix[1,1])*sy
    cx=float(row.get('cx') or matrix[0,2])*sx;cy=float(row.get('cy') or matrix[1,2])*sy
    z=depth[vv,uu];xyz=np.c_[(uu-cx)*z/fx,(vv-cy)*z/fy,z]
    # Normal fit supports area correction only for approximately planar patches.
    centered=xyz-xyz.mean(0);_,singular,vt=np.linalg.svd(centered,full_matrices=False)
    normal=vt[-1];cosine=abs(normal[2])
    if cosine<.2 or singular[-1]/max(singular[0],1e-8)>.08:return None
    area=float(np.sum(z*z/(fx*fy))/cosine)
    rotation=Rotation.from_quat([float(row[k]) for k in ['qx','qy','qz','qw']]).as_matrix()
    translation=np.array([float(row[k]) for k in ['x','y','z']]);world=xyz@rotation.T+translation
    return {'points':world,'center':world.mean(0),'area_m2':area,'valid_depth_pixels':len(uu),
            'surface_planarity_ratio':float(singular[-1]/max(singular[0],1e-8)),'normal_world':normal@rotation.T}


def detect_scan_anomalies(root,structure,output,max_frames=48):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=True)
    rows=read_poses(root);matrix=np.loadtxt(root/'camera_matrix.csv',delimiter=',')
    wanted=set(np.linspace(0,len(rows)-2,min(max_frames,len(rows))).astype(int))
    cap=cv2.VideoCapture(str(root/'rgb.mp4'));candidates=[];image_quality=[];region_counter=0
    for index in range(len(rows)):
        if not cap.grab():break
        if index not in wanted:continue
        ok,image=cap.retrieve()
        if not ok:continue
        image=cv2.resize(image,(768,576));gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        image_quality.append({'frame':index,'blur_variance':float(cv2.Laplacian(gray,cv2.CV_64F).var()),
                              'dark_fraction':float((gray<30).mean()),'clipped_fraction':float((gray>250).mean())})
        row=rows[index];name=f"{int(row['frame']):06d}.png"
        depth=np.asarray(Image.open(root/'depth'/name)).astype(float)/1000
        confidence=np.asarray(Image.open(root/'confidence'/name))
        for proposal in anomaly_masks(image):
            geometry=project_region(proposal['mask'],depth,confidence,row,matrix,image.shape)
            if geometry is None:continue
            # Assign only to a nearby observed vertical structural plane.
            center=geometry['center'];best=None
            for wall in structure['walls']:
                a,b=np.asarray(wall['start']),np.asarray(wall['end']);direction=b-a;length=np.linalg.norm(direction);direction/=length
                tangent=(center[[0,2]]-a)@direction
                offset=abs(direction[0]*(center[2]-a[1])-direction[1]*(center[0]-a[0]))
                if -.10<tangent<length+.10 and offset<.15 and abs(geometry['normal_world'][1])<.3:
                    if best is None or offset<best[0]:best=(offset,wall)
            if best is None:continue
            wall=best[1]
            if geometry['area_m2']>.8 or geometry['area_m2']<.001:continue
            # Merge repeated observations of the same anomaly in nearby world position.
            duplicate=next((c for c in candidates if c['surface_id']==wall['id'] and c['class']==proposal['class'] and np.linalg.norm(np.asarray(c['center_xyz'])-center)<.18),None)
            if duplicate:
                duplicate['support_frames'].append(index);continue
            region_counter+=1;rid=f'{root.name}-anomaly-{region_counter}'
            maskpath=output/(rid+'-mask.png');cv2.imwrite(str(maskpath),proposal['mask']*255)
            overlay=image.copy();overlay[proposal['mask']>0]=(.5*overlay[proposal['mask']>0]+.5*np.array([20,50,240])).astype(np.uint8)
            cv2.imwrite(str(output/(rid+'-evidence.jpg')),overlay)
            rule='surface_discoloration_requires_moisture_and_material_review' if proposal['class']=='discoloration_candidate' else 'irregular_linear_mark_requires_crack_vs_joint_review'
            candidates.append({'id':rid,'surface_id':wall['id'],'class':proposal['class'],'status':'unverified_candidate',
                               'center_xyz':center.round(4).tolist(),'support_frames':[index],
                               'image_bbox':proposal['bbox'],'area':measurement(geometry['area_m2'],max(.02,geometry['area_m2']*.5),'m2','planar_depth_supported_mask','candidate'),
                               'evidence_image':rid+'-evidence.jpg','mask_image':rid+'-mask.png',
                               'valid_depth_pixels':geometry['valid_depth_pixels'],
                               'concealed_damage_flag':{'rule_id':rule,'action':'inspect','damage_confirmed':False},
                               'scope_item':{'surface_id':wall['id'],'action':'inspect_and_document','quantity':measurement(geometry['area_m2'],max(.02,geometry['area_m2']*.5),'m2','candidate_mask_extent','candidate')},
                               'confounders':['lighting','texture','grout or panel joints','furniture edges','reflective surface']})
    cap.release()
    report={'method':'classical_surface_anomaly_proposals','status':'requires_human_review','frames_assessed':len(image_quality),
            'candidates':candidates,'image_quality':image_quality,
            'warnings':['Anomalies are not validated damage classes or concealed damage diagnoses.',
                        'Depth area estimates require planar support and can be biased by grazing angles.',
                        'No labelled positive/negative damage benchmark exists in the supplied data.',
                        'Surface projection currently uses raw poses; mismatch is bounded by proximity filtering.']}
    (output/'damage.json').write_text(json.dumps(report,indent=2)+'\n');return report
