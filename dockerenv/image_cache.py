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
    def __init__(self, image, comment, parent=None, timestamp=None):
        self.image = image
        self.comment = comment
        self.parent = parent
        self.timestamp = timestamp or time.asctime()


class ImageCache(object):
    def __init__(self):
        self.items = StrictDict()

    @classmethod
    def from_dict(cls, dct):
        self = cls()
        for snapshotter_hash, info in dct.iteritems():
            if isinstance(info, dict):
                self[snapshotter_hash] = ImageInfo(
                    image = info['image'],
                    comment = info['comment'],
                    parent = info.get('parent'),
                    timestamp = info.get('timestamp'),
                )
            else:
                image, comment, timestamp = info
                self[snapshotter_hash] = ImageInfo(image, comment, None, timestamp)
        return self

    def as_dict(self):
        return {
            snapshotter_hash: {
                'image': image.image,
                'comment': image.comment,
                'parent': image.parent,
                'timestamp': image.timestamp,
            }
            for snapshotter_hash, image in self.iteritems()
        }

    def __contains__(self, snapshotter_hash):
        return snapshotter_hash in self.items

    def __setitem__(self, snapshotter_hash, image_info):
        self.items[snapshotter_hash] = image_info

    def __delitem__(self, snapshotter_hash):
        del self.items[snapshotter_hash]

    def get(self, snapshotter_hash):
        return self.items.get(snapshotter_hash)

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
            self.cache[digest] = ImageInfo(
                image = self.snapshotter(image),
                comment = self.snapshotter.comment,
                parent = image,
            )
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


class CachedImage(object):
    def __init__(self, image):
        self.image = image

    def apply(self, snapshotter):
        with stored_cache('dockerenv_image_cache.json') as cache:
            return CachedImage(CachedSnapshotter(snapshotter, cache)(self.image))

    def apply_no_cache(self, snapshotter):
        return CachedImage(snapshotter(self.image))

