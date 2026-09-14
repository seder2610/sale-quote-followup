# -*- coding: utf-8 -*-
{
    "name": "Sale Quotation Follow-up",
    "version": "18.0.1.0.0",
    "summary": "Relances automatiques et progressives des devis envoyes (J+3, J+7, J+14)",
    "description": "Relance automatique des devis restes sans reponse : cron quotidien, "
                   "champ Jours depuis envoi, filtre En attente de relance, relances J+3 / "
                   "J+7 / J+14 par email ou activite, et historique sur le devis.",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "author": "Sedera Andriamanga",
    "website": "https://github.com/seder2610",
    "depends": ["sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "data/ir_cron.xml",
        "views/sale_order_followup_line_views.xml",
        "views/sale_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [
        "demo/sale_quote_followup_demo.xml",
    ],
    "application": False,
    "installable": True,
}
