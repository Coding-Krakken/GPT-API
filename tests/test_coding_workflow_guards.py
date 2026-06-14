from utils import patching

def test_patch_diagnostics_invalid():
    r = patching.patch_diagnostics('file: app.py\nchange stuff')
    assert r['valid_unified_diff_shape'] is False
    assert r['guidance']


def test_patch_normalize_fenced():
    p = '```diff\ndiff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1 +1 @@\n-a\n+b\n```'
    n = patching.normalize_patch(p)
    assert '```' not in n


def test_touch_coverage_threshold():
    diff = 'diff --git a/vitest.config.ts b/vitest.config.ts\n@@\n- lines: 50\n+ lines: 60\n'
    assert patching.touches_coverage_threshold(diff) is True
