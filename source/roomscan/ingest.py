"""Stray Scanner import: mm depth, confidence 0..2, xyzw camera-to-world poses."""
from pathlib import Path
import csv
import hashlib
import zipfile
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
import cv2


def extract_zip(source, target):
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        if sum(i.file_size for i in archive.infolist()) > 4 * 1024**3:
            raise ValueError('Archive exceeds 4 GiB uncompressed limit')
        for info in archive.infolist():
            dest = (target / info.filename).resolve()
            if not dest.is_relative_to(target) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unsafe archive path or symlink')
        archive.extractall(target)
    return target


def scan_roots(path):
    path = Path(path)
    return sorted(p.parent for p in path.rglob('odometry.csv'))


def read_poses(root):
    with open(Path(root) / 'odometry.csv') as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        rows = [{k.strip(): v.strip() for k, v in r.items()} for r in reader]
    required = ['timestamp', 'frame', 'x', 'y', 'z', 'qx', 'qy', 'qz', 'qw']
    for row in rows:
        if any(not row.get(k) for k in required):
            raise ValueError('Missing pose fields')
        if not np.all(np.isfinite([float(row[k]) for k in required])):
            raise ValueError('Nonfinite pose fields')
    if len({r['frame'] for r in rows}) != len(rows):
        raise ValueError('Duplicate frame IDs')
    return rows


def video_info(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f'Cannot decode video: {path}')
    info = {'width': int(cap.get(3)), 'height': int(cap.get(4)),
            'fps': float(cap.get(5)), 'frames': int(cap.get(7))}
    cap.release()
    if not info['width'] or not info['height']:
        raise ValueError('Video has invalid dimensions')
    return info


def unproject(depth, confidence, row, matrix, rgb_size, pixel_step=4, min_confidence=2):
    h, w = depth.shape
    if not np.isin(confidence, [0, 1, 2]).all():
        raise ValueError('Confidence must contain only 0/1/2')
    if confidence.shape != depth.shape:
        raise ValueError('Depth/confidence shape mismatch')
    if depth.dtype != np.uint16:
        raise ValueError('Depth must be 16-bit millimetres')
    sx, sy = w / rgb_size[0], h / rgb_size[1]
    fx = float(row.get('fx') or matrix[0, 0]) * sx
    fy = float(row.get('fy') or matrix[1, 1]) * sy
    cx = float(row.get('cx') or matrix[0, 2]) * sx
    cy = float(row.get('cy') or matrix[1, 2]) * sy
    if fx <= 0 or fy <= 0:
        raise ValueError('Invalid focal length')
    vv, uu = np.mgrid[0:h:pixel_step, 0:w:pixel_step]
    z = depth[::pixel_step, ::pixel_step].astype(float) / 1000
    keep = (z > .15) & (z < 6) & (confidence[::pixel_step, ::pixel_step] >= min_confidence)
    # Stray Scanner stores poses in OpenCV camera convention (x right, y down, z forward).
    xyz = np.stack(((uu - cx) * z / fx, (vv - cy) * z / fy, z), axis=-1)[keep]
    q = [float(row[k]) for k in ('qx', 'qy', 'qz', 'qw')]
    r = Rotation.from_quat(q).as_matrix()
    t = np.array([float(row[k]) for k in ('x', 'y', 'z')])
    return xyz @ r.T + t


def load_scan(root, every=20, pixel_step=4):
    root = Path(root)
    rows = read_poses(root)
    matrix = np.loadtxt(root / 'camera_matrix.csv', delimiter=',')
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError('Invalid camera matrix')
    info = video_info(root / 'rgb.mp4')
    if info['frames'] != len(rows):
        raise ValueError('Video/pose frame count mismatch; explicit synchronization required')
    clouds, selected = [], []
    for row in rows[::every]:
        name = f"{int(row['frame']):06d}.png"
        depth_path = root / 'depth' / name
        conf_path = root / 'confidence' / name
        if not depth_path.exists() or not conf_path.exists():
            raise ValueError(f'Missing depth/confidence for {name}')
        depth = np.asarray(Image.open(depth_path))
        confidence = np.asarray(Image.open(conf_path))
        cloud = unproject(depth, confidence, row, matrix, (info['width'], info['height']), pixel_step)
        if len(cloud) >= 100:
            clouds.append(cloud)
            selected.append(row)
    if not clouds:
        raise ValueError('No valid high-confidence depth samples')
    meta = {'source': root.name, 'pose_count': len(rows), 'sampled_frames': len(clouds),
            'duration_seconds': float(rows[-1]['timestamp']) - float(rows[0]['timestamp']),
            'video': info, 'depth_unit': 'mm', 'min_confidence': 2,
            'camera_convention': 'OpenCV', 'imu_present': (root / 'imu.csv').exists(),
            'lens_distortion_applied': False}
    return clouds, selected, meta


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def provenance(path):
    path = Path(path)
    files = [path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
    return [{'path': str(p.relative_to(path) if path.is_dir() else p.name),
             'bytes': p.stat().st_size, 'sha256': file_hash(p)} for p in files]
