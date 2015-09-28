#!/bin/bash

set -e
set -o pipefail

: ${TARGET_USER?}
: ${TARGET_UID?}
: ${TARGET_GID?}

userdel "${TARGET_USER}" || true
groupdel "${TARGET_USER}" || true

groupadd "${TARGET_USER}" --gid "${TARGET_GID}"
useradd "${TARGET_USER}" \
    --uid "${TARGET_UID}" \
    --gid "${TARGET_GID}" \
    --groups sudo \
    --password "$(perl -e'print crypt("user", "aa")')"

if [[ -x /usr/bin/chpst ]]; then
    sudo_cmd="chpst -u user:user"
elif [[ -x /usr/bin/sudo ]]; then
    sudo_cmd="sudo -u user -g user"
fi

if [[ $# != 0 ]]; then
    exec $sudo_cmd "$@"
else
    exec $sudo_cmd bash -i
fi

