#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Administration explicite des corrélations session_uid du pointage.

Le schéma doit avoir été activé séparément. Ce module ne crée aucune activité,
groupe, ouverture, événement ou consommation. Une corrélation déjà utilisée
par une livraison peut être désactivée mais jamais remappée silencieusement.
"""
from __future__ import unicode_literals

import datetime

from Data import DATA_Interdomain_Attendance
from Utils import UTILS_Interdomain_Attendance


TABLE_SESSIONS = DATA_Interdomain_Attendance.TABLE_SESSIONS
TABLE_INBOX = DATA_Interdomain_Attendance.TABLE_INBOX


class AttendanceCorrelationError(ValueError):
    pass


def _text(value, field, maximum=255):
    value = u"" if value is None else str(value).strip()
    if not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise AttendanceCorrelationError("%s invalide" % field)
    return value


def _integer(value, field, optional=False):
    if optional and value in (None, "", u""):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise AttendanceCorrelationError("%s invalide" % field)
    if value < 1:
        raise AttendanceCorrelationError("%s invalide" % field)
    return value


def _date(value):
    value = _text(value, "date", 10)
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise AttendanceCorrelationError("date invalide")
    return value


def _timestamp(value=None):
    if value is None:
        value = datetime.datetime.now()
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    value = _text(value, "date_creation", 19)
    try:
        datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise AttendanceCorrelationError("date_creation invalide")
    return value


def _sql(value):
    return str(value).replace("'", "''")


class GestionnaireCorrelationsAttendance(object):
    def __init__(self, db):
        self.db = db

    def _require_schema(self):
        missing = [
            table for table in (TABLE_SESSIONS, TABLE_INBOX)
            if not self.db.IsTableExists(table)
        ]
        if missing:
            raise AttendanceCorrelationError(
                "schéma pointage absent: %s" % ", ".join(missing)
            )

    def _query(self, sql, error):
        if self.db.ExecuterReq(sql) != 1:
            raise AttendanceCorrelationError(error)
        return self.db.ResultatReq() or []

    def _current(self, session_uid):
        rows = self._query(
            """SELECT IDsession_attendance,session_uid,IDactivite,IDgroupe,
                      IDunite,IDevenement,date,actif,date_creation
               FROM %s WHERE session_uid='%s';"""
            % (TABLE_SESSIONS, _sql(session_uid)),
            "lecture de corrélation impossible",
        )
        if len(rows) > 1:
            raise AttendanceCorrelationError("corrélation de séance ambiguë")
        if not rows:
            return None
        keys = (
            "IDsession_attendance", "session_uid", "IDactivite", "IDgroupe",
            "IDunite", "IDevenement", "date", "actif", "date_creation",
        )
        return dict(zip(keys, rows[0]))

    def _has_history(self, session_uid):
        rows = self._query(
            "SELECT COUNT(*) FROM %s WHERE session_uid='%s';"
            % (TABLE_INBOX, _sql(session_uid)),
            "lecture de l'historique pointage impossible",
        )
        return bool(rows and int(rows[0][0] or 0))

    def _validate(self, scope):
        try:
            UTILS_Interdomain_Attendance.GestionnaireInboxAttendance(
                self.db
            )._valider_reference_session(scope)
        except UTILS_Interdomain_Attendance.AttendanceInboxError as error:
            raise AttendanceCorrelationError(str(error))

    def Lire(self, session_uid):
        self._require_schema()
        return self._current(_text(session_uid, "session_uid", 128))

    def Configurer(
        self, session_uid, IDactivite, date, IDgroupe=None,
        IDunite=None, IDevenement=None, actif=True, date_creation=None,
    ):
        self._require_schema()
        session_uid = _text(session_uid, "session_uid", 128)
        scope = {
            "session_uid": session_uid,
            "IDactivite": _integer(IDactivite, "IDactivite"),
            "IDgroupe": _integer(IDgroupe, "IDgroupe", optional=True),
            "IDunite": _integer(IDunite, "IDunite", optional=True),
            "IDevenement": _integer(IDevenement, "IDevenement", optional=True),
            "date": _date(date),
            "actif": 1 if actif is True or actif == 1 else 0,
        }
        if scope["IDunite"] is None and scope["IDevenement"] is None:
            raise AttendanceCorrelationError(
                "unité ou événement requis pour la corrélation"
            )
        self._validate(scope)

        current = self._current(session_uid)
        business = (
            scope["IDactivite"], scope["IDgroupe"], scope["IDunite"],
            scope["IDevenement"], scope["date"],
        )
        if current is not None:
            old = (
                int(current["IDactivite"]),
                None if current["IDgroupe"] is None else int(current["IDgroupe"]),
                None if current["IDunite"] is None else int(current["IDunite"]),
                None if current["IDevenement"] is None else int(current["IDevenement"]),
                str(current["date"]),
            )
            if old != business and self._has_history(session_uid):
                raise AttendanceCorrelationError(
                    "corrélation déjà utilisée ; remappage interdit"
                )
            result = self.db.ReqMAJ(
                TABLE_SESSIONS,
                [
                    ("IDactivite", scope["IDactivite"]),
                    ("IDgroupe", scope["IDgroupe"]),
                    ("IDunite", scope["IDunite"]),
                    ("IDevenement", scope["IDevenement"]),
                    ("date", scope["date"]),
                    ("actif", scope["actif"]),
                ],
                "IDsession_attendance",
                current["IDsession_attendance"],
                commit=True,
            )
            if result is False:
                raise AttendanceCorrelationError("mise à jour refusée")
            return {"created": False, "session_uid": session_uid}

        inserted = self.db.ReqInsert(
            TABLE_SESSIONS,
            [
                ("session_uid", session_uid),
                ("IDactivite", scope["IDactivite"]),
                ("IDgroupe", scope["IDgroupe"]),
                ("IDunite", scope["IDunite"]),
                ("IDevenement", scope["IDevenement"]),
                ("date", scope["date"]),
                ("actif", scope["actif"]),
                ("date_creation", _timestamp(date_creation)),
            ],
            commit=True,
        )
        if inserted is None:
            raise AttendanceCorrelationError("création refusée")
        return {"created": True, "session_uid": session_uid}

    def Desactiver(self, session_uid):
        self._require_schema()
        session_uid = _text(session_uid, "session_uid", 128)
        current = self._current(session_uid)
        if current is None or int(current["actif"] or 0) == 0:
            return False
        result = self.db.ReqMAJ(
            TABLE_SESSIONS,
            [("actif", 0)],
            "IDsession_attendance",
            current["IDsession_attendance"],
            commit=True,
        )
        if result is False:
            raise AttendanceCorrelationError("désactivation refusée")
        return True
