import sys
import os.path
import argparse
import logging

from dockerenv.build_env import BuildEnv
from dockerenv.snapshotter import (
    Snapshotter,
    Context,
    get_snapshotters,
    get_develop_snapshotters,
    get_wrapped_snapshotters
)
from dockerenv.runner import Runner
from dockerenv.image_cache import stored_cache
from dockerenv.utils import resource


def main(
    script_dirs,
    base_dir=None,
    base_image='ubuntu:latest',
    image_cache_fname=None,
):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--cleanup', action="store_true")
    argparser.add_argument('--build-only', action="store_true")
    argparser.add_argument('--develop', action="store_true")
    argparser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = argparser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    base_dir = base_dir or os.path.abspath(os.path.dirname(sys.argv[0]))
    image_cache_fname = image_cache_fname or os.path.join(base_dir, 'docker_image_cache.json')

    with stored_cache(image_cache_fname) as image_cache:        
        init_image = image_cache.get_or_make(
            base_image,
            Snapshotter(
                cmd = ['/init_script'],
                context = Context({'/init_script': resource('image_init.sh')}),
                runner = Runner(entrypoint='/bin/sh'),
            )
        ).image

        snapshotters = get_snapshotters(script_dirs, init_image)
        if args.develop:
            snapshotters = get_develop_snapshotters(snapshotters, base_dir)
        snapshotters = get_wrapped_snapshotters(
            snapshotters,
            wrapper_script = resource('debian_cleanup_wrapper.sh'),
        )

        env = BuildEnv(base_dir, init_image, snapshotters, image_cache)

        env.build()
        if args.cleanup:
            env.cleanup()

        if not args.build_only:
            env.build_and_run(args.cmd)

