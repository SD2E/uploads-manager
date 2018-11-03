CONTAINER_IMAGE=$(shell bash scripts/container_image.sh)
PYTHON ?= "python3"
PYTEST_OPTS ?= "-s -vvv"
PYTEST_DIR ?= "tests"
ABACO_DEPLOY_OPTS ?= "-p"
SCRIPT_DIR ?= "scripts"
PREF_SHELL ?= "bash"
ACTOR_ID ?=
NOCLEANUP ?= 0
GITREF=$(shell git rev-parse --short HEAD)
REACTOR_ENV_FILE="env.json"

.PHONY: tests container tests-local tests-reactor tests-deployed
.SILENT: tests container tests-local tests-reactor tests-deployed

all: image
	true

image:
	abaco deploy -R -t $(GITREF) $(ABACO_DEPLOY_OPTS)

shell:
	REACTOR_ENV_FILE="env.json" USEPWD=1 bash $(SCRIPT_DIR)/run_container_process.sh bash

tests: tests-pytest tests-local

tests-pytest: image
	REACTOR_ENV_FILE="env.json" USEPWD=1 bash $(SCRIPT_DIR)/run_container_process.sh python3 -m "pytest" $(PYTEST_DIR) $(PYTEST_OPTS)

tests-integration:
	true

tests-local: image tests-local-file tests-local-dir

tests-local-file:
	REACTOR_ENV_FILE="env.json" USEPWD=1 bash $(SCRIPT_DIR)/run_container_message.sh tests/data/local-message-01.json

tests-local-dir:
	REACTOR_ENV_FILE="env.json" USEPWD=1 bash $(SCRIPT_DIR)/run_container_message.sh tests/data/local-message-02.json

tests-deployed:
	echo "not implemented"

clean: clean-image clean-tests

clean-image:
	docker rmi -f $(CONTAINER_IMAGE)

clean-tests:
	rm -rf .hypothesis .pytest_cache __pycache__ */__pycache__ tmp.* *junit.xml

deploy:
	abaco deploy -t $(GITREF) $(ABACO_DEPLOY_OPTS) -U $(ACTOR_ID)

postdeploy:
	bash tests/run_after_deploy.sh
