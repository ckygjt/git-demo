import sys

import numpy as np
from PIL import Image

from app.config import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import gen_edits_local as g  # noqa: E402


def test_plan_covers_both_generators_and_valid_types():
    bases = [{"bid": f"b{i:02d}", "file": f"f{i}.jpg", "container": c} for i, c in enumerate(["plastic_bottle", "tube", "box", "other", "jar", "compact"])]
    samples = g.plan(bases, 5)
    assert len(samples) == 30
    assert {s["gen"] for s in samples} == {"flux", "sdxl"}
    for s, b in zip(samples, [b for b in bases for _ in range(5)]):
        assert s["damage_type"] in g.ALLOWED[b["container"]]
    assert len({s["id"] for s in samples}) == 30


def test_masks_in_area_range_for_all_shapes():
    for shape in g.SHAPES:
        for seed in range(20):
            m = np.asarray(g.make_mask(np.random.default_rng(seed), shape)) > 0
            assert g.AREA_MIN <= m.mean() <= g.AREA_MAX


def test_splice_outside_mask_is_pixel_identical():
    rng = np.random.default_rng(0)
    base = Image.fromarray(rng.integers(0, 255, (g.SIZE, g.SIZE, 3), dtype=np.uint8))
    edited = Image.fromarray(rng.integers(0, 255, (g.SIZE, g.SIZE, 3), dtype=np.uint8))
    mask = np.asarray(g.make_mask(np.random.default_rng(1), "blob")) > 0
    out = np.asarray(g.splice(base, edited, mask))
    assert np.array_equal(out[~mask], np.asarray(base)[~mask])
    assert g.diff_frac(base, Image.fromarray(out)) > g.DIFF_MIN
