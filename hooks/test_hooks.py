#!/usr/bin/python3

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import yaml

os.environ['CHARM_DIR'] = os.path.join(os.path.dirname(__file__), '..')
os.environ['JUJU_UNIT_NAME'] = 'bundleservice/0'

from charmhelpers.core import hookenv  # noqa

hookenv.close_port = mock.MagicMock()
CONFIG = hookenv.Config({
    'source': 'deb http://example.com foo bar',
    'listen-port': 8082,
    'nagios_context': 'juju',
    'nagios_servicegroups': '',
})
CONFIG.save = mock.MagicMock()
hookenv.config = mock.MagicMock(return_value=CONFIG)
hookenv.log = mock.MagicMock()
hookenv.open_port = mock.MagicMock()
hookenv.unit_get = mock.MagicMock()
hookenv.status_set = mock.MagicMock()
hookenv.relation_id = mock.MagicMock()
hookenv.relation_set = mock.MagicMock()
RELATIONS = {}
hookenv.relations = mock.MagicMock(return_value=RELATIONS)
hookenv.unit_get = mock.MagicMock()

from charmhelpers.core import host  # noqa

host.adduser = mock.MagicMock()
host.mkdir = mock.MagicMock()
host.service = mock.MagicMock(return_value=True)
host.write_file = mock.MagicMock()

import hooks  # noqa

hooks.fetch.apt_install = mock.MagicMock()
hooks.fetch.apt_hold = mock.MagicMock()
hooks.fetch.apt_update = mock.MagicMock()
hooks.LOG = mock.MagicMock()


