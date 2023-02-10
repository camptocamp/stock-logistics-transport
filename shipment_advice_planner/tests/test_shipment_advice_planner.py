# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import Form, TransactionCase


class TestShipmentAdvicePlanner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pickings = cls.env["stock.picking"].search([])
        cls.context = {
            "active_ids": cls.pickings.ids,
            "active_model": "stock.picking",
        }
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.warehouse2 = cls.env.ref("stock.stock_warehouse_shop0")
        cls.dock = cls.env.ref("shipment_advice.stock_dock_demo")

    def setUp(self):
        super().setUp()
        self.wizard_form = Form(
            self.env["shipment.advice.planner"].with_context(**self.context)
        )

    def test_shipment_advice_planner_multi_warehouse(self):
        self.assertEqual(len(self.pickings), 31)
        self.assertEqual(len(self.wizard_form.picking_to_plan_ids), 10)
        wizard = self.wizard_form.save()
        action = wizard.button_plan_shipments()
        shipments = self.env[action.get("res_model")].search(action.get("domain"))
        self.assertEqual(len(shipments), 2)
        self.assertEqual(len(shipments.mapped("warehouse_id")), 2)
        self.assertEqual(
            shipments.mapped("warehouse_id"), self.pickings.mapped("warehouse_id")
        )

    def test_shipment_advice_planner_one_warehouse(self):
        self.wizard_form.warehouse_id = self.warehouse
        self.assertEqual(len(self.wizard_form.picking_to_plan_ids), 9)
        wizard = self.wizard_form.save()
        action = wizard.button_plan_shipments()
        self.assertEqual(wizard.picking_to_plan_ids.warehouse_id, self.warehouse)
        shipment = self.env[action.get("res_model")].search(action.get("domain"))
        self.assertEqual(len(shipment), 1)
        self.assertEqual(shipment.warehouse_id, self.warehouse)

    def test_shipment_advice_planner_dock(self):
        with self.assertRaises(
            AssertionError, msg="dock is invisible if warehouse is unset"
        ):
            self.wizard_form.dock_id = self.dock
        self.wizard_form.warehouse_id = self.warehouse
        self.wizard_form.dock_id = self.dock
        wizard = self.wizard_form.save()
        action = wizard.button_plan_shipments()
        self.assertEqual(wizard.picking_to_plan_ids.warehouse_id, self.warehouse)
        shipment = self.env[action.get("res_model")].search(action.get("domain"))
        self.assertEqual(shipment.dock_id, self.dock)

    def test_check_warehouse(self):
        self.wizard_form.warehouse_id = self.warehouse
        with self.assertRaises(
            ValidationError, msg="transfers must belong to the selected warehouse"
        ):
            self.wizard_form.picking_to_plan_ids.add(
                self.pickings.filtered(
                    lambda p, w=self.warehouse2: p.warehouse_id == w
                )[0]
            )
        self.wizard_form.warehouse_id = self.warehouse2
        with self.assertRaises(
            ValidationError, msg="dock must belong to the selected warehouse"
        ):
            self.wizard_form.dock_id = self.dock

    def test_check_picking_to_plan(self):
        with self.assertRaises(
            ValidationError,
            msg="The transfers selected must be ready and of the delivery type",
        ):
            self.wizard_form.picking_to_plan_ids.add(
                self.pickings.filtered(
                    lambda p: not p.can_be_planned_in_shipment_advice
                )[0]
            )
