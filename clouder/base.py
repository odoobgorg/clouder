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

from openerp import models, fields, api
import re

from datetime import datetime, timedelta
from . import model

import logging
_logger = logging.getLogger(__name__)


class ClouderDomain(models.Model):
    """
    Define the domain object, which represent all domains which can be linked
    to the bases hosted in this clouder.
    """

    _name = 'clouder.domain'
    _inherit = ['clouder.model']

    name = fields.Char('Domain name', required=True)
    organisation = fields.Char('Organisation', required=True)
    dns_id = fields.Many2one('clouder.container', 'DNS Server', required=False)
    cert_key = fields.Text('Wildcard Cert Key')
    cert_cert = fields.Text('Wildcart Cert')
    public = fields.Boolean('Public?')
    partner_id = fields.Many2one(
        'res.partner', 'Manager',
        default=lambda self: self.env.user.partner_id)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]

    @api.multi
    @api.constrains('name')
    def _check_name(self):
        """
        Check that the domain name does not contain any forbidden
        characters.
        """
        if not re.match(r"^[\w\d.-]*$", self.name):
            self.raise_error(
                "Name can only contains letters, digits - and dot"
            )

    @api.multi
    def write(self, vals):

        if 'dns_id' in vals:
            self.purge()

        super(ClouderDomain, self).write(vals)

        if 'dns_id' in vals:
            self.deploy()


