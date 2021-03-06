#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 F5 Networks Inc.
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: bigip_node
short_description: Manages F5 BIG-IP LTM nodes
description:
  - Manages F5 BIG-IP LTM nodes.
version_added: "1.4"
options:
  state:
    description:
      - Specifies the current state of the node. C(enabled) (All traffic
        allowed), specifies that system sends traffic to this node regardless
        of the node's state. C(disabled) (Only persistent or active connections
        allowed), Specifies that the node can handle only persistent or
        active connections. C(offline) (Only active connections allowed),
        Specifies that the node can handle only active connections. In all
        cases except C(absent), the node will be created if it does not yet
        exist.
      - Be particularly careful about changing the status of a node whose FQDN
        cannot be resolved. These situations disable your ability to change their
        C(state) to C(disabled) or C(offline). They will remain in an 
        *Unavailable - Enabled* state.
    default: present
    choices:
      - present
      - absent
      - enabled
      - disabled
      - offline
  name:
    description:
      - Specifies the name of the node.
    required: True
  monitor_type:
    description:
      - Monitor rule type when C(monitors) is specified. When creating a new
        pool, if this value is not specified, the default of 'and_list' will
        be used.
      - Both C(single) and C(and_list) are functionally identical since BIG-IP
        considers all monitors as "a list". BIG=IP either has a list of many,
        or it has a list of one. Where they differ is in the extra guards that
        C(single) provides; namely that it only allows a single monitor.
    version_added: "1.3"
    choices: ['and_list', 'm_of_n', 'single']
  quorum:
    description:
      - Monitor quorum value when C(monitor_type) is C(m_of_n).
    version_added: "2.2"
  monitors:
    description:
      - Specifies the health monitors that the system currently uses to
        monitor this node.
    version_added: "2.2"
  address:
    description:
      - IP address of the node. This can be either IPv4 or IPv6. When creating a
        new node, one of either C(address) or C(fqdn) must be provided. This
        parameter cannot be updated after it is set.
    aliases:
      - ip
      - host
    version_added: "2.2"
  fqdn:
    description:
      - FQDN name of the node. This can be any name that is a valid RFC 1123 DNS
        name. Therefore, the only characters that can be used are "A" to "Z",
        "a" to "z", "0" to "9", the hyphen ("-") and the period (".").
      - FQDN names must include at lease one period; delineating the host from
        the domain. ex. C(host.domain).
      - FQDN names must end with a letter or a number.
      - When creating a new node, one of either C(address) or C(fqdn) must be
        provided. This parameter cannot be updated after it is set.
    aliases:
      - hostname
    version_added: "2.2"
  description:
    description:
      - Specifies descriptive text that identifies the node.
  partition:
    description:
      - Device partition to manage resources on.
    default: Common
    version_added: 2.5
notes:
  - Requires the f5-sdk Python package on the host. This is as easy as
    pip install f5-sdk
  - Requires the netaddr Python package on the host. This is as easy as
    pip install netaddr
extends_documentation_fragment: f5
requirements:
  - f5-sdk >= 3.0.2
author:
  - Tim Rupp (@caphrim007)
'''

EXAMPLES = r'''
- name: Add node
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: present
    partition: Common
    host: 10.20.30.40
    name: 10.20.30.40
  delegate_to: localhost

- name: Add node with a single 'ping' monitor
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: present
    partition: Common
    host: 10.20.30.40
    name: mytestserver
    monitors:
      - /Common/icmp
  delegate_to: localhost

- name: Modify node description
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: present
    partition: Common
    name: 10.20.30.40
    description: Our best server yet
  delegate_to: localhost

- name: Delete node
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: absent
    partition: Common
    name: 10.20.30.40
  delegate_to: localhost

- name: Force node offline
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: disabled
    partition: Common
    name: 10.20.30.40
  delegate_to: localhost

- name: Add node by their FQDN
  bigip_node:
    server: lb.mydomain.com
    user: admin
    password: secret
    state: present
    partition: Common
    fqdn: foo.bar.com
    name: 10.20.30.40
  delegate_to: localhost
'''

RETURN = r'''
monitor_type:
  description:
    - Changed value for the monitor_type of the node.
  returned: changed and success
  type: string
  sample: m_of_n
quorum:
  description:
    - Changed value for the quorum of the node.
  returned: changed and success
  type: int
  sample: 1
monitors:
  description:
    - Changed list of monitors for the node.
  returned: changed and success
  type: list
  sample: ['icmp', 'tcp_echo']
description:
  description:
    - Changed value for the description of the node.
  returned: changed and success
  type: string
  sample: E-Commerce webserver in ORD
session:
  description:
    - Changed value for the internal session of the node.
  returned: changed and success
  type: string
  sample: user-disabled
