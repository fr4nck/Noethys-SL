#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Consommateur idempotent du contrat session-attendance/1.

La séance n'est pas recréée dans Noethys. Une table d'intégration corrèle
explicitement le session_uid externe avec un périmètre Noethys existant.
Aucune consommation, activité, groupe, unité ou événement n'est créé ici.
"""
from __future__ import unicode_literals

import datetime
import hashlib
import json
from uuid import UUID

from Data import DATA_Interdomain_Attendance


TABLE_SESSIONS = DATA_Interdomain_Attendance.TABLE_SESSIONS
TABLE_INBOX = DATA_Interdomain_Attendance.TABLE_INBOX
SOURCE_DOMAIN = "operations_portal"
CONTRACT_VERSION = "session-attendance/1"
EVENT_TYPE = "session_attendance_changed"
TARGET_PRESENT = "present"
TARGET_ABSENT = "absenti"
ELIGIBLE_STATES = ("reservation", "present", "absenti", "absentj")


class AttendanceInboxError(ValueError):
    pass


def _texte(valeur):
    if valeur is None:
        return u""
    try:
        return valeur.strip()
    except Exception:
        return str(valeur).strip()


def _texte_requis(valeur, champ, longueur=255):
    valeur = _texte(valeur)
    if not valeur:
        raise AttendanceInboxError("%s obligatoire" % champ)
    if len(valeur) > longueur or any(ord(ch) < 32 for ch in valeur):
        raise AttendanceInboxError("%s invalide" % champ)
    return valeur


def _uuid(valeur, champ):
    texte = _texte_requis(valeur, champ, 64)
    try:
        return str(UUID(texte))
    except (TypeError, ValueError, AttributeError):
        raise AttendanceInboxError("%s invalide" % champ)


def _entier_positif(valeur, champ, optionnel=False):
    if optionnel and valeur in (None, "", u""):
        return None
    try:
        entier = int(valeur)
    except (TypeError, ValueError):
        raise AttendanceInboxError("%s invalide" % champ)
    if entier < 1:
        raise AttendanceInboxError("%s invalide" % champ)
    return entier


def _sql_texte(valeur):
    return _texte(valeur).replace("'", "''")


def _datetime_reception(valeur=None):
    valeur = valeur or datetime.datetime.now()
    if isinstance(valeur, datetime.datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    texte = _texte_requis(valeur, "date_reception", 40).replace("T", " ")
    texte = texte[:19]
    try:
        datetime.datetime.strptime(texte, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise AttendanceInboxError("date_reception invalide")
    return texte


def _occurred_at(valeur):
    texte = _texte_requis(valeur, "occurred_at", 40)
    normalise = texte[:-1] + "+00:00" if texte.endswith("Z") else texte
    try:
        parsed = datetime.datetime.fromisoformat(normalise)
    except ValueError:
        raise AttendanceInboxError("occurred_at invalide")
    if parsed.tzinfo is None:
        raise AttendanceInboxError("occurred_at doit être timezone-aware")
    return texte


def _json_stable(donnees):
    return json.dumps(
        donnees,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _sha256(donnees):
    return hashlib.sha256(_json_stable(donnees).encode("utf-8")).hexdigest()


def _rollback(db):
    methode = getattr(db, "Rollback", None)
    if callable(methode):
        methode()
        return
    connexion = getattr(db, "connexion", None) or getattr(db, "conn", None)
    if connexion is not None and hasattr(connexion, "rollback"):
        connexion.rollback()
        return
    raise RuntimeError("La connexion DB ne permet pas le rollback")


def _commit(db):
    methode = getattr(db, "Commit", None)
    if callable(methode):
        methode()
        return
    connexion = getattr(db, "connexion", None) or getattr(db, "conn", None)
    if connexion is not None and hasattr(connexion, "commit"):
        connexion.commit()
        return
    raise RuntimeError("La connexion DB ne permet pas le commit")


def _normaliser_message(payload):
    if not isinstance(payload, dict):
        raise AttendanceInboxError("payload invalide")
    contract_version = _texte_requis(
        payload.get("contract_version"), "contract_version", 64
    )
    if contract_version != CONTRACT_VERSION:
        raise AttendanceInboxError("version de contrat non supportée")
    event_type = _texte_requis(payload.get("event_type"), "event_type", 64)
    if event_type != EVENT_TYPE:
        raise AttendanceInboxError("type d'événement non supporté")

    operation_uuid = _uuid(payload.get("operation_id"), "operation_id")
    assignment_uuid = _uuid(payload.get("assignment_uuid"), "assignment_uuid")
    session_uid = _texte_requis(payload.get("session_uid"), "session_uid", 128)
    occurred_at = _occurred_at(payload.get("occurred_at"))

    changes = payload.get("changes")
    if not isinstance(changes, list) or not changes:
        raise AttendanceInboxError("changes doit être une liste non vide")
    if len(changes) > 500:
        raise AttendanceInboxError("trop de changements dans une opération")

    normalises = []
    vus = set()
    for change in changes:
        if not isinstance(change, dict):
            raise AttendanceInboxError("changement de pointage invalide")
        participant_id = _entier_positif(
            change.get("participant_uid"), "participant_uid"
        )
        if participant_id in vus:
            raise AttendanceInboxError("participant dupliqué dans changes")
        vus.add(participant_id)
        status = _texte_requis(change.get("status"), "status", 16)
        if status not in ("present", "absent"):
            raise AttendanceInboxError("status doit être present ou absent")
        normalises.append(
            {
                "participant_uid": str(participant_id),
                "status": status,
            }
        )
    normalises.sort(key=lambda item: int(item["participant_uid"]))

    return {
        "contract_version": contract_version,
        "event_type": event_type,
        "operation_id": operation_uuid,
        "assignment_uuid": assignment_uuid,
        "session_uid": session_uid,
        "occurred_at": occurred_at,
        "changes": normalises,
    }


class GestionnaireInboxAttendance(object):
    def __init__(self, db):
        self.db = db

    def _exiger_schema(self):
        requises = (
            "activites",
            "groupes",
            "ouvertures",
            "evenements",
            "consommations",
            TABLE_SESSIONS,
            TABLE_INBOX,
        )
        absentes = [nom for nom in requises if not self.db.IsTableExists(nom)]
        if absentes:
            raise AttendanceInboxError(
                "Tables requises absentes: %s" % ", ".join(absentes)
            )

    def _lire_inbox(self, champ, valeur):
        req = (
            "SELECT idempotence_key, operation_uuid, payload_sha256, "
            "change_count, applied_rows FROM %s WHERE %s='%s';"
            % (TABLE_INBOX, champ, _sql_texte(valeur))
        )
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire l'inbox pointage")
        lignes = self.db.ResultatReq() or []
        if len(lignes) > 1:
            raise AttendanceInboxError("%s dupliqué dans l'inbox" % champ)
        if not lignes:
            return None
        return dict(
            zip(
                (
                    "idempotence_key",
                    "operation_uuid",
                    "payload_sha256",
                    "change_count",
                    "applied_rows",
                ),
                lignes[0],
            )
        )

    def _lire_reference_session(self, session_uid):
        req = """
