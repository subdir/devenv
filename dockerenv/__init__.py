import sys
import os.path
import argparse
import logging
import json

from dockerenv.snapshotter import (
    Snapshotter,
    BuildInstallSnapshotter,
    DevelopSnapshotter,
    CompoundSnapshotter,
    Context,
)
from dockerenv.runner import Runner, HostUserRunner
from dockerenv.snapshotter import BuildInstallSnapshotter, DevelopSnapshotter
from dockerenv.image_cache import stored_cache, CachedSnapshotter
from dockerenv.utils import resource


def wrapped(snapshotter):
    wrapper = resource('debian_cleanup_wrapper.sh')
    snapshotter.context.add('wrapper.sh', wrapper)
    snapshotter.cmd_prefix = ['./wrapper.sh'] + snapshotter.cmd_prefix
    snapshotter.comment += ' (wrapped ' + wrapper + ')'
    return snapshotter


def parse_config(fname, base_dir, base_image, cache):
    runner = HostUserRunner(allow_sudo=True)
    config_dir = os.path.dirname(fname)
    with open(fname) as fobj:
        config = json.load(fobj)

    for rec in config:
        # TODO: support config['context']
        script_path = os.path.join(config_dir, rec['script'])
        if rec.get('dev'):
            yield DevelopSnapshotter([script_path], base_dir, runner)
        else:
            yield CachedSnapshotter(
                wrapped(BuildInstallSnapshotter(
                    cmd_prefix = ["./" + os.path.basename(script_path)],
                    context = Context({os.path.basename(script_path): script_path}),
                    build_runner = runner.with_image(base_image),
                    install_runner = runner,
                )),
                cache,
            )


def main(
    target_configs,
    base_dir = None,
    base_image = 'ubuntu:latest',
    image_cache_fname = None,
):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--build-only', action="store_true")
    argparser.add_argument('target')
    argparser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = argparser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    base_dir = base_dir or os.path.abspath(os.path.dirname(sys.argv[0]))
    image_cache_fname = image_cache_fname or os.path.join(base_dir, 'docker_image_cache.json')

    with stored_cache(image_cache_fname) as image_cache:        
        init_snapshotter = CachedSnapshotter(
            cache = image_cache,
            snapshotter = Snapshotter(
                cmd = ['/init_script'],
                context = Context({'/init_script': resource('image_init.sh')}),
                runner = Runner(entrypoint='/bin/sh'),
            ),
        )
        init_image = init_snapshotter(base_image)
        snapshotter = CompoundSnapshotter(
            parse_config(target_configs[args.target], base_dir, init_image, image_cache)
        )

        image = snapshotter(init_image)
        if not args.build_only:
            runner = HostUserRunner(allow_sudo=True, home_volume=base_dir)
            runner = runner.with_volumes([Volume(base_dir, base_dir, 'rw')])
            return runner(image, args.cmd, work_dir=work_dir or os.getcwd())

