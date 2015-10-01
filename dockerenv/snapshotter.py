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
        work_dir = '/dockerenv_context'
        with make_tmpdir() as tmpdir:
            build_runner = self.build_runner.with_volumes(
                [Volume(tmpdir, work_dir, 'rw')]
                + list(self.context.as_volumes(work_dir))
            )
            build_runner(
                self.cmd_prefix + ['build'],
                work_dir = work_dir,
            )
            install_runner = self.install_runner.with_volumes(
                [Volume(tmpdir, work_dir, 'ro')]
                + list(self.context.as_volumes(work_dir))
            )
            return snapshot(
                install_runner.with_image(image),
                self.cmd_prefix + ['install'],
                work_dir = work_dir,
            )

    def update_hash(self, hashobj):
        hash_str(hashobj, self.__class__.__name__)
        hash_str(hashobj, str(self.cmd_prefix))
        self.context.update_hash(hashobj)


class DevelopSnapshotter(object):
    def __init__(self, cmd_prefix, base_dir, develop_runner, comment=None):
        self.cmd_prefix = cmd_prefix
        self.base_dir = base_dir
        self.develop_runner = develop_runner
        self.comment = comment or " ".join(self.cmd_prefix + ["develop"])

    def __call__(self, image):
        check_call(
            self.cmd_prefix + ['checkout'],
            shell = False,
            preexec_fn = lambda: os.chdir(self.base_dir)
        )
        runner = self.develop_runner.with_volumes([Volume(self.base_dir, self.base_dir, 'rw')]).with_image(image)
        runner(
            self.cmd_prefix + ['develop'],
            work_dir = self.base_dir,
        )
        return image


class CompoundSnapshotter(object):
    def __init__(self, snapshotters):
        self.snapshotters = snapshotters

    def __call__(self, image):
        last_image = image
        for snapshotter in self.snapshotters:
            last_image = snapshotter(last_image)
        return last_image


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

