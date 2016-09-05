ifeq ($(JUJU_REPOSITORY),)
	echo "Please set the JUJU_REPOSITORY environment variable"
	exit 1
endif
ifeq ($(LAYER_PATH),)
	echo "Please set the LAYER_PATH environment variable"
	exit 1
endif
ifeq ($(INTERFACE_PATH),)
	echo "Please set the INTERFACE_PATH environment variable"
	exit 1
endif

.PHONY: build
build: venv/bin/charm-build
	venv/bin/charm-build

.PHONY: clean
clean:
	rm -rf venv
	rm -rf .tox

# Since having a Makefile in the layer means that the Makefile that would wind
# up in the built charm gets overwritten, the generated Makefile is included
# here so that the targets remain.
.PHONY: all
all: lint unit_test

.PHONY: apt_prereqs
apt_prereqs:
	@# Need tox, but don't install the apt version unless we have to (don't want to conflict with pip)
	@which tox >/dev/null || (sudo apt-get install -y python-pip && sudo pip install tox)

.PHONY: lint
lint: apt_prereqs
	@tox --notest
	@PATH=.tox/py34/bin:.tox/py35/bin flake8 $(wildcard hooks reactive lib unit_tests tests)
	@charm proof

.PHONY: unit_test
unit_test: apt_prereqs
	@echo Starting tests...
	tox

venv/bin/charm-build: venv
	venv/bin/pip install -r requirements.txt

venv:
	virtualenv venv