SELECT session_uid,IDactivite,IDgroupe,IDunite,IDevenement,date,actif
FROM %s
WHERE session_uid='%s';
""" % (TABLE_SESSIONS, _sql_texte(session_uid))
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire la corrélation de séance")
        lignes = self.db.ResultatReq() or []
        if len(lignes) != 1:
            if not lignes:
                raise AttendanceInboxError("corrélation de séance introuvable")
            raise AttendanceInboxError("corrélation de séance ambiguë")

        champs = (
            "session_uid",
            "IDactivite",
            "IDgroupe",
            "IDunite",
            "IDevenement",
            "date",
            "actif",
        )
        session = dict(zip(champs, lignes[0]))
        if session["actif"] in (0, False, "0", None):
            raise AttendanceInboxError("corrélation de séance inactive")
        session["IDactivite"] = _entier_positif(
            session["IDactivite"], "IDactivite"
        )
        session["IDgroupe"] = _entier_positif(
            session["IDgroupe"], "IDgroupe", optionnel=True
        )
        session["IDunite"] = _entier_positif(
            session["IDunite"], "IDunite", optionnel=True
        )
        session["IDevenement"] = _entier_positif(
            session["IDevenement"], "IDevenement", optionnel=True
        )
        session["date"] = _texte_requis(session["date"], "date de séance", 10)
        if session["IDunite"] is None and session["IDevenement"] is None:
            raise AttendanceInboxError(
                "corrélation de séance trop large: unité ou événement requis"
            )
        self._valider_reference_session(session)
        return session

    def _existe_exactement_une(self, req, message):
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError(message)
        lignes = self.db.ResultatReq() or []
        if len(lignes) != 1:
            raise AttendanceInboxError(message)

    def _valider_reference_session(self, session):
        self._existe_exactement_une(
            "SELECT IDactivite FROM activites WHERE IDactivite=%d;"
            % session["IDactivite"],
            "activité de corrélation introuvable",
        )
        if session["IDgroupe"] is not None:
            self._existe_exactement_une(
                "SELECT IDgroupe FROM groupes WHERE IDgroupe=%d AND IDactivite=%d;"
                % (session["IDgroupe"], session["IDactivite"]),
                "groupe de corrélation introuvable",
            )

        filtres = [
            "IDactivite=%d" % session["IDactivite"],
            "date='%s'" % _sql_texte(session["date"]),
        ]
        if session["IDgroupe"] is not None:
            filtres.append("IDgroupe=%d" % session["IDgroupe"])
        if session["IDunite"] is not None:
            filtres.append("IDunite=%d" % session["IDunite"])

        if session["IDevenement"] is not None:
            filtres_evt = list(filtres)
            filtres_evt.append("IDevenement=%d" % session["IDevenement"])
            self._existe_exactement_une(
                "SELECT IDevenement FROM evenements WHERE %s;"
                % " AND ".join(filtres_evt),
                "événement de corrélation introuvable ou ambigu",
            )
        else:
            if self.db.ExecuterReq(
                "SELECT IDouverture FROM ouvertures WHERE %s;"
                % " AND ".join(filtres)
            ) != 1:
                raise AttendanceInboxError("ouverture de séance illisible")
            if not (self.db.ResultatReq() or []):
                raise AttendanceInboxError("ouverture de séance introuvable")

    def _lire_consommation(self, session, participant_id):
        filtres = [
            "date='%s'" % _sql_texte(session["date"]),
            "IDactivite=%d" % session["IDactivite"],
            "IDindividu=%d" % int(participant_id),
            "etat IN ('reservation','present','absenti','absentj')",
        ]
        if session["IDgroupe"] is not None:
            filtres.append("IDgroupe=%d" % session["IDgroupe"])
        if session["IDevenement"] is not None:
            filtres.append("IDevenement=%d" % session["IDevenement"])
        else:
            filtres.append("IDunite=%d" % session["IDunite"])

        req = """
