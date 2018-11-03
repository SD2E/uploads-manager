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
    MESSAGE_PATH="sample-message.json"
fi
MESSAGE=
if [ -f "${MESSAGE_PATH}" ]; then
    # Read in and minify message
    MESSAGE=$(jq -rc . ${MESSAGE_PATH})
fi
if [ -z "${MESSAGE}" ]; then
    die "Message not readable from ${MESSAGE_PATH}"
fi

# Refresh Agave credentials
AGAVE_CREDS="${AGAVE_CACHE_DIR}"
log "Pulling API credentials from ${AGAVE_CREDS}"
if [ ! -d "${AGAVE_CREDS}" ]; then
    AGAVE_CREDS="${HOME}/.agave"
    # Refresh them with a call to Agave.restore()
    if ((AGAVE_PREFER_PYTHON)); then
        log "Refreshing using AgavePy"
        eval python ${DIR}/refresh_agave_credentials.py
    else
        log "Refreshing using CLI"
        auth-tokens-refresh -S
    fi
fi
if [ ! -f "${AGAVE_CREDS}/current" ]; then
    die "No Agave API credentials found in ${AGAVE_CREDS}"
fi

# Emphemeral directory
WD=${PWD}
if ((! USEPWD)); then
    WD=`mktemp -d $PWD/tmp.XXXXXX`
fi
log "Working directory: ${WD}"

# Set up CI vars
CNAME=${CI_CONTAINER_NAME}
log "Container name: ${CNAME}"

# Set up enviroment
DOCKER_ENVS="-e LOCALONLY=1"

# Read Docker envs from secrets.json
if [ ! -f "${REACTOR_SECRETS_FILE}" ]; then
    die "No secrets.json found"
fi
# This emulates Abaco's secret-setting behavior
log "Reading in container secrets file..."
SECRET_ENVS=$(python ${DIR}/secrets_to_docker_envs.py ${REACTOR_SECRETS_FILE})
# Set the Reactor.local flag. Also ensures DOCKER_ENVS is not empty
DOCKER_ENVS="${DOCKER_ENVS} ${SECRET_ENVS}"

# Read additional envs from env.json
if [ -f "${REACTOR_ENV_FILE}" ]; then
    # This allow overrides of some env used to set up various systems
    log "Reading in container env file..."
    CONTAINER_ENVS=$(python ${DIR}/secrets_to_docker_envs.py ${REACTOR_ENV_FILE})
    DOCKER_ENVS="${DOCKER_ENVS} ${CONTAINER_ENVS}"
fi

# Tweak Docker depending if we're running under CI
if ((UNDER_CI)); then
    # If running a Dockerized process with a volume mount
    # written files will be owned by root and unwriteable by
    # the CI user. We resolve this by setting the group, which
    # is the same approach we use in the container runner
    # that powers container-powered Agave jobs
    DOCKER_ENVS="-t ${DOCKER_ENVS} --user=0:${CI_GID}"
else
    DOCKER_ENVS="-it ${DOCKER_ENVS}"
fi

function finish {
    log "Forcing ${CNAME} to stop..."
    docker stop ${CNAME} ; log "(Stopped)"
    if ((! NOCLEANUP)); then
        rm -rf ${TEMP}
    fi
}
trap finish EXIT

docker run -t -v ${AGAVE_CREDS}:/root/.agave:rw \
--name ${CNAME} \
-v ${WD}:/mnt/ephemeral-01:rw \
-e MSG="${MESSAGE}" \
${DOCKER_ENVS} \
${CONTAINER_IMAGE}

DOCKER_EXIT_CODE="$?"

exit ${DOCKER_EXIT_CODE}