class ClouderBase(models.Model):
    """
    Define the base object, which represent all websites hosted in this clouder
    with a specific url and a specific database.
    """

    _name = 'clouder.base'
    _inherit = ['clouder.model']

    name = fields.Char('Name', required=True)
    domain_id = fields.Many2one('clouder.domain', 'Domain name', required=True)
    environment_id = fields.Many2one('clouder.environment', 'Environment',
                                     required=True)
    title = fields.Char('Title', required=True)
    application_id = fields.Many2one('clouder.application', 'Application',
                                     required=True)
    container_id = fields.Many2one(
        'clouder.container', 'Container', required=True)
    admin_name = fields.Char('Admin name', required=True)
    admin_password = fields.Char(
        'Admin password', required=True,
        default=model.generate_random_password(20))
    admin_email = fields.Char('Admin email', required=True)
    poweruser_name = fields.Char('PowerUser name')
    poweruser_password = fields.Char(
        'PowerUser password',
        default=model.generate_random_password(12))
    poweruser_email = fields.Char('PowerUser email')
    build = fields.Selection(
        [('none', 'No action'), ('build', 'Build'), ('restore', 'Restore')],
        'Build?', default='build')
    ssl_only = fields.Boolean('SSL Only?', default=True)
    test = fields.Boolean('Test?')
    lang = fields.Selection(
        [('en_US', 'en_US'), ('fr_FR', 'fr_FR')],
        'Language', required=True, default='en_US')
    state = fields.Selection([
        ('installing', 'Installing'), ('enabled', 'Enabled'),
        ('blocked', 'Blocked'), ('removing', 'Removing')],
        'State', readonly=True)
    option_ids = fields.One2many('clouder.base.option', 'base_id', 'Options')
    link_ids = fields.One2many('clouder.base.link', 'base_id', 'Links')
    parent_id = fields.Many2one('clouder.base.child', 'Parent')
    child_ids = fields.One2many('clouder.base.child',
                                'base_id', 'Childs')
    metadata_ids = fields.One2many(
        'clouder.base.metadata', 'base_id', 'Metadata')
    time_between_save = fields.Integer('Minutes between each save')
    save_expiration = fields.Integer('Days before save expiration')
    date_next_save = fields.Datetime('Next save planned')
    save_comment = fields.Text('Save Comment')
    autosave = fields.Boolean('Save?', default=True)
    reset_each_day = fields.Boolean('Reset each day?')
    cert_key = fields.Text('Cert Key')
    cert_cert = fields.Text('Cert')
    cert_renewal_date = fields.Date('Cert renewal date')
    reset_id = fields.Many2one('clouder.base', 'Reset with this base')
    backup_ids = fields.Many2many(
        'clouder.container', 'clouder_base_backup_rel',
        'base_id', 'backup_id', 'Backup containers', required=True)
    public = fields.Boolean('Public?')

    @property
    def is_root(self):
        """
        Property returning is this base is the root of the domain or not.
        """
        if self.name == 'www':
            return True
        return False

    @property
    def fullname(self):
        """
        Property returning the full name of the base.
        """
        return self.application_id.fullcode + '-' + \
            self.fulldomain.replace('.', '-')

    @property
    def fullname_(self):
        """
        Property returning the full name of the base with all - replace by
        underscore (databases compatible names).
        """
        return self.fullname.replace('-', '_')

    @property
    def fulldomain(self):
        """
        Property returning the full url of the base.
        """
        if self.is_root:
            return self.domain_id.name
        return self.name + '.' + self.domain_id.name

    @property
    def databases(self):
        """
        Property returning all databases names used for this base, in a dict.
        """
        databases = {'single': self.fullname_}
        if self.application_id.type_id.multiple_databases:
            databases = {}
            for database in \
                    self.application_id.type_id.multiple_databases.split(','):
                databases[database] = self.fullname_ + '_' + database
        return databases

    @property
    def databases_comma(self):
        """
        Property returning all databases names used for this base,
        separated by a comma.
        """
        return ','.join([d for k, d in self.databases.iteritems()])

    @property
    def http_port(self):
        return self.container_id.childs['exec'] and \
            self.container_id.childs['exec'].ports['http']['hostport']

    @property
    def options(self):
        """
        Property returning a dictionary containing the value of all options
        for this base, even is they are not defined here.
        """
        options = {}
        for option in \
                self.application_id.type_id.option_ids:
            if option.type == 'base':
                options[option.name] = {'id': option.id, 'name': option.id,
                                        'value': option.default}
        for option in self.option_ids:
            options[option.name.name] = {'id': option.id,
                                         'name': option.name.id,
                                         'value': option.value}
        return options

    @property
    def links(self):
        """
        Property returning a dictionary containing the value of all links
        for this base.
        """
        links = {}
        for link in self.link_ids:
            links[link.name.name.code] = link
        return links

    _sql_constraints = [
        ('name_uniq', 'unique (name,domain_id)',
         'Name must be unique per domain !')
    ]

    @api.multi
    @api.constrains('name', 'admin_name', 'admin_email', 'poweruser_email')
    def _check_forbidden_chars_credentials(self):
        """
        Check that the base name and some other fields does not contain any
        forbidden characters.
        """
        if not re.match(r"^[\w\d-]*$", self.name):
            self.raise_error(
                "Name can only contains letters, digits and -",
            )
        if not re.match(r"^[\w\d_.@-]*$", self.admin_name):
            self.raise_error(
                "Admin name can only contains letters, digits and underscore",
            )
        if self.admin_email\
                and not re.match(r"^[\w\d_.@-]*$", self.admin_email):
            self.raise_error(
                "Admin email can only contains letters, "
                "digits, underscore, - and @"
            )
        if self.poweruser_email \
                and not re.match(r"^[\w\d_.@-]*$", self.poweruser_email):
            self.raise_error(
                "Poweruser email can only contains letters, "
                "digits, underscore, - and @"
            )

    @api.multi
    @api.constrains('container_id', 'application_id')
    def _check_application(self):
        """
        Check that the application of the base is the same than application
        of services.
        """
        if self.application_id.id != \
                self.container_id.application_id.id:
            self.raise_error(
                "The application of base must be the same "
                "than the application of the container."
            )

    @api.multi
    def onchange_application_id_vals(self, vals):
        """
        Update the options, links and some other fields when we change
        the application_id field.
        """
        if 'application_id' in vals and vals['application_id']:
            application = self.env['clouder.application'].browse(
                vals['application_id'])

            if 'admin_name' not in vals or not vals['admin_name']:
                vals['admin_name'] = application.admin_name \
                    and application.admin_name \
                    or self.email_sysadmin
            if 'admin_email' not in vals or not vals['admin_email']:
                vals['admin_email'] = application.admin_email \
                    and application.admin_email \
                    or self.email_sysadmin

            options = []
            # Getting sources for new options
            option_sources = {x.id: x for x in application.type_id.option_ids}
            sources_to_add = option_sources.keys()
            # Checking old options
            if 'option_ids' in vals:
                for option in vals['option_ids']:
                    # Standardizing for possible odoo x2m input
                    if isinstance(option, (list, tuple)):
                        option = {
                            'name': option[2].get('name', False),
                            'value': option[2].get('value', False)
                        }
                        # This case means we do not have an odoo recordset
                        # and need to load the link manually
                        if isinstance(option['name'], int):
                            option['name'] = \
                                self.env['clouder.application.type.option'].\
                                browse(option['name'])
                    else:
                        option = {
                            'name': getattr(option, 'name', False),
                            'value': getattr(option, 'value', False)
                        }
                    # Keeping the option if there is a match with the sources
                    if option['name'] and option['name'].id in option_sources:
                        option['source'] = option_sources[option['name'].id]

                        if option['source'].type == 'base' \
                                and option['source'].auto:
                            # Updating the default value
                            # if there is no current one set
                            options.append((0, 0, {
                                'name': option['source'].id,
                                'value':
                                    option['value'] or
                                    option['source'].get_default}))

                            # Removing the source id from those to add later
                            sources_to_add.remove(option['name'].id)

            # Adding missing option from sources
            for def_opt_key in sources_to_add:
                if option_sources[def_opt_key].type == 'base' \
                        and option_sources[def_opt_key].auto:
                    options.append((0, 0, {
                        'name': option_sources[def_opt_key].id,
                        'value': option_sources[def_opt_key].get_default
                    }))

            # Replacing old options
            vals['option_ids'] = options

            link_sources = {
                x.id: x for code, x in application.links.iteritems()}
            sources_to_add = link_sources.keys()
            links_to_process = []
            # Checking old links
            if 'link_ids' in vals:
                for link in vals['link_ids']:
                    # Standardizing for possible odoo x2m input
                    if isinstance(link, (list, tuple)):
                        link = {
                            'name': link[2].get('name', False),
                            'required': link[2].get('required', False),
                            'auto': link[2].get('auto', False),
                            'next': link[2].get('next', False)
                        }
                        # This case means we do not have an odoo recordset
                        # and need to load the link manually
                        if isinstance(link['name'], int):
                            link['name'] = \
                                self.env['clouder.application.link'].\
                                browse(link['name'])
                    else:
                        link = {
                            'name': getattr(link, 'name', False),
                            'required': getattr(link, 'required', False),
                            'auto': getattr(link, 'auto', False),
                            'next': getattr(link, 'next', False)
                        }
                    # Keeping the link if there is a match with the sources
                    if link['name'] and link['name'].id in link_sources:
                        link['source'] = link_sources[link['name'].id]
                        links_to_process.append(link)

                        # Remove used link from sources
                        sources_to_add.remove(link['name'].id)

            # Adding links from source
            for def_key_link in sources_to_add:
                link = {
                    'name': getattr(link_sources[def_key_link], 'name', False),
                    'required': getattr(
                        link_sources[def_key_link], 'required', False),
                    'auto': getattr(link_sources[def_key_link], 'auto', False),
                    'next': getattr(link_sources[def_key_link], 'next', False),
                    'source': link_sources[def_key_link]
                }
                links_to_process.append(link)

            # Running algorithm to determine new links
            links = []
            for link in links_to_process:
                if link['source'].base and link['source'].auto:
                    next_id = link['next']
                    if 'parent_id' in vals and vals['parent_id']:
                        parent = self.env['clouder.base.child'].browse(
                            vals['parent_id'])
                        for parent_link in parent.base_id.link_ids:
                            if link['source'].name.code == \
                                    parent_link.name.name.code \
                                    and parent_link.target:
                                next_id = parent_link.target.id
                    context = self.env.context
                    if not next_id and 'base_links' in context:
                        fullcode = link['source'].name.fullcode
                        if fullcode in context['base_links']:
                            next_id = context['base_links'][fullcode]
                    if not next_id:
                        next_id = link['source'].next.id
                    if not next_id:
                        target_ids = self.env['clouder.container'].search([
                            ('application_id.code', '=',
                             link['source'].name.code),
                            ('parent_id', '=', False)])
                        if target_ids:
                            next_id = target_ids[0].id
                    links.append((0, 0, {'name': link['source'].name.id,
                                         'required': link['required'],
                                         'auto': link['auto'],
                                         'target': next_id}))
            # Replacing old links
            vals['link_ids'] = links

            childs = []
            # Getting source for childs
            child_sources = {x.id: x for x in application.child_ids}
            sources_to_add = child_sources.keys()
            childs_to_process = []

            # Checking for old childs
            if 'child_ids' in vals:
                for child in vals['child_ids']:
                    # Standardizing for possible odoo x2m input
                    if isinstance(child, (list, tuple)):
                        child = {
                            'name': child[2].get('name', False),
                            'sequence': child[2].get('sequence', False)
                        }
                        # This case means we do not have an odoo recordset
                        # and need to load the link manually
                        if isinstance(child['name'], int):
                            child['name'] = self.env['clouder.application'].\
                                browse(child['name'])
                    else:
                        child = {
                            'name': getattr(child, 'name', False),
                            'sequence': getattr(child, 'sequence', False)
                        }
                    if child['name'] and child['name'].id in child_sources:
                        child['source'] = child_sources[child['name'].id]
                        childs_to_process.append(child)

                        # Removing from sources
                        sources_to_add.remove(child['name'].id)

            # Adding remaining childs from source
            for def_child_key in sources_to_add:
                child = {
                    'name': getattr(
                        child_sources[def_child_key], 'name', False),
                    'sequence': getattr(
                        child_sources[def_child_key], 'sequence', False),
                    'source': child_sources[def_child_key]
                }
                childs_to_process.append(child)

            # Processing new childs
            for child in childs_to_process:
                if child['source'].required and child['source'].base:
                    childs.append((0, 0, {
                        'name': child['source'].id,
                        'sequence':  child['sequence']}))

            # Replacing old childs
            vals['child_ids'] = childs

            # Processing Metadata
            metadata_vals = []
            metadata_sources = {
                x.id: x for x in application.metadata_ids
                if x.clouder_type == 'base'}
            sources_to_add = metadata_sources.keys()
            metadata_to_process = []
            if 'metadata_ids' in vals:
                for metadata in vals['metadata_ids']:
                    # Standardizing for possible odoo x2m input
                    if isinstance(metadata, (list, tuple)):
                        metadata = {
                            'name': metadata[2].get('name', False),
                            'value_data': metadata[2].get('value_data', False)
                        }
                        # This case means we do not have an odoo recordset
                        # and need to load the link manually
                        if isinstance(metadata['name'], int):
                            metadata['name'] = \
                                self.env['clouder.application']\
                                .browse(metadata['name'])
                    else:
                        metadata = {
                            'name': getattr(metadata, 'name', False),
                            'value_data': getattr(
                                metadata, 'value_data', False)
                        }
                    # Processing metadata and adding to list
                    if metadata['name'] \
                            and metadata['name'].id in metadata_sources:
                        metadata['source'] = \
                            metadata_sources[metadata['name'].id]
                        metadata['value_data'] = \
                            metadata['value_data'] \
                            or metadata['source'].default_value
                        metadata_to_process.append(metadata)

                        # Removing from sources
                        sources_to_add.remove(metadata['name'].id)

            # Adding remaining metadata from source
            for metadata_key in sources_to_add:
                metadata = {
                    'name': getattr(
                        metadata_sources[metadata_key], 'name', False),
                    'value_data': metadata_sources[metadata_key].default_value,
                    'source': metadata_sources[metadata_key]
                }
                metadata_to_process.append(metadata)

            # Processing new metadata
            for metadata in metadata_to_process:
                if metadata['source'].clouder_type == 'base':
                    metadata_vals.append((0, 0, {
                        'name': metadata['source'].id,
                        'value_data':  metadata['value_data']}))

            # Replacing old metadata
            vals['metadata_ids'] = metadata_vals

            if 'backup_ids' not in vals or not vals['backup_ids']:
                if application.base_backup_ids:
                    vals['backup_ids'] = [(6, 0, [
                        b.id for b in application.base_backup_ids])]
                else:
                    backups = self.env['clouder.container'].search([
                        ('application_id.type_id.name', '=', 'backup')])
                    if backups:
                        vals['backup_ids'] = [(6, 0, [backups[0].id])]

            vals['autosave'] = application.autosave

            vals['time_between_save'] = \
                application.base_time_between_save
            vals['save_expiration'] = \
                application.base_save_expiration

        return vals

    @api.multi
    @api.onchange('application_id')
    def onchange_application_id(self):
        vals = {
            'application_id': self.application_id.id,
            'container_id':
                self.application_id.next_container_id and
                self.application_id.next_container_id.id or False,
            'admin_name': self.admin_name,
            'admin_email': self.admin_email,
            'option_ids': self.option_ids,
            'link_ids': self.link_ids,
            'child_ids': self.child_ids,
            'metadata_ids': self.metadata_ids,
            'parent_id': self.parent_id and self.parent_id.id or False
            }
        vals = self.onchange_application_id_vals(vals)
        self.env['clouder.container.option'].search(
            [('container_id', '=', self.id)]).unlink()
        self.env['clouder.container.link'].search(
            [('container_id', '=', self.id)]).unlink()
        self.env['clouder.container.child'].search(
            [('container_id', '=', self.id)]).unlink()
        for key, value in vals.iteritems():
            setattr(self, key, value)

    @api.multi
    def control_priority(self):
        return self.container_id.check_priority_childs(self)

    @api.model
    def create(self, vals):
        """
        Override create method to create a container and a service if none
        are specified.

        :param vals: The values needed to create the record.
        """
        if ('container_id' not in vals) or (not vals['container_id']):
            application_obj = self.env['clouder.application']
            domain_obj = self.env['clouder.domain']
            container_obj = self.env['clouder.container']
            if 'application_id' not in vals or not vals['application_id']:
                self.raise_error(
                    "You need to specify the application of the base."
                )
            application = application_obj.browse(vals['application_id'])
            if not application.next_server_id:
                self.raise_error(
                    "You need to specify the next server in "
                    "application for the container autocreate."
                )
            if not application.default_image_id.version_ids:
                self.raise_error(
                    "No version for the image linked to the application, "
                    "abandoning container autocreate..."
                )
            if 'domain_id' not in vals or not vals['domain_id']:
                self.raise_error(
                    "You need to specify the domain of the base."
                )
            if 'environment_id' not in vals or not vals['environment_id']:
                self.raise_error(
                    "You need to specify the environment of the base."
                )
            domain = domain_obj.browse(vals['domain_id'])
            container_vals = {
                'name': vals['name'] + '-' +
                domain.name.replace('.', '-'),
                'server_id': application.next_server_id.id,
                'application_id': application.id,
                'image_id': application.default_image_id.id,
                'image_version_id':
                    application.default_image_id.version_ids[0].id,
                'environment_id': vals['environment_id'],
                'suffix': vals['name']
            }
            vals['container_id'] = container_obj.create(container_vals).id

        vals = self.onchange_application_id_vals(vals)

        return super(ClouderBase, self).create(vals)

    @api.multi
    def write(self, vals):
        """
        Override write method to move base if we change the service.

        :param vals: The values to update.
        """

        save = False
        if 'service_id' in vals:
            self = self.with_context(self.create_log('service change'))
            self = self.with_context(save_comment='Before service change')
            save = self.save_exec(no_enqueue=True, forcesave=True)
            self.purge()

        res = super(ClouderBase, self).write(vals)
        if save:
            save.service_id = vals['service_id']
            self = self.with_context(base_restoration=True)
            self.deploy()
            save.restore()
            self.end_log()
        if 'autosave' in vals and self.autosave != vals['autosave'] \
                or 'ssl_only' in vals and self.ssl_only != vals['ssl_only']:
            self.deploy_links()

        return res

    @api.multi
    def unlink(self):
        """
        Override unlink method to make a save before we delete a base.
        """
        self = self.with_context(save_comment='Before unlink')
        save = self.save_exec(no_enqueue=True)
        if self.parent_id:
            self.parent_id.save_id = save
        return super(ClouderBase, self).unlink()

    @api.multi
    def save(self):
        self.do('save', 'save_exec')

    @api.multi
    def save_exec(self, no_enqueue=False, forcesave=False):
        """
        Make a new save.
        """
        save = False
        now = datetime.now()

        if forcesave:
            self = self.with_context(forcesave=True)

        if no_enqueue:
            self = self.with_context(no_enqueue=True)

        if 'nosave' in self.env.context \
                or (not self.autosave and 'forcesave' not in self.env.context):
            self.log(
                'This base shall not be saved or the backup '
                'isnt configured in conf, skipping save base')
            return

        if no_enqueue:
            self = self.with_context(no_enqueue=True)

        for backup_server in self.backup_ids:
            save_vals = {
                'name': self.now_bup + '_' + self.fullname,
                'backup_id': backup_server.id,
                # 'repo_id': self.save_repository_id.id,
                'date_expiration': (now + timedelta(
                    days=self.save_expiration or
                    self.application_id.base_save_expiration)
                ).strftime("%Y-%m-%d"),
                'comment': 'save_comment' in self.env.context and
                           self.env.context['save_comment'] or
                           self.save_comment or 'Manual',
                'now_bup': self.now_bup,
                'container_id': self.container_id.id,
                'base_id': self.id,
            }
            save = self.env['clouder.save'].create(save_vals)
        date_next_save = (datetime.now() + timedelta(
            minutes=self.time_between_save or
            self.application_id.base_time_between_save)
        ).strftime("%Y-%m-%d %H:%M:%S")
        self.write({'save_comment': False, 'date_next_save': date_next_save})
        return save

    @api.multi
    def post_reset(self):
        """
        Hook which can be called by submodules to execute commands after we
        reset a base.
        """
        self.deploy_links()
        return

    @api.multi
    def reset_base(self):
        self = self.with_context(no_enqueue=True)
        self.do('reset_base', 'reset_base_exec')

    @api.multi
    def reset_base_exec(self):
        """
        Reset the base with the parent base.

        :param base_name: Specify another base name
        if the reset need to be done in a new base.

        :param service_id: Specify the service_id is the reset
        need to be done in another service.
        """
        base_name = False
        if 'reset_base_name' in self.env.context:
            base_name = self.env.context['reset_base_name']
        container = False
        if 'reset_container' in self.env.context:
            container = self.env.context['reset_container']
        base_reset_id = self.reset_id and self.reset_id or self
        if 'save_comment' not in self.env.context:
            self = self.with_context(save_comment='Reset base')
        save = base_reset_id.save_exec(no_enqueue=True, forcesave=True)
        self.with_context(nosave=True)
        vals = {'base_id': self.id, 'base_restore_to_name': self.name,
                'base_restore_to_domain_id': self.domain_id.id,
                'container_id': self.container_id.id, 'base_nosave': True}
        if base_name and container:
            vals = {'base_id': False, 'base_restore_to_name': base_name,
                    'base_restore_to_domain_id': self.domain_id.id,
                    'container_id': container.id, 'base_nosave': True}
        save.write(vals)
        base = save.restore()
        base.write({'reset_id': base_reset_id.id})
        base = base.with_context(
            base_reset_fullname_=base_reset_id.fullname_)
        base = base.with_context(
            container_reset_name=base_reset_id.container_id.name)
        base.deploy_salt()
        base.update_exec()
        base.post_reset()
        base.deploy_post()

    @api.multi
    def deploy_database(self):
        """
        Hook which can be called by submodules to execute commands when we
        want to create the database. If return False, the database will be
        created by default method.
        """
        return False

    @api.multi
    def deploy_build(self):
        """
        Hook which can be called by submodules to execute commands when we
        want to build the database.
        """
        return

    @api.multi
    def deploy_post_restore(self):
        """
        Hook which can be called by submodules to execute commands after we
        restore a database.
        """
        return

    @api.multi
    def deploy_create_poweruser(self):
        """
        Hook which can be called by submodules to execute commands when we
        want to create a poweruser.
        """
        return

    @api.multi
    def deploy_test(self):
        """
        Hook which can be called by submodules to execute commands when we
        want to deploy test datas.
        """
        return

    @api.multi
    def deploy_post(self):
        """
        Hook which can be called by submodules to execute commands after we
        deploy a base.
        """
        return

    @api.multi
    def deploy(self):
        """
        Deploy the base.
        """
        super(ClouderBase, self).deploy()

        if 'base_restoration' in self.env.context:
            return

        if self.child_ids:
            for child in self.child_ids:
                child.create_child_exec()
            return

        self.deploy_salt()

        self.deploy_database()
        self.log('Database created')

        if self.build == 'build':
            self.deploy_build()

        elif self.build == 'restore':
            # TODO restore from a selected save
            self.deploy_post_restore()

        if self.build != 'none':
            if self.poweruser_name and self.poweruser_email \
                    and self.admin_name != self.poweruser_name:
                self.deploy_create_poweruser()
            if self.test:
                self.deploy_test()

        self.deploy_post()

        # For shinken
        self = self.with_context(save_comment='First save')
        self.save_exec(no_enqueue=True)

        if self.application_id.update_bases:
            self.container_id.deploy_salt()
        for key, child in self.container_id.childs.iteritems():
            if child.application_id.update_bases:
                child.deploy_salt()

    @api.multi
    def purge_post(self):
        """
        Hook which can be called by submodules to execute commands after we
        purge a base.
        """
        return

    @api.multi
    def purge_database(self):
        """
        Purge the database.
        """
        return

    @api.multi
    def purge(self):
        """
        Purge the base.
        """
        self.purge_database()
        self.purge_post()
        self.purge_salt()

        if self.application_id.update_bases:
            self.container_id.deploy_salt()
        for key, child in self.container_id.childs.iteritems():
            if child.application_id.update_bases:
                child.deploy_salt()

        super(ClouderBase, self).purge()

    @api.multi
    def update(self):
        self = self.with_context(no_enqueue=True)
        self.do('update', 'update_exec')

    @api.multi
    def update_exec(self):
        """
        Hook which can be called by submodules to execute commands when we
        want to update a base.
        """
        self = self.with_context(save_comment='Before update')
        self.save_exec(no_enqueue=True)
        return

    @api.multi
    def generate_cert(self):
        self = self.with_context(no_enqueue=True)
        self.do('generate_cert', 'generate_cert_exec')

    @api.multi
    def generate_cert_exec(self):
        """
        Generate a new certificate
        """
        return True

    @api.multi
    def renew_cert(self):
        self = self.with_context(no_enqueue=True)
        self.do('renew_cert', 'renew_cert_exec')

    @api.multi
    def renew_cert_exec(self):
        """
        Renew a certificate
        """
        return True


