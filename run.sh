#!/bin/bash

set -e
set -o pipefail


devdir="$(readlink -f "$(dirname "${BASH_SOURCE[0]}")")"
container_user=dev
container_home=/home/dev
container_workdir="${container_home}"
docker_args=()

while [ -n "$1" ]; do
    case "$1" in
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option $1" 1>&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done


if [[ -t 1 ]]; then
    docker_args=("${docker_args[@]}" "--tty" "--interactive")
fi


# - монтируем devdir как хомяк, чтобы сохранялся стейт между запусками, например, .bash_history;
# - монтируем devdir под тем же именем, что и на хосте, чтобы можно было использовать инструменты
#   отладки на хосте, да и стектрейсы читать удобней.
docker run \
    --volume="${devdir}:${devdir}:rw" \
    --volume="${devdir}:${container_home}:rw" \
    --env="PATH=$container_home/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    --env="HOME=${container_home}" \
    --env="TARGET_USER=${container_user}" \
    --env="TARGET_UID=$(id -u)" \
    --env="TARGET_GID=$(id -g)" \
    --env="SHELL=${SHELL}" \
    --env="TERM=${TERM}" \
    --entrypoint="${container_home}/entrypoint.sh" \
    --workdir="${devdir}" \
    --rm \
    "${docker_args[@]}" \
    "$@"

