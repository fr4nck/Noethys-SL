#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Schéma additif du consommateur inter-domaines session-attendance/1.

Ces tables sont des artefacts d'intégration. Elles ne remplacent ni les
activités, ni les groupes, ni les consommations de Noethys.
"""
from __future__ import unicode_literals


TABLE_SESSIONS = "interdomain_attendance_sessions"
TABLE_INBOX = "interdomain_attendance_inbox"

DB_INTERDOMAIN_ATTENDANCE = {
    TABLE_SESSIONS: [
        ("IDsession_attendance", "INTEGER PRIMARY KEY AUTOINCREMENT", u"ID local de corrélation"),
        ("session_uid", "VARCHAR(128) UNIQUE", u"UID canonique fourni par le domaine opérations"),
        ("IDactivite", "INTEGER", u"Activité Noethys existante"),
        ("IDgroupe", "INTEGER", u"Groupe Noethys existant, optionnel"),
        ("IDunite", "INTEGER", u"Unité de consommation Noethys, optionnelle si événement"),
        ("IDevenement", "INTEGER", u"Événement Noethys, optionnel si unité"),
        ("date", "DATE", u"Date Noethys de la séance"),
        ("actif", "INTEGER", u"Corrélation active (1/0)"),
        ("date_creation", "DATETIME", u"Horodatage technique de création"),
    ],
    TABLE_INBOX: [
        ("IDinbox_attendance", "INTEGER PRIMARY KEY AUTOINCREMENT", u"ID local de réception"),
        ("idempotence_key", "VARCHAR(255) UNIQUE", u"Clé stable de livraison"),
        ("operation_uuid", "VARCHAR(64) UNIQUE", u"Identifiant de l'opération de pointage"),
        ("source_domain", "VARCHAR(64)", u"Domaine émetteur stable"),
        ("contract_version", "VARCHAR(64)", u"Version du contrat métier"),
        ("event_type", "VARCHAR(64)", u"Type d'événement métier"),
        ("assignment_uuid", "VARCHAR(64)", u"Identifiant d'affectation côté opérations"),
        ("session_uid", "VARCHAR(128)", u"UID canonique de la séance"),
        ("payload_sha256", "VARCHAR(64)", u"Empreinte du payload normalisé"),
        ("change_count", "INTEGER", u"Nombre de participants demandés"),
        ("applied_rows", "INTEGER", u"Nombre de consommations effectivement modifiées"),
        ("date_reception", "DATETIME", u"Horodatage de réception"),
    ],
}
