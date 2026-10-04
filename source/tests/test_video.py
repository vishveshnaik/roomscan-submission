import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from roomscan.geometry import measurement
from roomscan.pipeline import run
from roomscan.vision import extract_video, photo_room


class VideoTests(unittest.TestCase):
    def make_video(self, root, name='walkthrough.AVI', frames=32):
        path=Path(root)/name
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,48))
        if not writer.isOpened():self.fail('MJPG video writer unavailable')
        for i in range(frames):
            writer.write(np.full((48,64,3),i*6,np.uint8))
        writer.release()
        return path

    def test_short_video_does_not_duplicate_frames(self):
        with tempfile.TemporaryDirectory() as td:
            video=self.make_video(td,frames=6)
            files,stats=extract_video(video,Path(td)/'frames',count=240,return_metadata=True)
            self.assertEqual(len(files),6)
            self.assertEqual(stats['decoded_keyframes'],6)
            values=[round(float(cv2.imread(str(p)).mean())) for p in files]
            self.assertEqual(len(set(values)),6)
            self.assertLessEqual(stats['max_sample_gap_seconds'],.11)

    def test_default_video_pipeline_honors_keyframes_and_uppercase_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'input';source.mkdir();self.make_video(source)
            result=run(source,Path(td)/'output',tier='video',keyframes=12)
            self.assertEqual(result['rooms'][0]['image_count'],12)
            self.assertEqual(result['diagnostics'][0]['video_sampling']['decoded_keyframes'],12)
            self.assertEqual(result['status'],'unresolved')  # Relative scale is not metres.

    def metric_structure(self,status,capture_id='candidate',rooms=True):
        room,_=photo_room([],capture_id,'video')
        room.update(polygon=[[0,0],[3,0],[3,4],[0,4]],coordinate_unit='m',status='candidate',
                    floor_area=measurement(12,2,'m2'),ceiling_height=measurement(2.5,.5))
        return {'status':status,'rooms':[room] if rooms else [],'walls':[],
                'openings':[],'adjacency':[],'diagnostics':{}},np.empty((0,3))

    def test_metric_pipeline_preserves_recovered_geometry_status(self):
        for status in ['needs_review','partial_reconstruction']:
            with self.subTest(status=status),tempfile.TemporaryDirectory() as td:
                video=self.make_video(td)
                with patch('roomscan.thin.metric_multiview',return_value=self.metric_structure(status)):
                    result=run(video,Path(td)/'output',tier='video',metric=True,keyframes=4)
                self.assertEqual(result['status'],status)
                self.assertEqual(result['rooms'][0]['floor_area']['value'],12)

    def test_empty_metric_geometry_is_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            video=self.make_video(td)
            with patch('roomscan.thin.metric_multiview',return_value=self.metric_structure('needs_review',rooms=False)):
                result=run(video,Path(td)/'output',tier='video',metric=True,keyframes=4)
            self.assertEqual(result['status'],'unresolved')
            self.assertIsNone(result['rooms'][0]['floor_area']['value'])

    def test_independent_metric_videos_are_not_claimed_as_one_stitched_plan(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'input';source.mkdir()
            self.make_video(source,'one.AVI');self.make_video(source,'two.AVI')
            def recovered(*args,**kwargs):
                return self.metric_structure('needs_review',capture_id=kwargs['capture_id'])
            with patch('roomscan.thin.metric_multiview',side_effect=recovered):
                result=run(source,Path(td)/'output',tier='video',metric=True,keyframes=4)
            self.assertEqual(result['status'],'partial_reconstruction')
            self.assertIsNone(result['footprint_area']['value'])


if __name__=='__main__':unittest.main()
