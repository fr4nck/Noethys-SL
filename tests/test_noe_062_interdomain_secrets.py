#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_Interdomain_Secrets as secrets
from Utils import UTILS_Interdomain_Mailbox_Client as mailbox_client


class MemoryProvider(secrets.SecretProvider):
    def __init__(self):
        self.values = {}

    def get(self, name):
        return self.values.get(name)

    def set(self, name, secret):
        self.values[name] = secret
        return True

    def delete(self, name):
        return self.values.pop(name, None) is not None


class InterdomainSecretsTests(unittest.TestCase):
    def test_logical_names_are_stable_and_product_agnostic(self):
        self.assertEqual(
            secrets.MAILBOX_BEARER,
            "mailbox/operations_portal/activity_users/bearer",
        )
        self.assertEqual(
            secrets.HmacSecretName("activity-2026-09"),
            "delivery/operations_portal/activity_users/hmac/activity-2026-09",
        )
        for forbidden in ("noethys", "connecthys", "teamworks"):
            self.assertNotIn(forbidden, secrets.MAILBOX_BEARER.lower())
            self.assertNotIn(forbidden, secrets.HMAC_PREFIX.lower())

    def test_invalid_names_and_plaintext_controls_are_rejected(self):
        for name in ("", " space", "../escape", "bad?name", "x" * 193):
            with self.assertRaises(secrets.SecretProviderError):
                secrets._logical_name(name)
        for value in ("", "secret\nleak"):
            with self.assertRaises(secrets.SecretProviderError):
                secrets._secret_bytes(value)

    def test_mailbox_secrets_are_loaded_separately(self):
        provider = MemoryProvider()
        provider.set(secrets.MAILBOX_BEARER, "mbx1.token.secret-value")
        provider.set(secrets.HmacSecretName("kid-1"), "h" * 32)
        provider.set(secrets.HmacSecretName("kid-2"), "j" * 48)

        bearer, keyring = secrets.ChargerSecretsMailbox(provider, ["kid-1", "kid-2"])

        self.assertEqual(bearer, "mbx1.token.secret-value")
        self.assertEqual(keyring["kid-1"], b"h" * 32)
        self.assertEqual(keyring["kid-2"], b"j" * 48)
        self.assertNotEqual(bearer.encode("utf-8"), keyring["kid-1"])

    def test_mailbox_client_is_built_from_vault_only(self):
        provider = MemoryProvider()
        provider.set(secrets.MAILBOX_BEARER, "mbx1.token.from-vault")
        provider.set(secrets.HmacSecretName("kid-1"), "k" * 32)

        transport, keyring = mailbox_client.ConstruireClientDepuisCoffre(
            "https://portal.example.test",
            ["kid-1"],
            provider=provider,
        )

        self.assertEqual(transport.base_url, "https://portal.example.test")
        self.assertEqual(transport.bearer_token, "mbx1.token.from-vault")
        self.assertEqual(keyring, {"kid-1": b"k" * 32})

    def test_missing_or_weak_secret_fails_closed(self):
        provider = MemoryProvider()
        with self.assertRaisesRegex(secrets.SecretProviderError, "bearer mailbox absent"):
            secrets.ChargerSecretsMailbox(provider, ["kid-1"])

        provider.set(secrets.MAILBOX_BEARER, "bearer")
        provider.set(secrets.HmacSecretName("kid-1"), "short")
        with self.assertRaisesRegex(secrets.SecretProviderError, "HMAC trop court"):
            secrets.ChargerSecretsMailbox(provider, ["kid-1"])

    def test_non_windows_default_provider_is_fail_closed(self):
        if sys.platform == "win32":
            self.skipTest("test réservé aux plateformes non-Windows")
        provider = secrets.DefaultSecretProvider()
        with self.assertRaises(secrets.SecretProviderUnavailable):
            provider.get(secrets.MAILBOX_BEARER)

    @unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager requis")
    def test_windows_credential_manager_roundtrip(self):
        namespace = "org.pelemele.test.%s" % uuid4().hex
        provider = secrets.WindowsCredentialManagerProvider(namespace=namespace)
        name = "mailbox/test/bearer"
        value = "credential-%s" % uuid4().hex
        try:
            self.assertIsNone(provider.get(name))
            self.assertTrue(provider.set(name, value))
            self.assertEqual(provider.get(name), value)
            self.assertTrue(provider.delete(name))
            self.assertIsNone(provider.get(name))
            self.assertFalse(provider.delete(name))
        finally:
            try:
                provider.delete(name)
            except secrets.SecretProviderError:
                pass


if __name__ == "__main__":
    unittest.main()
