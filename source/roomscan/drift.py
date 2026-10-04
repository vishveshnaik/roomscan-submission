"""Bounded frame-to-model ICP. No claim of global loop closure."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def voxel_downsample(points, size=.04):
    _, indices = np.unique(np.floor(points / size).astype(np.int64), axis=0, return_index=True)
    return points[np.sort(indices)]


def register(source, target, iterations=12):
    tree = cKDTree(target)
    transformed = source.copy()
    total_r = np.eye(3)
    total_t = np.zeros(3)
    d0, _ = tree.query(source)
    for _ in range(iterations):
        d, idx = tree.query(transformed)
        keep = d < min(.18, np.quantile(d, .75))
        if keep.sum() < 50:
            break
        a, b = transformed[keep], target[idx[keep]]
        ac, bc = a.mean(0), b.mean(0)
        u, _, vt = np.linalg.svd((a - ac).T @ (b - bc))
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt[-1] *= -1
            r = vt.T @ u.T
        t = bc - r @ ac
        transformed = transformed @ r.T + t
        total_t = r @ total_t + t
        total_r = r @ total_r
        if np.linalg.norm(t) < .0005:
            break
    d1, _ = tree.query(transformed)
    before = float(np.median(d0))
    after = float(np.median(d1))
    shift = float(np.linalg.norm(total_t))
    angle = float(Rotation.from_matrix(total_r).magnitude())
    accepted = shift < .20 and angle < np.deg2rad(4) and after < before * .98
    return (transformed if accepted else source), {
        'accepted': bool(accepted), 'before_residual_m': before,
        'after_residual_m': after if accepted else before,
        'translation_m': shift, 'rotation_degrees': float(np.rad2deg(angle))}


def correct_clouds(clouds, enabled=True):
    model = voxel_downsample(clouds[0])
    result, log = [clouds[0]], []
    for i, cloud in enumerate(clouds[1:], 1):
        if enabled:
            fixed, stats = register(cloud, model)
            stats['sample_index'] = i
            log.append(stats)
        else:
            fixed = cloud
        result.append(fixed)
        model = voxel_downsample(np.concatenate([model, fixed]))
        if len(model) > 65000:
            model = model[::2]
    return result, {'method': 'bounded_frame_to_model_icp' if enabled else 'poses_as_is',
                    'enabled': enabled, 'accepted_frames': sum(x['accepted'] for x in log),
                    'frames': log, 'global_loop_closure': False}
