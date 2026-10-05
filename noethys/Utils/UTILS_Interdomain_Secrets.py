#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stockage local protégé des secrets inter-domaines.

Le contrat ``SecretProvider`` isole le client mailbox du mécanisme de coffre.
Le premier backend utilise Windows Credential Manager via ``ctypes`` : aucun
secret n'est écrit dans Config.json, dans sa sauvegarde .bak ou dans le dépôt.

Le namespace et les noms logiques ne sont pas des secrets. Le backend peut être
remplacé plus tard (keyring système, HSM, identité de workload...) sans modifier
les contrats ADR-012/ADR-013 ni le client pull.
"""
from __future__ import unicode_literals

import ctypes
from ctypes import wintypes
import re
import sys


DEFAULT_NAMESPACE = "org.pelemele.inter-domain"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168
MAX_SECRET_BYTES = 2048
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")


class SecretProviderError(RuntimeError):
    pass


class SecretProviderUnavailable(SecretProviderError):
    pass


class SecretProvider(object):
    """Interface minimale d'un coffre de secrets local."""

    def get(self, name):
        raise NotImplementedError

    def set(self, name, secret):
        raise NotImplementedError

    def delete(self, name):
        raise NotImplementedError


class UnavailableSecretProvider(SecretProvider):
    """Backend fail-closed pour un environnement sans coffre supporté."""

    def __init__(self, reason="coffre de secrets indisponible"):
        self.reason = str(reason)

    def _raise(self):
        raise SecretProviderUnavailable(self.reason)

    def get(self, name):
        self._raise()

    def set(self, name, secret):
        self._raise()

    def delete(self, name):
        self._raise()


def _logical_name(value):
    if not isinstance(value, str):
        raise SecretProviderError("nom logique de secret obligatoire")
    normalized = value.strip()
    if value != normalized or not _NAME_RE.match(normalized):
        raise SecretProviderError("nom logique de secret invalide")
    return normalized


def _namespace(value):
    value = _logical_name(value)
    if len(value) > 128:
        raise SecretProviderError("namespace de secrets trop long")
    return value.rstrip("/")


def _secret_bytes(value):
    if not isinstance(value, str):
        raise SecretProviderError("secret texte obligatoire")
    if not value or any(ord(character) < 32 for character in value):
        raise SecretProviderError("secret texte invalide")
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_SECRET_BYTES:
        raise SecretProviderError("secret trop long")
    return encoded


if sys.platform == "win32":
    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]


    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


    PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
else:
    FILETIME = None
    CREDENTIALW = None
    PCREDENTIALW = None


class WindowsCredentialManagerProvider(SecretProvider):
    """Coffre utilisateur Windows Credential Manager, sans dépendance pywin32."""

    def __init__(self, namespace=DEFAULT_NAMESPACE, api=None):
        if sys.platform != "win32" and api is None:
            raise SecretProviderUnavailable("Windows Credential Manager indisponible sur cette plateforme")
        self.namespace = _namespace(namespace)
        self._api = api or self._load_api()

    @staticmethod
    def _load_api():
        try:
            library = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        except Exception as error:
            raise SecretProviderUnavailable("Windows Credential Manager indisponible") from error

        library.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
        library.CredWriteW.restype = wintypes.BOOL
        library.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(PCREDENTIALW),
        ]
        library.CredReadW.restype = wintypes.BOOL
        library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        library.CredDeleteW.restype = wintypes.BOOL
        library.CredFree.argtypes = [ctypes.c_void_p]
        library.CredFree.restype = None
        return library

    def _target(self, name):
        return "%s/%s" % (self.namespace, _logical_name(name))

    @staticmethod
    def _last_error():
        return ctypes.get_last_error()

    def get(self, name):
        target = self._target(name)
        pointer = PCREDENTIALW()
        if not self._api.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = self._last_error()
            if error == ERROR_NOT_FOUND:
                return None
            raise SecretProviderError("lecture du coffre Windows impossible (code %s)" % error)
        try:
            credential = pointer.contents
            size = int(credential.CredentialBlobSize)
            if size < 1 or size > MAX_SECRET_BYTES:
                raise SecretProviderError("taille du secret Windows invalide")
            raw = ctypes.string_at(credential.CredentialBlob, size)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise SecretProviderError("secret Windows non UTF-8") from error
        finally:
            self._api.CredFree(pointer)

    def set(self, name, secret):
        target = self._target(name)
        encoded = _secret_bytes(secret)
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = CREDENTIALW()
        credential.Flags = 0
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.Comment = "PMSL inter-domain secret"
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.AttributeCount = 0
        credential.Attributes = None
        credential.TargetAlias = None
        credential.UserName = self.namespace
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            error = self._last_error()
            raise SecretProviderError("écriture du coffre Windows impossible (code %s)" % error)
        return True

    def delete(self, name):
        target = self._target(name)
        if self._api.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
            return True
        error = self._last_error()
        if error == ERROR_NOT_FOUND:
            return False
        raise SecretProviderError("suppression du coffre Windows impossible (code %s)" % error)


def DefaultSecretProvider(namespace=DEFAULT_NAMESPACE):
    """Retourne le coffre natif supporté ou un provider explicitement indisponible."""
    if sys.platform == "win32":
        return WindowsCredentialManagerProvider(namespace=namespace)
    return UnavailableSecretProvider("aucun backend de secrets local supporté sur cette plateforme")


# Noms logiques du vertical actuel. Ils ne contiennent ni produit ni hostname.
MAILBOX_BEARER = "mailbox/operations_portal/activity_users/bearer"
HMAC_PREFIX = "delivery/operations_portal/activity_users/hmac/"


def HmacSecretName(key_id):
    key_id = _logical_name(key_id)
    return HMAC_PREFIX + key_id


def ChargerSecretsMailbox(provider, key_ids):
    """Charge séparément le bearer du canal et les clés HMAC ADR-012.

    Les clés HMAC sont stockées comme texte de forte entropie puis converties en
    bytes au dernier moment pour l'adaptateur de livraison. Aucun fallback vers
    Config.json ou une variable vide n'est autorisé.
    """
    if provider is None or not callable(getattr(provider, "get", None)):
        raise SecretProviderError("SecretProvider invalide")
    if not isinstance(key_ids, (tuple, list)) or not key_ids:
        raise SecretProviderError("au moins un key_id HMAC est requis")

    bearer = provider.get(MAILBOX_BEARER)
    if not isinstance(bearer, str) or not bearer:
        raise SecretProviderError("bearer mailbox absent du coffre")

    keyring = {}
    for raw_key_id in key_ids:
        key_id = _logical_name(raw_key_id)
        if key_id in keyring:
            raise SecretProviderError("key_id HMAC dupliqué")
        secret = provider.get(HmacSecretName(key_id))
        if not isinstance(secret, str) or not secret:
            raise SecretProviderError("secret HMAC absent du coffre pour %s" % key_id)
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise SecretProviderError("secret HMAC trop court pour %s" % key_id)
        keyring[key_id] = encoded
    return bearer, keyring