class ClouderBaseOption(models.Model):
    """
    Define the base.option object, used to define custom values specific
    to a base.
    """
    _name = 'clouder.base.option'

    base_id = fields.Many2one('clouder.base', 'Base', ondelete="cascade",
                              required=True)
    name = fields.Many2one('clouder.application.type.option', 'Option',
                           required=True)
    value = fields.Text('Value')

    _sql_constraints = [
        ('name_uniq', 'unique(base_id,name)',
         'Option name must be unique per base!'),
    ]

    @api.multi
    @api.constrains('base_id')
    def _check_required(self):
        """
        Check that we specify a value for the option
        if this option is required.
        """
        if self.name.required and not self.value:
            self.raise_error(
                'You need to specify a value for the option "%s" '
                'for the base "%s".',
                self.name.name, self.base_id.name,
            )


class ClouderBaseLink(models.Model):
    """
    Define the base.link object, used to specify the applications linked
    to a base.
    """
    _name = 'clouder.base.link'
    _inherit = ['clouder.model']
    _autodeploy = False

    base_id = fields.Many2one('clouder.base', 'Base', ondelete="cascade",
                              required=True)
    name = fields.Many2one('clouder.application', 'Application',
                           required=True)
    target = fields.Many2one('clouder.container', 'Target')
    required = fields.Boolean('Required?')
    auto = fields.Boolean('Auto?')
    deployed = fields.Boolean('Deployed?', readonly=True)

    @property
    def target_base(self):
        """
        Property returning the first base of the target container.
        """
        return self.target.base_ids and \
            self.target.base_ids[0]

    @api.multi
    @api.constrains('base_id')
    def _check_required(self):
        """
        Check that we specify a value for the link
        if this link is required.
        """
        if self.required and not self.target:
            self.raise_error(
                'You need to specify a link to "%s" for the base "%s"',
                self.name.name, self.base_id.name,
            )

    @api.multi
    def deploy_link(self):
        """
        Hook which can be called by submodules to execute commands when we
        deploy a link.
        """
        self.purge_link()
        self.deployed = True
        return

    @api.multi
    def purge_link(self):
        """
        Hook which can be called by submodules to execute commands when we
        purge a link.
        """
        self.deployed = False
        return

    def control(self):
        """
        Make the control to know if we can launch the deploy/purge.
        """
        if not self.target:
            self.log(
                'The target isnt configured in the link, skipping deploy link')
            return False
        return True

    @api.multi
    def deploy_(self):
        self = self.with_context(no_enqueue=True)
        self.do(
            'deploy_link ' + self.name.name, 'deploy_exec', where=self.base_id)

    @api.multi
    def deploy_exec(self):
        """
        Control and call the hook to deploy the link.
        """
        self.control() and self.deploy_link()

    @api.multi
    def purge_(self):
        self = self.with_context(no_enqueue=True)
        self.do(
            'purge_link ' + self.name.name, 'purge_exec', where=self.base_id)

    @api.multi
    def purge_exec(self):
        """
        Control and call the hook to purge the link.
        """
        self.control() and self.purge_link()


