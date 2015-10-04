import sys
import os.path
import argparse
import logging
import json

from dockerenv.snapshotter import Cmd, HostUserCwdCmd
from dockerenv.runner import Runner, HostUserRunner, Volume
from dockerenv.image_cache import stored_cache, CachedImage
from dockerenv.utils import resource


def debian_cleanup_wrapper(cmd):
    wrapper = 'debian_cleanup_wrapper.sh'
    return Cmd(
        ['./' + wrapper] + cmd.cmd,
        cmd.context.added(wrapper, resource(wrapper)),
        cmd.comment + ' (wrapped ' + wrapper + ')',
    )

