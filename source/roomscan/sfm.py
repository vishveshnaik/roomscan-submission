"""CPU COLMAP reconstruction using images alone, with explicit component coverage."""
from pathlib import Path
import json
import hashlib
import numpy as np
import cv2


def reconstruct(files,output,max_dimension=960,video=False):
    import pycolmap
    output=Path(output);images=output/'images';images.mkdir(parents=True,exist_ok=True)
    image_index={};signature=hashlib.sha256()
    for index,file in enumerate(files):
        file=Path(file);image=cv2.imread(str(file))
        if image is None:raise ValueError(f'Cannot decode {file}')
        h,w=image.shape[:2];scale=min(1.,max_dimension/max(w,h));image=cv2.resize(image,(round(w*scale),round(h*scale)))
        name=f'{index:05d}.jpg';cv2.imwrite(str(images/name),image)
        image_index[name]={'source':str(file),'input_index':index,'scale':scale,'width':image.shape[1],'height':image.shape[0]}
        signature.update(file.read_bytes())
    for stale in images.glob('*.jpg'):
        if stale.name not in image_index:stale.unlink()
    fingerprint=signature.hexdigest()
    cache=output/'reconstruction.json'
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved.get('input_sha256')==fingerprint and saved.get('max_dimension')==max_dimension and saved.get('configuration_revision')==4 and saved.get('video',bool(saved.get('loop_pair_candidates'))) == (video if len(files)>100 else False):
            saved['image_index']=image_index
            cache.write_text(json.dumps(saved,indent=2)+'\n')
            reconstruction=pycolmap.Reconstruction(output/'model') if (output/'model').exists() else None
            return reconstruction,saved
    database=output/'database.db'
    for suffix in ['', '-shm','-wal']:
        path=Path(str(database)+suffix)
        if path.exists():path.unlink()
    pycolmap.set_random_seed(0)
    pycolmap.extract_features(database,images,camera_mode=pycolmap.CameraMode.SINGLE,
                             reader_options={'camera_model':'SIMPLE_RADIAL','camera_params':f'{max(image.shape[:2])*.85},{image.shape[1]/2},{image.shape[0]/2},0'},
                             extraction_options={'num_threads':4,'sift':{'max_num_features':7000,'peak_threshold':.002}},device=pycolmap.Device.cpu)
    if video and len(files)>100:
        pycolmap.match_sequential(database,matching_options={'num_threads':4},pairing_options={'overlap':12,'loop_detection':False},device=pycolmap.Device.cpu)
    else:
        pycolmap.match_exhaustive(database,matching_options={'num_threads':4},device=pycolmap.Device.cpu)
    loop_pairs=add_visual_loop_matches(database,output) if video and len(files)>100 else 0
    options={'num_threads':4,'random_seed':0,'min_model_size':3,'init_num_trials':150,'mapper':{'init_min_num_inliers':40,'init_min_tri_angle':3.0,
                                                    'abs_pose_min_num_inliers':25},
             'ba_global_max_num_iterations':35,'ba_local_max_num_iterations':20}
    maps=pycolmap.incremental_mapping(database,images,output/'components',options=options)
    summaries=[]
    for idx,reconstruction in maps.items():
        summaries.append({'component':int(idx),'images':reconstruction.num_reg_images(),'points':reconstruction.num_points3D(),
                          'mean_reprojection_error_px':reconstruction.compute_mean_reprojection_error()})
    best=max(maps.values(),key=lambda r:r.num_reg_images()) if maps else None
    model=output/'model';model.mkdir(parents=True,exist_ok=True)
    if not best:
        import shutil
        shutil.rmtree(model)
    if best:
        best.write(model);best.export_PLY(output/'sparse.ply')
    saved={'engine':'pycolmap','version':pycolmap.__version__,'input_sha256':fingerprint,'max_dimension':max_dimension,'configuration_revision':4,
           'input_images':len(files),'registered_images':best.num_reg_images() if best else 0,
           'video':video if len(files)>100 else False,'component_count':len(maps),'loop_pair_candidates':loop_pairs,'components':summaries,'image_index':image_index,
           'metric_scale':'unresolved_until_metric_depth_fusion','used_depth_or_sensor_poses':False}
    cache.write_text(json.dumps(saved,indent=2)+'\n')
    return best,saved


def add_visual_loop_matches(database,output,neighbors=10):
    """Input-trained bag-of-SIFT retrieval, then COLMAP geometric verification."""
    import sqlite3
    import pycolmap
    connection=sqlite3.connect(database)
    rows=connection.execute('SELECT images.image_id,images.name,descriptors.rows,descriptors.cols,descriptors.data FROM images JOIN descriptors USING(image_id)').fetchall();connection.close()
    descriptors=[np.frombuffer(r[4],dtype=np.uint8).reshape(r[2],r[3]).astype(np.float32) for r in rows]
    valid=[d for d in descriptors if len(d)>0]
    if not valid:return 0
    combined=np.concatenate(valid);rng=np.random.default_rng(0)
    sample=combined[rng.choice(len(combined),min(20000,len(combined)),replace=False)]
    cv2.setRNGSeed(0);_,_,centers=cv2.kmeans(sample,64,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,15,.5),1,cv2.KMEANS_PP_CENTERS)
    from scipy.spatial import cKDTree
    tree=cKDTree(centers);hist=[]
    for d in descriptors:
        if len(d):_,word=tree.query(d);h=np.bincount(word,minlength=64).astype(float)
        else:h=np.zeros(64)
        hist.append(h)
    hist=np.asarray(hist);idf=np.log((len(rows)+1)/(1+(hist>0).sum(0)))+1;hist*=idf
    hist/=np.maximum(np.linalg.norm(hist,axis=1,keepdims=True),1e-8);similarity=hist@hist.T
    pairs=set()
    for i,row in enumerate(rows):
        for j in np.argsort(similarity[i])[::-1]:
            if abs(i-j)<15 or similarity[i,j]<.55:continue
            pairs.add(tuple(sorted((row[1],rows[j][1]))))
            if sum(row[1] in pair for pair in pairs)>=neighbors:break
    output=Path(output);output.mkdir(parents=True,exist_ok=True);pairfile=output/'loop-pairs.txt'
    pairfile.write_text(''.join(a+' '+b+'\n' for a,b in sorted(pairs)))
    pycolmap.match_image_pairs(database,matching_options={'num_threads':4},pairing_options={'match_list_path':str(pairfile)},device=pycolmap.Device.cpu)
    return len(pairs)