SELECT IDconso,IDindividu,etat
FROM consommations
WHERE %s
ORDER BY IDconso;
""" % " AND ".join(filtres)
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire les consommations")
        lignes = self.db.ResultatReq() or []
        if not lignes:
            raise AttendanceInboxError("participant absent de la séance corrélée")
        if len(lignes) != 1:
            raise AttendanceInboxError(
                "consommation de séance ambiguë pour le participant"
            )
        return dict(zip(("IDconso", "IDindividu", "etat"), lignes[0]))

    @staticmethod
    def _etat_cible(status, etat_actuel):
        if etat_actuel == "absentj":
            if status == "present":
                raise AttendanceInboxError(
                    "absence justifiée protégée ; correction administrative requise"
                )
            return "absentj"
        if status == "present":
            return TARGET_PRESENT
        return TARGET_ABSENT

    def AppliquerMessage(
        self,
        payload,
        idempotence_key,
        source_domain=SOURCE_DOMAIN,
        date_reception=None,
    ):
        self._exiger_schema()
        source_domain = _texte_requis(source_domain, "source_domain", 64)
        if source_domain != SOURCE_DOMAIN:
            raise AttendanceInboxError("domaine source non supporté")
        idempotence_key = _texte_requis(
            idempotence_key, "idempotence_key", 255
        )

        normalise = _normaliser_message(payload)
        attendu = (
            "session-attendance:%s:activity_users"
            % normalise["operation_id"]
        )
        if idempotence_key != attendu:
            raise AttendanceInboxError("clé d'idempotence incohérente")

        empreinte = _sha256(normalise)
        date_reception_sql = _datetime_reception(date_reception)

        for deja in (
            self._lire_inbox("idempotence_key", idempotence_key),
            self._lire_inbox("operation_uuid", normalise["operation_id"]),
        ):
            if deja is None:
                continue
            if (
                _texte(deja["payload_sha256"]) != empreinte
                or _texte(deja["operation_uuid"]) != normalise["operation_id"]
            ):
                raise AttendanceInboxError(
                    "opération rejouée avec un payload différent"
                )
            return {
                "applique": False,
                "replay": True,
                "session_uid": normalise["session_uid"],
                "operation_id": normalise["operation_id"],
                "change_count": int(deja["change_count"] or 0),
                "applied_rows": int(deja["applied_rows"] or 0),
            }

        session = self._lire_reference_session(normalise["session_uid"])

        plans = []
        for change in normalise["changes"]:
            consommation = self._lire_consommation(
                session, int(change["participant_uid"])
            )
            etat_actuel = _texte(consommation["etat"])
            if etat_actuel not in ELIGIBLE_STATES:
                raise AttendanceInboxError("état de consommation non pointable")
            etat_cible = self._etat_cible(change["status"], etat_actuel)
            plans.append(
                {
                    "IDconso": int(consommation["IDconso"]),
                    "etat_actuel": etat_actuel,
                    "etat_cible": etat_cible,
                }
            )

        applied_rows = sum(
            1 for plan in plans if plan["etat_actuel"] != plan["etat_cible"]
        )
        valeurs_inbox = [
            ("idempotence_key", idempotence_key),
            ("operation_uuid", normalise["operation_id"]),
            ("source_domain", source_domain),
            ("contract_version", normalise["contract_version"]),
            ("event_type", normalise["event_type"]),
            ("assignment_uuid", normalise["assignment_uuid"]),
            ("session_uid", normalise["session_uid"]),
            ("payload_sha256", empreinte),
            ("change_count", len(normalise["changes"])),
            ("applied_rows", applied_rows),
            ("date_reception", date_reception_sql),
        ]

        try:
            IDinbox = self.db.ReqInsert(
                TABLE_INBOX, valeurs_inbox, commit=False
            )
            if IDinbox is None:
                raise AttendanceInboxError(
                    "échec d'enregistrement de l'inbox pointage"
                )
            for plan in plans:
                if plan["etat_actuel"] == plan["etat_cible"]:
                    continue
                resultat = self.db.ReqMAJ(
                    "consommations",
                    [("etat", plan["etat_cible"])],
                    "IDconso",
                    plan["IDconso"],
                    commit=False,
                )
                if resultat is False:
                    raise AttendanceInboxError(
                        "échec de mise à jour d'une consommation"
                    )
            _commit(self.db)
        except Exception:
            try:
                _rollback(self.db)
            except Exception:
                pass
            raise

        return {
            "applique": True,
            "replay": False,
            "session_uid": normalise["session_uid"],
            "operation_id": normalise["operation_id"],
            "change_count": len(normalise["changes"]),
            "applied_rows": applied_rows,
        }
