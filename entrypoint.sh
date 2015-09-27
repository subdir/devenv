#!/bin/bash
#
# Здесь не должно быть никакой лишней инициализации,
# только создание пользователя и настройка прав.

set -e
set -o pipefail

: ${TARGET_USER?}
: ${TARGET_UID?}
: ${TARGET_GID?}

groupadd ${TARGET_USER} --gid ${TARGET_GID}
useradd ${TARGET_USER} \
    --uid ${TARGET_UID} \
    --gid ${TARGET_GID} \
    --groups sudo \
    --password $(perl -e'print crypt("dev", "aa")')

if [[ $# != 0 ]]; then
    exec chpst -u dev:dev "$@"
else
    exec chpst -u dev:dev bash -i
fi