class TestInstall(unittest.TestCase):

    def test_install_does_not_raise(self):
        '''Testing that there are no exceptions in hooks.install.'''
        with mock.patch('charmhelpers.fetch.log'):
            hooks.install()

    @mock.patch('hooks.add_source_list')
    @mock.patch('hooks.apt_get_update')
    def test_installs_packages(
            self, mock_apt_get_update, mock_add_source_list):
        hooks.fetch.apt_install.reset_mock()
        hooks.install()
        hooks.fetch.apt_install.assert_any_call(
            hooks.BINARY_DEPENDENCIES, options=hooks.APT_INSTALL_OPTIONS)
        mock_apt_get_update.assert_any_call()
        mock_add_source_list.assert_any_call()

    def test_install_exec_d(self):
        file = tempfile.NamedTemporaryFile()
        if not os.path.exists('exec.d/test'):
            os.makedirs('exec.d/test')
        self.addCleanup(shutil.rmtree, 'exec.d')
        with open('exec.d/test/charm-pre-install', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('echo PASS > {}\n'.format(file.name))
        os.chmod('exec.d/test/charm-pre-install', 0o755)
        with mock.patch('charmhelpers.fetch.log'):
            hooks.install()
        result = file.read()
        self.assertEqual('PASS', result.strip().decode('UTF-8'))

    def test_install_no_exec_d(self):
        file = tempfile.NamedTemporaryFile()
        if not os.path.exists('exec.d/test'):
            os.makedirs('exec.d/test')
        self.addCleanup(shutil.rmtree, 'exec.d')
        with open('exec.d/test/charm-pre-install', 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('echo FAIL > {}\n'.format(file.name))
        os.chmod('exec.d/test/charm-pre-install', 0o755)
        with mock.patch('charmhelpers.fetch.log'):
            hooks.install(run_pre=False)
        result = file.read()
        self.assertNotEqual('FAIL', result.strip())

    def test_install_handles_exception(self):
        exception_caught = False
        with mock.patch('charmhelpers.fetch.log'):
            with mock.patch('hooks.fetch.apt_install') as mock_apt_install:
                mock_apt_install.side_effect = \
                    subprocess.CalledProcessError('cmd', 'ENOSPACE')
                with mock.patch('hooks.active_status') as mock_active_status:
                    try:
                        hooks.install()
                    except hooks.InstallIncompleteException:
                        exception_caught = True
        self.assertTrue(exception_caught)
        mock_active_status.assert_not_called()


class TestConfigChanged(unittest.TestCase):

    def setUp(self):
        CONFIG._prev_dict = dict(CONFIG)
        hookenv.close_port.reset_mock()
        hookenv.open_port.reset_mock()

    def test_config_changed_does_not_raise(self):
        '''Testing that there are no exceptions in hooks.config_changed.'''
        hooks.config_changed()

    def test_config_changed_calls_save(self):
        hooks.config_changed()
        self.assertTrue(CONFIG.save.called)

    @mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE')
    def test_listen_port_opens_port(self, nrpe):
        CONFIG['listen-port'] = 80
        CONFIG._prev_dict['listen-port'] = None
        hooks.config_changed()
        hookenv.open_port.assert_called_once_with(80)

    @mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE')
    def test_listen_port_closes_old_port(self, nrpe):
        CONFIG['listen-port'] = 80
        CONFIG._prev_dict['listen-port'] = 8080
        hooks.config_changed()
        hookenv.close_port.assert_called_once_with(8080)

    @mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE')
    def test_listen_port_updates_web_relations(self, nrpe):
        RELATIONS['website'] = {1: {'server/0': {}}}
        CONFIG['listen-port'] = 8081
        hooks.config_changed()
        hookenv.relation_set.assert_called_once_with(
            relation_id=1,
            relation_settings={
                'hostname': hookenv.unit_private_ip(),
                'port': 8081})

    def test_listen_port_updates_nrpe(self):
        CONFIG['listen-port'] = 8082
        with mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE') as nrpe:
            hooks.config_changed()
            nrpe().add_check.assert_called_once_with(
                shortname="bundleservice",
                description="Check bundleservice response",
                check_cmd="check_http -I {} -p 8082 -u /debug/info"
                "".format(hookenv.unit_private_ip()))

    @mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE')
    def test_listen_port_writes_config_and_restarts(self, nrpe):
        CONFIG['listen-port'] = 8080
        CONFIG._prev_dict['listen-port'] = 8081
        with mock.patch('hooks.write_config_file') as write_config_file:
            with mock.patch('hooks.restart') as restart:
                hooks.config_changed()
                self.assertEqual(write_config_file.call_count, 1)
                self.assertEqual(restart.call_count, 1)

    def test_source_restarts(self):
        with mock.patch('charmhelpers.fetch.log'):
            CONFIG['source'] = 'master'
            CONFIG._prev_dict['source'] = None
            with mock.patch('hooks.restart') as restart:
                hooks.config_changed()
                self.assertEqual(restart.call_count, 1)


class TestWriteConfigFile(unittest.TestCase):

    def setUp(self):
        host.write_file.reset_mock()

    def assertEqualUnordered(self, a, b):
        '''
        Given a and b, which are comma-separated strings,
        assert the components are the same regardless of order.
        '''
        a = sorted(a.split(','))
        b = sorted(b.split(','))
        self.assertEqual(a, b)

    def test_does_not_raise(self):
        hooks.write_config_file()

    def test_values(self):
        CONFIG['listen-port'] = 80
        result = hooks.write_config_file()
        self.assertTrue(result)
        self.assertTrue(host.write_file.called)
        self.assertEqual(
            host.write_file.call_args[0][0],
            '/etc/bundleserviced/config.yaml')
        data = yaml.load(host.write_file.call_args[0][1])
        self.assertEqual(data['api-addr'], '0.0.0.0:80')
        for k, v in data.items():
            self.assertTrue(v is None or
                            isinstance(v, str) or
                            isinstance(v, dict))


class TestStart(unittest.TestCase):

    def test_start_does_not_raise(self):
        hooks.start()

    def test_start_runs_service(self):
        hooks.start()
        host.service.assert_called_with('restart', 'bundleservice')


class TestStop(unittest.TestCase):

    def test_stop_does_not_raise(self):
        hooks.stop()

    def test_stop_stops_service(self):
        hooks.stop()
        host.service.assert_called_with('stop', 'bundleservice')

    def test_stop_removes_config_file(self):
        with mock.patch('os.unlink') as unlink:
            hooks.stop()
        unlink.assert_any_call(
            '/etc/bundleserviced/config.yaml')


class TestWebsiteRelation(unittest.TestCase):

    def test_website_relation_does_not_raise(self):
        hooks.website_relation_hooks()

    def test_website_relation_sets(self):
        CONFIG['listen-port'] = 8085
        hooks.website_relation_hooks()
        hookenv.relation_set.assert_called_with(
            relation_id=hookenv.relation_id(),
            relation_settings={
                'hostname': hookenv.unit_private_ip(), 'port': 8085})


class TestNRPERelation(unittest.TestCase):

    def test_nrpe_relation_updates_config(self):
        CONFIG['listen-port'] = 8090
        with mock.patch('charmhelpers.contrib.charmsupport.nrpe.NRPE') as nrpe:
            hooks.update_nrpe_checks()
            nrpe().add_check.assert_called_once_with(
                shortname="bundleservice",
                description="Check bundleservice response",
                check_cmd="check_http -I {} -p 8090 -u /debug/info"
                "".format(hookenv.unit_private_ip()))


class TestStatusSetting(unittest.TestCase):

    def setUp(self):
        hookenv.status_set.reset_mock()

    def test_maintenance(self):
        hooks.maintenance_status('pow')
        hookenv.status_set.assert_called_once_with('maintenance', 'pow')

    def test_blocked(self):
        hooks.blocked_status('bam')
        hookenv.status_set.assert_called_once_with('blocked', 'bam')

    def test_active(self):
        hooks.active_status('kaboom')
        hookenv.status_set.assert_called_once_with('active', 'kaboom')


class TestAddSourceList(unittest.TestCase):

    def test_add_source_list(self):
        source = 'ppa:elmo/red'
        with mock.patch('hooks.fetch.add_source') as mock_add_source:
            CONFIG[hooks.SOURCE_KEY] = source
            hooks.add_source_list()
        mock_add_source.assert_called_with(source)


class TestAptGetUpdate(unittest.TestCase):

    def setUp(self):
        hooks.fetch.apt_update.reset_mock()

    def test_apt_get_update(self):
        hooks.apt_get_update()
        hooks.fetch.apt_update.assert_called_once_with()

    def test_apt_get_update_raises(self):
        with mock.patch('hooks.blocked_status') as mock_blocked_status:
            hooks.fetch.apt_update.side_effect = Exception('Cannot connect')
            hooks.apt_get_update()
        expected = "apt_get_update error: Cannot connect"
        mock_blocked_status.assert_called_once_with(expected)


class TestUpgradeCharm(unittest.TestCase):

    def setUp(self):
        hooks.fetch.apt_install.reset_mock()
        hooks.fetch.apt_hold.reset_mock()

    @mock.patch('hooks.host.service_stop')
    @mock.patch('hooks.apt_get_update')
    @mock.patch('hooks.fetch.apt_unhold')
    @mock.patch('hooks.restart')
    @mock.patch('hooks.maintenance_status')
    @mock.patch('hooks.active_status')
    def test_upgrade_charm(
            self,
            mock_active_status,
            mock_maintenace_status,
            mock_restart,
            mock_apt_unhold,
            mock_apt_get_update,
            mock_service_stop):
        hooks.upgrade_charm()

        mock_service_stop.assert_called_once_with(hooks.APPLICATION)
        mock_apt_get_update.assert_called_once_with()
        mock_apt_unhold.assert_called_once_with(hooks.BINARY_DEPENDENCIES)
        hooks.fetch.apt_install.assert_called_once_with(
            hooks.BINARY_DEPENDENCIES,
            options=hooks.APT_INSTALL_OPTIONS,
        )
        hooks.fetch.apt_hold.assert_called_once_with(hooks.BINARY_DEPENDENCIES)
        mock_maintenace_status.assert_called_once_with('restarting service')
        mock_restart.assert_called_once_with()
        mock_active_status.assert_called_once_with('upgrade-charm succeeded')
