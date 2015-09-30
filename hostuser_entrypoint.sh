#!/bin/bash

set -e
set -o pipefail

: ${TARGET_USER?}
: ${TARGET_UID?}
: ${TARGET_GID?}

groupadd "${TARGET_USER}" --gid "${TARGET_GID}"
useradd "${TARGET_USER}" \
    --uid "${TARGET_UID}" \
    --gid "${TARGET_GID}" \
    --groups sudo \
    --password "$(perl -e'print crypt("user", "aa")')"

[[ -v ALLOW_SUDO ]] && echo "${TARGET_USER} ALL=(ALL:ALL) NOPASSWD: ALL" > "/etc/sudoers.d/${TARGET_USER}"

mkdir -p "$HOME"
chown "${TARGET_USER}":"${TARGET_USER}" "$HOME"

if [[ $# != 0 ]]; then
    chpst -u "${TARGET_USER}":"${TARGET_USER}" "$@"
else
    chpst -u "${TARGET_USER}":"${TARGET_USER}" bash -i
fi

[[ -v ALLOW_SUDO ]] && rm -f "/etc/sudoers.d/${TARGET_USER}"
userdel "${TARGET_USER}"

