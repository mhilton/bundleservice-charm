#!/usr/bin/python3

import glob
import os
import subprocess
import sys
import yaml

from charmhelpers.core import (
    hookenv,
    host,
)
from charmhelpers.contrib.charmsupport import nrpe
import charmhelpers.fetch as fetch

APPLICATION = 'bundleservice'
CHARMDIR = os.environ['CHARM_DIR']
CONFIG_YAML = '/etc/{}d/config.yaml'.format(APPLICATION)
LISTEN_PORT_KEY = 'listen-port'
SOURCE_KEY = 'source'
NAGIOS_CONTEXT_KEY = 'nagios_context'
CONTROLLER_ADMIN_KEY = 'controller-admin'
WEBSITE_RELATION = 'website'

BINARY_DEPENDENCIES = (APPLICATION, 'nacl-tools',)

CONFIG = hookenv.config()
CONFIG.implicit_save = False
HOOKS = hookenv.Hooks()
RELATIONS = hookenv.relations()
LOG = hookenv.log
UTF8 = 'utf-8'
APT_INSTALL_OPTIONS = (
    '--option=Dpkg::Options::=--force-confold',
    '--no-install-recommends',
)


class InstallIncompleteException(Exception):
    pass


@HOOKS.hook('nrpe-external-master-relation-changed')
@HOOKS.hook('local-monitors-relation-changed')
def update_nrpe_checks():
    nrpe_compat = nrpe.NRPE()
    port = CONFIG[LISTEN_PORT_KEY]
    ip_address = hookenv.unit_private_ip()
    nrpe_compat.add_check(
        shortname=APPLICATION,
        description='Check ' + APPLICATION + ' response',
        check_cmd='check_http -I {} -p {} -u /debug/info'.format(
            ip_address, port))
    nrpe_compat.write()


def maintenance_status(msg):
    hookenv.status_set('maintenance', msg)


def blocked_status(msg):
    hookenv.status_set('blocked', msg)


def active_status(msg):
    hookenv.status_set('active', msg)


def ensure_ppa():
    """Running apt-get update is slow.  Check if it needs to be done."""
    if not has_source_list():
        add_source_list()


def add_source_list():
    fetch.add_source(CONFIG[SOURCE_KEY])


def has_source_list():
    """Return true if the configured source is already added.
    Returns false if it is not already added.
    """
    sources = ['/etc/apt/sources.list']
    sources.extend(glob.glob('/etc/apt/sources.list.d/*.list'))
    for f in sources:
        lines = open(f, 'r').readlines()
        for line in lines:
            if CONFIG[SOURCE_KEY] in line:
                return True
    return False


def apt_get_update():
    maintenance_status('apt get update')
    try:
        fetch.apt_update()
    except Exception as e:
        msg = "apt_get_update error: {}".format(e)
        LOG(msg)
        print(msg)
        blocked_status(msg)


def write_config_file():
    params = {}
    params['api-addr'] = '0.0.0.0:{}'.format(CONFIG[LISTEN_PORT_KEY])
    params = yaml.safe_dump(params).encode(UTF8)
    host.write_file(
        CONFIG_YAML, params)
    LOG("wrote " + CONFIG_YAML)
    active_status("wrote configuration")
    return True


@HOOKS.hook('config-changed')
def config_changed():
    needs_restart = False
    update_config = False
    for key in CONFIG:
        if CONFIG.changed(key):
            msg = "CONFIG['{}'] changed from {} to {}".format(
                key, CONFIG.previous(key), CONFIG[key])
            print(msg)
            LOG(msg)
    if CONFIG.changed(SOURCE_KEY) and CONFIG[SOURCE_KEY]:
        install(run_pre=False)
        needs_restart = True
    if CONFIG.changed(LISTEN_PORT_KEY):
        if CONFIG.previous(LISTEN_PORT_KEY) is not None:
            msg = "close-port {}".format(CONFIG.previous(LISTEN_PORT_KEY))
            print(msg)
            LOG(msg)
            hookenv.close_port(CONFIG.previous(LISTEN_PORT_KEY))
        listen_port = CONFIG[LISTEN_PORT_KEY]
        msg = "open-port {}".format(listen_port)
        print(msg)
        LOG(msg)
        hookenv.open_port(listen_port)
        update_website_relations()
        update_nrpe_checks()
        update_config = True
    if CONFIG.changed(NAGIOS_CONTEXT_KEY):
        update_nrpe_checks()

    CONFIG.save()
    if update_config:
        needs_restart = True
        write_config_file()
    if needs_restart:
        restart()


@HOOKS.hook('upgrade-charm')
def upgrade_charm():
    host.service_stop(APPLICATION)
    LOG('upgrade_charm')
    apt_get_update()
    fetch.apt_unhold(BINARY_DEPENDENCIES)
    fetch.apt_install(BINARY_DEPENDENCIES, options=APT_INSTALL_OPTIONS)
    fetch.apt_hold(BINARY_DEPENDENCIES)
    maintenance_status("restarting service")
    restart()
    active_status("upgrade-charm succeeded")


def restart():
    LOG('(re)starting ' + APPLICATION)
    host.service_restart(APPLICATION) or host.service_start(APPLICATION)


@HOOKS.hook('start')
def start():
    restart()


@HOOKS.hook('stop')
def stop():
    host.service_stop(APPLICATION)
    try:
        os.unlink(CONFIG_YAML)
    except Exception as e:
        LOG(repr(e))


@HOOKS.hook('install')
def install(run_pre=True):
    if run_pre:
        for f in glob.glob('exec.d/*/charm-pre-install'):
            if os.path.isfile(f) and os.access(f, os.X_OK):
                subprocess.check_call(['sh', '-c', f])
    ensure_ppa()
    apt_get_update()
    try:
        fetch.apt_install(BINARY_DEPENDENCIES, options=APT_INSTALL_OPTIONS)
        fetch.apt_hold(BINARY_DEPENDENCIES)
    except subprocess.CalledProcessError:
        raise InstallIncompleteException()
    active_status("install succeeded")


def update_website_relations():
    for relation_id in list(RELATIONS.get(WEBSITE_RELATION, {}).keys()):
        update_website_relation(relation_id)


def update_website_relation(relation_id):
    port = CONFIG[LISTEN_PORT_KEY]
    private_address = hookenv.unit_private_ip()
    hookenv.relation_set(
        relation_id=relation_id,
        relation_settings={'hostname': private_address, 'port': port})


@HOOKS.hook('website-relation-joined')
@HOOKS.hook('website-relation-departed')
@HOOKS.hook('website-relation-changed')
@HOOKS.hook('website-relation-broken')
def website_relation_hooks():
    update_website_relation(hookenv.relation_id())


if __name__ == "__main__":
    argv = sys.argv[-1:]
    LOG(os.path.basename(argv[0]), hookenv.INFO)
    HOOKS.execute(argv)
