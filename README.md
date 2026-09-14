# Sale Quotation Follow-up (`sale_quote_followup`)

Relance automatique et **progressive** des devis (`sale.order`) restés à l'état
**« Devis envoyé »** sans réponse du client.

| | |
|---|---|
| Version | `18.0.1.0.0` |
| Dépend de | `sale_management` |
| Licence | LGPL-3 |

---

## Fonctionnalités

- **Cron quotidien** « Devis : relances automatiques progressives » qui scanne les
  devis à l'état `sent`, envoyés depuis plus de *N* jours et sans réponse.
- **Champ calculé « Jours depuis envoi »** (`followup_days_since_sent`), affiché dans
  la liste des devis et sur le formulaire, avec code couleur (orange ≥ J+7, rouge ≥ J+14).
- **Filtre « En attente de relance »** dans la vue liste des devis (+ « Sans relance
  depuis J+7 », « Relance envoyée », « Relance désactivée » et un regroupement
  « Niveau de relance »).
- **Relance à ton progressif :**
  | Palier | Défaut | Ton |
  |--------|--------|-----|
  | `reminder` | **J+3** | Rappel doux |
  | `firm` | **J+7** | Relance ferme |
  | `last` | **J+14** | Dernière relance |
- **Canal configurable** (Paramètres › Ventes) : email via `mail.template`,
  activité assignée, ou les deux.
- **Historique horodaté** de chaque relance sur le devis : onglet *Relances*,
  bouton statistique, modèle `sale.order.followup.line`, menu
  *Ventes › Devis › Relances de devis*.
- Bouton **« Relancer maintenant »** sur le devis (envoie le palier suivant) et
  case **« Ne pas relancer »** pour exclure un devis.

## Règles métier

- La date d'envoi (`followup_sent_date`) est horodatée automatiquement au passage
  à l'état `sent` (et remise à zéro si le devis repasse en brouillon).
- Le cron envoie **le palier le plus élevé atteint** par l'ancienneté du devis et
  non encore envoyé (un devis oublié jusqu'à J+7 reçoit directement la relance ferme).
  Le bouton manuel, lui, envoie le **palier suivant** dans l'ordre.
- Un devis est considéré **« avec réponse »** (donc exclu du cron) s'il a reçu un
  email entrant (`mail.message` de type *email*) d'un contact du client depuis la
  date d'envoi. Le devis confirmé (`state = sale`) sort mécaniquement du périmètre.
- Le filtre liste « En attente de relance » est un **indicateur** (état `sent`,
  ≥ J+3, non bloqué, dernier palier ≠ *dernière relance*) ; l'exclusion fine
  « sans réponse » est faite par le cron au moment de l'envoi.

## Paramétrage

*Ventes › Configuration › Paramètres › section « Relances automatiques des devis »* :
délais J+3 / J+7 / J+14, canal, et responsable des activités. Stockés dans
`ir.config_parameter` (`sale_quote_followup.reminder_days`, `.firm_days`,
`.last_days`, `.channel`, `.activity_user_id`).

## Installation

```bash
# depuis le projet odoo_18_test
make init MODULE=sale_quote_followup          # DB "odoo"
# ou
docker compose exec web odoo -d <db> -i sale_quote_followup --stop-after-init
```

Déclencher le cron à la demande :

```bash
docker compose exec web odoo shell -d <db> --no-http \
  -c "env['sale.order']._cron_send_quotation_followups(); env.cr.commit()"
```

## Données de démonstration

10 devis couvrant tous les cas : brouillon, J+1, J+3, J+5 (rappel envoyé),
J+7, J+8, J+14, J+21 (cycle terminé), J+10 *client a répondu* (exclu),
J+6 *ne pas relancer* (exclu). Chargées avec le mode démo.

## Captures d'écran

### Liste des devis — filtre « En attente de relance »
![Liste des devis filtrée](static/description/screenshot_list.png)

### Formulaire — onglet « Relances »
![Onglet Relances](static/description/screenshot_form.png)

## Performances

Le moteur de relance est **borné en requêtes** quel que soit le nombre de devis :
une `search`, un `fetch` de préchargement, une seule requête `mail.message` pour
la détection des réponses, et **un seul `create`** groupé pour tout l'historique
(pas de N+1). Le seul coût par devis est l'envoi de l'email lui‑même, inhérent.
