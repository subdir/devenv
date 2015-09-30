# coding: utf-8

from __future__ import print_function

import os
import re
import tempfile
import shutil
import struct
from contextlib import contextmanager
from subprocess import check_output, check_call, CalledProcessError

from dockerenv.runner import Runner, HostUserRunner, Volume
from dockerenv.utils import make_tmpdir


def snapshot(runner_with_image, cmd, work_dir=None):
    cid = runner_with_image(cmd, work_dir, remove=False)
    try:
        return check_output(['docker', 'commit', cid], shell=False).strip()
    finally:
        check_call(['docker', 'rm', cid], shell=False)


class Context(object):
    def __init__(self, context):
        self.context = context

    @contextmanager
    def isolated(self, base_dir):
        with make_tmpdir(base_dir) as tmpdir:
            for target_fname, fpath in self.context.iteritems():
                if os.path.isdir(fpath):
                    shutil.copytree(fpath, os.path.join(tmpdir, target_fname))
                else:
                    shutil.copyfile(fpath, os.path.join(tmpdir, target_fname))
                    shutil.copymode(fpath, os.path.join(tmpdir, target_fname))
            yield tmpdir

    def as_volumes(self, base_dir='/', mode='ro'):
        return [
            Volume(fpath, os.path.join(base_dir, target_fname), mode)
                for target_fname, fpath in self.context.iteritems()
        ]

    def add(self, target_fname, fpath):
        if target_fname in self.context:
            raise Exception('Context conflict {!r}: {!r} -> {!r}'.format(
                target_fname,
                self.context[target_fname],
                fpath,
            ))
        else:
            self.context[target_fname] = fpath

    def __contains__(self, item):
        return item in self.context

    def update_hash(self, hashobj):
        for target_fname, fpath in self.context.iteritems():
            hash_str(hashobj, target_fname)
            if os.path.isdir(fpath):
                hash_dir(hashobj, fpath)
            else:
                hash_file(hashobj, fpath)
        hashobj.update(struct.pack("Q", len(self.context)))


class Snapshotter(object):
    def __init__(self, cmd, context, runner, comment=None):
        self.cmd = cmd
        self.context = context
        self.runner = runner
        self.comment = comment or " ".join(cmd)

    def __call__(self, image):
        return snapshot(
            self.runner.with_volumes(self.context.as_volumes()).with_image(image),
            self.cmd,
        )

    def update_hash(self, hashobj):
        hash_str(hashobj, self.__class__.__name__)
        hash_str(hashobj, str(self.cmd))
        self.context.update_hash(hashobj)


class BuildInstallSnapshotter(object):
    def __init__(self, cmd_prefix, context, build_runner, install_runner, comment=None):
        self.cmd_prefix = cmd_prefix
        self.context = context
        self.build_runner = build_runner
        self.install_runner = install_runner
        self.comment = comment or " ".join(cmd_prefix + ["install"])

    def __call__(self, image):
        with make_tmpdir() as tmpdir:
            build_runner = self.build_runner.with_volumes(
                [Volume(tmpdir, '/dockerenv_context', 'rw')]
                + list(self.context.as_volumes('/dockerenv_context'))
            )
            build_runner(
                self.cmd_prefix + ['build'],
                work_dir = '/dockerenv_context',
            )
            install_runner = self.install_runner.with_volumes(
                [Volume(tmpdir, '/dockerenv_context', 'ro')]
                + list(self.context.as_volumes('/dockerenv_context'))
            )
            return snapshot(
                install_runner.with_image(image),
                self.cmd_prefix + ['install'],
                work_dir = '/dockerenv_context',
            )

    def update_hash(self, hashobj):
        hash_str(hashobj, self.__class__.__name__)
        hash_str(hashobj, str(self.cmd_prefix))
        self.context.update_hash(hashobj)


class DevelopSnapshotter(object):
    def __init__(self, cmd_prefix, base_dir, develop_runner, build_install_snapshotter, comment=None):
        self.cmd_prefix = cmd_prefix
        self.base_dir = base_dir
        self.develop_runner = develop_runner
        self.build_install_snapshotter = build_install_snapshotter
        self.comment = comment or " ".join(self.cmd_prefix + ["develop"])

    def __call__(self, image):
        def dev_check_call(cmd):
            return check_call(cmd, shell=False, preexec_fn=lambda: os.chdir(self.base_dir))

        try:
            # проверяем, поддерживает ли скрипт режим develop
            dev_check_call(self.cmd_prefix + ['nodevelop'])
        except CalledProcessError:
            dev_check_call(self.cmd_prefix + ['checkout'])
            return snapshot(
                self.develop_runner.with_volumes(self.base_dir, self.base_dir, 'rw').with_image(image),
                self.cmd_prefix + ['develop'],
                work_dir = self.base_dir,
            )

        else:
            return self.build_install_snapshotter(image)

    def update_hash(self, hashobj):
        hash_str(hashobj, self.__class__.__name__)
        hash_str(hashobj, str(self.cmd_prefix))
        hash_str(hashobj, str(self.base_dir))
        self.build_install_snapshotter.update_hash(hashobj)


def get_snapshotters(script_dirs, image):
    for script_dir in script_dirs:
        for fname in sorted(os.listdir(script_dir)):
            fpath = os.path.join(script_dir, fname)
            if (
                os.path.isfile(fpath)
                and os.access(fpath, os.X_OK)
                and re.match(r'^\d+\.', os.path.basename(fpath))
            ):
                yield BuildInstallSnapshotter(
                    cmd_prefix = ["./" + os.path.basename(fpath)],
                    context = Context({os.path.basename(fpath): fpath}),
                    build_runner = HostUserRunner(allow_sudo=True).with_image(image),
                    install_runner = HostUserRunner(allow_sudo=True),
                )


def get_develop_snapshotters(snapshotters, base_dir):
    for snapshotter in snapshotters:
        yield DevelopSnapshotter(
            snapshotter.cmd_prefix,
            base_dir,
            develop_runner = snapshotter.install_runner,
            build_install_snapshotter = snapshotter,
        )


def get_wrapped_snapshotters(snapshotters, wrapper_script):
    for snapshotter in snapshotters:
        snapshotter.context.add('wrapper.sh', wrapper_script)
        snapshotter.cmd_prefix = ['./wrapper.sh'] + snapshotter.cmd_prefix
        snapshotter.comment += ' (wrapped ' + wrapper_script + ')'
        yield snapshotter



def hash_file(hashobj, fname, blocksize=4*1024*1024):
    size = 0
    with open(fname) as fobj:
        while True:
            block = fobj.read(blocksize)
            if block:
                hashobj.update(block)
                size += len(block)
            else:
                break
    hashobj.update(struct.pack("Q", size))


def hash_dir(hashobj, dirpath):
    def onerror(err):
        raise err
    cnt = 0
    for subdirpath, dirnames, filenames in os.walk(dirpath, onerror=onerror, followlinks=True):
        dirnames.sort()
        for fname in sorted(filenames):
            fpath = os.path.join(subdirpath, fname)
            relpath = os.path.relpath(fpath, dirpath)
            hashobj.update(relpath)
            hash_file(hashobj, fpath)
            cnt += 1
    hashobj.update(struct.pack("Q", cnt))


def hash_str(hashobj, string):
    hashobj.update(string)
    hashobj.update(struct.pack("Q", len(string)))

