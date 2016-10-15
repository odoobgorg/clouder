# -*- coding: utf-8 -*-
##############################################################################
#
# Author: Yannick Buron
# Copyright 2015, TODAY Clouder SASU
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License with Attribution
# clause as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License with
# Attribution clause along with this program. If not, see
# <http://www.gnu.org/licenses/>.
#
##############################################################################


from openerp import models, api
from openerp import modules
from datetime import datetime

import socket


class ClouderDomain(models.Model):
    """
    Add method to manage domain general configuration on the bind container.
    """

    _inherit = 'clouder.domain'

    @property
    def configfile(self):
        """
        Property returning the path to the domain config file
        in the bind container.
        """
        return'/etc/bind/db.' + self.name

    @api.multi
    def refresh_serial(self, domain=False):
        """
        Refresh the serial number in the config file
        """
        if self.dns_id and self.dns_id.application_id.type_id.name == 'bind':
            self.dns_id.execute([
                'sed', '-i',
                '"s/[0-9]* ;serial/' +
                datetime.now().strftime('%m%d%H%M%S') + ' ;serial/g"',
                self.configfile])
            self.dns_id.execute(['/etc/init.d/bind9 reload'])

            if domain:
                try:
                    socket.gethostbyname(domain)
                except:
                    self.dns_id.start()
                    pass

    @api.multi
    def deploy(self):
        """
        Configure the domain in the bind container, if configured.
        """
        if self.dns_id and self.dns_id.application_id.type_id.name == 'bind':
            self.dns_id.send(
                modules.get_module_path('clouder_template_bind') +
                '/res/bind.config', self.configfile)
            self.dns_id.execute([
                'sed', '-i', '"s/DOMAIN/' + self.name + '/g"',
                self.configfile])
            self.dns_id.execute([
                'sed', '-i',
                '"s/IP/' + self.dns_id.server_id.ip + '/g"',
                self.configfile])
            self.dns_id.execute([
                "echo 'zone \"" + self.name + "\" {' >> /etc/bind/named.conf"])
            self.dns_id.execute([
                'echo "type master;" >> /etc/bind/named.conf'])

            # Configure this only if the option is set
            if self.dns_id.options['slave_ip']['value']:
                self.dns_id.execute([
                    'echo "allow-transfer { ' +
                    self.dns_id.options['slave_ip']['value'] + ';};" '
                    '>> /etc/bind/named.conf'])

            self.dns_id.execute([
                "echo 'file \"/etc/bind/db." +
                self.name + "\";' >> /etc/bind/named.conf"])
            self.dns_id.execute(['echo "notify yes;" >> /etc/bind/named.conf'])
            self.dns_id.execute(['echo "};" >> /etc/bind/named.conf'])
            self.dns_id.execute([
                'echo "//END ' + self.name + '" >> /etc/bind/named.conf'])
            self.refresh_serial()

    @api.multi
    def purge(self):
        """
        Remove the domain config in the bind container.
        """
        if self.dns_id and self.dns_id.application_id.type_id.name == 'bind':
            self.dns_id.execute([
                'sed', '-i',
                r"'/zone\s\"" + self.name + r"\"/,/END\s" + self.name + "/d'",
                '/etc/bind/named.conf'])
            self.dns_id.execute(['rm', self.configfile])
            self.dns_id.execute(['/etc/init.d/bind9 reload'])


class ClouderBaseLink(models.Model):
    """
    Add method to manage links between bases and the bind container.
    """

    _inherit = 'clouder.base.link'

    @api.multi
    def deploy_bind_config(self, name):
        proxy_link = self.search([('base_id', '=', self.base_id.id), (
            'name.type_id.name', '=', 'proxy')])
        self.target.execute([
            'echo "' + name + ' IN A ' +
            (proxy_link and proxy_link[0].target.server_id.ip or
             self.base_id.container_id.server_id.ip) +
            '" >> ' + self.base_id.domain_id.configfile])
        self.base_id.domain_id.refresh_serial(self.base_id.fulldomain)

    @api.multi
    def purge_bind_config(self, name):
        self.target.execute([
            'sed', '-i',
            '"/' + name + r'\sIN\sA/d"',
            self.base_id.domain_id.configfile])
        self.base_id.domain_id.refresh_serial()

    @api.multi
    def deploy_link(self):
        """
        Add a new A record when we create a new base, and MX if the
        base has a postfix link.
        """
        super(ClouderBaseLink, self).deploy_link()
        if self.name.type_id.name == 'bind':
            if self.base_id.is_root:
                self.deploy_bind_config('@')
            self.deploy_bind_config(self.base_id.name)

            proxy_link = self.search([
                ('base_id', '=', self.base_id.id),
                ('name.type_id.name', '=', 'proxy')])
            if proxy_link and proxy_link.target and not self.base_id.cert_key \
                    and not self.base_id.cert_cert:
                self.base_id.generate_cert_exec()

    @api.multi
    def purge_link(self):
        """
        Remove base records on the bind container.
        """
        super(ClouderBaseLink, self).purge_link()
        if self.name.type_id.name == 'bind':
            if self.base_id.is_root:
                self.purge_bind_config('@')
            self.purge_bind_config(self.base_id.name)
