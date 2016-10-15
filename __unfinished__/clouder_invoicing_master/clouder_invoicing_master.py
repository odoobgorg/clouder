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

import xmlrpclib
from openerp import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    """
    Overrides clouder_invoicing definitions to add functionnality
    """
    _inherit = "account.invoice"

    @api.model
    def invoice_clouder_child(self, base, amount):
        """
        Request creation of a supplier invoice in the child clouder
        :param base - the child clouder base
        :param amount - the amount of the invoice
        """
        url = "http://{0}:{1}".\
            format(base.container_id.server_id.ip, base.odoo_port)
        conn = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(url))
        dbname = base.fullname.replace('-', '_')
        uid = conn.authenticate(
            dbname, base.admin_name, base.admin_password, {})
        model = xmlrpclib.ServerProxy('{}/xmlrpc/2/object'.format(url))

        return model.execute_kw(
            dbname,
            uid,
            base.admin_password,
            'account.invoice',
            'create_clouder_supplier_invoice',
            [amount],
            {}
        )

    @api.model
    def invoice_master_clouder_containers(self, containers):
        # Gathering invoice data from containers
        invoice_data = containers.get_invoicing_data()

        # Processing bases only,
        # since there is no container-based invoicing on clouder
        for base_data in invoice_data['invoice_base_data']:
            # TODO: create a real invoice
            _logger.info(
                '\nINVOICING BASE {0} FOR {1}\n'.format(base_data['id'],
                                                        base_data['amount']))

            # Updating date for base
            base = self.env['clouder.base'].search(
                [('id', '=', base_data['id'])])[0]
            base.write({'last_invoiced': fields.Date.today()})

            # Making a supplier invoice in child clouder instance
            self.invoice_clouder_child(base, base_data['amount'])

    @api.model
    def clouder_invoicing(self):
        """
        Invoice containers
        """
        clouder_app_ids = [
            self.env.ref('clouder_template_odoo.app_odoo_clouder').id,
            self.env.ref('clouder_template_odoo.app_odoo_clouder_data').id,
            self.env.ref('clouder_template_odoo.app_odoo_clouder_files').id,
            self.env.ref('clouder_template_odoo.app_odoo_clouder_exec').id,
            self.env.ref('clouder_template_odoo.app_odoo_clouder_ssh').id
        ]

        # Invoicing all non-clouder containers
        containers = self.env['clouder.container'].search(
            [('application_id', 'not in', clouder_app_ids)])
        self.invoice_containers(containers)

        # Invoicing all clouder containers
        clouder_containers = self.env['clouder.container'].search(
            [('application_id', 'in', clouder_app_ids)])
        self.invoice_master_clouder_containers(clouder_containers)
