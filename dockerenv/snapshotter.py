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

    def added(self, target_fname, fpath):
        context = Context(dict(self.context))
        context.add(target_fname, fpath)
        return context

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


class Cmd(object):
    def __init__(self, cmd, context, comment=None):
        self.cmd = cmd
        self.context = context
        self.comment = comment or " ".join(cmd)

    @classmethod
    def from_script(cls, script, args=(), context=None):
        cmd = os.path.basename(script)
        context = (context or Context({})).added(cmd, script)
        return cls(["./" + cmd] + list(args), context)

    def __call__(self, image):
        return snapshot(
            Runner().with_volumes(self.context.as_volumes()).with_image(image),
            self.cmd,
        )

    def update_hash(self, hashobj):
        hash_str(hashobj, self.__class__.__name__)
        hash_str(hashobj, str(self.cmd))
        self.context.update_hash(hashobj)


class HostUserCwdCmd(object):
    def __init__(self, cmd, work_dir=None, allow_sudo=False, comment=None):
        self.cmd = cmd
        self.work_dir = work_dir or os.getcwd()
        self.allow_sudo = allow_sudo
        self.comment = comment or " ".join(self.cmd)

    def __call__(self, image):
        return snapshot(
            HostUserRunner(allow_sudo=self.allow_sudo).with_volumes([
                Volume(os.path.abspath(self.work_dir), '/dockerenv', 'rw')
            ]).with_image(
                image
            ),
            self.cmd,
            work_dir = '/dockerenv',
        )


class CompoundSnapshotter(object):
    def __init__(self, snapshotters):
        self.snapshotters = snapshotters

    def __call__(self, image):
        for snapshotter in self.snapshotters:
            image = snapshotter(image)
        return image


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

