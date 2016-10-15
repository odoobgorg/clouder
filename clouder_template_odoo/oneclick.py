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

        for oneclick in self.oneclick_ids:
            if oneclick.code == 'odoo':
                self.oneclick_deploy_element('container', 'clouder9-all')
                self.oneclick_deploy_element(
                    'base', 'clouder9', code_container='clouder9-all-clouder9')

                self.oneclick_deploy_element(
                    'subservice', 'clouder9-all-clouder9')

    @api.multi
    def oneclick_purge_exec(self):

        container_obj = self.env['clouder.container']

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'clouder-test')]).unlink()

        container_obj.search([('environment_id', '=', self.environment_id.id),
                              ('suffix', '=', 'clouder9-all')]).unlink()

        super(ClouderServer, self).oneclick_purge_exec()