state:
  description:
    - Changed value for the internal state of the node.
  returned: changed and success
  type: string
  sample: m_of_n
'''

import os
import re
import time

try:
    import netaddr
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

from ansible.module_utils.f5_utils import AnsibleF5Client
from ansible.module_utils.f5_utils import AnsibleF5Parameters
from ansible.module_utils.f5_utils import HAS_F5SDK
from ansible.module_utils.f5_utils import F5ModuleError
from ansible.module_utils.six import iteritems
from collections import defaultdict

try:
    from ansible.module_utils.f5_utils import iControlUnexpectedHTTPError
except ImportError:
    HAS_F5SDK = False


class Parameters(AnsibleF5Parameters):
    api_map = {
        'monitor': 'monitors'
    }

    api_attributes = [
        'monitor', 'description', 'address', 'fqdn',

        # Used for changing state
        #
        # user-enabled (enabled)
        # user-disabled (disabled)
        # user-disabled (offline)
        'session',

        # Used for changing state
        # user-down (offline)
        'state'
    ]

    returnables = [
        'monitor_type', 'quorum', 'monitors', 'description', 'fqdn', 'session', 'state'
    ]

    updatables = [
        'monitor_type', 'quorum', 'monitors', 'description', 'state'
    ]

    def __init__(self, params=None):
        self._values = defaultdict(lambda: None)
        self._values['__warnings'] = []
        if params:
            self.update(params=params)

    def update(self, params=None):
        if params:
            for k, v in iteritems(params):
                if self.api_map is not None and k in self.api_map:
                    map_key = self.api_map[k]
                else:
                    map_key = k

                # Handle weird API parameters like `dns.proxy.__iter__` by
                # using a map provided by the module developer
                class_attr = getattr(type(self), map_key, None)
                if isinstance(class_attr, property):
                    # There is a mapped value for the api_map key
                    if class_attr.fset is None:
                        # If the mapped value does not have
                        # an associated setter
                        self._values[map_key] = v
                    else:
                        # The mapped value has a setter
                        setattr(self, map_key, v)
                else:
                    # If the mapped value is not a @property
                    self._values[map_key] = v

    def to_return(self):
        result = {}
        try:
            for returnable in self.returnables:
                result[returnable] = getattr(self, returnable)
            result = self._filter_params(result)
            return result
        except Exception:
            return result

    def api_params(self):
        result = {}
        for api_attribute in self.api_attributes:
            if self.api_map is not None and api_attribute in self.api_map:
                result[api_attribute] = getattr(self, self.api_map[api_attribute])
            else:
                result[api_attribute] = getattr(self, api_attribute)
        result = self._filter_params(result)
        return result

    def _fqdn_name(self, value):
        if value is not None and not value.startswith('/'):
            return '/{0}/{1}'.format(self.partition, value)
        return value

    @property
    def monitors_list(self):
        if self._values['monitors'] is None:
            return []
        try:
            result = re.findall(r'/\w+/[^\s}]+', self._values['monitors'])
            return result
        except Exception:
            return self._values['monitors']

    @property
    def monitors(self):
        if self._values['monitors'] is None:
            return None
        monitors = [self._fqdn_name(x) for x in self.monitors_list]
        if self.monitor_type == 'm_of_n':
            monitors = ' '.join(monitors)
            result = 'min %s of { %s }' % (self.quorum, monitors)
        else:
            result = ' and '.join(monitors).strip()

        return result

    @property
    def quorum(self):
        if self.kind == 'tm:ltm:pool:poolstate':
            if self._values['monitors'] is None:
                return None
            pattern = r'min\s+(?P<quorum>\d+)\s+of'
            matches = re.search(pattern, self._values['monitors'])
            if matches:
                quorum = matches.group('quorum')
            else:
                quorum = None
        else:
            quorum = self._values['quorum']
        try:
            if quorum is None:
                return None
            return int(quorum)
        except ValueError:
            raise F5ModuleError(
                "The specified 'quorum' must be an integer."
            )

    @property
    def monitor_type(self):
        if self.kind == 'tm:ltm:node:nodestate':
            if self._values['monitors'] is None:
                return None
            pattern = r'min\s+\d+\s+of'
            matches = re.search(pattern, self._values['monitors'])
            if matches:
                return 'm_of_n'
            else:
                return 'and_list'
        else:
            if self._values['monitor_type'] is None:
                return None
            return self._values['monitor_type']

    @property
    def fqdn(self):
        if self._values['fqdn'] is None:
            return None
        result = dict(
            addressFamily='ipv4',
            autopopulate='disabled',
            downInterval=3600,
            tmName=self._values['fqdn']
        )
        return result


class Changes(Parameters):
    pass


class Difference(object):
    def __init__(self, want, have=None):
        self.want = want
        self.have = have

    def compare(self, param):
        try:
            result = getattr(self, param)
            return result
        except AttributeError:
            return self.__default(param)

    def __default(self, param):
        attr1 = getattr(self.want, param)
        try:
            attr2 = getattr(self.have, param)
            if attr1 != attr2:
                return attr1
        except AttributeError:
            return attr1

    @property
    def monitor_type(self):
        if self.want.monitor_type is None:
            self.want.update(dict(monitor_type=self.have.monitor_type))
        if self.want.quorum is None:
            self.want.update(dict(quorum=self.have.quorum))
        if self.want.monitor_type == 'm_of_n' and self.want.quorum is None:
            raise F5ModuleError(
                "Quorum value must be specified with monitor_type 'm_of_n'."
            )
        elif self.want.monitor_type == 'single':
            if len(self.want.monitors_list) > 1:
                raise F5ModuleError(
                    "When using a 'monitor_type' of 'single', only one monitor may be provided."
                )
            elif len(self.have.monitors_list) > 1 and len(self.want.monitors_list) == 0:
                # Handle instances where there already exists many monitors, and the
                # user runs the module again specifying that the monitor_type should be
                # changed to 'single'
                raise F5ModuleError(
                    "A single monitor must be specified if more than one monitor currently exists on your pool."
                )
            # Update to 'and_list' here because the above checks are all that need
            # to be done before we change the value back to what is expected by
            # BIG-IP.
            #
            # Remember that 'single' is nothing more than a fancy way of saying
            # "and_list plus some extra checks"
            self.want.update(dict(monitor_type='and_list'))
        if self.want.monitor_type != self.have.monitor_type:
            return self.want.monitor_type

    @property
    def monitors(self):
        if self.want.monitor_type is None:
            self.want.update(dict(monitor_type=self.have.monitor_type))
        if not self.want.monitors_list:
            self.want.monitors = self.have.monitors_list
        if not self.want.monitors and self.want.monitor_type is not None:
            raise F5ModuleError(
                "The 'monitors' parameter cannot be empty when 'monitor_type' parameter is specified"
            )
        if self.want.monitors != self.have.monitors:
            return self.want.monitors

    @property
    def state(self):
        result = None
        if self.want.state in ['present', 'enabled']:
            if self.have.session != 'user-enabled':
                result = dict(
                    session='user-enabled',
                    state='user-up',
                )
        elif self.want.state == 'disabled':
            if self.have.session != 'user-disabled' or self.have.state == 'user-down':
                result = dict(
                    session='user-disabled',
                    state='user-up'
                )
        elif self.want.state == 'offline':
            if self.have.state != 'user-down':
                result = dict(
                    session='user-disabled',
                    state='user-down'
                )
        return result


class ModuleManager(object):
    def __init__(self, client):
        self.client = client
        self.have = None
        self.want = Parameters(self.client.module.params)
        self.changes = Changes()

    def _set_changed_options(self):
        changed = {}
        for key in Parameters.returnables:
            if getattr(self.want, key) is not None:
                changed[key] = getattr(self.want, key)
        if changed:
            self.changes = Changes(changed)

    def _update_changed_options(self):
        diff = Difference(self.want, self.have)
        updatables = Parameters.updatables
        changed = dict()
        for k in updatables:
            change = diff.compare(k)
            if change is None:
                continue
            else:
                if isinstance(change, dict):
                    changed.update(change)
                else:
                    changed[k] = change
        if changed:
            self.changes = Changes(changed)
            return True
        return False

    def _announce_deprecations(self):
        warnings = []
        if self.want:
            warnings += self.want._values.get('__warnings', [])
        if self.have:
            warnings += self.have._values.get('__warnings', [])
        for warning in warnings:
            self.client.module.deprecate(
                msg=warning['msg'],
                version=warning['version']
            )

    def exec_module(self):
        changed = False
        result = dict()
        state = self.want.state

        try:
            if state in ['present', 'enabled', 'disabled', 'offline']:
                changed = self.present()
            elif state == "absent":
                changed = self.absent()
        except IOError as e:
            raise F5ModuleError(str(e))

        changes = self.changes.to_return()
        result.update(**changes)
        result.update(dict(changed=changed))
        self._announce_deprecations()
        return result

    def present(self):
        if self.exists():
            return self.update()
        else:
            return self.create()

    def _check_required_creation_vars(self):
        if self.want.address is None and self.want.fqdn is None:
            raise F5ModuleError(
                "At least one of 'address' or 'fqdn' is required when creating a node"
            )
        elif self.want.address is not None and self.want.fqdn is not None:
            raise F5ModuleError(
                "Only one of 'address' or 'fqdn' can be provided when creating a node"
            )
        elif self.want.fqdn is not None:
            self.want.update(dict(address='any6'))

    def _munge_creation_state_for_device(self):
        # Modifying the state before sending to BIG-IP
        #
        # The 'state' must be set to None to exclude the values (accepted by this
        # module) from being sent to the BIG-IP because for specific Ansible states,
        # BIG-IP will consider those state values invalid.
        if self.want.state in ['present', 'enabled']:
            self.want.update(dict(
                session='user-enabled',
                state='user-up',
            ))
        elif self.want.state in 'disabled':
            self.want.update(dict(
                session='user-disabled',
                state='user-up'
            ))
        else:
            # State 'offline'
            # Offline state will result in the monitors stopping for the node
            self.want.update(dict(
                session='user-disabled',

                # only a valid state can be specified. The module's value is "offline",
                # but this is an invalid value for the BIG-IP. Therefore set it to user-down.
                state='user-down',

                # Even user-down wil not work when _creating_ a node, so we register another
                # want value (that is not sent to the API). This is checked for later to
                # determine if we have to PATCH the node to be offline.
                is_offline=True
            ))

    def create(self):
        self._check_required_creation_vars()
        self._munge_creation_state_for_device()
        self._set_changed_options()
        if self.client.check_mode:
            return True
        self.create_on_device()
        if not self.exists():
            raise F5ModuleError("Failed to create the node")
        # It appears that you cannot create a node in an 'offline' state, so instead
        # we update its status to offline after we create it.
        if self.want.is_offline:
            self.update_node_offline_on_device()
        return True

    def should_update(self):
        result = self._update_changed_options()
        if result:
            return True
        return False

    def update(self):
        self.have = self.read_current_from_device()
        if not self.should_update():
            return False
        if self.client.check_mode:
            return True
        self.update_on_device()
        if self.want.state == 'offline':
            self.update_node_offline_on_device()
        return True

    def absent(self):
        if self.exists():
            return self.remove()
        return False

    def remove(self):
        if self.client.check_mode:
            return True
        self.remove_from_device()
        if self.exists():
            raise F5ModuleError("Failed to delete the node.")
        return True

    def read_current_from_device(self):
        resource = self.client.api.tm.ltm.nodes.node.load(
            name=self.want.name,
            partition=self.want.partition
        )
        result = resource.attrs
        return Parameters(result)

    def exists(self):
        result = self.client.api.tm.ltm.nodes.node.exists(
            name=self.want.name,
            partition=self.want.partition
        )
        return result

    def update_node_offline_on_device(self):
        params = dict(
            session="user-disabled",
            state="user-down"
        )
        result = self.client.api.tm.ltm.nodes.node.load(
            name=self.want.name,
            partition=self.want.partition
        )
        result.modify(**params)

    def update_on_device(self):
        params = self.changes.api_params()
        result = self.client.api.tm.ltm.nodes.node.load(
            name=self.want.name,
            partition=self.want.partition
        )
        result.modify(**params)

    def create_on_device(self):
        params = self.want.api_params()
        resource = self.client.api.tm.ltm.nodes.node.create(
            name=self.want.name,
            partition=self.want.partition,
            **params
        )
        self._wait_for_fqdn_checks(resource)

    def _wait_for_fqdn_checks(self, resource):
        while True:
            if resource.state == 'fqdn-checking':
                resource.refresh()
                time.sleep(1)
            else:
                break

    def remove_from_device(self):
        result = self.client.api.tm.ltm.nodes.node.load(
            name=self.want.name,
            partition=self.want.partition
        )
        if result:
            result.delete()


class ArgumentSpec(object):
    def __init__(self):
        self.supports_check_mode = True
        self.argument_spec = dict(
            name=dict(required=True),
            address=dict(
                aliases=['host', 'ip']
            ),
            fqdn=dict(
                aliases=['hostname']
            ),
            description=dict(),
            monitor_type=dict(
                choices=[
                    'and_list', 'm_of_n', 'single'
                ]
            ),
            quorum=dict(type='int'),
            monitors=dict(type='list'),
            state=dict(
                choices=['absent', 'present', 'enabled', 'disabled', 'offline'],
                default='present'
            )
        )
        self.f5_product_name = 'bigip'


def main():
    spec = ArgumentSpec()

    client = AnsibleF5Client(
        argument_spec=spec.argument_spec,
        supports_check_mode=spec.supports_check_mode,
        f5_product_name=spec.f5_product_name
    )
    try:
        if not HAS_F5SDK:
            raise F5ModuleError("The python f5-sdk module is required")

        if not HAS_NETADDR:
            raise F5ModuleError("The python netaddr module is required")

        mm = ModuleManager(client)
        results = mm.exec_module()
        client.module.exit_json(**results)
    except F5ModuleError as e:
        client.module.fail_json(msg=str(e))


if __name__ == '__main__':
    main()
