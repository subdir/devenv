# coding: utf-8
from __future__ import print_function

import os
import struct
from subprocess import check_output, check_call

from dockerenv.runner import Runner, HostUserRunner, Volume


def snapshot(runner_with_image, cmd, work_dir=None):
    cid = runner_with_image(cmd, work_dir, remove=False)
    try:
        return check_output(['docker', 'commit', cid], shell=False).strip()
    finally:
        check_call(['docker', 'rm', cid], shell=False)


class Context(object):
    def __init__(self, context):
        self.context = context

    def as_volumes(self, base_dir='/'):
        return [
            Volume(fpath, os.path.join(base_dir, target_fname), mode)
                for target_fname, (fpath, mode) in self.context.iteritems()
        ]

    def added(self, target_fname, fpath, mode='ro'):
        context = Context(dict(self.context))
        context.add(target_fname, fpath, mode)
        return context

    def add(self, target_fname, fpath, mode='ro'):
        if target_fname in self.context:
            raise Exception('Context conflict {!r}: {!r} -> {!r}'.format(
                target_fname,
                self.context[target_fname],
                fpath,
            ))
        else:
            self.context[target_fname] = (fpath, mode)

    def __contains__(self, item):
        return item in self.context

    def update_hash(self, hashobj):
        for target_fname, (fpath, mode) in self.context.iteritems():
            hash_str(hashobj, target_fname)
            hash_str(hashobj, mode)
            if os.path.isdir(fpath):
                hash_dir(hashobj, fpath)
            else:
                hash_file(hashobj, fpath)
        hashobj.update(struct.pack("Q", len(self.context)))


class Cmd(object):
    def __init__(self, cmd, context, comment=None):
        self.cmd = cmd
        self.context = context
        self.comment = comment or os.getcwd() + ": " + (" ".join(cmd))

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


class HostUserCwdCmd(Cmd):
    def __init__(self, cmd, context, work_dir=None,
                 allow_sudo=False, comment=None):
        self.work_dir = work_dir or os.getcwd()
        self.allow_sudo = allow_sudo
        comment = comment or self.work_dir + ": " + (" ".join(cmd))
        super(HostUserCwdCmd, self).__init__(cmd, context, comment)

    @classmethod
    def from_script(cls, script, args=(), context=None,  # pylint: disable=arguments-differ
                    work_dir=None, allow_sudo=None):
        script = os.path.abspath(script)
        context = (context or Context({})).added(script, script)
        return cls([script] + list(args), context, work_dir, allow_sudo)

    def __call__(self, image):
        work_dir = os.path.abspath(self.work_dir)
        volumes = [
            Volume(os.path.join(work_dir, '.dockerenv.home'), '/home/user', 'rw'),
            Volume(self.work_dir, self.work_dir, 'rw')
        ] + self.context.as_volumes()

        return snapshot(
            HostUserRunner(allow_sudo=self.allow_sudo).with_volumes(
                volumes).with_image(image),
            self.cmd,
            work_dir = work_dir,
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
