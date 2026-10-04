"""Classical two-view reconstruction for thin input; metric scale is unobservable."""
from pathlib import Path
import numpy as np
import cv2
from .geometry import measurement

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.heic', '.webp'}
VIDEO_SUFFIXES = {'.mov', '.mp4', '.m4v', '.avi', '.mkv'}


def extract_video(path, output, count=240, rotate_cw=False, return_metadata=False):
    if count < 1:
        raise ValueError('Video frame count must be positive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('Cannot decode video')
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if frames < 2:
        cap.release()
        raise ValueError('Video has fewer than two frames')
    files = []
    indices = np.linspace(0, frames-1, min(count, frames)).astype(int)
    decoded_indices = []
    for i, frame in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
        ok, image = cap.read()
        if ok:
            p = output / f'{i:03d}.jpg'
            if rotate_cw:image=cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE)
            h,w=image.shape[:2];scale=min(1.,960/max(h,w));image=cv2.resize(image,(round(w*scale),round(h*scale)))
            if not cv2.imwrite(str(p), image):
                cap.release()
                raise OSError(f'Cannot save extracted frame {p}')
            files.append(p)
            decoded_indices.append(int(frame))
    cap.release()
    metadata = {'method':'uniform_temporal_sampling','source_frames':frames,
                'fps':fps if np.isfinite(fps) and fps>0 else None,
                'requested_keyframes':count,'decoded_keyframes':len(files),
                'duration_seconds':frames/fps if np.isfinite(fps) and fps>0 else None,
                'max_sample_gap_seconds':float(max(np.diff(decoded_indices)))/fps
                    if len(decoded_indices)>1 and np.isfinite(fps) and fps>0 else None}
    return (files, metadata) if return_metadata else files


def describe(files):
    detector = cv2.SIFT_create(nfeatures=3000)
    features = []
    for file in files:
        image = cv2.imread(str(file))
        if image is None:
            raise ValueError(f'Cannot decode image {file}; convert HEIC to JPEG first')
        h, w = image.shape[:2]
        scale = min(1., 960/w)
        image = cv2.resize(image, (round(w*scale), round(h*scale)))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kp, desc = detector.detectAndCompute(gray, None)
        features.append((kp, desc, image.shape[:2]))
    return features


def pair_reconstruction(a, b):
    ka, da, shape = a
    kb, db, shape_b = b
    if da is None or db is None or shape != shape_b:
        return None
    matches = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [m[0] for m in matches if len(m) == 2 and m[0].distance < .7*m[1].distance]
    if len(good) < 30:
        return None
    pa = np.float32([ka[m.queryIdx].pt for m in good])
    pb = np.float32([kb[m.trainIdx].pt for m in good])
    h, w = shape
    # Approximate calibration only; disclosed and never converted to metric units.
    k = np.array([[w*.9, 0, w/2], [0, w*.9, h/2], [0, 0, 1.]])
    e, mask = cv2.findEssentialMat(pa, pb, k, method=cv2.RANSAC, prob=.999, threshold=1.)
    if e is None or e.shape != (3, 3):
        return None
    n, r, t, posemask = cv2.recoverPose(e, pa, pb, k, mask=mask)
    if n < 20:
        return None
    keep = posemask.ravel() > 0
    p1 = k @ np.c_[np.eye(3), np.zeros(3)]
    p2 = k @ np.c_[r, t]
    hom = cv2.triangulatePoints(p1, p2, pa[keep].T, pb[keep].T)
    xyz = (hom[:3] / hom[3]).T
    valid = np.isfinite(xyz).all(1) & (xyz[:,2] > 0) & (xyz[:,2] < 50)
    xyz = xyz[valid]
    if len(xyz) < 20:
        return None
    return xyz, {'matches': len(good), 'pose_inliers': int(n), 'points': len(xyz),
                 'intrinsics': 'assumed_focal_0.9_image_width', 'scale': 'arbitrary'}


def photo_room(files, rid, tier):
    features = describe(files)
    candidates = []
    # Dense video needs nearby overlapping views. Exhaustive comparisons are
    # retained for small photo sets, not hundreds of video frames.
    pairs = [(i, i+d) for d in (1,2) for i in range(len(features)-d)] if tier=='video' else [
        (i,j) for i in range(len(features)) for j in range(i+1,len(features))]
    for i,j in pairs:
        pair = pair_reconstruction(features[i], features[j])
        if pair:
            candidates.append((*pair, i, j))
    best = max(candidates, key=lambda p: p[1]['pose_inliers']) if candidates else None
    cloud = best[0] if best else np.empty((0,3))
    room = {'id': rid, 'name': rid, 'tier': tier, 'polygon': [], 'coordinate_unit': 'unresolved',
            'floor_area': measurement(unit='m2', method='metric_scale_unobservable'),
            'ceiling_height': measurement(method='metric_scale_unobservable'),
            'walls': [], 'openings': [], 'damage_regions': [], 'concealed_damage_flags': [],
            'scope_items': [], 'status': 'unresolved',
            'warnings': ['No metric scale or verified floor planes from monocular input.',
                         'Photo-only room adjacency is unresolved without shared geometric evidence.'],
            'image_count': len(files), 'reconstruction': best[1] if best else {'status':'insufficient_parallax_or_matches'}}
    if best:
        room['reconstruction']['status'] = 'relative_reconstruction'
        room['reconstruction']['pair'] = [Path(files[best[2]]).name, Path(files[best[3]]).name]
    room['reconstruction']['attempted_pairs'] = len(pairs)
    room['reconstruction']['successful_pairs'] = len(candidates)
    if tier=='video':
        room['warnings'][1] = 'This lightweight video path recovers one arbitrary-scale image pair, not a stitched room plan. Use --metric for experimental multi-view metric reconstruction.'
    return room, cloud
