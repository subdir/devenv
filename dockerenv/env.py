# coding: utf-8

from __future__ import print_function

import argparse
import hashlib
import logging
from logging import info
from subprocess import check_call

from dockerenv.image_cache import ImageInfo
from dockerenv.run import run

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
                    image_id=layer.get_builder().run(self.base_dir, last_image_id),
                    comment=layer.get_comment(),
                )
            last_image_id = self.image_cache.get(layer.hexdigest).image_id
        return last_image_id

    def build_and_run(self, cmd, docker_args=(), work_dir=None):
        return run(self.base_dir, self.build(), list(docker_args) + ['--rm'], cmd, work_dir)

    def find_unused_images(self):
        keep = {layer.hexdigest for layer in self.get_layers()}
        for layer_hexdigest, image_info in self.image_cache.iteritems():
            if layer_hexdigest not in keep:
                yield layer_hexdigest, image_info

    def cleanup(self):
        for layer_hexdigest, image_info in self.find_unused_images():
            info("Removing layer {!r}, image_id: {!r} ({!r})".format(
                layer_hexdigest,
                image_info.image_id,
                image_info.comment,
            ))
            check_call(['docker', 'rmi', image_info.image_id], shell=False)
            del self.image_cache[layer_hexdigest]


def main(env):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--cleanup', action="store_true")
    argparser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = argparser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if args.cleanup:
        env.cleanup()

    env.build_and_run(args.cmd)

