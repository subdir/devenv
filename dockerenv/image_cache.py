# coding: utf-8

from __future__ import print_function

import os.path
import json
import time
import hashlib
from contextlib import contextmanager


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
    def __init__(self, image, comment, timestamp=None):
        self.image = image
        self.comment = comment
        self.timestamp = timestamp or time.asctime()


class ImageCache(object):
    def __init__(self):
        self.items = StrictDict()

    @classmethod
    def from_dict(cls, dct):
        self = cls()
        for layer_hexdigest, info in dct.iteritems():
            if len(info) == 2:
                image, comment = info
                timestamp = None
            else:
                image, comment, timestamp = info
            self[layer_hexdigest] = ImageInfo(image, comment, timestamp)
        return self

    def as_dict(self):
        return {
            layer_hexdigest: (image.image, image.comment, image.timestamp)
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


class CachedSnapshotter(object):
    def __init__(self, snapshotter, cache):
        self.snapshotter = snapshotter
        self.cache = cache

    def __call__(self, image):
        md5 = hashlib.md5()
        md5.update(image)
        self.snapshotter.update_hash(md5)
        digest = md5.hexdigest()
        if digest not in self.cache:
            self.cache[digest] = ImageInfo(self.snapshotter(image), self.snapshotter.comment)
        return self.cache.get(digest).image


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

