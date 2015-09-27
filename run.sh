#!/bin/bash

set -e
set -o pipefail


devenv_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
dev_dir="$(dirname "${devenv_dir}")"
container_user=dev
container_home=/home/dev
container_workdir="${container_home}"
docker_args=()
volumes=yes


while [ -n "$1" ]; do
    case "$1" in
        --no-volumes)
            volumes=no
            shift
            ;;
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


if [[ "${volumes}" == "yes" ]]; then
    # - монтируем dev_dir как хомяк, чтобы сохранялся стейт между запусками, например, .bash_history;
    # - монтируем dev_dir под тем же именем, что и на хосте, чтобы можно было использовать инструменты
    #   отладки на хосте, да и стектрейсы читать удобней.
    docker_args=("${docker_args[@]}" --volume="${dev_dir}:${dev_dir}:rw" --volume="${dev_dir}:${container_home}:rw")
fi


docker run \
    --env="PATH=$container_home/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    --env="HOME=${container_home}" \
    --env="TARGET_USER=${container_user}" \
    --env="TARGET_UID=$(id -u)" \
    --env="TARGET_GID=$(id -g)" \
    --env="SHELL=${SHELL}" \
    --env="TERM=${TERM}" \
    --entrypoint="${devenv_dir}/entrypoint.sh" \
    --workdir="${container_home}" \
    --rm \
    "${docker_args[@]}" \
    "$@"

