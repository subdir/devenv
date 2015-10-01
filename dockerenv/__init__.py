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


class Script(object):
    def __init__(self, fpath, dev):
        self.fpath = fpath
        self.dev = dev


class Config(object):
    def __init__(self, base_image, scripts):
        self.base_image = base_image
        self.scripts = scripts

    @classmethod
    def from_file(cls, fname):
        config_dir = os.path.dirname(fname)
        with open(fname) as fobj:
            config = json.load(fobj)
        scripts = []
        for rec in config['scripts']:
            scripts.append(Script(
                fpath = os.path.join(config_dir, rec['script']),
                dev = bool(rec.get('dev')),
            ))
        return cls(config["base_image"], scripts)


def make_snapshotters(scripts, base_dir, base_image, cache):
    runner = HostUserRunner(allow_sudo=True)
    for script in scripts:
        if script.dev:
            yield DevelopSnapshotter([script.fpath], base_dir, runner)
        else:
            yield CachedSnapshotter(
                wrapped(BuildInstallSnapshotter(
                    cmd_prefix = ["./" + os.path.basename(script.fpath)],
                    context = Context({os.path.basename(script.fpath): script.fpath}),
                    build_runner = runner.with_image(base_image),
                    install_runner = runner,
                )),
                cache,
            )


def wrapped(snapshotter):
    wrapper = resource('debian_cleanup_wrapper.sh')
    snapshotter.context.add('wrapper.sh', wrapper)
    snapshotter.cmd_prefix = ['./wrapper.sh'] + snapshotter.cmd_prefix
    snapshotter.comment += ' (wrapped ' + wrapper + ')'
    return snapshotter


def main(
    target_configs,
    base_dir = None,
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

    config = Config.from_file(target_configs[args.target])

    with stored_cache(image_cache_fname) as image_cache:        
        init_snapshotter = CachedSnapshotter(
            cache = image_cache,
            snapshotter = Snapshotter(
                cmd = ['/init_script'],
                context = Context({'/init_script': resource('image_init.sh')}),
                runner = Runner(entrypoint='/bin/sh'),
            ),
        )
        init_image = init_snapshotter(config.base_image)
        snapshotter = CompoundSnapshotter(
            make_snapshotters(config.scripts, base_dir, init_image, image_cache)
        )
        image = snapshotter(init_image)

        if not args.build_only:
            runner = HostUserRunner(allow_sudo=True, home_volume=base_dir)
            runner = runner.with_volumes([Volume(base_dir, base_dir, 'rw')])
            return runner(image, args.cmd, work_dir=work_dir or os.getcwd())

