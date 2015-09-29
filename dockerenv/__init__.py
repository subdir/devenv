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
    script_dirs,
    base_dir = None,
    base_image = 'ubuntu:latest',
    image_cache_fname = None,
    wrapper_script = None,
    init_script = None,
    cleanup_script = None,
):
    base_dir = base_dir or os.path.abspath(os.path.dirname(sys.argv[0]))
    image_cache_fname = image_cache_fname or os.path.join(base_dir, 'docker_image_cache.json')
    env_script_dir = env_script_dir or os.path.join(base_dir, 'setup')
    with stored_cache(image_cache_fname) as cache:
        return main_env(
            env = DockerEnv(
                base_dir = base_dir,
                base_image = base_image,
                builders = get_wrapped_script_builders(
                    repo_script_dirs,
                    wrapper_script = wrapper_script,
                    init_script = init_script,
                    cleanup_script = cleanup_script,
                ),
                image_cache = cache,
            ),
        )

