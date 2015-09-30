#!/bin/sh

set -e

apt-get update
apt-get install --yes --no-install-recommends sudo runit make

apt-get autoremove --yes
apt-get purge --yes
apt-get clean --yes
find /var/lib/apt/lists/ /tmp/ -mindepth 1 -maxdepth 1 -print0 | sudo xargs -0 -r rm -rf

