# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .sale_order_followup_line import (
    FOLLOWUP_LEVELS,
    LEVEL_LABELS,
    LEVEL_ORDER,
    LEVEL_TEMPLATE,
)

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    followup_sent_date = fields.Datetime(
        string="Devis envoyé le",
        copy=False, readonly=True, index=True,
        help="Renseigné automatiquement quand le devis passe à l'état "
             "« Devis envoyé ». Point de départ du calcul des relances.",
    )
    followup_block = fields.Boolean(
        string="Ne pas relancer", copy=False,
        help="Exclut ce devis des relances automatiques.",
    )
    followup_days_since_sent = fields.Integer(
        string="Jours depuis envoi",
        compute="_compute_followup_days_since_sent",
        search="_search_followup_days_since_sent",
    )
    followup_line_ids = fields.One2many(
        "sale.order.followup.line", "order_id", string="Relances",
    )
    followup_count = fields.Integer(
        string="Nombre de relances",
        compute="_compute_followup_stats", store=True,
    )
    followup_last_level = fields.Selection(
        FOLLOWUP_LEVELS, string="Dernière relance",
        compute="_compute_followup_stats", store=True,
    )
    followup_last_date = fields.Datetime(
        string="Dernière relance le",
        compute="_compute_followup_stats", store=True,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("followup_sent_date", "state")
    def _compute_followup_days_since_sent(self):
        now = fields.Datetime.now()
        for order in self:
            if order.state == "sent" and order.followup_sent_date:
                order.followup_days_since_sent = (now - order.followup_sent_date).days
            else:
                order.followup_days_since_sent = 0

    def _search_followup_days_since_sent(self, operator, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return [("id", "=", False)]
        # days >= value  <=>  followup_sent_date <= now - value days
        inverse = {">=": "<=", ">": "<", "<=": ">=", "<": ">", "=": "=", "!=": "!="}
        if operator not in inverse:
            return [("id", "=", False)]
        threshold = fields.Datetime.now() - relativedelta(days=value)
        return ["&", ("followup_sent_date", "!=", False),
                ("followup_sent_date", inverse[operator], threshold)]

    @api.depends(
        "followup_line_ids.level",
        "followup_line_ids.create_date",
        "followup_sent_date",
    )
    def _compute_followup_stats(self):
        for order in self:
            lines = order._followup_current_lines().sorted(
                key=lambda l: (l.create_date or fields.Datetime.now(), l.id or 0)
            )
            order.followup_count = len(lines)
            newest = lines[-1:]
            order.followup_last_level = newest.level if newest else False
            order.followup_last_date = newest.create_date if newest else False

    # ------------------------------------------------------------------
    # Override — stamp / reset the "sent" date, nothing else
    # ------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "sent":
            todo = self.filtered(lambda o: not o.followup_sent_date)
            if todo:
                super(SaleOrder, todo).write(
                    {"followup_sent_date": fields.Datetime.now()}
                )
        elif vals.get("state") == "draft":
            dated = self.filtered("followup_sent_date")
            if dated:
                super(SaleOrder, dated).write({"followup_sent_date": False})
        return res

    # ------------------------------------------------------------------
    # Follow-up engine
    # ------------------------------------------------------------------
    @api.model
    def _followup_get_config(self):
        icp = self.env["ir.config_parameter"].sudo()

        def _int(key, default):
            try:
                return int(icp.get_param(key) or default)
            except (TypeError, ValueError):
                return default

        thresholds = {
            "reminder": _int("sale_quote_followup.reminder_days", 3),
            "firm": _int("sale_quote_followup.firm_days", 7),
            "last": _int("sale_quote_followup.last_days", 14),
        }
        channel = icp.get_param("sale_quote_followup.channel") or "email"
        if channel not in ("email", "activity", "both"):
            channel = "email"
        return thresholds, channel, _int("sale_quote_followup.activity_user_id", 0)

    def _followup_current_lines(self):
        """Relances belonging to the current send cycle (after followup_sent_date)."""
        self.ensure_one()
        lines = self.followup_line_ids
        if self.followup_sent_date:
            lines = lines.filtered(
                lambda l: l.create_date and l.create_date >= self.followup_sent_date
            )
        return lines

    def _followup_due_level(self, days, thresholds):
        """Firmest tier reached by an order aged ``days`` days (or False)."""
        due = False
        for level in LEVEL_ORDER:
            if days >= thresholds[level]:
                due = level
        return due

    def _followup_get_replied_ids(self):
        """Ids of orders that received a customer email since they were sent.

        One prefetch + one ``mail.message`` query, whatever the number of
        orders (no N+1).
        """
        if not self:
            return set()
        self.fetch(["followup_sent_date", "partner_id"])
        sent = {o.id: o.followup_sent_date for o in self}
        allowed = {
            o.id: {o.partner_id.id, o.partner_id.commercial_partner_id.id}
            for o in self
        }
        dates = [d for d in sent.values() if d]
        if not dates:
            return set()

        messages = self.env["mail.message"].sudo().search_fetch(
            [
                ("model", "=", "sale.order"),
                ("res_id", "in", self.ids),
                ("message_type", "=", "email"),
                ("author_id", "!=", False),
                ("date", ">=", min(dates)),
            ],
            ["res_id", "author_id", "date"],
        )
        replied = set()
        for msg in messages:
            start = sent.get(msg.res_id)
            if start and msg.date and msg.date >= start \
                    and msg.author_id.id in allowed.get(msg.res_id, ()):
                replied.add(msg.res_id)
        return replied

    def _followup_send_one(self, level, days, channel, activity_user_id, manual):
        """Send one relance for ``self`` and return the history-line values."""
        self.ensure_one()
        template = False
        if channel in ("email", "both"):
            template = self.env.ref(LEVEL_TEMPLATE[level], raise_if_not_found=False)
            if template:
                template.send_mail(
                    self.id,
                    email_layout_xmlid="mail.mail_notification_light",
                    force_send=False,
                )
            else:  # pragma: no cover
                _logger.warning(
                    "sale_quote_followup: modèle d'email %s introuvable",
                    LEVEL_TEMPLATE[level],
                )

        activity = False
        if channel in ("activity", "both"):
            responsible = self.env["res.users"].browse(activity_user_id).exists() \
                if activity_user_id else self.env["res.users"]
            responsible = responsible or self.user_id or self.env.user
            activity = self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Relance devis %s — %s", self.name, LEVEL_LABELS[level]),
                note=_("Devis envoyé il y a %s jour(s) sans réponse du client.", days),
                user_id=responsible.id,
            )

        self.message_post(
            body=_(
                "Relance « %(label)s » enregistrée (%(days)s jour(s) depuis l'envoi).",
                label=LEVEL_LABELS[level], days=days,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "order_id": self.id,
            "level": level,
            "days_since_sent": days,
            "channel": channel,
            "mail_template_id": template.id if template else False,
            "activity_id": activity.id if activity else False,
            "user_id": self.user_id.id or self.env.uid,
            "manual": manual,
            "note": _("Déclenchée manuellement") if manual else False,
        }

    def _followup_process(self, orders, force=False):
        """Shared engine for the cron (age-based) and the button (force=next tier).

        Every write is batched: a single ``create`` for all history lines.
        """
        if not orders:
            return 0
        thresholds, channel, activity_user_id = self._followup_get_config()
        now = fields.Datetime.now()
        # A manual click is an explicit intent: don't second-guess it.
        replied_ids = set() if force else orders._followup_get_replied_ids()

        line_vals = []
        for order in orders:
            if order.id in replied_ids or not order.followup_sent_date:
                continue
            days = (now - order.followup_sent_date).days
            done = set(order._followup_current_lines().mapped("level"))
            if force:
                level = next((lv for lv in LEVEL_ORDER if lv not in done), False)
            else:
                level = order._followup_due_level(days, thresholds)
                if level in done:
                    level = False
            if not level:
                continue
            line_vals.append(
                order._followup_send_one(level, days, channel, activity_user_id, force)
            )

        if line_vals:
            self.env["sale.order.followup.line"].sudo().create(line_vals)
        return len(line_vals)

    @api.model
    def _cron_send_quotation_followups(self, limit=None):
        orders = self.search(
            [
                ("state", "=", "sent"),
                ("followup_sent_date", "!=", False),
                ("followup_block", "=", False),
            ],
            limit=limit,
        )
        count = self._followup_process(orders, force=False)
        _logger.info("sale_quote_followup: %s relance(s) envoyée(s)", count)
        return count

    # ------------------------------------------------------------------
    # UI actions
    # ------------------------------------------------------------------
    def action_followup_send_now(self):
        eligible = self.filtered(
            lambda o: o.state == "sent" and o.followup_sent_date and not o.followup_block
        )
        self._followup_process(eligible, force=True)
        return True

    def action_open_followup_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relances — %s", self.name),
            "res_model": "sale.order.followup.line",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
            "context": {"default_order_id": self.id, "create": False},
        }
