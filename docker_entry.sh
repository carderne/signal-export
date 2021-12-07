#!/bin/sh

set -e
trap "{ exit 0; }" TERM INT

sigexport --overwrite --source=/tmp/Signal /output "$@"
chown -R dummy /output/
