#!/bin/sh

set -e
trap "{ exit 0; }" TERM INT

sigexport --source=/Signal /output "$@"
chown -R dummy /output/
