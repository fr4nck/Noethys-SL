#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Activation additive de l'inbox du pointage session-attendance/1."""
from __future__ import unicode_literals

from Data import DATA_Interventions_Attendance_Inbox


TABLE_INBOX = DATA_Interventions_Attendance_Inbox.TABLE_INBOX
PREREQUIS = (
    "interventions",
    "interventions_programmations",
    "consommations",
)


def _chaine(valeur):
    if isinstance(valeur, bytes):
        return valeur.decode("ascii", "ignore")
    return str(valeur)


def _categorie_type(type_sql):
    valeur = _chaine(type_sql or "").strip().lower()
    base = valeur.split("(", 1)[0].strip()
    if "int" in base:
        return "integer"
    if base in ("char", "varchar", "text", "tinytext", "mediumtext", "longtext"):
        return "text"
    if base in ("date", "datetime", "timestamp"):
        return "date"
    return base


def _metadata_table(db, nom_table):
    is_network = bool(getattr(db, "isNetwork", False))
    colonnes = {}
    if not is_network:
        if db.ExecuterReq("PRAGMA table_info('%s');" % nom_table) != 1:
            return None
        for cid, nom, type_sql, notnull, valeur_defaut, pk in db.ResultatReq():
            colonnes[_chaine(nom)] = {
                "type": type_sql,
                "pk": bool(pk),
                "auto": bool(pk) and _categorie_type(type_sql) == "integer",
            }
    else:
        if db.ExecuterReq("SHOW COLUMNS FROM %s;" % nom_table) != 1:
            return None
        for valeurs in db.ResultatReq():
            colonnes[_chaine(valeurs[0])] = {
                "type": valeurs[1],
                "pk": _chaine(valeurs[3] if len(valeurs) > 3 else "").upper() == "PRI",
                "auto": "auto_increment" in _chaine(
                    valeurs[5] if len(valeurs) > 5 else ""
                ).lower(),
            }
    return colonnes


def InspecterSchemaAttendanceInbox(db):
    prerequis_absents = tuple(
        nom for nom in PREREQUIS if not db.IsTableExists(nom)
    )
    rapport = {
        "existe": db.IsTableExists(TABLE_INBOX),
        "champs_manquants": (),
        "conforme": False,
    }
    if rapport["existe"]:
        metadata = _metadata_table(db, TABLE_INBOX) or {}
        attendus = tuple(
            champ[0]
            for champ in DATA_Interventions_Attendance_Inbox.DB_INTERVENTIONS_ATTENDANCE_INBOX[
                TABLE_INBOX
            ]
        )
        rapport["champs_manquants"] = tuple(
            champ for champ in attendus if champ not in metadata
        )
        rapport["conforme"] = not rapport["champs_manquants"]
    return {
        "prerequis_absents": prerequis_absents,
        "inbox": rapport,
    }


def AssurerSchemaAttendanceInbox(db, appliquer=False):
    avant = InspecterSchemaAttendanceInbox(db)
    if avant["prerequis_absents"]:
        return {
            "ok": False,
            "appliquer": bool(appliquer),
            "tables_creees": (),
            "prerequis_absents": avant["prerequis_absents"],
            "rapport": avant,
        }
    if avant["inbox"]["existe"] and not avant["inbox"]["conforme"]:
        return {
            "ok": False,
            "appliquer": bool(appliquer),
            "tables_creees": (),
            "prerequis_absents": (),
            "rapport": avant,
        }

    creees = []
    if appliquer and not avant["inbox"]["existe"]:
        db.CreationTable(
            TABLE_INBOX,
            DATA_Interventions_Attendance_Inbox.DB_INTERVENTIONS_ATTENDANCE_INBOX,
        )
        db.Commit()
        creees.append(TABLE_INBOX)

    apres = InspecterSchemaAttendanceInbox(db)
    return {
        "ok": bool(
            not apres["prerequis_absents"]
            and (apres["inbox"]["conforme"] if appliquer else True)
        ),
        "appliquer": bool(appliquer),
        "tables_creees": tuple(creees),
        "prerequis_absents": apres["prerequis_absents"],
        "rapport": apres,
    }
