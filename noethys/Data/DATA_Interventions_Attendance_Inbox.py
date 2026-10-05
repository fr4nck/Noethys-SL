#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Schéma additif de réception du pointage d'une séance."""
from __future__ import unicode_literals


TABLE_INBOX = "interventions_attendance_inbox"

DB_INTERVENTIONS_ATTENDANCE_INBOX = {
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
