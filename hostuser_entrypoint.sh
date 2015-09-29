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

if [[ $# != 0 ]]; then
    chpst -u user:user "$@"
else
    chpst -u user:user bash -i
fi

userdel "${TARGET_USER}"

