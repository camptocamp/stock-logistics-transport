# Copyright 2022 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..const import MAXOPTRA_ADDRESS_FORMAT


class ResPartner(models.Model):

    _inherit = "res.partner"

    maxoptra_driver_name = fields.Char(
        string="Driver External ID",
        help="External ID of Driver in Maxoptra, used to target the right "
        "partner to set on Batch pickings after import.",
    )

    maxoptra_partner_key = fields.Text(string="Maxoptra Key")

    @api.constrains("maxoptra_partner_key")
    def _check_maxoptra_partner_key(self):
        """ Check that the maxoptra_partner_key is unique """
        for record in self:
            existing_partners_ids = (
                self.env["res.partner"].search(
                    [("maxoptra_partner_key", "=", record.maxoptra_partner_key)]
                )
                - record
            )
            if existing_partners_ids:
                raise ValidationError(
                    _(
                        "The Maxoptra partner key(%s) should be unique. Try another value.",
                        record.maxoptra_partner_key,
                    )
                )

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
