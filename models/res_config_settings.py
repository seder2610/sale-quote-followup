# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    followup_reminder_days = fields.Integer(
        string="Rappel doux (jours)", default=3,
        config_parameter="sale_quote_followup.reminder_days",
        help="Ancienneté minimale du devis (J+n) avant l'envoi du rappel doux.",
    )
    followup_firm_days = fields.Integer(
        string="Relance ferme (jours)", default=7,
        config_parameter="sale_quote_followup.firm_days",
    )
    followup_last_days = fields.Integer(
        string="Dernière relance (jours)", default=14,
        config_parameter="sale_quote_followup.last_days",
    )
    followup_channel = fields.Selection(
        [
            ("email", "Email (mail.template)"),
            ("activity", "Activité assignée"),
            ("both", "Email + Activité"),
        ],
        string="Canal de relance", default="email",
        config_parameter="sale_quote_followup.channel",
    )
    followup_activity_user_id = fields.Many2one(
        "res.users", string="Responsable des activités",
        config_parameter="sale_quote_followup.activity_user_id",
        help="Utilisateur assigné aux activités de relance. "
             "Par défaut : le commercial du devis.",
    )
