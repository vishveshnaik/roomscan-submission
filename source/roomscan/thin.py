"""Image-only multi-view reconstruction with learned metric scale and explicit gaps."""
from pathlib import Path
import json
import numpy as np
import cv2
from scipy.spatial.transform import Rotation
from .metric_depth import MetricDepthClient,scale_reconstruction
from .structure import extract_structure
from .drift import voxel_downsample
from .render import write_ply,cloud_preview


def rotate_to_up(points,cameras,up):
    up=np.asarray(up);up=up/np.linalg.norm(up)
    rotation,_=Rotation.align_vectors([[0.,1.,0.]],[up])
    matrix=rotation.as_matrix()
    return points@matrix.T,np.asarray(cameras)@matrix.T,matrix


def metric_multiview(files,output,weights='models/depth_pro.pt',video=False,max_depth_images=12,capture_id='visual-component'):
    from .sfm import reconstruct
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    reconstruction,metadata=reconstruct(files,output/'sfm',video=video)
    if reconstruction is None:
        return {'status':'unresolved','rooms':[],'walls':[],'openings':[],'adjacency':[],
                'diagnostics':{'sfm':metadata,'reason':'No geometrically verified reconstruction'}},np.empty((0,3))
    model=MetricDepthClient(weights)
    scale,scaleinfo=scale_reconstruction(reconstruction,metadata['image_index'],model,output/'metric-depth',max_depth_images)
    if scale is None:
        return {'status':'unresolved','rooms':[],'walls':[],'openings':[],'adjacency':[],
                'diagnostics':{'sfm':metadata,'metric_scale':scaleinfo}},np.empty((0,3))
    selected_names={p['image'] for p in scaleinfo['per_image']};clouds=[];cameras=[];ups=[]
    image_support=[]
    for image in sorted(reconstruction.images.values(),key=lambda i:i.name):
        if image.name not in selected_names:continue
        depth=np.load(output/'metric-depth'/(image.name+'.npy'))
        camera=reconstruction.camera(image.camera_id);cam_from_world=image.cam_from_world()
        h,w=depth.shape;vv,uu=np.mgrid[0:h:6,0:w:6];z=depth[::6,::6]
        # SIMPLE_RADIAL camera has one focal and a radial coefficient; inversion handles it.
        uv=np.c_[uu.ravel()*camera.width/w,vv.ravel()*camera.height/h]
        rays=np.asarray(camera.cam_from_img(uv));keep=np.isfinite(rays).all(1)&(z.ravel()>.2)&(z.ravel()<8)
        local=np.c_[rays[keep],np.ones(keep.sum())]*z.ravel()[keep,None]
        rotation=cam_from_world.rotation.matrix();translation=cam_from_world.translation
        # Monocular scale is fixed globally from model depths, not fitted to LiDAR.
        camera_position=-rotation.T@translation*scale
        world=local@rotation+camera_position
        clouds.append(world);cameras.append(camera_position);ups.append(np.array([0.,-1.,0.])@rotation)
        image_support.append({'image':image.name,'source':metadata['image_index'][image.name]['source'],'points':len(world)})
    if not clouds:
        return {'status':'unresolved','rooms':[],'walls':[],'openings':[],'adjacency':[],
                'diagnostics':{'sfm':metadata,'metric_scale':scaleinfo,'reason':'No supported dense views'}},np.empty((0,3))
    up=np.mean(ups,axis=0);points=np.concatenate(clouds)
    points,cameras,gravity_rotation=rotate_to_up(points,cameras,up)
    clouds=[cloud@gravity_rotation.T for cloud in clouds]
    structure=extract_structure(points,clouds,cameras,capture_id,output/'structure',grid=.08)
    coverage=metadata['registered_images']/metadata['input_images']
    for room in structure['rooms']:
        room['tier']='video' if video else 'photos'
        room['warnings'].extend(['Metric scale is a learned-depth estimate, not sensor-measured scale.',
                                 f"Only {metadata['registered_images']} of {metadata['input_images']} input images registered in this component.",
                                 'Unregistered views and disconnected components are excluded; property completeness is not established.'])
        # Add learned-scale systematic uncertainty instead of recycling LiDAR precision.
        for measurement in [room['floor_area'],room['ceiling_height']]+[w[k] for w in room['walls'] for k in ['length','area']]:
            if measurement['value'] is None:continue
            relative=scaleinfo['uncertainty_relative']*(2 if measurement['unit']=='m2' else 1)
            budget=max(measurement['upper']-measurement['value'],measurement['value']*relative)
            measurement['lower']=round(max(0,measurement['value']-budget),4);measurement['upper']=round(measurement['value']+budget,4)
            measurement['method']='learned_metric_scale+'+measurement['method']
    structure['diagnostics']['sfm']=metadata;structure['diagnostics']['metric_scale']=scaleinfo
    structure['diagnostics']['gravity_method']='mean_upright_camera_up_vector';structure['diagnostics']['views']=image_support
    structure['diagnostics']['registered_view_fraction']=coverage;structure['diagnostics']['used_lidar_or_sensor_poses']=False
    structure['status']='unresolved' if not structure['rooms'] else ('partial_reconstruction' if coverage<.95 or metadata['component_count']>1 else 'needs_review')
    p=voxel_downsample(points,.04);write_ply(p,output/'cloud.ply');cloud_preview(p,output/'cloud.png')
    (output/'thin-structure.json').write_text(json.dumps(structure,indent=2)+'\n')
    return structure,points
