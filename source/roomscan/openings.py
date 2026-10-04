"""Openings require vertically supported jambs and evidence of clear passage."""
import numpy as np
from .geometry import measurement
from .topology import trajectory_crossings,height_column_support


def side_rooms(center,axis,regions,origin,grid,region_ids):
    rooms=[]
    for direction in [-1,1]:
        labels=[]
        for distance in [.2,.35,.5,.75]:
            point=center.copy();point[axis]+=direction*distance
            pix=np.rint((point[[0,2]]-origin)/grid).astype(int)
            if 0<=pix[0]<regions.shape[1] and 0<=pix[1]<regions.shape[0]:
                label=int(regions[pix[1],pix[0]])
                if label in region_ids:labels.append(label)
        rooms.append(region_ids[max(set(labels),key=lambda n:(labels.count(n),-n))] if labels else None)
    return rooms


def wall_gap_candidates(lines,local,cameras,floor,rotation,regions,origin,grid,region_ids,source,diagnostics=None):
    candidates=[];groups=[];rejections=[]
    for line in sorted(lines,key=lambda x:(x['axis'],x['position'],x['start'])):
        group=next((g for g in groups if g[0]['axis']==line['axis'] and abs(g[0]['position']-line['position'])<.10),None)
        if group is None:groups.append([line])
        else:group.append(line)
    for group in groups:
        segments=sorted(group,key=lambda x:x['start'])
        for a,b in zip(segments,segments[1:]):
            start,end=a['end'],b['start'];width=end-start
            if not .45<width<1.6:continue
            axis=a['axis'];other=2 if axis==0 else 0;position=(a['position']+b['position'])/2
            evidence={'bounding_plane_ids':[a.get('id'),b.get('id')],'initial_width_m':float(width)}
            def reject(reason):rejections.append(dict(evidence,reason=reason))
            # Jamb transitions are fitted only from lower wall faces, not lintels.
            x,vertical_bins=height_column_support(local,axis,position,start-.3,end+.3,floor)
            left=x[(x<=start+.06)&(x>=start-.25)&(vertical_bins>=4)]
            right=x[(x>=end-.06)&(x<=end+.25)&(vertical_bins>=4)]
            if len(left)<2 or len(right)<2:reject('insufficient_vertical_jamb_support');continue
            refined_start=float(left.max()+.02);refined_end=float(right.min()-.02);width=refined_end-refined_start
            if not .45<width<1.6:reject('refined_width_outside_passage_range');continue
            interior=(x>refined_start+.08)&(x<refined_end-.08)
            occupied=float((vertical_bins[interior]>=4).mean()) if interior.any() else 1.
            evidence['lower_gap_occupied_fraction']=occupied
            if occupied>.20:reject('wall_surface_present_inside_gap');continue
            center=np.zeros(3);center[axis]=position;center[other]=(refined_start+refined_end)/2;center[1]=floor
            crossings=trajectory_crossings(cameras,axis,position,refined_start,refined_end)
            head=local[(np.abs(local[:,axis]-position)<.09)&(local[:,other]>refined_start+.08)
                       &(local[:,other]<refined_end-.08)&(local[:,1]>floor+1.7)&(local[:,1]<floor+2.7)]
            head_edges=np.arange(refined_start+.08,refined_end-.08+.08,.08)
            head_counts,_=np.histogram(head[:,other],head_edges)
            head_coverage=float((head_counts>0).mean()) if len(head_counts) else 0.
            head_supported=len(head)>=20 and head_coverage>=.60
            room_a,room_b=side_rooms(center,axis,regions,origin,grid,region_ids)
            distinct_rooms=bool(room_a and room_b and room_a!=room_b)
            # A blind furniture recess or unobserved strip is not an opening.
            if not crossings and not (head_supported and distinct_rooms):reject('no_traversal_or_supported_two_sided_head');continue
            jambs=[]
            for tangent in [refined_start,refined_end]:
                q=center.copy();q[other]=tangent;jambs.append((q@rotation)[[0,2]].round(4).tolist())
            height=float(np.quantile(head[:,1],.05)-floor) if head_supported else None
            evidence.update({'camera_crossings':len(crossings),'crossing_positions_local':crossings,
                             'head_support_points':len(head),'head_span_coverage':head_coverage,
                             'vertically_supported_jambs':True,'bounded_by_two_wall_segments':True,
                             'distinct_room_sides':distinct_rooms,'classification_confirmed':False,
                             'jamb_accuracy_calibrated':False})
            world=center@rotation
            candidate={'id':f'{source}-door-gap-{len(candidates)+1}','class':'doorway_candidate',
                       'center':world[[0,2]].round(4).tolist(),'jamb_points':jambs,
                       'width':measurement(width,max(.12,grid*2),method='lower_wall_jamb_transitions',status='candidate'),
                       'height':measurement(height,.15,method='spanning_head_support',status='candidate') if height else measurement(),
                       'room_a':room_a,'room_b':room_b if distinct_rooms else None,
                       'status':'candidate','jambs_verified':False,'evidence':evidence}
            duplicate=next((old for old in candidates if np.linalg.norm(np.array(old['center'])-candidate['center'])<.3),None)
            if duplicate:reject('duplicate_collinear_gap');continue
            candidates.append(candidate)
    if diagnostics is not None:diagnostics.update({'rejected_gaps':rejections,'accepted_gap_count':len(candidates)})
    return candidates
