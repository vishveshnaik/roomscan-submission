"""Structural surface extraction from RGB-D points and observed free-space rays.

Candidates are evidence-based and explicitly unverified. Manhattan assumptions are
reported, not silently imposed on general geometry.
"""
from pathlib import Path
import numpy as np
import cv2
from scipy import ndimage
from scipy.spatial import cKDTree
from scipy.signal import find_peaks
from skimage.segmentation import watershed
from .geometry import measurement, horizontal_levels, area
from .topology import clip_ray_to_walls,boundary_support


def estimate_normals(points, voxel=.04, neighbors=16):
    from .drift import voxel_downsample
    p=voxel_downsample(points,voxel)
    if len(p)<3:return p,np.zeros_like(p),np.ones(len(p))
    tree=cKDTree(p);normals=np.zeros_like(p);quality=np.zeros(len(p))
    for start in range(0,len(p),15000):
        chunk=p[start:start+15000]
        distances,indices=tree.query(chunk,k=min(neighbors,len(p)))
        patches=p[indices];centered=patches-patches.mean(axis=1,keepdims=True)
        covariance=np.einsum('nki,nkj->nij',centered,centered)/patches.shape[1]
        values,vectors=np.linalg.eigh(covariance)
        normals[start:start+len(chunk)]=vectors[:,:,0]
        quality[start:start+len(chunk)]=values[:,0]/np.maximum(values.sum(1),1e-12)
    return p,normals,quality


def manhattan_yaw(normals,quality):
    keep=(np.abs(normals[:,1])<.20)&(quality<.025)
    angle=np.arctan2(normals[keep,2],normals[keep,0])
    if len(angle)<100:return 0.,0.
    hist,edges=np.histogram(angle%(np.pi/2),bins=180,range=(0,np.pi/2))
    smooth=ndimage.gaussian_filter1d(hist.astype(float),2,mode='wrap')
    yaw=float((edges[np.argmax(smooth)]+edges[np.argmax(smooth)+1])/2)
    deviations=np.abs(np.angle(np.exp(4j*(angle-yaw))))/4
    support=float((deviations<np.deg2rad(8)).mean())
    return yaw,support


def horizontal_plane(points,expected,window=.18):
    """Robust y=a*x+b*z+c plane with residual-based rejection."""
    p=points[np.abs(points[:,1]-expected)<window]
    if len(p)<150:return None
    if len(p)>25000:p=p[::int(np.ceil(len(p)/25000))]
    a=np.c_[p[:,0],p[:,2],np.ones(len(p))];keep=np.ones(len(p),bool)
    coef=None
    for _ in range(6):
        coef=np.linalg.lstsq(a[keep],p[keep,1],rcond=None)[0]
        residual=np.abs(a@coef-p[:,1]);mad=np.median(residual[keep])
        keep=residual<max(.025,min(.08,3*mad))
        if keep.sum()<100:return None
    if np.linalg.norm(coef[:2])>.12:return None
    residual=np.abs(a[keep]@coef-p[keep,1])
    return {'coefficients':coef.tolist(),'support_points':int(keep.sum()),
            'median_residual_m':float(np.median(residual)),
            'p95_residual_m':float(np.quantile(residual,.95)),'observed_fraction':float(keep.mean())}


def region_rings(mask,origin,grid):
    """Preserve internal exclusions instead of painting over enclosed spaces."""
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:return None,[]
    top=[i for i,h in enumerate(hierarchy[0]) if h[3]<0]
    selected=max(top,key=lambda i:cv2.contourArea(contours[i]))
    def ring(index):return cv2.approxPolyDP(contours[index],.025/grid,True)[:,0].astype(float)*grid+origin
    outer=ring(selected);holes=[];child=hierarchy[0,selected,2]
    while child>=0:
        hole=ring(child)
        if len(hole)>=3:holes.append(hole)
        child=hierarchy[0,child,0]
    return outer,holes


def local_ceiling_plane(horizontal,floor,room_area):
    """Highest broad, planar upper surface; a small shelf cannot define height."""
    p=horizontal[(horizontal[:,1]>floor+1.8)&(horizontal[:,1]<floor+4.5)]
    if len(p)<150:return None
    bins=np.arange(floor+1.76,floor+4.55,.04)
    counts,edges=np.histogram(p[:,1],bins);smooth=ndimage.gaussian_filter1d(counts.astype(float),1)
    peaks,_=find_peaks(smooth,prominence=max(10,smooth.max()*.05),distance=5)
    candidates=[]
    for peak in peaks:
        expected=(edges[peak]+edges[peak+1])/2;plane=horizontal_plane(p,expected,window=.12)
        if plane is None:continue
        a,b,c=plane['coefficients'];residual=np.abs(p[:,1]-(p[:,0]*a+p[:,2]*b+c))
        support=p[residual<max(.03,plane['p95_residual_m'])]
        cell_area=len(np.unique(np.floor(support[:,[0,2]]/.10).astype(int),axis=0))*.01
        if cell_area<max(.30,room_area*.12):continue
        plane['observed_horizontal_coverage_m2']=float(cell_area)
        plane['selection_method']='highest_spatially_supported_horizontal_surface'
        plane['surface_class_confirmed']=False
        candidates.append((expected,plane))
    return max(candidates,key=lambda item:item[0])[1] if candidates else None


