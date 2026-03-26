"""
Global pytest configuration for QPopCV tests.
"""
import _pytest.pathlib
import _pytest.tmpdir

# Python 3.14 on Windows 11 raises OSError (WinError 448 - untrusted mount point)
# when pathlib.resolve() traverses symlinks inside %TEMP%. Patch both modules where
# cleanup_dead_symlinks is referenced, since tmpdir.py imports it by name at load time.
_orig_cleanup_dead_symlinks = _pytest.pathlib.cleanup_dead_symlinks


def _safe_cleanup_dead_symlinks(root):
    try:
        _orig_cleanup_dead_symlinks(root)
    except OSError:
        pass


_pytest.pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
_pytest.tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
