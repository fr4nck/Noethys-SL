#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Vérification locale de l'enveloppe inter-domaines du pointage.

Ce module ne contient aucun transport réseau et ne charge aucun secret.
La matière HMAC est fournie explicitement par l'appelant dans keyring.
Après authentification de l'enveloppe, seul le consommateur local
session-attendance/1 est appelé.
"""
from __future__ import unicode_literals

import hashlib
import hmac
import json
import re

from Utils import UTILS_Interdomain_Attendance


ENVELOPE_VERSION = "inter-domain-delivery/1"
SOURCE_DOMAIN = "operations_portal"
TARGET_DOMAIN = "activity_users"
CONTRACT_VERSION = "session-attendance/1"
EVENT_TYPE = "session_attendance_changed"
ACK_STATUSES = ("accepted", "replayed", "rejected", "retryable")


class DeliveryEnvelopeError(ValueError):
    pass


def _text(value, field, maximum):
    if not isinstance(value, str):
        raise DeliveryEnvelopeError("%s obligatoire" % field)
    value = value.strip()
    if not value:
        raise DeliveryEnvelopeError("%s obligatoire" % field)
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise DeliveryEnvelopeError("%s invalide" % field)
    return value


def _secret(value):
    if not isinstance(value, (bytes, bytearray)):
        raise DeliveryEnvelopeError("secret HMAC binaire obligatoire")
    value = bytes(value)
    if len(value) < 32:
        raise DeliveryEnvelopeError("secret HMAC trop court")
    return value


def _occurred_at(value):
    value = _text(value, "occurred_at", 40)
    if not re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$",
        value,
    ):
        raise DeliveryEnvelopeError("occurred_at invalide")
    return value


def _mapping_copy(value, field):
    if not isinstance(value, dict):
        raise DeliveryEnvelopeError("%s invalide" % field)
    try:
        return json.loads(json.dumps(value, ensure_ascii=True))
    except (TypeError, ValueError):
        raise DeliveryEnvelopeError("%s non sérialisable" % field)


def _canonical_json(envelope):
    if not isinstance(envelope, dict):
        raise DeliveryEnvelopeError("enveloppe invalide")
    try:
        return json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    except (TypeError, ValueError):
        raise DeliveryEnvelopeError("enveloppe non sérialisable")


def _signature(envelope, secret):
    message = _canonical_json(envelope).encode("utf-8")
    return hmac.new(_secret(secret), message, hashlib.sha256).hexdigest()


def VerifierEnveloppe(
    livraison,
    keyring,
    target_domain=TARGET_DOMAIN,
    source_domain=SOURCE_DOMAIN,
):
    if not isinstance(livraison, dict):
        raise DeliveryEnvelopeError("livraison signée invalide")
    if set(livraison.keys()) != set(("envelope", "signature")):
        raise DeliveryEnvelopeError("livraison signée invalide")

    envelope = _mapping_copy(livraison.get("envelope"), "enveloppe")
    signature = _text(livraison.get("signature"), "signature", 64).lower()
    if not re.match(r"^[0-9a-f]{64}$", signature):
        raise DeliveryEnvelopeError("signature HMAC invalide")

    if envelope.get("envelope_version") != ENVELOPE_VERSION:
        raise DeliveryEnvelopeError("version d'enveloppe non supportée")
    if _text(envelope.get("source_domain"), "source_domain", 64) != source_domain:
        raise DeliveryEnvelopeError("domaine source inattendu")
    if _text(envelope.get("target_domain"), "target_domain", 64) != target_domain:
        raise DeliveryEnvelopeError("domaine cible inattendu")

    contract_version = _text(
        envelope.get("contract_version"), "contract_version", 64
    )
    event_type = _text(envelope.get("event_type"), "event_type", 64)
    if contract_version != CONTRACT_VERSION or event_type != EVENT_TYPE:
        raise DeliveryEnvelopeError("contrat métier ou type d'événement non supporté")

    idempotence_key = _text(
        envelope.get("idempotence_key"), "idempotence_key", 255
    )
    correlation_id = _text(
        envelope.get("correlation_id"), "correlation_id", 128
    )
    _occurred_at(envelope.get("occurred_at"))
    key_id = _text(envelope.get("key_id"), "key_id", 64)

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise DeliveryEnvelopeError("payload invalide")
    if payload.get("contract_version") != contract_version:
        raise DeliveryEnvelopeError(
            "contract_version incohérente avec le payload"
        )
    if payload.get("event_type") != event_type:
        raise DeliveryEnvelopeError("event_type incohérent avec le payload")

    if not isinstance(keyring, dict) or key_id not in keyring:
        raise DeliveryEnvelopeError("key_id inconnu")
    expected = _signature(envelope, keyring[key_id])
    if not hmac.compare_digest(expected, signature):
        raise DeliveryEnvelopeError("signature HMAC invalide")

    envelope["idempotence_key"] = idempotence_key
    envelope["correlation_id"] = correlation_id
    return envelope


def ConstruireAccuse(status, idempotence_key, correlation_id, detail=""):
    status = _text(status, "status", 32)
    if status not in ACK_STATUSES:
        raise DeliveryEnvelopeError("statut d'accusé invalide")
    idempotence_key = _text(
        idempotence_key, "idempotence_key", 255
    )
    correlation_id = _text(correlation_id, "correlation_id", 128)
    if detail is None:
        detail = ""
    if not isinstance(detail, str) or len(detail) > 500:
        raise DeliveryEnvelopeError("detail invalide")
    return {
        "status": status,
        "idempotence_key": idempotence_key,
        "correlation_id": correlation_id,
        "detail": detail,
    }


def RecevoirLivraisonSignee(db, livraison, keyring, date_reception=None):
    """Authentifie puis applique une livraison de pointage.

    Les erreurs déterministes d'enveloppe ou de contrat produisent rejected.
    Une panne technique inattendue est propagée : le futur transport pourra la
    classer retryable sans masquer une panne locale.
    """
    try:
        envelope = VerifierEnveloppe(livraison, keyring)
    except DeliveryEnvelopeError as error:
        idempotence_key = "invalid"
        correlation_id = "invalid"
        if isinstance(livraison, dict) and isinstance(
            livraison.get("envelope"), dict
        ):
            candidate = livraison["envelope"]
            try:
                idempotence_key = _text(
                    candidate.get("idempotence_key"),
                    "idempotence_key",
                    255,
                )
            except DeliveryEnvelopeError:
                pass
            try:
                correlation_id = _text(
                    candidate.get("correlation_id"),
                    "correlation_id",
                    128,
                )
            except DeliveryEnvelopeError:
                pass
        return ConstruireAccuse(
            "rejected",
            idempotence_key,
            correlation_id,
            str(error),
        )

    payload = envelope["payload"]
    try:
        if str(payload.get("operation_id") or "").strip() != envelope["correlation_id"]:
            raise UTILS_Interdomain_Attendance.AttendanceInboxError(
                "correlation_id incohérente avec le payload"
            )
        resultat = (
            UTILS_Interdomain_Attendance.GestionnaireInboxAttendance(db)
            .AppliquerMessage(
                payload,
                envelope["idempotence_key"],
                source_domain=envelope["source_domain"],
                date_reception=date_reception,
            )
        )
    except UTILS_Interdomain_Attendance.AttendanceInboxError as error:
        return ConstruireAccuse(
            "rejected",
            envelope["idempotence_key"],
            envelope["correlation_id"],
            str(error),
        )

    if resultat.get("replay") is True:
        status = "replayed"
    elif resultat.get("applique") is True:
        status = "accepted"
    else:
        raise RuntimeError("résultat du consommateur de pointage indéterminé")
    return ConstruireAccuse(
        status,
        envelope["idempotence_key"],
        envelope["correlation_id"],
    )