def surface_lines(local,normal_local,quality,floor,ceiling,grid=.05):
    keep=(np.abs(normal_local[:,1])<.20)&(quality<.025)&(local[:,1]>floor+.20)
    if ceiling is not None:keep&=local[:,1]<ceiling-.15
    pts=local[keep];normals=normal_local[keep]
    lines=[]
    for axis in [0,2]:
        other=2 if axis==0 else 0
        aligned=np.abs(normals[:,axis])>.94
        p=pts[aligned]
        if len(p)<100:continue
        lo,hi=np.quantile(p[:,axis],[.005,.995])
        edges=np.arange(lo-.10,hi+.10,.025)
        counts,_=np.histogram(p[:,axis],edges)
        smooth=ndimage.gaussian_filter1d(counts.astype(float),1)
        peaks,_=find_peaks(smooth,prominence=max(30,smooth.max()*.045),distance=5)
        for peak in peaks:
            position=(edges[peak]+edges[peak+1])/2
            subset=p[np.abs(p[:,axis]-position)<.06]
            if len(subset)<100:continue
            tangential=np.arange(subset[:,other].min()-.1,subset[:,other].max()+.1,grid)
            # Require observed vertical extent so tabletops are not walls.
            height_edges=np.arange(floor+.15,(ceiling if ceiling is not None else floor+2.8)+.1,.15)
            counts2d,_,_=np.histogram2d(subset[:,other],subset[:,1],bins=(tangential,height_edges))
            vertical_bins=(counts2d>=1).sum(1)
            strong=(vertical_bins>=6)&((counts2d[:,height_edges[:-1]<floor+1.6]>0).sum(1)>=4)
            strong=ndimage.binary_closing(strong,structure=np.ones(3))
            segments,n=ndimage.label(strong)
            for label in range(1,n+1):
                indices=np.flatnonzero(segments==label)
                start,end=tangential[indices[0]],tangential[indices[-1]+1]
                if end-start<.55:continue
                support=subset[(subset[:,other]>=start)&(subset[:,other]<=end)]
                if len(support)<70 or np.ptp(support[:,1])<1.2:continue
                value=float(np.median(support[:,axis]));residual=float(np.median(np.abs(support[:,axis]-value)))
                lines.append({'axis':axis,'position':value,'start':float(start),'end':float(end),
                              'support_points':len(support),'vertical_extent_m':float(np.ptp(support[:,1])),
                              'median_residual_m':residual,'normal_alignment':float(np.median(np.abs(normals[aligned,axis])))})
    return lines


