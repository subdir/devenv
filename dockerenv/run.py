# coding: utf-8

from __future__ import print_function

import sys
import os
import tempfile
from subprocess import check_call, check_output


def run(base_dir, image, docker_args, cmd, work_dir=None, entrypoint=None):
    dirname = os.path.abspath(os.path.dirname(__file__))
    default_entrypoint = os.path.join(dirname, '../hostuser.sh')
    container_home = '/home/user'
    container_user = 'user'

    basic_docker_args = [
        # монтируем base_dir как хомяк, чтобы сохранялся стейт между запусками, например, .bash_history
        '--volume=' + base_dir + ':' + base_dir + ':rw',

        # монтируем base_dir под тем же именем, что и на хосте, чтобы можно было использовать инструменты
        # отладки на хосте, да и стектрейсы читать удобней
        '--volume=' + base_dir + ':' + container_home + ':rw',

        '--env=PATH=' + container_home + '/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        '--env=HOME=' + container_home,
        '--env=TARGET_USER=' + container_user,
        '--env=TARGET_UID=' + str(os.getuid()),
        '--env=TARGET_GID=' + str(os.getgid()),
        '--env=SHELL=' + os.environ.get('SHELL', ''),
        '--env=TERM=' + os.environ.get('TERM', ''),
        '--entrypoint=' + (entrypoint or default_entrypoint),
        '--workdir=' + (work_dir or os.getcwd()),
    ]

    if 'SSH_AUTH_SOCK' in os.environ:
        basic_docker_args.extend([
            '--volume=' + os.environ['SSH_AUTH_SOCK'] + ':/run/ssh:rw',
            '--env=SSH_AUTH_SOCK=/run/ssh',
        ])

    try:
        os.ttyname(sys.stdin.fileno())
    except EnvironmentError:
        pass # stdin is not a tty
    else:
        basic_docker_args.extend([
            '--tty',
            '--interactive',
        ])

    status = check_call(
        shell=False,
        args=['docker', 'run'] + basic_docker_args + list(docker_args) + [image] + cmd
    )
    return status


def build_image(base_dir, base_image, cmd, work_dir=None, entrypoint=None):
    fileno, cidfile = tempfile.mkstemp()
    try:
        os.close(fileno)
        os.unlink(cidfile)
        run(
            base_dir,
            base_image,
            docker_args=['--cidfile=' + cidfile],
            cmd=cmd,
            work_dir=work_dir,
            entrypoint=entrypoint,
        )
        try:
            with open(cidfile) as cidfobj:
                cid = cidfobj.read()
            return check_output(['docker', 'commit', cid], shell=False).strip()
        finally:
            check_call(['docker', 'rm', cid], shell=False)
    finally:
        if os.path.isfile(cidfile):
            os.unlink(cidfile)

