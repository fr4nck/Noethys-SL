#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Client pull sortant ``inter-domain-mailbox-pull/1`` du domaine activité/usagers.

Le transport HTTP est isolé de l'orchestration métier. Noethys initie uniquement
des connexions sortantes, reçoit une enveloppe ADR-012, la transmet à
``UTILS_Interdomain_Delivery`` puis renvoie l'accusé canonique.

Aucun jeton, secret HMAC ou nom de produit distant n'est stocké dans ce module.
"""
from __future__ import unicode_literals

import json
import socket
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from Utils import UTILS_Interdomain_Delivery
from Utils import UTILS_Interdomain_Secrets


MAILBOX_VERSION = "inter-domain-mailbox-pull/1"
TARGET_DOMAIN = "activity_users"
CLAIM_PATH = "/api/inter-domain/mailbox/v1/claim"
ACK_PATH_PREFIX = "/api/inter-domain/mailbox/v1/ack/"


class MailboxPullError(RuntimeError):
    pass


class MailboxTransportError(MailboxPullError):
    pass


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Refuse toute redirection pour ne jamais retransmettre le bearer ailleurs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _text(value, field, maximum):
    if not isinstance(value, str):
        raise MailboxPullError("%s obligatoire" % field)
    value = value.strip()
    if not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise MailboxPullError("%s invalide" % field)
    return value


def _limit(value):
    if type(value) is not int or value < 1 or value > 200:
        raise MailboxPullError("limit invalide")
    return value


def _delivery(value):
    if not isinstance(value, dict):
        raise MailboxPullError("livraison mailbox invalide")
    if value.get("mailbox_version") != MAILBOX_VERSION:
        raise MailboxPullError("version mailbox non supportée")
    if value.get("target_domain") != TARGET_DOMAIN:
        raise MailboxPullError("domaine cible mailbox inattendu")
    delivery_id = _text(value.get("delivery_id"), "delivery_id", 64)
    idempotence_key = _text(value.get("idempotence_key"), "idempotence_key", 255)
    correlation_id = _text(value.get("correlation_id"), "correlation_id", 128)
    signed = value.get("signed_delivery")
    if not isinstance(signed, dict):
        raise MailboxPullError("livraison signée absente")
    attempts = value.get("attempts")
    if type(attempts) is not int or attempts < 1:
        raise MailboxPullError("attempts invalide")
    return {
        "delivery_id": delivery_id,
        "idempotence_key": idempotence_key,
        "correlation_id": correlation_id,
        "signed_delivery": signed,
        "attempts": attempts,
    }


def _safe_detail(error):
    text = " ".join(("%s: %s" % (error.__class__.__name__, str(error))).split()).strip()
    return (text or "échec technique local")[:500]


class TransportMailboxHTTP(object):
    """Transport HTTPS sortant sans dépendance externe à ``requests``."""

    def __init__(self, base_url, bearer_token, timeout=20, opener=None):
        base_url = _text(base_url, "base_url", 512).rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise MailboxTransportError("base_url HTTPS invalide")
        self.base_url = base_url
        self.bearer_token = _text(bearer_token, "bearer_token", 512)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            raise MailboxTransportError("timeout invalide")
        if timeout < 1 or timeout > 300:
            raise MailboxTransportError("timeout invalide")
        self.timeout = timeout
        # urllib suit normalement les 30x et peut recopier Authorization vers la
        # nouvelle requête. Le client de mailbox refuse donc tout redirect :
        # l'URL d'exploitation doit être canonique et HTTPS dès le départ.
        self.opener = opener or urllib_request.build_opener(_NoRedirectHandler()).open

    def _post_json(self, path, payload):
        if not isinstance(payload, dict):
            raise MailboxTransportError("payload HTTP invalide")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        req = urllib_request.Request(
            self.base_url + path,
            data=data,
            headers={
                "Authorization": "Bearer " + self.bearer_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "activity-users-mailbox/1",
            },
            method="POST",
        )
        try:
            response = self.opener(req, timeout=self.timeout)
            raw = response.read()
            status = getattr(response, "status", getattr(response, "code", 200))
        except urllib_error.HTTPError as error:
            # Inclut volontairement les redirections refusées. Ne jamais recopier
            # Location ni le corps distant : ils peuvent contenir de l'infra.
            raise MailboxTransportError("mailbox HTTP refusée (%s)" % error.code)
        except (urllib_error.URLError, socket.timeout, OSError) as error:
            raise MailboxTransportError("mailbox HTTPS indisponible: %s" % error.__class__.__name__)
        if status < 200 or status >= 300:
            raise MailboxTransportError("mailbox HTTP inattendue (%s)" % status)
        try:
            decoded = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            result = json.loads(decoded)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise MailboxTransportError("réponse mailbox JSON invalide")
        if not isinstance(result, dict):
            raise MailboxTransportError("réponse mailbox invalide")
        return result

    def Reclamer(self, limit=20):
        limit = _limit(limit)
        result = self._post_json(CLAIM_PATH, {"limit": limit})
        deliveries = result.get("deliveries")
        if not isinstance(deliveries, list):
            raise MailboxTransportError("lot mailbox invalide")
        return tuple(deliveries)

    def Acquitter(self, delivery_id, receipt):
        delivery_id = _text(delivery_id, "delivery_id", 64)
        if not isinstance(receipt, dict):
            raise MailboxTransportError("accusé invalide")
        result = self._post_json(ACK_PATH_PREFIX + delivery_id, receipt)
        status = result.get("status")
        if status not in UTILS_Interdomain_Delivery.ACK_STATUSES:
            raise MailboxTransportError("statut d'acquittement distant invalide")
        return result


def ConstruireClientDepuisCoffre(base_url, key_ids, provider=None, timeout=20, opener=None):
    """Construit transport + keyring sans faire transiter les secrets par Config.json.

    ``base_url`` et ``key_ids`` sont des métadonnées non sensibles. Bearer et
    matière HMAC sont chargés uniquement via le ``SecretProvider``.
    """
    provider = provider or UTILS_Interdomain_Secrets.DefaultSecretProvider()
    try:
        bearer, keyring = UTILS_Interdomain_Secrets.ChargerSecretsMailbox(provider, key_ids)
    except UTILS_Interdomain_Secrets.SecretProviderError as error:
        raise MailboxPullError("chargement des secrets mailbox impossible: %s" % error) from error
    return TransportMailboxHTTP(
        base_url,
        bearer,
        timeout=timeout,
        opener=opener,
    ), keyring


def SynchroniserMailbox(db, transport, keyring, limit=20, date_reception=None):
    """Traite un lot borné et renvoie un résumé sans masquer les échecs réseau.

    Une panne avant ``claim`` laisse la mailbox distante intacte. Une panne d'ACK
    après application locale provoquera un replay après expiration de lease ; le
    consommateur Noethys étant idempotent, ce replay est sûr.
    """
    limit = _limit(limit)
    if transport is None or not callable(getattr(transport, "Reclamer", None)) or not callable(getattr(transport, "Acquitter", None)):
        raise MailboxPullError("transport mailbox invalide")
    if not isinstance(keyring, dict) or not keyring:
        raise MailboxPullError("keyring HMAC obligatoire")

    raw_deliveries = transport.Reclamer(limit=limit)
    if not isinstance(raw_deliveries, (tuple, list)):
        raise MailboxPullError("lot mailbox invalide")

    summary = {
        "claimed": len(raw_deliveries),
        "accepted": 0,
        "replayed": 0,
        "rejected": 0,
        "retryable": 0,
        "acked": 0,
    }
    for raw in raw_deliveries:
        item = _delivery(raw)
        try:
            receipt = UTILS_Interdomain_Delivery.RecevoirLivraisonSignee(
                db,
                item["signed_delivery"],
                keyring,
                date_reception=date_reception,
            )
        except Exception as error:
            # L'adaptateur ADR-012 propage volontairement les pannes techniques.
            # Le client de transport les transforme ici en ``retryable``.
            receipt = UTILS_Interdomain_Delivery.ConstruireAccuse(
                "retryable",
                item["idempotence_key"],
                item["correlation_id"],
                _safe_detail(error),
            )

        status = receipt.get("status")
        if status not in UTILS_Interdomain_Delivery.ACK_STATUSES:
            raise MailboxPullError("statut d'accusé local invalide")

        # Pour une enveloppe déterministement invalide, l'adaptateur ADR-012 peut
        # légitimement ne pas pouvoir faire confiance aux identifiants internes et
        # renvoyer ``invalid``. La mailbox externe, elle, a déjà fourni des
        # identifiants de livraison validés : on les utilise pour acquitter le
        # poison message comme ``rejected`` et empêcher une boucle sans fin.
        if status == "rejected" and (
            receipt.get("idempotence_key") != item["idempotence_key"]
            or receipt.get("correlation_id") != item["correlation_id"]
        ):
            receipt = UTILS_Interdomain_Delivery.ConstruireAccuse(
                "rejected",
                item["idempotence_key"],
                item["correlation_id"],
                str(receipt.get("detail") or "")[:500],
            )
        else:
            if receipt.get("idempotence_key") != item["idempotence_key"]:
                raise MailboxPullError("idempotence_key de l'accusé local incohérente")
            if receipt.get("correlation_id") != item["correlation_id"]:
                raise MailboxPullError("correlation_id de l'accusé local incohérente")

        summary[status] += 1
        transport.Acquitter(item["delivery_id"], receipt)
        summary["acked"] += 1
    return summary
