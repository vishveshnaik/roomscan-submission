"""Local Apple Depth Pro inference; metric predictions are estimates, not truth."""
from pathlib import Path
import json
import hashlib
import time
import numpy as np
from PIL import Image


class MetricDepth:
    def __init__(self,weights='models/depth_pro.pt',device='auto'):
        import torch
        import depth_pro
        from dataclasses import replace
        from depth_pro.depth_pro import DEFAULT_MONODEPTH_CONFIG_DICT
        self.weights=Path(weights).resolve()
        if not self.weights.exists():raise ValueError('Metric model weights missing; run scripts/fetch-depth-model.py')
        self.device=torch.device('mps' if device=='auto' and torch.backends.mps.is_available() else ('cpu' if device=='auto' else device))
        torch.set_num_threads(4)
        self.model,self.transform=depth_pro.create_model_and_transforms(
            config=replace(DEFAULT_MONODEPTH_CONFIG_DICT,checkpoint_uri=str(self.weights)),device=self.device,
            precision=torch.float16 if self.device.type=='mps' else torch.float32)
        self.model.eval()
        self.weights_digest=None

    def infer(self,file,output,focal_px=None):
        import torch
        import depth_pro
        file,output=Path(file),Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        fingerprint=hashlib.sha256(file.read_bytes()).hexdigest()
        meta=output.with_suffix('.json')
        if output.exists() and meta.exists():
            old=json.loads(meta.read_text())
            if old.get('image_sha256')==fingerprint and old.get('supplied_focal_px')==focal_px:
                return np.load(output),old
        image,_,exif_focal=depth_pro.load_rgb(file)
        # Use only image EXIF or explicit calibration. LiDAR depth is never an inference input.
        supplied=focal_px if focal_px is not None else exif_focal
        start=time.perf_counter()
        with torch.inference_mode():prediction=self.model.infer(self.transform(image),f_px=torch.tensor(supplied,device=self.device) if supplied is not None else None)
        depth=prediction['depth'].float().cpu().numpy();focal=float(prediction['focallength_px'].float().cpu())
        np.save(output,depth)
        info={'model':'Apple Depth Pro','image_sha256':fingerprint,'image_size':[image.shape[1],image.shape[0]],
              'focal_px':focal,'supplied_focal_px':focal_px,'used_exif_focal':exif_focal is not None and focal_px is None,
              'device':str(self.device),'seconds':round(time.perf_counter()-start,3),
              'metric_units':'m','status':'uncalibrated_model_estimate','depth_used_as_ground_truth':False}
        meta.write_text(json.dumps(info,indent=2)+'\n')
        return depth,info


def scale_reconstruction(reconstruction,image_index,model,output,max_images=12):
    """Estimate one global SfM scale from model depth at triangulated tracks."""
    output=Path(output);ratios=[];per_image=[]
    images=sorted(reconstruction.images.values(),key=lambda x:x.name)
    selected=np.linspace(0,len(images)-1,min(max_images,len(images))).astype(int)
    if hasattr(model,'ensure_batch'):
        requests=[]
        for index in selected:
            image=images[index];source=Path(image_index[image.name]['source']);camera=reconstruction.camera(image.camera_id)
            requests.append({'file':str(source.resolve()),'output':str((output/(image.name+'.npy')).resolve()),
                             'focal_px':float(camera.focal_length)*Image.open(source).width/camera.width})
        model.ensure_batch(requests,output)
    for index in selected:
        image=images[index];source=Path(image_index[image.name]['source'])
        camera=reconstruction.camera(image.camera_id);pose=image.cam_from_world()
        source_width=Image.open(source).width
        depth,info=model.infer(source,output/(image.name+'.npy'),focal_px=float(camera.focal_length)*source_width/camera.width)
        local=[]
        for point in image.points2D:
            if not point.has_point3D():continue
            xyz=reconstruction.point3D(point.point3D_id).xyz
            predicted_z=float((pose*xyz)[2])
            uv=point.xy
            u=int(round(uv[0]*depth.shape[1]/camera.width));v=int(round(uv[1]*depth.shape[0]/camera.height))
            if not (0<=u<depth.shape[1] and 0<=v<depth.shape[0]) or predicted_z<=0:continue
            metric_z=float(depth[v,u])
            if .2<metric_z<8:local.append(metric_z/predicted_z)
        if len(local)>=20:
            scale=float(np.median(local));ratios.extend(local);per_image.append({'image':image.name,'scale':scale,'track_samples':len(local)})
    if len(ratios)<50:return None,{'status':'unresolved','reason':'Insufficient supported depth/track correspondences'}
    # Images receive equal weight to avoid one textured surface dominating scale.
    scales=np.array([x['scale'] for x in per_image]);scale=float(np.median(scales))
    spread=float(np.median(np.abs(scales-scale))/scale)
    return scale,{'status':'estimated','method':'median_model_depth_to_sfm_track_depth',
                  'scale_m_per_sfm_unit':scale,'per_image':per_image,'relative_scale_mad':spread,
                  'uncertainty_relative':max(.20,3*spread),'calibrated':False,'used_lidar_for_scale':False}


class MetricDepthClient:
    """Run torch in a separate process to avoid COLMAP's OpenMP runtime conflict."""
    def __init__(self,weights='models/depth_pro.pt'):
        self.weights=Path(weights).resolve()

    def ensure_batch(self,requests,output):
        import subprocess,sys
        output=Path(output);output.mkdir(parents=True,exist_ok=True)
        request_path=output/'inference-request.json'
        request_path.write_text(json.dumps({'weights':str(self.weights),'requests':requests},indent=2)+'\n')
        missing=False
        for req in requests:
            p=Path(req['output']);meta=p.with_suffix('.json')
            if not p.exists() or not meta.exists():missing=True;break
            old=json.loads(meta.read_text())
            if old.get('image_sha256')!=hashlib.sha256(Path(req['file']).read_bytes()).hexdigest() or old.get('supplied_focal_px')!=req.get('focal_px'):
                missing=True;break
        if missing:subprocess.run([sys.executable,'-m','roomscan.depth_worker',str(request_path)],check=True)

    def infer(self,file,output,focal_px=None):
        p=Path(output)
        self.ensure_batch([{'file':str(Path(file).resolve()),'output':str(p.resolve()),'focal_px':focal_px}],p.parent)
        return np.load(p),json.loads(p.with_suffix('.json').read_text())
