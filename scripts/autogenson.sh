#!/bin/bash

# Given a directory containing JSON files and an optional starting schema, use
# Genson to build a unified draft schema that maps to all of them

INPUT_DIR=$1
OUT_SCHEMA=$2
REF_SCHEMA=$3
TMP_SCHEMA=
PREV_TMP_SCHEMA=

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$DIR/common.sh"

if [ -z "$INPUT_DIR" ];
then
    die "Please provide a directory containing JSON files"
fi

if [ -z "$OUT_SCHEMA" ];
then
    die "Please specify an output filename for the new schema"
fi

if [ ! -z "$REF_SCHEMA" ]; then
    SCHEMA_OPTS="-s $REF_SCHEMA"
    log "Refining the following schema: ${REF_SCHEMA}"
fi

handle_error() {
    mv $PREV_TMP_SCHEMA ${OUT_SCHEMA} && \
    log "An error occurred a4 $LINENO. Saving last known good iteration to ${OUT_SCHEMA}"
}

trap 'handle_error $LINENO' ERR
log "Destination: ${OUT_SCHEMA}"

for JSON in $(find $INPUT_DIR -name "*.json" -print)
do
    log "Now processing: ${JSON}"
    PREV_TMP_SCHEMA=$TMP_SCHEMA
    TMP_SCHEMA=`mktemp /tmp/genson.XXXXXX`
    log "Temp: $TMP_SCHEMA"
    genson -i 2 ${SCHEMA_OPTS} $JSON > ${TMP_SCHEMA}
    if [ "$?" != 0 ]; then
        exit 1
    fi
    SCHEMA_OPTS="-s ${TMP_SCHEMA}"
done

log "Here's the final file..."

mv -f ${TMP_SCHEMA} ${OUT_SCHEMA} && \
    jq -r . ${OUT_SCHEMA}

