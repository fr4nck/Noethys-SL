#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Coffre local des secrets inter-domaines.

Le client mailbox ne reçoit jamais ses secrets depuis Config.json. Le backend
Windows s'appuie uniquement sur Credential Manager via ctypes. Sur toute autre
plateforme, le provider par défaut échoue fermé.

Les noms logiques et key_id ne sont pas des secrets ; bearer et matière HMAC
restent dans le coffre et ne sont chargés qu'au moment de construire le client.
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
MAX_HMAC_KEYS = 8
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")


class SecretProviderError(RuntimeError):
    pass


class SecretProviderUnavailable(SecretProviderError):
    pass


class SecretProvider(object):
    def get(self, name):
        raise NotImplementedError

    def set(self, name, secret):
        raise NotImplementedError

    def delete(self, name):
        raise NotImplementedError


class UnavailableSecretProvider(SecretProvider):
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
    """Coffre Credential Manager de l'utilisateur Windows courant."""

    def __init__(self, namespace=DEFAULT_NAMESPACE, api=None):
        if sys.platform != "win32" and api is None:
            raise SecretProviderUnavailable(
                "Windows Credential Manager indisponible sur cette plateforme"
            )
        self.namespace = _namespace(namespace)
        self._api = api or self._load_api()

    @staticmethod
    def _load_api():
        try:
            library = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        except Exception as error:
            raise SecretProviderUnavailable(
                "Windows Credential Manager indisponible"
            ) from error

        library.CredWriteW.argtypes = [
            ctypes.POINTER(CREDENTIALW),
            wintypes.DWORD,
        ]
        library.CredWriteW.restype = wintypes.BOOL
        library.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(PCREDENTIALW),
        ]
        library.CredReadW.restype = wintypes.BOOL
        library.CredDeleteW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
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
        if not self._api.CredReadW(
            target,
            CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            error = self._last_error()
            if error == ERROR_NOT_FOUND:
                return None
            raise SecretProviderError(
                "lecture du coffre Windows impossible (code %s)" % error
            )
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
        credential.Comment = "Inter-domain application secret"
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(
            blob,
            ctypes.POINTER(ctypes.c_ubyte),
        )
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.AttributeCount = 0
        credential.Attributes = None
        credential.TargetAlias = None
        credential.UserName = self.namespace
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            error = self._last_error()
            raise SecretProviderError(
                "écriture du coffre Windows impossible (code %s)" % error
            )
        return True

    def delete(self, name):
        target = self._target(name)
        if self._api.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
            return True
        error = self._last_error()
        if error == ERROR_NOT_FOUND:
            return False
        raise SecretProviderError(
            "suppression du coffre Windows impossible (code %s)" % error
        )


def DefaultSecretProvider(namespace=DEFAULT_NAMESPACE):
    if sys.platform == "win32":
        return WindowsCredentialManagerProvider(namespace=namespace)
    return UnavailableSecretProvider(
        "aucun backend de secrets local supporté sur cette plateforme"
    )


MAILBOX_BEARER = "mailbox/operations_portal/activity_users/bearer"
HMAC_PREFIX = "delivery/operations_portal/activity_users/hmac/"


def HmacSecretName(key_id):
    return HMAC_PREFIX + _logical_name(key_id)


def ChargerSecretsMailbox(provider, key_ids):
    if provider is None or not callable(getattr(provider, "get", None)):
        raise SecretProviderError("SecretProvider invalide")
    if not isinstance(key_ids, (tuple, list)) or not key_ids:
        raise SecretProviderError("au moins un key_id HMAC est requis")
    if len(key_ids) > MAX_HMAC_KEYS:
        raise SecretProviderError("trop de key_id HMAC")

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
            raise SecretProviderError(
                "secret HMAC absent du coffre pour %s" % key_id
            )
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise SecretProviderError(
                "secret HMAC trop court pour %s" % key_id
            )
        keyring[key_id] = encoded
    return bearer, keyring
