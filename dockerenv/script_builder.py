# coding: utf-8

from __future__ import print_function

import os
import tempfile
import shutil
from contextlib import contextmanager

from dockerenv.run import build_image

class ScriptBuilder(object):
    def __init__(self, script, context, comment, entrypoint=None):
        assert 'builder.sh' not in context
        self.script = script
        self.context = context
        self.comment = comment
        self.entrypoint = entrypoint

    def run(self, base_dir, base_image):
        with make_tmpdir(base_dir) as tmpdir:
            shutil.copyfile(self.script, os.path.join(tmpdir, 'builder.sh'))
            shutil.copymode(self.script, os.path.join(tmpdir, 'builder.sh'))
            for target_fname, fpath in self.context.iteritems():
                if os.path.isdir(fpath):
                    shutil.copytree(fpath, os.path.join(tmpdir, target_fname))
                else:
                    shutil.copyfile(fpath, os.path.join(tmpdir, target_fname))
                    shutil.copymode(fpath, os.path.join(tmpdir, target_fname))

            return build_image(
                base_dir,
                base_image,
                cmd=['./builder.sh'],
                work_dir=tmpdir,
                entrypoint=self.entrypoint,
            )

    def get_comment(self):
        return self.comment

    def update_hash(self, hashobj):
        hash_file(hashobj, self.script)
        for target_fname, fpath in self.context.iteritems():
            hashobj.update(target_fname)
            if os.path.isdir(fpath):
                hash_dir(hashobj, fpath)
            else:
                hash_file(hashobj, fpath)


@contextmanager
def make_tmpdir(base_dir=None):
    dirpath = tempfile.mkdtemp(dir=base_dir)
    os.chmod(dirpath, 0755)
    try:
        yield dirpath
    finally:
        shutil.rmtree(dirpath)


def get_script_builders(scriptdir):
    for fname in sorted(os.listdir(scriptdir)):
        fpath = os.path.join(scriptdir, fname)
        if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
            yield ScriptBuilder(fpath, {}, comment=fpath)


def get_wrapped_script_builders(wrapperdir, scriptdir):
    yield ScriptBuilder(os.path.join(wrapperdir, 'init.sh'), {}, comment='init.sh', entrypoint='bash')

    for builder in get_script_builders(scriptdir):
        assert 'subbuilder.sh' not in builder.context
        yield ScriptBuilder(
            script='setup/wrapper.sh',
            context=dict(builder.context, **{'subbuilder.sh': builder.script}), # pylint: disable=star-args
            comment=builder.comment + ' (wrapped)',
        )

    yield ScriptBuilder(os.path.join(wrapperdir, 'cleanup.sh'), {}, comment='cleanup.sh', entrypoint='bash')


def hash_file(hashobj, fname, blocksize=4*1024*1024):
    with open(fname) as fobj:
        while True:
            block = fobj.read(blocksize)
            if block:
                hashobj.update(block)
            else:
                break


def hash_dir(hashobj, dirpath):
    def onerror(err):
        raise err
    for subdirpath, dirnames, filenames in os.walk(dirpath, onerror=onerror, followlinks=True):
        dirnames.sort()
        for fname in sorted(filenames):
            fpath = os.path.join(subdirpath, fname)
            relpath = os.path.relpath(fpath, dirpath)
            hashobj.update(relpath)
            hash_file(hashobj, fpath)

