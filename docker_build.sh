#!/bin/bash

set -e
set -o pipefail

docker build "$@" \
| tee -a /dev/stderr \
| tail -n1 \
| grep -E '^Successfully built [0-9a-f]+$$' \
| cut -f3 -d' '
