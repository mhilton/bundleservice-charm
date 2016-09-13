from charms.reactive import (
    set_state,
    when,
    when_not,
)
from charmhelpers.core import (
    hookenv,
    host,
)


@when('nrpe-external-master.available')
@when_not('bundleservice-charm.nrpe-check-added')
def setup_nagios(nagios):
    unit_name = hookenv.local_unit()
    nagios.add_check(
        ['/usr/lib/nagios/plugins/check_http',
         '-I', '127.0.0.1', '-p', str(hookenv.config('listen-port')),
         '-e', " 404 Not Found", '-u', '/'],
        name="check_http",
        description="Verify bundleservice is running",
        context=config["nagios_context"],
        unit=unit_name,
    )
    set_state('bundleservice-charm.nrpe-check-added')


@when('website.available')
def configure_website(website):
    website.configure(port=hookenv.config('listen-port'))


@when('apt.installed.bundleservice')
def activate():
    hookenv.open_port(hookenv.config()['listen-port'])
    restart()
    hookenv.status_set('active', 'ready')


@when('config.changed')
def config_changed():
    restart()


def restart():
    host.service_restart('bundleservice')