class ClouderBaseChild(models.Model):
    """
    Define the base.child object, used to specify the applications linked
    to a container.
    """

    _name = 'clouder.base.child'
    _inherit = ['clouder.model']
    _autodeploy = False

    base_id = fields.Many2one(
        'clouder.base', 'Base', ondelete="cascade", required=True)
    name = fields.Many2one(
        'clouder.application', 'Application', required=True)
    sequence = fields.Integer('Sequence')
    domainname = fields.Char('Name')
    domain_id = fields.Many2one('clouder.domain', 'Domain')
    container_id = fields.Many2one(
        'clouder.container', 'Container')
    child_id = fields.Many2one(
        'clouder.container', 'Container')
    save_id = fields.Many2one('clouder.save',
                              'Restore this save on deployment')

    _order = 'sequence'

    @api.multi
    @api.constrains('child_id')
    def _check_child_id(self):
        if self.child_id and not self.child_id.parent_id == self:
            self.raise_error(
                "The child container is not correctly linked to the parent",
            )

    @api.multi
    def create_child(self):
        self = self.with_context(no_enqueue=True)
        self.do(
            'create_child ' + self.name.name,
            'create_child_exec', where=self.base_id)

    @api.multi
    def create_child_exec(self):
        self = self.with_context(autocreate=True)
        self.delete_child_exec()
        self.child_id = self.env['clouder.base'].create({
            'name':
                self.domainname or self.base_id.name + '-' + self.name.code,
            'domain_id':
                self.domainname and
                self.domain_id or self.base_id.domain_id.id,
            'parent_id': self.id,
            'environment_id': self.base_id.environment_id.id,
            'application_id': self.name.id,
            'container_id': self.container_id.id
        })
        if self.save_id:
            self.save_id.container_id = self.child_id.container_id
            self.save_id.base_id = self.child_id
            self.save_id.restore()

    @api.multi
    def delete_child(self):
        self.do(
            'delete_child ' + self.name.name,
            'delete_child_exec', where=self.base_id)

    @api.multi
    def delete_child_exec(self):
        self.child_id and self.child_id.unlink()


