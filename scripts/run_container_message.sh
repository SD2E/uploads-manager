#!/usr/bin/env bash

# Usage: run_container_message.sh (relative/path/to/message.json)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$DIR/common.sh"

read_reactor_rc
detect_ci

# Load up the message to send
if [ ! -z "$1" ]; then
  MESSAGE_PATH=$1
else
  MESSAGE_PATH="tests/data/local-message-01.json"
fi
MESSAGE=
if [ -f "${MESSAGE_PATH}" ]; then
    MESSAGE=$(cat ${MESSAGE_PATH})
fi
if [ -z "${MESSAGE}" ]; then
    die "Message not readable from ${MESSAGE_PATH}"
fi

# Read Docker envs from secrets.json
# This emulates Abaco's environment-setting behavior
DOCKER_ENVS=$(python ${DIR}/secrets_to_docker_envs.py ${REACTOR_SECRETS_FILE})
# Set the Reactor.local flag. Also ensures DOCKER_ENVS is not empty
DOCKER_ENVS="-e LOCALONLY=1 ${DOCKER_ENVS}"

# Agave API integration
AGAVE_CREDS="${AGAVE_CACHE_DIR}"
if [ ! -d "${AGAVE_CREDS}" ]; then
    AGAVE_CREDS="${HOME}/.agave"
    # Refresh them with a call to Agave.restore()
    if ((AGAVE_PREFER_PYTHON)); then
      eval python ${DIR}/refresh_agave_credentials.py
    else
      auth-tokens-refresh -S
    fi
fi
if [ ! -f "${AGAVE_CREDS}/current" ]; then
    die "No Agave API credentials found in ${AGAVE_CREDS}"
fi

TEMP=`mktemp -d $PWD/tmp.XXXXXX` && \
  echo "Working directory: $TEMP"

docker run -t -v ${AGAVE_CREDS}:/root/.agave:rw \
           -v ${TEMP}:/mnt/ephemeral-01:rw \
           -e MSG="${MESSAGE}" \
           ${DOCKER_ENVS} \
           ${CONTAINER_IMAGE}

DOCKER_EXIT_CODE="$?"

if [ "$DOCKER_EXIT_CODE" == 0 ]; then
    rm -rf ${TEMP}
fi

exit ${DOCKER_EXIT_CODE}
