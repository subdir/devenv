#!/bin/bash

set -e
set -o pipefail

apt-get install --yes --no-install-recommends sudo runit make
echo "user ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/user

