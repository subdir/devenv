import tempfile
import shutil
import os.path
from contextlib import contextmanager

def resource(fname):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', fname))


@contextmanager
def make_tmpdir(base_dir=None):
    dirpath = tempfile.mkdtemp(dir=base_dir)
    os.chmod(dirpath, 0755)
    try:
        yield dirpath
    finally:
        shutil.rmtree(dirpath)

