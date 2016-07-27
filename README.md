# Overview

juju charm for bundleservice service

# Usage

## General Usage

The bundleservice is a stand-alone service and has no other charm dependencies.

All examples here are for juju 2 command-line usage but the charm can be
deployed with juju 1.

### Upgrading the bundleservice Without Upgrading the Charm

Upgrading is done by triggering the config-changed hook by setting the `source`
configuration value. It can either be set to a new value or by an innocuous
change, such as adding a trailing space.  The equivalent of apt-get update and
apt-get upgrade will be done . Afterwards, bundleservice will be
restarted.

#### When Using PPA

Change the source config to trigger apt-get update & install bundleservice
package. Adding whitespace to source is a good option:

    juju get-config bundleservice  # note the source
    juju set-config bundleservice source='<SAME AS OLD SOURCE WITH A TRAILING WHITESPACE>'

## Scale Out Usage

The bundleservice can be scaled out by deploying more units and using a load balancer. To
use apache as a load balancer, deploy bundleservice and apache.

    juju deploy apache2
    juju deploy . bundleservice

Add relations between them

    juju add-relation bundleservice apache2:balancer

Create a vhost template that uses the balancer, write the something like
the following to a file (e.g. /tmp/vhost-jem.tmpl)

    <VirtualHost _default_:80>
      ProxyPreserveHost On
      ProxyPass / balancer://bundleservice/
      ProxyPassReverse / balancer://bundleservice/
    </VirtualHost>

Upload the configuration to the apache charm

    juju set-config apache2 "vhost_http_template=$(base64 /tmp/vhost-bundleservice.tmpl)"

Expose apache

    juju expose apache2

Additional bundleservice capacity can now be added by adding more units

    juju add-unit bundleservice

# Configuration

The source for getting the bundleservice can be set. It can be a public PPA or a
sources.list entry if using a private PPA, e.g.

    juju set-config bundleservice source='deb https://USER:TOKEN@private-ppa.launchpad.net/yellow/theblues-unstable/ubuntu trusty main'

## Other config

The TCP port on which to listen can be set using the listen-port variable.

     juju set-config bundleservice listen-port=8000

# Series Support
The bundleservice charm only supports being deployed on trusty (Ubuntu 14.04) and
later. This can cause problems with subordinate charms, at the time of writing
there is no trusty/nrpe charm. If nrpe functionality is required
~rcj/trusty/nrpe is known to work.

# Contact Information

[#juju-gui] on freenode

## Upstream - bundleservice

- Upstream website - https://github.com/CanonicalLtd/bundleservice
- Upstream bug tracker - https://github.com/CanonicalLtd/bundleservice-charm/issues
- Upstream contact information is the same as the charm. [#juju-gui] on freenode
