#!/usr/bin/env bash

# Invoke code for a Reactor in an environment
# that closely emulates the Abaco runtime

# Required Globals
#   CONTAINER_IMAGE
# Optional Globals
#   REACTOR_RUN_OPTS
#   REACTOR_USE_TMP
#   REACTOR_CLEANUP_TMP
#   REACTOR_LOCALONLY
#   CONTAINER_REPO
#   CONTAINER_TAG
#   AGAVE_CACHE_DIR
#   REACTOR_JOB_DIR
#
# Required inputs
#   MESSAGE - File containing JSON message body
#   CONFIG - Reactor config file (reactor.rc)


COMMANDS="$@"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$DIR/common.sh"

read_reactor_rc

if [ -z "$CONTAINER_IMAGE" ]; then
    die "CONTAINER_IMAGE not set"
fi

# API integration
AGAVE_CREDS="${AGAVE_CACHE_DIR}"
if [ ! -d "${AGAVE_CREDS}" ]; then
    AGAVE_CREDS="${HOME}/.agave"
fi
if [ ! -f "${AGAVE_CREDS}/current" ]; then
    log "No API credentials found in ${AGAVE_CREDS}"
fi

# Read Docker envs from secrets.json
if [ ! -f "${REACTOR_SECRETS_FILE}" ]; then
    die "No secrets.json found"
fi
# This emulates Abaco's environment-setting behavior
log "Reading in container secrets file..."
DOCKER_ENVS=$(python ${DIR}/secrets_to_docker_envs.py ${REACTOR_SECRETS_FILE})
# Set the Reactor.local flag. Also ensures DOCKER_ENVS is not empty
DOCKER_ENVS="-e LOCALONLY=1 ${DOCKER_ENVS}"

# Read additional envs from env.json
if [ -f "${REACTOR_ENV_FILE}" ]; then
    # This allow overrides of some env used to set up various systems
    log "Reading in container env file..."
    CONTAINER_ENVS=$(python ${DIR}/secrets_to_docker_envs.py ${REACTOR_ENV_FILE})
    DOCKER_ENVS="-e LOCALONLY=1 ${DOCKER_ENVS} ${CONTAINER_ENVS}"
fi

# Emphemeral directory
WD=${PWD}
if ((! USEPWD)); then
    WD=`mktemp -d $PWD/tmp.XXXXXX`
fi
log "Working directory: ${WD}"

# Volume mounts
MOUNTS="-v ${WD}:/mnt/ephemeral-01"
if [ -d "${AGAVE_CREDS}" ]; then
    MOUNTS="$MOUNTS -v ${AGAVE_CREDS}:/root/.agave:rw"
fi

# Tweak config for Docker depending on if we're running under CI
dockeropts="${REACTOR_RUN_OPTS}"
detect_ci
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

docker run ${DOCKER_ENVS} ${MOUNTS} ${CONTAINER_IMAGE} ${@}
DOCKER_RUN_EXIT_CODE="$?"

# Clean up: Set permissions and ownership on volume mount
if ((UNDER_CI)); then
    docker run ${dockeropts} ${MOUNTS} bash -c "chown -R ${CI_UID}:${CI_GID} /mnt/ephemeral-01; sleep 2"
fi

if ((REACTOR_CLEANUP_TMP)) && [ -z "${TEMP}" ]; then
    log "Cleaning up ${TEMP}"
    rm -rf ${TEMP}
fi

exit ${DOCKER_RUN_EXIT_CODE}
