# -*- coding: utf-8 -*-
from odoo import fields, models

# Ordered from the softest to the firmest tone.
FOLLOWUP_LEVELS = [
    ("reminder", "J+3 · Rappel doux"),
    ("firm", "J+7 · Relance ferme"),
    ("last", "J+14 · Dernière relance"),
]
LEVEL_ORDER = [code for code, _label in FOLLOWUP_LEVELS]
LEVEL_LABELS = dict(FOLLOWUP_LEVELS)
LEVEL_TEMPLATE = {
    "reminder": "sale_quote_followup.mail_template_followup_reminder",
    "firm": "sale_quote_followup.mail_template_followup_firm",
    "last": "sale_quote_followup.mail_template_followup_last",
}


class SaleOrderFollowupLine(models.Model):
    _name = "sale.order.followup.line"
    _description = "Historique de relance de devis"
    _order = "create_date desc, id desc"

    order_id = fields.Many2one(
        "sale.order", string="Devis", required=True,
        ondelete="cascade", index=True,
    )
    partner_id = fields.Many2one(
        related="order_id.partner_id", store=True, string="Client", index=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id", store=True, index=True,
    )
    level = fields.Selection(FOLLOWUP_LEVELS, string="Niveau", required=True, index=True)
    days_since_sent = fields.Integer(
        string="Jours depuis envoi",
        help="Ancienneté du devis (en jours) au moment de la relance.",
    )
    channel = fields.Selection(
        [
            ("email", "Email"),
            ("activity", "Activité"),
            ("both", "Email + Activité"),
        ],
        string="Canal", default="email",
    )
    mail_template_id = fields.Many2one(
        "mail.template", string="Modèle d'email", ondelete="set null",
    )
    activity_id = fields.Many2one(
        "mail.activity", string="Activité", ondelete="set null",
    )
    user_id = fields.Many2one(
        "res.users", string="Commercial", default=lambda self: self.env.user,
    )
    manual = fields.Boolean(string="Déclenchée manuellement")
    note = fields.Char(string="Note")