def extract_structure(points,clouds,cameras,source,output=None,grid=.05):
    source=f'{source}-g2'
    if len(points)<150:return {'status':'unresolved','rooms':[],'walls':[],'openings':[],'adjacency':[],
                                'diagnostics':{'reason':'Insufficient geometry','geometry_revision':2}}
    p,normals,quality=estimate_normals(points)
    horizontal=p[(np.abs(normals[:,1])>.94)&(quality<.025)]
    level_points=horizontal if len(horizontal)>=300 else points
    floor,ceiling,leveldiag=horizontal_levels(level_points)
    leveldiag['input_method']='planar_horizontal_samples' if len(horizontal)>=300 else 'raw_points_fallback'
    if floor is None:return {'status':'unresolved','rooms':[],'walls':[],'openings':[],'adjacency':[],'diagnostics':leveldiag}
    yaw,alignment=manhattan_yaw(normals,quality)
    # Local axes rotate world XZ into the dominant Manhattan frame.
    rotation=np.array([[np.cos(yaw),0,np.sin(yaw)],[0,1,0],[-np.sin(yaw),0,np.cos(yaw)]])
    local=p@rotation.T;lnorm=normals@rotation.T;lcameras=np.asarray(cameras)@rotation.T
    lines=surface_lines(local,lnorm,quality,floor,ceiling,grid)
    for index,line in enumerate(lines):line['id']=f'{source}-plane-{index+1}'
    floor_plane=horizontal_plane(local,floor)
    ceiling_plane=horizontal_plane(local,ceiling) if ceiling is not None else None
    xz=local[:,[0,2]];lo=np.floor(np.quantile(xz,.002,axis=0)/grid)*grid-.5
    hi=np.ceil(np.quantile(xz,.998,axis=0)/grid)*grid+.5
    shape=np.ceil((hi-lo)/grid).astype(int)+1
    if np.prod(shape)>4_000_000:raise ValueError('Structural raster too large')
    raster_shape=(shape[1],shape[0])
    def pixel(xz):return np.rint((np.asarray(xz)-lo)/grid).astype(int)
    wall=np.zeros(raster_shape,np.uint8)
    for line in lines:
        a=np.zeros(2);b=np.zeros(2);axis=0 if line['axis']==0 else 1;other=1-axis
        a[axis]=b[axis]=line['position'];a[other]=line['start'];b[other]=line['end']
        cv2.line(wall,tuple(pixel(a)),tuple(pixel(b)),1,2)
    free=np.zeros(raster_shape,np.uint8);ray_count=0;clipped_rays=0
    for cloud,camera in zip(clouds,lcameras):
        q=cloud@rotation.T
        band=q[(q[:,1]>floor+.25)&(q[:,1]<floor+1.6)]
        camera_xz=camera[[0,2]]
        for endpoint in band[::10]:
            delta=endpoint[[0,2]]-camera_xz;distance=np.linalg.norm(delta)
            if distance<.2 or distance>6:continue
            # Do not carve through the hit surface; tolerate imperfect pose registration.
            end=camera_xz+delta*max(0,(distance-.12)/distance)
            begin=pixel(camera_xz);end_pixel,clipped=clip_ray_to_walls(begin,pixel(end),wall)
            ray_count+=1;clipped_rays+=int(clipped)
            cv2.line(free,tuple(begin),tuple(end_pixel),1,1)
    # Floor is additional positive occupancy evidence, including downward-looking scans.
    floorpoints=local[np.abs(local[:,1]-floor)<.10][:,[0,2]]
    fp=pixel(floorpoints);valid=(fp>=0).all(1)&(fp<shape).all(1)
    free[fp[valid,1],fp[valid,0]]=1
    observed=free.copy()
    free=cv2.morphologyEx(free,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    free=ndimage.binary_fill_holes(free).astype(np.uint8)
    # Thickened structural partitions block watershed from merging across walls.
    free[wall>0]=0
    labels,n=ndimage.label(free)
    for i in range(1,n+1):
        if (labels==i).sum()*grid**2<.8:free[labels==i]=0
    distance=ndimage.distance_transform_edt(free)*grid
    # Room centers separated by narrow doors are distance-transform watershed basins.
    maxima=(distance==ndimage.maximum_filter(distance,size=int(2.5/grid)))&(distance>.55)
    seeds,n=ndimage.label(maxima)
    components,ncomp=ndimage.label(free)
    for i in range(1,ncomp+1):
        mask=components==i
        if not (seeds[mask]>0).any():
            n+=1;yx=np.unravel_index(np.argmax(np.where(mask,distance,-1)),distance.shape);seeds[yx]=n
    regions=watershed(-distance,seeds,mask=free.astype(bool))
    # Merge broad watershed cuts in open spaces; retain narrow supported connectors.
    for _ in range(4):
        merged=False
        ids=[int(x) for x in np.unique(regions) if x>0]
        for i,aa in enumerate(ids):
            if not np.any(regions==aa):continue
            ma=regions==aa
            for bb in ids[i+1:]:
                interface=ndimage.binary_dilation(ma)&(regions==bb)
                coords=np.column_stack(np.nonzero(interface))
                if len(coords)<3:continue
                span=np.linalg.norm(coords.max(0)-coords.min(0))*grid
                if span>1.6 and np.quantile(distance[interface],.8)>.55:
                    regions[regions==bb]=aa;ma=regions==aa;merged=True
        if not merged:break
    # Merge spurious tiny basins into their strongest neighboring basin.
    for label in np.unique(regions):
        if label==0 or (regions==label).sum()*grid**2>=1.4:continue
        mask=regions==label;border=ndimage.binary_dilation(mask)&~mask
        neighbors,counts=np.unique(regions[border],return_counts=True)
        choices=[(c,int(v)) for v,c in zip(neighbors,counts) if v>0]
        if choices:regions[mask]=max(choices)[1]
    rooms=[];region_ids={};polys_local=[]
    for label in sorted(np.unique(regions)):
        if label==0:continue
        mask=(regions==label).astype(np.uint8)
        if mask.sum()*grid**2<1.0:continue
        poly,holes=region_rings(mask,lo,grid)
        if len(poly)<3 or area(poly)<1:continue
        rid=f'{source}-space-{len(rooms)+1}';region_ids[int(label)]=rid
        poly3=np.c_[poly[:,0],np.zeros(len(poly)),poly[:,1]]@rotation
        worldholes=[(np.c_[hole[:,0],np.zeros(len(hole)),hole[:,1]]@rotation)[:,[0,2]].round(4).tolist() for hole in holes]
        worldpoly=poly3[:,[0,2]];perimeter=np.linalg.norm(poly-np.roll(poly,-1,axis=0),axis=1).sum()
        center=np.column_stack(np.nonzero(mask))[:,::-1].mean(0)*grid+lo
        pointpixels=pixel(local[:,[0,2]]);inside=(pointpixels>=0).all(1)&(pointpixels<shape).all(1)
        selected=np.flatnonzero(inside);selected=selected[regions[pointpixels[selected,1],pointpixels[selected,0]]==label]
        roompoints=local[selected]
        roomhorizontal=roompoints[(np.abs(lnorm[selected,1])>.94)&(quality[selected]<.025)]
        fplane=horizontal_plane(roomhorizontal,floor) if len(roomhorizontal)>150 else None
        cplane=local_ceiling_plane(roomhorizontal,floor,mask.sum()*grid**2) if ceiling is not None else None
        height=None;budget=None
        if fplane and cplane:
            coeff=np.array(cplane['coefficients'])-np.array(fplane['coefficients']);height=float(np.dot([center[0],center[1],1],coeff))
            budget=max(.08,.04+fplane['p95_residual_m']+cplane['p95_residual_m'])
        roomwalls=[]
        for k,(a,b) in enumerate(zip(worldpoly,np.roll(worldpoly,-1,axis=0))):
            length=np.linalg.norm(b-a)
            support=boundary_support(poly[k],poly[(k+1)%len(poly)],lines)
            supported=support["kind"]=="supported_wall_boundary"
            roomwalls.append({'id':f'{rid}-boundary-{k+1}','start':a.round(4).tolist(),'end':b.round(4).tolist(),
                              'length':measurement(length,max(.08,length*.03,length*(1-support['supported_fraction'])),method='plane_supported_boundary',status='candidate') if supported else measurement(method='physical_wall_length_unresolved'),
                              'coverage_length':measurement(length,max(.05,grid*2),method='raster_contour_extent',status='candidate'),
                              'area':measurement(length*height,max(.2,length*height*.08),'m2','boundary_times_local_height','candidate') if height and supported else measurement(unit='m2',method='physical_wall_surface_unresolved'),
                              'status':'candidate_supported_wall' if supported else 'unresolved_boundary',
                              'structural_evidence':support})
        room={'id':rid,'name':f'Space {len(rooms)+1}','tier':'lidar','polygon':worldpoly.round(4).tolist(),'polygon_holes':worldholes,'coordinate_unit':'m',
              'floor_area':measurement(mask.sum()*grid**2,max(.3,perimeter*.08,float(((mask>0)&(observed==0)).sum()*grid**2)),'m2','raster_region_extent_with_explicit_exclusions','candidate'),
              'ceiling_height':measurement(height,budget,method='local_robust_horizontal_planes',status='estimated') if height else measurement(method='local_ceiling_not_supported'),
              'walls':roomwalls,'openings':[],'damage_regions':[],'concealed_damage_flags':[],'scope_items':[],
              'status':'needs_review','warnings':['Room partition is inferred from walls and observed free space; verify semantic identity.',
                                                'Boundary segments without structural plane support may be occlusion or watershed cuts.'],
              'label_position':((np.array([np.unravel_index(np.argmax(ndimage.distance_transform_edt(mask)),mask.shape)[1]*grid+lo[0],0,np.unravel_index(np.argmax(ndimage.distance_transform_edt(mask)),mask.shape)[0]*grid+lo[1]])@rotation)[[0,2]]).round(4).tolist(),
              'surface_evidence':{'floor_plane':fplane,'ceiling_plane':cplane,
                                  'raster_extent_m2':float(mask.sum()*grid**2),
                                  'directly_observed_extent_m2':float(((mask>0)&(observed>0)).sum()*grid**2),
                                  'inferred_extent_m2':float(((mask>0)&(observed==0)).sum()*grid**2),
                                  'supported_boundary_fraction':float(sum(np.linalg.norm(np.array(w['end'])-w['start'])*w['structural_evidence']['supported_fraction'] for w in roomwalls)/max(perimeter,1e-8))}}
        rooms.append(room);polys_local.append(poly)
    adjacency=[];openings=[];partition_interfaces=[]
    # Interfaces between directly connected basins are passage candidates, not doors by decree.
    seen=set()
    for axis in [0,1]:
        a=np.take(regions,range(regions.shape[axis]-1),axis=axis);b=np.take(regions,range(1,regions.shape[axis]),axis=axis)
        yy,xx=np.nonzero((a!=b)&(a>0)&(b>0))
        for aa,bb in set(tuple(sorted((int(x),int(y)))) for x,y in zip(a[yy,xx],b[yy,xx])):
            if (aa,bb) in seen or aa not in region_ids or bb not in region_ids:continue
            seen.add((aa,bb))
            ma=regions==aa;mb=regions==bb
            interface=ndimage.binary_dilation(ma)&mb
            coords=np.column_stack(np.nonzero(interface))[:,::-1]*grid+lo
            if len(coords)<3:continue
            span=float(np.linalg.norm(coords.max(0)-coords.min(0)))
            center=coords.mean(0);world=np.array([center[0],floor,center[1]])@rotation
            partition_interfaces.append({'room_a':region_ids[aa],'room_b':region_ids[bb],
                                         'center':world[[0,2]].round(4).tolist(),'interface_span_m':span,
                                         'status':'geometric_contact_only','physical_opening_established':False})
    from .openings import wall_gap_candidates
    opening_diagnostics={}
    door_gaps=wall_gap_candidates(lines,local,lcameras,floor,rotation,regions,lo,grid,region_ids,source,opening_diagnostics)
    openings.extend(door_gaps)
    for gap in door_gaps:
        for room in rooms:
            if room['id'] in [gap['room_a'],gap['room_b']]:room['openings'].append(gap)
        if gap['room_a'] and gap['room_b']:
            adjacency.append({'room_a':gap['room_a'],'room_b':gap['room_b'],'opening_id':gap['id'],
                              'status':'candidate','evidence':'bounded_wall_gap'})
    walls=[]
    for i,line in enumerate(lines):
        a=np.zeros(3);b=np.zeros(3);axis=line['axis'];other=2 if axis==0 else 0
        a[axis]=b[axis]=line['position'];a[other]=line['start'];b[other]=line['end'];a[1]=b[1]=floor
        wa,wb=a@rotation,b@rotation
        walls.append({'id':f'{source}-plane-{i+1}','start':wa[[0,2]].round(4).tolist(),'end':wb[[0,2]].round(4).tolist(),
                      'length':measurement(line['end']-line['start'],max(.04,line['median_residual_m']*3),method='vertical_plane_support',status='estimated'),
                      'support':line,'status':'candidate_structural_wall'})
    if output:
        output=Path(output);output.mkdir(parents=True,exist_ok=True)
        colors=np.array([[245,247,251],[197,219,248],[196,231,218],[229,213,244],[249,224,197],[203,225,238],[235,218,228]],np.uint8)
        image=colors[regions%len(colors)];image[wall>0]=[36,54,82]
        image[free==0]=np.where((wall>0)[...,None],[36,54,82],[245,247,251])[free==0]
        cv2.imwrite(str(output/'structural-raster.png'),cv2.resize(cv2.cvtColor(image,cv2.COLOR_RGB2BGR),None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST))
        np.savez_compressed(output/'structure-map.npz',regions=regions,wall=wall,free=free,origin=lo,rotation=rotation,grid=grid,observed=observed)
    return {'status':'needs_review','rooms':rooms,'walls':walls,'openings':openings,'adjacency':adjacency,
            'diagnostics':{'horizontal_levels':leveldiag,'floor_plane':floor_plane,'ceiling_plane':ceiling_plane,
                           'manhattan_yaw_radians':yaw,'manhattan_normal_support_fraction':alignment,
                           'structural_planes':len(walls),'free_space_area_m2':float(free.sum()*grid**2),
                           'region_count':len(rooms),'opening_candidates':len(openings),'grid_m':grid,'geometry_revision':2,
                           'ray_count':ray_count,'wall_clipped_rays':clipped_rays,
                           'partition_interfaces':partition_interfaces,'opening_evidence':opening_diagnostics,
                           'directly_observed_area_m2':float(((free>0)&(observed>0)).sum()*grid**2),
                           'inferred_area_m2':float(((free>0)&(observed==0)).sum()*grid**2),
                           'limitations':['Manhattan orientation prior','Furniture planes may appear as walls',
                                          'Watershed cuts are not verified door jambs','Local plane ranges are uncalibrated']}}
