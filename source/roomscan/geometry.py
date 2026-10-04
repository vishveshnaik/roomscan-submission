"""Observed-floor segmentation. Polygons are coverage estimates, not certified walls."""
import numpy as np
import cv2
from scipy import ndimage
from scipy.signal import find_peaks


def measurement(value=None, uncertainty=None, unit='m', method='unresolved', status='unresolved'):
    if value is None:
        return {'value': None, 'lower': None, 'upper': None, 'unit': unit,
                'confidence_level': None, 'interval_kind': 'unavailable', 'method': method, 'status': status}
    value, uncertainty = float(value), float(uncertainty)
    return {'value': round(value, 4), 'lower': round(max(0., value - uncertainty), 4),
            'upper': round(value + uncertainty, 4), 'unit': unit,
            'confidence_level': None, 'interval_kind': 'uncalibrated_error_budget',
            'method': method, 'status': status}


def horizontal_levels(points):
    y = points[:, 1]
    low, high = np.quantile(y, [.005, .995])
    bins = np.arange(low - .05, high + .05, .02)
    hist, edges = np.histogram(y, bins)
    smooth = ndimage.gaussian_filter1d(hist.astype(float), 1)
    peaks, _ = find_peaks(smooth, prominence=max(10., smooth.max() * .08), distance=15)
    centers = (edges[:-1] + edges[1:]) / 2
    # Structural floor/ceiling must be widely separated; strongest consistent pair.
    pairs = [(smooth[a] + smooth[b], centers[a], centers[b]) for a in peaks for b in peaks
             if 1.8 < centers[b] - centers[a] < 4.5]
    if not pairs:
        if len(peaks) == 0:
            return None, None, {'reason': 'No supported horizontal floor plane'}
        floor_peaks = [p for p in peaks if centers[p] < np.quantile(y, .25) + .10]
        if not floor_peaks:
            return None, None, {'reason': 'No supported low horizontal floor plane'}
        peak = max(floor_peaks, key=lambda p: smooth[p])
        floor = float(np.median(y[np.abs(y - centers[peak]) < .035]))
        return floor, None, {'floor_y_m': floor, 'ceiling_y_m': None,
                             'floor_samples': int((np.abs(y-floor)<.08).sum()),
                             'ceiling_samples': 0, 'reason': 'Ceiling not observed; floor retained'}
    _, floor, ceiling = max(pairs)
    floor = float(np.median(y[np.abs(y - floor) < .035]))
    ceiling = float(np.median(y[np.abs(y - ceiling) < .035]))
    return floor, ceiling, {'floor_y_m': floor, 'ceiling_y_m': ceiling,
                            'floor_samples': int((np.abs(y - floor) < .08).sum()),
                            'ceiling_samples': int((np.abs(y - ceiling) < .08).sum())}


def area(poly):
    p = np.asarray(poly)
    return abs(float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1)))) / 2


def rooms_from_cloud(points, source_id, grid=.05):
    floor, ceiling, levels = horizontal_levels(points)
    if floor is None:
        return [], [], {'levels': levels, 'status': 'unresolved'}
    fp = points[np.abs(points[:, 1] - floor) < .10][:, [0, 2]]
    lo = np.floor(fp.min(0) / grid) * grid - .25
    hi = np.ceil(fp.max(0) / grid) * grid + .25
    shape = np.ceil((hi - lo) / grid).astype(int) + 1
    if np.prod(shape) > 4_000_000:
        raise ValueError('Scan footprint too large; check units')
    count = np.zeros((shape[1], shape[0]), dtype=np.uint16)
    ij = np.floor((fp - lo) / grid).astype(int)
    np.add.at(count, (ij[:, 1], ij[:, 0]), 1)
    occupied = (count > 0).astype(np.uint8)
    occupied = cv2.morphologyEx(occupied, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    occupied = ndimage.binary_fill_holes(occupied)
    labels, n = ndimage.label(occupied)
    for i in range(1, n + 1):
        if (labels == i).sum() * grid**2 < .6:
            occupied[labels == i] = False
    # Erode narrow connectors, retain cores, propagate within each connected footprint.
    cores, n = ndimage.label(ndimage.binary_erosion(occupied, iterations=7))
    seeds = np.zeros_like(cores)
    seq = 0
    for i in range(1, n + 1):
        if (cores == i).sum() * grid**2 > .45:
            seq += 1
            seeds[cores == i] = seq
    components, nc = ndimage.label(occupied)
    segments = np.zeros_like(seeds)
    for i in range(1, nc + 1):
        mask = components == i
        local = np.where(mask, seeds, 0)
        if not local.any():
            seq += 1
            segments[mask] = seq
        else:
            _, nearest = ndimage.distance_transform_edt(local == 0, return_indices=True)
            segments[mask] = local[tuple(nearest)][mask]
    rooms = []
    for i in sorted(np.unique(segments)):
        if i == 0:
            continue
        mask = (segments == i).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(contours, key=cv2.contourArea)
        poly = cv2.approxPolyDP(c, .12 / grid, True)[:, 0].astype(float) * grid + lo
        if len(poly) < 3 or area(poly) < .5:
            continue
        rid = f'{source_id}-room-{int(i)}'
        room_area = area(poly)
        perimeter = float(np.linalg.norm(poly - np.roll(poly, -1, axis=0), axis=1).sum())
        walls = []
        for k, (a, b) in enumerate(zip(poly, np.roll(poly, -1, axis=0))):
            length = float(np.linalg.norm(b - a))
            # A floor boundary can be occlusion or a segmentation cut, not a wall.
            walls.append({'id': f'{rid}-wall-{k+1}', 'start': a.round(4).tolist(),
                          'end': b.round(4).tolist(),
                          'length': measurement(length, max(.15, length * .06), method='floor_boundary', status='candidate'),
                          'area': (measurement(length * (ceiling-floor), max(.4, length*(ceiling-floor)*.12),
                                              'm2', 'boundary_times_height', 'candidate') if ceiling is not None else measurement(unit='m2')),
                          'status': 'candidate'})
        rooms.append({'id': rid, 'name': f'Observed space {len(rooms)+1}', 'tier': 'lidar',
                      'polygon': poly.round(4).tolist(), 'coordinate_unit': 'm',
                      'floor_area': measurement(room_area, max(.5, perimeter*.15), 'm2', 'observed_floor_polygon', 'candidate'),
                      'ceiling_height': (measurement(ceiling-floor, .08, method='horizontal_plane_modes', status='estimated') if ceiling is not None else measurement(method='ceiling_not_observed')),
                      'walls': walls, 'openings': [], 'damage_regions': [], 'concealed_damage_flags': [],
                      'scope_items': [], 'status': 'needs_review',
                      'warnings': ['Floor coverage boundary can differ from true wall location.',
                                   'Room split is morphological; semantic rooms and openings require verification.'],
                      '_segment': int(i)})
    adjacency = []
    for ia, a in enumerate(rooms):
        ma = segments == a['_segment']
        dilated = ndimage.binary_dilation(ma)
        for b in rooms[ia+1:]:
            border = dilated & (segments == b['_segment'])
            if border.any():
                adjacency.append({'room_a': a['id'], 'room_b': b['id'], 'status': 'candidate',
                                  'evidence': 'touching_floor_segments', 'opening_id': None})
    for room in rooms:
        room.pop('_segment')
    return rooms, adjacency, {'levels': levels, 'grid_m': grid, 'observed_floor_points': len(fp),
                              'room_candidates': len(rooms), 'status': 'uncalibrated'}
