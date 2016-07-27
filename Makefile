# Copyright 2016 Canonical Ltd.

# Development environment dependencies: keep these in alphabetical order.
SYSDEPS = build-essential bzr charm charm-tools git golang jq juju-core juju-local \
    mercurial python-apt python3 python3-coverage python3-nose python3-pyflakes \
    python3-pep8 python3-six python3-yaml rsync

.PHONY: all
all: help

.PHONY: deploy
deploy:
	juju deploy . bundleservice

.PHONY: check
check: lint test
	charm proof

.PHONY: lint
lint:
	find hooks -name '*.py' | xargs pep8
	find hooks -name '*.py' | xargs pyflakes3

.PHONY: help
help:
	@echo -e 'bundleservice charm - list of make targets:\n'
	@echo 'make unittest - Run Python unit tests.'
	@echo 'make test - Run unit tests and functional tests.'
	@echo '     Functional tests are run bootstrapping the current default'
	@echo '     Juju environment.'
	@echo 'make check - Run Python linter, tests, and charm proof.'
	@echo 'make deploy - Deploy local charm from a temporary local repository.'
	@echo '     The charm is deployed to the current default Juju environment.'
	@echo '     The environment must be already bootstrapped.'
	@echo 'make sync - Synchronize/update the charm helpers library.'
	@echo 'make sysdeps - Install system deb dependencies.'

.PHONY: sync
sync: charm-helpers.yaml
	scripts/charm_helpers_sync.py -d lib/charmhelpers -c charm-helpers.yaml

.PHONY: sysdeps
sysdeps:
	sudo add-apt-repository ppa:juju/stable
	sudo apt-get install --yes $(SYSDEPS)

.PHONY: test
test: unittest

.PHONY: unittest
unittest:
	nosetests3 -v --with-coverage --cover-package hooks hooks
