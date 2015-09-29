# coding: utf-8

from __future__ import print_function

import os.path
import json
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

