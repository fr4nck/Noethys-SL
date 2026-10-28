#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Activation explicite du consommateur session-attendance/1.

Aucune migration implicite : l'appelant choisit appliquer=True. Le rollback
refuse de supprimer des tables contenant des données.
"""
from __future__ import unicode_literals

from Data import DATA_Interdomain_Attendance


TABLE_SESSIONS = DATA_Interdomain_Attendance.TABLE_SESSIONS
TABLE_INBOX = DATA_Interdomain_Attendance.TABLE_INBOX
PREREQUIS = (
    "activites",
    "groupes",
    "ouvertures",
    "evenements",
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


def _rapport_table(db, nom_table):
    existe = db.IsTableExists(nom_table)
    rapport = {
        "existe": existe,
        "champs_manquants": (),
        "conforme": False,
    }
    if not existe:
        return rapport
    metadata = _metadata_table(db, nom_table) or {}
    attendus = tuple(
        champ[0]
        for champ in DATA_Interdomain_Attendance.DB_INTERDOMAIN_ATTENDANCE[nom_table]
    )
    rapport["champs_manquants"] = tuple(
        champ for champ in attendus if champ not in metadata
    )
    rapport["conforme"] = not rapport["champs_manquants"]
    return rapport


def InspecterSchemaAttendance(db):
    return {
        "prerequis_absents": tuple(
            nom for nom in PREREQUIS if not db.IsTableExists(nom)
        ),
        "sessions": _rapport_table(db, TABLE_SESSIONS),
        "inbox": _rapport_table(db, TABLE_INBOX),
    }


def AssurerSchemaAttendance(db, appliquer=False):
    avant = InspecterSchemaAttendance(db)
    if avant["prerequis_absents"]:
        return {
            "ok": False,
            "appliquer": bool(appliquer),
            "tables_creees": (),
            "prerequis_absents": avant["prerequis_absents"],
            "rapport": avant,
        }

    for nom in ("sessions", "inbox"):
        rapport = avant[nom]
        if rapport["existe"] and not rapport["conforme"]:
            return {
                "ok": False,
                "appliquer": bool(appliquer),
                "tables_creees": (),
                "prerequis_absents": (),
                "rapport": avant,
            }

    creees = []
    try:
        if appliquer:
            for nom_table in (TABLE_SESSIONS, TABLE_INBOX):
                if not db.IsTableExists(nom_table):
                    db.CreationTable(
                        nom_table,
                        DATA_Interdomain_Attendance.DB_INTERDOMAIN_ATTENDANCE,
                    )
                    creees.append(nom_table)
            if creees:
                db.Commit()
    except Exception:
        try:
            db.Rollback()
        except Exception:
            pass
        raise

    apres = InspecterSchemaAttendance(db)
    return {
        "ok": bool(
            not apres["prerequis_absents"]
            and (
                (
                    apres["sessions"]["conforme"]
                    and apres["inbox"]["conforme"]
                )
                if appliquer
                else True
            )
        ),
        "appliquer": bool(appliquer),
        "tables_creees": tuple(creees),
        "prerequis_absents": apres["prerequis_absents"],
        "rapport": apres,
    }


def _compter(db, nom_table):
    if db.ExecuterReq("SELECT COUNT(*) FROM %s;" % nom_table) != 1:
        raise RuntimeError("Impossible de compter %s" % nom_table)
    lignes = db.ResultatReq() or []
    return int(lignes[0][0]) if lignes else 0


def RetirerSchemaAttendance(db, appliquer=False):
    """Rollback explicite, autorisé uniquement si les tables sont vides."""
    existantes = tuple(
        table
        for table in (TABLE_INBOX, TABLE_SESSIONS)
        if db.IsTableExists(table)
    )
    non_vides = tuple(table for table in existantes if _compter(db, table))
    if non_vides:
        return {
            "ok": False,
            "appliquer": bool(appliquer),
            "tables_supprimees": (),
            "tables_non_vides": non_vides,
        }

    supprimees = []
    try:
        if appliquer:
            for table in (TABLE_INBOX, TABLE_SESSIONS):
                if db.IsTableExists(table):
                    if db.ExecuterReq("DROP TABLE %s;" % table) != 1:
                        raise RuntimeError("Impossible de supprimer %s" % table)
                    supprimees.append(table)
            if supprimees:
                db.Commit()
    except Exception:
        try:
            db.Rollback()
        except Exception:
            pass
        raise

    return {
        "ok": True,
        "appliquer": bool(appliquer),
        "tables_supprimees": tuple(supprimees),
        "tables_non_vides": (),
    }