class ClouderBaseMetadata(models.Model):
    """
    Defines an object to store metadata linked to an application
    """

    _name = 'clouder.base.metadata'

    name = fields.Many2one(
        'clouder.application.metadata', 'Application Metadata',
        ondelete="cascade", required=True)
    base_id = fields.Many2one(
        'clouder.base', 'Base', ondelete="cascade", required=True)
    value_data = fields.Text('Value')

    _sql_constraints = [
        ('name_uniq', 'unique(name, base_id)',
         'Metadata must be unique per container!'),
    ]

    @property
    def value(self):
        """
        Property that returns the value formatted by type
        """
        def _missing_function():
            # If the function is missing, raise an exception
            self.raise_error(
                'Invalid function name "%s" for "clouder.base".',
                self.name.func_name,
            )

        # Computing the function if needed
        val_to_convert = self.value_data
        if self.name.is_function:
            val_to_convert = "{0}".format(getattr(
                self.base_id, self.name.func_name, _missing_function)())
            # If it is a function,
            # the text version should be updated for display
            self.with_context(skip_check=True).write({
                'value_data': val_to_convert})

        # Empty value
        if not val_to_convert:
            return False

        # value_type cases
        if self.name.value_type == 'int':
            return int(val_to_convert)
        elif self.name.value_type == 'float':
            return float(val_to_convert)
        # Defaults to char
        return str(val_to_convert)

    @api.multi
    @api.constrains('name')
    def _check_clouder_type(self):
        """
        Checks that the metadata is intended for containers
        """
        if self.name.clouder_type != 'base':
            self.raise_error(
                "This metadata is intended for %s only.",
                self.name.clouder_type,
            )

    @api.multi
    @api.constrains('name', 'value_data')
    def _check_object(self):
        """
        Checks if the data can be loaded properly
        """
        if 'skip_check' in self.env.context and self.env.context['skip_check']:
            return
        # call the value property to see if the metadata can be loaded properly
        try:
            self.value
        except ValueError:
            # User display
            self.raise_error(
                'Invalid value for type "%s": \n\t"%s"\n',
                self.name.value_type, self.value_data,
            )
