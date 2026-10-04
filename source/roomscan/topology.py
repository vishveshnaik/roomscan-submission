"""Evidence gates for geometric boundaries and camera-supported free space."""
import numpy as np


def clip_ray_to_walls(start,end,wall,ignore_start_pixels=2):
    """Stop a ray before its first structural barrier, including diagonal rays.

    Sample at half-pixel intervals so rounding cannot skip a thin raster barrier.
    This is geometric consistency, not proof that a detected plane is a real wall.
    """
    start,end=np.asarray(start,float),np.asarray(end,float)
    steps=max(1,int(np.ceil(np.max(np.abs(end-start))*2)))
    samples=np.rint(start+(end-start)*np.linspace(0,1,steps+1)[:,None]).astype(int)
    valid=(samples[:,0]>=0)&(samples[:,0]<wall.shape[1])&(samples[:,1]>=0)&(samples[:,1]<wall.shape[0])
    distance=np.linalg.norm(samples-start,axis=1)
    valid&=distance>ignore_start_pixels
    indices=np.flatnonzero(valid)
    hit=indices[wall[samples[indices,1],samples[indices,0]]>0]
    if len(hit):
        index=int(hit[0]);return samples[max(0,index-2)],True
    return np.rint(end).astype(int),False


def trajectory_crossings(cameras,axis,position,start,end,max_step=1.2):
    """Reject large pose jumps; return actual interpolated crossing locations."""
    cameras=np.asarray(cameras);other=2 if axis==0 else 0;crossings=[]
    for c,d in zip(cameras,cameras[1:]):
        if np.linalg.norm(d-c)>max_step:continue
        if (c[axis]-position)*(d[axis]-position)>=0:continue
        alpha=(position-c[axis])/(d[axis]-c[axis]);point=c+alpha*(d-c)
        if start<point[other]<end:crossings.append(point.tolist())
    return crossings


def boundary_support(start,end,lines,max_offset=.14):
    """Measure collinear support; an unsupported contour is not an observed wall."""
    a,b=np.asarray(start),np.asarray(end);delta=b-a;length=np.linalg.norm(delta)
    if length<1e-8:return {'kind':'coverage_boundary','supported_fraction':0.,'plane_ids':[]}
    direction=delta/length;intervals=[];ids=[];offsets=[]
    for line in lines:
        axis=0 if line['axis']==0 else 1;other=1-axis
        if abs(direction[axis])>.15:continue
        offset=max(abs(a[axis]-line['position']),abs(b[axis]-line['position']))
        if offset>max_offset:continue
        c=a.copy();d=a.copy();c[axis]=d[axis]=line['position'];c[other]=line['start'];d[other]=line['end']
        span=sorted([(c-a)@direction,(d-a)@direction]);left=max(0,span[0]);right=min(length,span[1])
        if right-left>.10:intervals.append((left,right));ids.append(line['id']);offsets.append(offset)
    covered=0.;right=-float('inf')
    for left,end in sorted(intervals):
        covered+=max(0,end-max(left,right));right=max(right,end)
    fraction=min(1.,covered/length)
    return {'kind':'supported_wall_boundary' if fraction>=.6 else 'coverage_boundary',
            'supported_fraction':round(float(fraction),4),'plane_ids':ids,
            'max_plane_offset_m':float(max(offsets)) if offsets else None}


def height_column_support(points,axis,position,start,end,floor,step=.04):
    """Vertical occupancy distinguishes a wall face from a sparse rail or head."""
    other=2 if axis==0 else 0
    p=points[(np.abs(points[:,axis]-position)<.075)&(points[:,other]>=start)&(points[:,other]<=end)
             &(points[:,1]>floor+.20)&(points[:,1]<floor+1.65)]
    edges=np.arange(start,end+step*1.01,step)
    if len(edges)<2:return np.array([]),np.array([])
    heights=np.arange(floor+.20,floor+1.66,.15)
    counts,_,_=np.histogram2d(p[:,other],p[:,1],bins=(edges,heights))
    return (edges[:-1]+edges[1:])/2,(counts>0).sum(1)
