#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Réception idempotente du pointage d'une séance dans activité/usagers."""
from __future__ import unicode_literals

import datetime
import hashlib
import json
from uuid import UUID

from Data import DATA_Interventions_Attendance_Inbox


TABLE_INBOX = DATA_Interventions_Attendance_Inbox.TABLE_INBOX
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


def _entier_positif(valeur, champ):
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
            "interventions",
            "interventions_programmations",
            "consommations",
            TABLE_INBOX,
        )
        absentes = [nom for nom in requises if not self.db.IsTableExists(nom)]
        if absentes:
            raise AttendanceInboxError(
                "Tables requises absentes: %s" % ", ".join(absentes)
            )

    def _lire_inbox_par_cle(self, cle):
        req = (
            "SELECT idempotence_key, operation_uuid, payload_sha256, "
            "change_count, applied_rows FROM %s WHERE idempotence_key='%s';"
            % (TABLE_INBOX, _sql_texte(cle))
        )
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire l'inbox pointage")
        lignes = self.db.ResultatReq() or []
        if len(lignes) > 1:
            raise AttendanceInboxError("Clé d'idempotence dupliquée")
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

    def _lire_inbox_par_operation(self, operation_uuid):
        req = (
            "SELECT idempotence_key, operation_uuid, payload_sha256, "
            "change_count, applied_rows FROM %s WHERE operation_uuid='%s';"
            % (TABLE_INBOX, _sql_texte(operation_uuid))
        )
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire l'opération de pointage")
        lignes = self.db.ResultatReq() or []
        if len(lignes) > 1:
            raise AttendanceInboxError("operation_uuid dupliqué")
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

    def _lire_session(self, session_uid):
        req = """
SELECT i.IDintervention, i.uid, i.date, i.statut, i.actif,
       ip.type_source, ip.IDactivite, ip.IDgroupe_activite
FROM interventions i
JOIN interventions_programmations ip
  ON ip.IDintervention = i.IDintervention
WHERE i.uid='%s';
""" % _sql_texte(session_uid)
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire la séance canonique")
        lignes = self.db.ResultatReq() or []
        if len(lignes) != 1:
            if not lignes:
                raise AttendanceInboxError(
                    "Séance canonique ou traçabilité de programmation introuvable"
                )
            raise AttendanceInboxError(
                "Traçabilité de programmation de séance ambiguë"
            )
        champs = (
            "IDintervention",
            "session_uid",
            "date",
            "statut",
            "actif",
            "type_source",
            "IDactivite",
            "IDgroupe_activite",
        )
        session = dict(zip(champs, lignes[0]))
        if session["actif"] in (0, False, "0"):
            raise AttendanceInboxError("séance canonique archivée")
        if _texte(session["statut"]) == "annulee":
            raise AttendanceInboxError("séance canonique annulée")
        if _texte(session["type_source"]) != "activite":
            raise AttendanceInboxError(
                "pointage non défini pour une séance hors activité"
            )
        session["IDactivite"] = _entier_positif(
            session["IDactivite"], "IDactivite"
        )
        if session["IDgroupe_activite"] in (None, "", u""):
            session["IDgroupe_activite"] = None
        else:
            session["IDgroupe_activite"] = _entier_positif(
                session["IDgroupe_activite"], "IDgroupe_activite"
            )
        session["date"] = _texte_requis(session["date"], "date de séance", 10)
        return session

    def _lire_consommations(self, session, participant_id):
        filtre_groupe = ""
        if session["IDgroupe_activite"] is not None:
            filtre_groupe = " AND IDgroupe=%d" % session["IDgroupe_activite"]
        req = """
SELECT IDconso, IDindividu, etat
FROM consommations
WHERE date='%s'
  AND IDactivite=%d
  AND IDindividu=%d
  %s
  AND etat IN ('reservation','present','absenti','absentj')
ORDER BY IDconso;
""" % (
            _sql_texte(session["date"]),
            session["IDactivite"],
            int(participant_id),
            filtre_groupe,
        )
        if self.db.ExecuterReq(req) != 1:
            raise AttendanceInboxError("Impossible de lire les consommations")
        lignes = self.db.ResultatReq() or []
        return tuple(
            dict(zip(("IDconso", "IDindividu", "etat"), ligne))
            for ligne in lignes
        )

    @staticmethod
    def _etat_cible(status, etat_actuel):
        if etat_actuel == "absentj":
            if status == "present":
                # Retirer une justification traverse une frontière de
                # facturation Noethys : le pointage terrain ne peut pas le faire
                # sans passer par le workflow administratif de correction.
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
        attendu = "session-attendance:%s:activity_users" % normalise["operation_id"]
        if idempotence_key != attendu:
            raise AttendanceInboxError("clé d'idempotence incohérente")

        empreinte = _sha256(normalise)
        date_reception_sql = _datetime_reception(date_reception)

        for deja in (
            self._lire_inbox_par_cle(idempotence_key),
            self._lire_inbox_par_operation(normalise["operation_id"]),
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

        session = self._lire_session(normalise["session_uid"])

        # Tout le lot est qualifié avant la première écriture.
        plans = []
        for change in normalise["changes"]:
            participant_id = int(change["participant_uid"])
            consommations = self._lire_consommations(session, participant_id)
            if not consommations:
                raise AttendanceInboxError(
                    "participant absent de la séance canonique"
                )
            for consommation in consommations:
                etat_actuel = _texte(consommation["etat"])
                if etat_actuel not in ELIGIBLE_STATES:
                    raise AttendanceInboxError(
                        "état de consommation non pointable"
                    )
                etat_cible = self._etat_cible(
                    change["status"], etat_actuel
                )
                plans.append(
                    {
                        "IDconso": int(consommation["IDconso"]),
                        "participant_uid": change["participant_uid"],
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
