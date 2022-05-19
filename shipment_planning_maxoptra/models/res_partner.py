# Copyright 2022 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models

from ..const import MAXOPTRA_ADDRESS_FORMAT


class ResPartner(models.Model):

    _inherit = "res.partner"

    maxoptra_driver_name = fields.Char(
        string="Driver External ID",
        help="External ID of Driver in Maxoptra, used to target the right "
        "partner to set on Batch pickings after import.",
    )

    partner_key = fields.Text(string="Key")

    _sql_constraints = [
        (
            "partner_key_uniq",
            "unique(partner_key)",
            "partner key must be unique!",
        ),
    ]

    def _get_maxoptra_address(self):
        self.ensure_one()
        args = {
            "state_code": self.state_id.code or "",
            "country_name": self._get_country_name(),
        }
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ""
        # TODO: Add possibility to format address for MaxOptra on res.country?
        # TODO: Improve to allow automatic address recognition in Maxoptra
        return MAXOPTRA_ADDRESS_FORMAT % args
