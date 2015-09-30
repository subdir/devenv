# coding: utf-8

from __future__ import print_function

import argparse
import hashlib
import logging
from logging import info
from subprocess import check_call, CalledProcessError

from dockerenv.image_cache import ImageInfo
from dockerenv.runner import Runner


class BuildEnv(object):
    def __init__(self, base_dir, base_image, snapshotters, image_cache):
        self.base_dir = base_dir
        self.base_image = base_image
        self.snapshotters = list(snapshotters)
        self.image_cache = image_cache

    def build(self):
        last_image = self.base_image
        for snapshotter in self.snapshotters:
            last_image = self.image_cache.get_or_make(last_image, snapshotter).image
        return last_image

    def build_and_run(self, cmd, docker_args=(), work_dir=None):
        return Runner(self.base_dir, self.build(), list(docker_args))(cmd, work_dir)

    def find_unused_images(self):
        keep = {}
        last_image = self.base_image
        for snapshotter in self.snapshotters:
            snapshotter_hash = calc_hash(last_image, snapshotter)
            if snapshotter_hash in self.image_cache:
                last_image = self.image_cache.get(snapshotter_hash).image
                keep.add(snapshotter_hash)
            else:
                break

        for snapshotter_hash, image_info in self.image_cache.iteritems():
            if snapshotter_hash not in keep:
                yield snapshotter_hash, image_info

    def cleanup(self):
        for snapshotter_hash, image_info in list(self.find_unused_images()):
            info("Removing snapshot {!r}, image: {!r} ({!r}, {})".format(
                snapshotter_hash,
                image_info.image,
                image_info.comment,
                image_info.timestamp,
            ))
            try:
                check_call(['docker', 'rmi', image_info.image], shell=False)
            except CalledProcessError:
                logging.exception('Failed to remove image')
            else:
                del self.image_cache[snapshotter_hash]

