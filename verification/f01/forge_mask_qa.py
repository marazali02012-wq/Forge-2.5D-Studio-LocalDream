"""Regression for forge_mask.py decisions without model weights.

BiRefNet and SAM2 are replaced by fixed outputs so the HARD10 rules run in
CI with numpy/scipy/Pillow only: soft alpha is never binarised, thin parts
near the subject survive, far specks go, and an occluder is attached only
when it touches both split parts, is not the subject and is not huge.
"""
import contextlib
from pathlib import Path
import sys
import types
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "studio/cloud-ai"))
from forge_mask import bridge_occluders, clean_alpha


class FakePredictor:
    masks = None
    calls = []

    def __init__(self, model):
        pass

    def set_image(self, image):
        FakePredictor.calls.append(("image", image.shape))

    def predict(self, point_coords, point_labels, multimask_output):
        FakePredictor.calls.append(("predict", point_coords.copy(), point_labels.copy()))
        return FakePredictor.masks, np.array([0.9, 0.8, 0.7]), None


def install_fakes():
    sam2 = types.ModuleType("sam2")
    build = types.ModuleType("sam2.build_sam")
    build.build_sam2 = lambda *a, **k: object()
    predictor = types.ModuleType("sam2.sam2_image_predictor")
    predictor.SAM2ImagePredictor = FakePredictor
    sys.modules.update({"sam2": sam2, "sam2.build_sam": build, "sam2.sam2_image_predictor": predictor})
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.SimpleNamespace(inference_mode=contextlib.nullcontext)


class MaskTest(unittest.TestCase):
    def test_soft_alpha_thin_parts_and_specks(self):
        alpha = np.zeros((200, 200), np.float32)
        alpha[60:140, 60:140] = 1.0               # body
        alpha[58, 60:140] = 0.3                   # soft feather edge
        alpha[30:56, 100] = 0.8                   # thin feather tip, 2 px from the body
        alpha[190:193, 5:8] = 0.9                 # far speck (9 px)
        alpha[0:20, 180:200] = 0.9                # far but large part (400 px)
        out, stats = clean_alpha(alpha)
        self.assertEqual(out[58, 100], np.float32(0.3))          # not binarised
        self.assertTrue((out[30:56, 100] == np.float32(0.8)).all())  # thin tip kept
        self.assertEqual(out[191, 6], 0)                         # speck removed
        self.assertTrue((out[0:20, 180:200] > 0).all())          # large part kept
        self.assertEqual(stats["removed_components"], 1)
        self.assertEqual(stats["removed_pixels"], 9)

    def test_occluder_bridge_rules(self):
        install_fakes()
        image = Image.new("RGB", (100, 120), "gray")
        alpha = np.zeros((120, 100), np.float32)
        alpha[10:50, 35:65] = 1.0     # torso
        alpha[62:110, 38:62] = 1.0    # legs, split by an occluder at rows 50-62
        table = np.zeros((120, 100), bool)
        table[50:62, 10:90] = True
        background = np.ones((120, 100), bool)
        subject = alpha > 0.5

        FakePredictor.masks = np.stack([background, subject, table])
        FakePredictor.calls = []
        out, info = bridge_occluders(image, alpha, "checkpoint")
        self.assertEqual(info["occluder"], "attached")
        self.assertTrue((out[55, 20:80] == 1).all())
        _, points, labels = FakePredictor.calls[-1]
        self.assertEqual(labels.tolist(), [1, 0, 0])
        self.assertTrue(50 <= points[0][1] <= 62)               # prompt in the gap
        self.assertAlmostEqual(info["occluder_area_ratio"], table.sum() / subject.sum(), places=3)

        FakePredictor.masks = np.stack([background, subject, background])
        out, info = bridge_occluders(image, alpha, "checkpoint")
        self.assertEqual(info["occluder"], "rejected")
        self.assertTrue((out == alpha).all())

        single = np.zeros_like(alpha)
        single[10:110, 35:65] = 1.0
        out, info = bridge_occluders(image, single, "checkpoint")
        self.assertEqual(info["occluder"], "not_needed")


if __name__ == "__main__":
    unittest.main()
