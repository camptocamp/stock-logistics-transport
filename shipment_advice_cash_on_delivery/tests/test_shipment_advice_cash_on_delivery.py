# Copyright 2024 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import Command

from odoo.addons.queue_job.tests.common import trap_jobs
from odoo.addons.shipment_advice.tests.common import Common


class TestShipmentAdviceCashOnDelivery(Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product COD",
                "type": "product",
                "weight": 0.1,
                "uom_id": cls.uom_kg.id,
                "uom_po_id": cls.uom_kg.id,
            }
        )
        cls.warehouse = cls.env.ref("stock.warehouse0")

        cls.pay_terms_immediate = cls.env.ref("account.account_payment_term_immediate")
        cls.pay_terms_cash_on_delivery = cls.env["account.payment.term"].create(
            {
                "name": "Cash on delivery",
                "cash_on_delivery": True,
                "line_ids": [Command.create({"value": "balance", "value_amount": 0})],
            }
        )
        cls.partner_a = cls.env["res.partner"].create(
            {"name": "partner_a", "invoicing_mode": "at_shipping"}
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "partner_b", "invoicing_mode": "at_shipping"}
        )
        cls.company = cls.env.user.company_id
        cls.default_pricelist = (
            cls.env["product.pricelist"]
            .with_company(cls.company)
            .create(
                {
                    "name": "default_pricelist",
                    "currency_id": cls.company.currency_id.id,
                }
            )
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.warehouse.lot_stock_id, 3
        )
        cls.shipment_advice_out_1 = cls.env["shipment.advice"].create(
            {"shipment_type": "outgoing"}
        )
        cls.shipment_advice_out_2 = cls.env["shipment.advice"].create(
            {"shipment_type": "outgoing"}
        )

    def _create_and_process_sale_order(self, dict_val):
        # Create and confirm sale order
        so = self.env["sale.order"].create(dict_val)
        so.action_confirm()
        pick = so.picking_ids

        # Process shipment advice & picking
        shipment_advice = self.env["shipment.advice"].create(
            {"shipment_type": "outgoing"}
        )
        self._plan_records_in_shipment(shipment_advice, pick)
        self._in_progress_shipment_advice(shipment_advice)
        wiz = self._load_records_in_shipment(shipment_advice, pick)
        self.assertEqual(wiz.picking_ids, pick)
        self.assertFalse(wiz.move_line_ids)
        pick.move_ids.write({"quantity_done": 1})
        with trap_jobs() as trap:
            pick._action_done()
            trap.assert_enqueued_job(
                pick._invoicing_at_shipping,
            )
            trap.perform_enqueued_jobs()
        pick._invoicing_at_shipping()
        shipment_advice.action_done()
        self.assertEqual(shipment_advice.state, "done")

        return pick, shipment_advice

    def test01(self):
        """
        Create 1 so for partner_a with payment terms having cash on delivery.

        create 1 so for partner_b with payment terms not having cash on delivery
        Validate the pickings of each so

        the picking of so partner_a has a cash on delivery invoice for partner_a
        the picking of so partner_b doesn't have a cash on delivery invoice for
        partner_b
        """

        pick1, shipment1 = self._create_and_process_sale_order(
            {
                "partner_id": self.partner_a.id,
                "partner_invoice_id": self.partner_a.id,
                "partner_shipping_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "product_uom": self.product.uom_id.id,
                            "price_unit": self.product.list_price,
                        },
                    ),
                ],
                "pricelist_id": self.default_pricelist.id,
                "picking_policy": "direct",
                "payment_term_id": self.pay_terms_cash_on_delivery.id,
            }
        )

        pick2, dummy = self._create_and_process_sale_order(
            {
                "partner_id": self.partner_b.id,
                "partner_invoice_id": self.partner_b.id,
                "partner_shipping_id": self.partner_b.id,
                "order_line": [
                    Command.create(
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "product_uom": self.product.uom_id.id,
                            "price_unit": self.product.list_price,
                        },
                    ),
                ],
                "pricelist_id": self.default_pricelist.id,
                "picking_policy": "direct",
                "payment_term_id": self.pay_terms_immediate.id,
            }
        )

        # check that pick1 has a cash_on_delivery invoice for partner_a
        self.assertEqual(len(pick1.cash_on_delivery_invoice_ids), 1)
        cod_invoice = pick1.cash_on_delivery_invoice_ids[0]
        self.assertEqual(cod_invoice.invoice_partner_display_name, self.partner_a.name)
        action = shipment1.with_context(
            discard_logo_check=True
        ).print_cash_on_delivery_invoices()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_name"), "account.report_invoice")
        self.assertEqual(action.get("report_type"), "qweb-pdf")
        self.assertEqual(
            action.get("context").get("active_ids"),
            pick1.cash_on_delivery_invoice_ids.ids,
        )

        # check that pick2 doesn't have any cash_on_delivery invoice
        self.assertEqual(len(pick2.cash_on_delivery_invoice_ids), 0)
