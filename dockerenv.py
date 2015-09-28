#!/usr/bin/python
# coding: utf-8

from __future__ import print_function

import sys
import os
import argparse
import hashlib
import json
import tempfile
import shutil
import logging
from subprocess import check_call, check_output
from logging import info
from contextlib import contextmanager


def run(base_dir, image, docker_args, cmd, work_dir=None, entrypoint=None):
    dirname = os.path.abspath(os.path.dirname(__file__))
    container_home = '/home/user'
    container_user = 'user'

    basic_docker_args = [
        # монтируем base_dir как хомяк, чтобы сохранялся стейт между запусками, например, .bash_history
        '--volume=' + base_dir + ':' + base_dir + ':rw',
        # монтируем base_dir под тем же именем, что и на хосте, чтобы можно было использовать инструменты
        #   отладки на хосте, да и стектрейсы читать удобней
        '--volume=' + base_dir + ':' + container_home + ':rw',
        '--env=PATH=' + container_home + '/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        '--env=HOME=' + container_home,
        '--env=TARGET_USER=' + container_user,
        '--env=TARGET_UID=' + str(os.getuid()),
        '--env=TARGET_GID=' + str(os.getgid()),
        '--env=SHELL=' + os.environ.get('SHELL', ''),
        '--env=TERM=' + os.environ.get('TERM', ''),
        '--entrypoint=' + (entrypoint or dirname + '/entrypoint.sh'),
        '--workdir=' + (work_dir or os.getcwd()),
    ]

    try:
        os.ttyname(sys.stdin.fileno()) # fails if stdin is not a tty
        basic_docker_args.extend([
            '--tty',
            '--interactive',
        ])
    except:
        pass

    status = check_call(
        shell = False,
        args = ['docker', 'run'] + basic_docker_args + docker_args + [image] + cmd
    )
    return status


def build_image(base_dir, base_image, cmd, work_dir=None, entrypoint=None):
    fd, cidfile = tempfile.mkstemp()
    try:
        os.close(fd)
        os.unlink(cidfile)
        run(
            base_dir,
            base_image,
            docker_args = ['--cidfile=' + cidfile],
            cmd = cmd,
            work_dir = work_dir,
            entrypoint = entrypoint,
        )
        with open(cidfile) as cidfobj:
            cid = cidfobj.read()
        image_id = check_output(['docker', 'commit', cid], shell=False)
        return image_id.strip()
    finally:
        if os.path.isfile(cidfile):
            os.unlink(cidfile)


class StrictDict(dict):
    '''
    Does not allow overwrites.
    '''
    def __setitem__(self, key, val):
        if key in self:
            raise Exception('Key overwrite {!r}: {!r} -> {!r}'.format(
                key, self[key], val,
            ))
        else:
            super(StrictDict, self).__setitem__(key, val)


class ImageInfo(object):
    def __init__(self, image_id, comment):
        self.image_id = image_id
        self.comment = comment


class ImageCache(object):
    def __init__(self):
        self.items = StrictDict()

    @classmethod
    def from_dict(cls, dct):
        self = cls()
        for layer_hexdigest, (image_id, comment) in dct.iteritems():
            self[layer_hexdigest] = ImageInfo(image_id, comment)
        return self

    def as_dict(self):
        return {
            layer_hexdigest: (image.image_id, image.comment)
                for layer_hexdigest, image in self.iteritems()
        }

    def __contains__(self, layer_hexdigest):
        return layer_hexdigest in self.items

    def __setitem__(self, layer_hexdigest, image_info):
        self.items[layer_hexdigest] = image_info

    def __delitem__(self, layer_hexdigest):
        del self.items[layer_hexdigest]

    def get(self, layer_hexdigest):
        return self.items.get(layer_hexdigest)

    def iteritems(self):
        return self.items.iteritems()


@contextmanager
def stored_cache(fname):
    if not os.path.exists(fname):
        cache = ImageCache()
    else:
        with open(fname) as fobj:
            cache = ImageCache.from_dict(json.load(fobj))
    try:
        yield cache
    finally:
        with open(fname, 'w') as fobj:
            json.dump(cache.as_dict(), fobj, indent=4)


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
                cmd = ['./builder.sh'],
                work_dir = tmpdir,
                entrypoint = self.entrypoint,
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
def make_tmpdir(dir=None):
    dirpath = tempfile.mkdtemp(dir=dir)
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
            script = 'setup/wrapper.sh',
            context = dict(builder.context, **{'subbuilder.sh': builder.script}),
            comment = builder.comment + ' (wrapped)',
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
    for subdirpath, dirnames, filenames in os.walk(dirname, onerror=onerror, followlinks=True):
        dirnames.sort()
        for fname in sorted(filenames):
            fpath = os.path.join(subdirpath, fname)
            relpath = os.path.relpath(fpath, dirpath)
            hashobj.update(relpath)
            hash_file(hashobj, fpath)


class Layer(object):
    def __init__(self, builders, hexdigest):
        self.builders = builders
        self.hexdigest = hexdigest

    def get_builder(self):
        return self.builders[-1]

    def get_comment(self):
        return ", ".join(builder.get_comment() for builder in self.builders)


class DockerEnv(object):
    def __init__(self, base_dir, base_image, builders, image_cache):
        self.base_dir = base_dir
        self.base_image = base_image
        self.builders = list(builders)
        self.image_cache = image_cache

    def get_layers(self):
        md5 = hashlib.md5()
        md5.update(self.base_image)
        for i, builder in enumerate(self.builders):
            builder.update_hash(md5)
            yield Layer(self.builders[:i + 1], md5.hexdigest())

    def build(self):
        last_image_id = self.base_image
        for layer in self.get_layers():
            if layer.hexdigest not in self.image_cache:
                self.image_cache[layer.hexdigest] = ImageInfo(
                    image_id = layer.get_builder().run(self.base_dir, last_image_id),
                    comment = layer.get_comment(),
                )
            last_image_id = self.image_cache.get(layer.hexdigest).image_id
        return last_image_id

    def run_cmd(self, cmd, docker_args=(), work_dir=None):
        return run(self.base_dir, self.build(), docker_args, cmd, work_dir)

    def find_unused_images(self):
        keep = {layer.hexdigest for layer in self.get_layers()}
        for layer_hexdigest, image_info in self.image_cache.iteritems():
            if layer_hexdigest not in keep:
                yield layer_hexdigest, image_info

    def cleanup(cache, setupdir, base_image):
        for layer_hexdigest, image_info in self.find_unused_images():
            info("Removing layer {!r}, image_id: {!r} ({!r})".format(
                layer_hexdigest,
                image_info.image_id,
                image_info.comment,
            ))
            check_call(['docker', 'rmi', image_id], shell=False)
            cache.remove(script_name, script_hash)


def main(env):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--cleanup', action="store_true")
    argparser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = argparser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if args.cleanup:
        env.cleanup()

    env.run_cmd(args.cmd)


if __name__ == '__main__':
    main()

