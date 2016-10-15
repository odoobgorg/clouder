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


class ClouderServer(models.Model):
    """
    Add methods to manage the postgres specificities.
    """

    _inherit = 'clouder.server'

    @api.multi
    def oneclick_deploy_exec(self):

        super(ClouderServer, self).oneclick_deploy_exec()

        self.oneclick_deploy_element('container', 'backup-bup')

        bind = self.oneclick_deploy_element('container', 'bind', ports=[53])
        if not self.domain_id.dns_id:
            self.domain_id.write({'dns_id': bind.id})
            self.deploy_dns_exec()

        self.oneclick_deploy_element('container', 'postfix', ports=[25])

        self.oneclick_deploy_element('container', 'proxy', ports=[80, 443])

        container = self.oneclick_deploy_element('container', 'shinken')
        self.oneclick_deploy_element('base', 'shinken', container=container)

        container = self.oneclick_deploy_element('container', 'registry')
        self.oneclick_deploy_element('base', 'registry', container=container)

        self.oneclick_deploy_element('container', 'gitlab-all')
        self.oneclick_deploy_element(
            'base', 'gitlab', code_container='gitlab-all-gitlab')

        self.oneclick_deploy_element('container', 'gitlabci')

    @api.multi
    def oneclick_purge_exec(self):

        container_obj = self.env['clouder.container']

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'gitlabci')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'gitlab-all')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'registry')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'shinken')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'proxy')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'bind')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'postfix')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'backup-bup')]).unlink()

        super(ClouderServer, self).oneclick_purge_exec()
