#!/bin/bash

set -e
set -o pipefail

"$@"

if [[ "${!#}" == "install" ]]; then
    sudo apt-get autoremove --yes
    sudo apt-get purge --yes
    sudo apt-get clean --yes
    sudo find /var/lib/apt/lists/ /tmp/ -mount -mindepth 1 -maxdepth 1 -delete | true
fi

