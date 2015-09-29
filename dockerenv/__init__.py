import sys
import os.path
import argparse
import logging

from dockerenv.env import DockerEnv
from dockerenv.script_builder import get_wrapped_script_builders
from dockerenv.image_cache import stored_cache


def main_env(env):
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--cleanup', action="store_true")
    argparser.add_argument('cmd', nargs=argparse.REMAINDER)
    args = argparser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if args.cleanup:
        env.cleanup()

    env.build_and_run(args.cmd)


def main(
    repo_script_dirs,
    env_script_dir = None,
    base_dir = None,
    base_image = 'ubuntu:latest',
    cache_fname = None,
):
    base_dir = base_dir or os.path.abspath(os.path.dirname(sys.argv[0]))
    cache_fname = cache_fname or os.path.join(base_dir, 'docker_image_cache.json')
    env_script_dir = env_script_dir or os.path.join(base_dir, 'setup')
    with stored_cache(cache_fname) as cache:
        return main_env(
            env = DockerEnv(
                base_dir = base_dir,
                base_image = base_image,
                builders = get_wrapped_script_builders(env_script_dir, repo_script_dirs),
                image_cache = cache,
            ),
        )

