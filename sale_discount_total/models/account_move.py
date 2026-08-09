# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Raneesha MK(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#############################################################################
from odoo import api, fields, models


class AccountInvoice(models.Model):
    """Add total-discount controls without replacing Odoo accounting core."""

    _inherit = "account.move"

    discount_type = fields.Selection(
        [('percent', 'Percentage'), ('amount', 'Amount')],
        string='Discount type',
        default='percent',
        help="Type of discount.",
    )
    discount_rate = fields.Float(
        'Discount Rate', digits=(16, 2), help="Give the discount rate."
    )
    amount_discount = fields.Monetary(
        string='Discount',
        store=True,
        compute='_compute_amount_discount',
        readonly=True,
        help="Give the amount to be discounted.",
    )

    @api.depends(
        'discount_type',
        'discount_rate',
        'invoice_line_ids.quantity',
        'invoice_line_ids.price_unit',
        'invoice_line_ids.discount',
    )
    def _compute_amount_discount(self):
        """Compute only this module's field.

        Odoo 19 owns ``account.move._compute_amount`` and its payment-state,
        reconciliation, residual and multi-currency semantics. Replacing that
        method with an older copy caused accounting behavior to drift from the
        native core. This method deliberately stays scoped to the custom
        discount amount.
        """
        for move in self:
            if move.discount_type == 'amount':
                move.amount_discount = move.discount_rate
                continue
            move.amount_discount = sum(
                line.quantity * line.price_unit * line.discount / 100.0
                for line in move.invoice_line_ids
                if line.display_type == 'product'
            )

    @api.onchange('discount_type', 'discount_rate', 'invoice_line_ids')
    def _supply_rate(self):
        """Apply the requested total discount to invoice line percentages."""
        for inv in self:
            if inv.discount_type == 'percent':
                for line in inv.invoice_line_ids:
                    if line.display_type == 'product':
                        line.discount = inv.discount_rate
                        line._compute_totals()
            else:
                total = sum(
                    line.quantity * line.price_unit
                    for line in inv.invoice_line_ids
                    if line.display_type == 'product'
                )
                discount = (
                    (inv.discount_rate / total) * 100.0
                    if inv.discount_rate and total
                    else 0.0
                )
                for line in inv.invoice_line_ids:
                    if line.display_type == 'product':
                        line.discount = discount
                        line._compute_totals()
            inv._compute_tax_totals()

    def button_dummy(self):
        """Refresh line discounts using the module's onchange logic."""
        self._supply_rate()
        return True


class AccountInvoiceLine(models.Model):
    """Add a line-level discount percentage used by total-discount logic."""

    _inherit = "account.move.line"

    discount = fields.Float(
        string='Discount (%)',
        digits=(16, 20),
        default=0.0,
        help="Give the discount needed",
    )
