#!/usr/bin/env python3
from pathlib import Path
import hashlib
import hmac
import json
import sys
import unittest
from unittest.mock import patch
from urllib import error as urllib_error

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_Interdomain_Mailbox_Client as client
from tests import test_noethys_sl_interdomain_attendance as FIXTURE


SECRET = b"s" * 32
KEY_ID = "activity-2026-10"
CORRELATION = FIXTURE.OPERATION_UUID
IDEMPOTENCE = FIXTURE.idempotence()
DELIVERY_ID = "22222222-2222-2222-2222-222222222222"


def signed_delivery():
    payload = FIXTURE.payload()
    envelope = {
        "envelope_version": "inter-domain-delivery/1",
        "source_domain": "operations_portal",
        "target_domain": "activity_users",
        "contract_version": "session-attendance/1",
        "event_type": "session_attendance_changed",
        "idempotence_key": IDEMPOTENCE,
        "correlation_id": CORRELATION,
        "occurred_at": "2026-10-28T08:00:00Z",
        "key_id": KEY_ID,
        "payload": payload,
    }
    raw = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return {
        "envelope": envelope,
        "signature": hmac.new(SECRET, raw, hashlib.sha256).hexdigest(),
    }


def delivery(target="activity_users", signed=None):
    return {
        "mailbox_version": "inter-domain-mailbox-pull/1",
        "delivery_id": DELIVERY_ID,
        "target_domain": target,
        "idempotence_key": IDEMPOTENCE,
        "correlation_id": CORRELATION,
        "attempts": 1,
        "signed_delivery": signed or signed_delivery(),
    }


class FakeTransport:
    def __init__(self, deliveries=None, ack_error=None):
        self.deliveries = list(deliveries or [])
        self.acks = []
        self.ack_error = ack_error

    def Reclamer(self, limit=20):
        self.limit = limit
        return tuple(self.deliveries)

    def Acquitter(self, delivery_id, receipt):
        if self.ack_error:
            raise self.ack_error
        self.acks.append((delivery_id, dict(receipt)))
        return {"status": receipt["status"]}


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MailboxClientTests(unittest.TestCase):
    def test_real_consumer_is_accepted_then_replayed_without_network(self):
        db = FIXTURE.ready_db()
        try:
            transport = FakeTransport([delivery()])
            first = client.SynchroniserMailbox(
                db,
                transport,
                {KEY_ID: SECRET},
                date_reception="2026-10-28 09:00:01",
            )
            second_transport = FakeTransport([delivery()])
            second = client.SynchroniserMailbox(
                db,
                second_transport,
                {KEY_ID: SECRET},
                date_reception="2026-10-28 09:00:02",
            )
            self.assertEqual(1, first["accepted"])
            self.assertEqual(1, second["replayed"])
            self.assertEqual(
                "accepted",
                transport.acks[0][1]["status"],
            )
            self.assertEqual(
                "replayed",
                second_transport.acks[0][1]["status"],
            )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_technical_consumer_failure_becomes_retryable_ack(self):
        transport = FakeTransport([delivery()])
        with patch.object(
            client.UTILS_Interdomain_Delivery,
            "RecevoirLivraisonSignee",
            side_effect=RuntimeError("db offline"),
        ):
            summary = client.SynchroniserMailbox(
                object(),
                transport,
                {"kid": b"x" * 32},
            )
        self.assertEqual(1, summary["retryable"])
        self.assertEqual(
            "retryable",
            transport.acks[0][1]["status"],
        )
        self.assertNotIn(
            "Bearer",
            transport.acks[0][1].get("detail", ""),
        )

    def test_malformed_signed_delivery_is_acked_rejected_with_outer_ids(self):
        transport = FakeTransport([delivery()])
        rejected = {
            "status": "rejected",
            "idempotence_key": "invalid",
            "correlation_id": "invalid",
            "detail": "signature HMAC invalide",
        }
        with patch.object(
            client.UTILS_Interdomain_Delivery,
            "RecevoirLivraisonSignee",
            return_value=rejected,
        ):
            summary = client.SynchroniserMailbox(
                object(),
                transport,
                {"kid": b"x" * 32},
            )
        self.assertEqual(1, summary["rejected"])
        ack = transport.acks[0][1]
        self.assertEqual(IDEMPOTENCE, ack["idempotence_key"])
        self.assertEqual(CORRELATION, ack["correlation_id"])

    def test_identifier_mismatch_still_fails_closed(self):
        transport = FakeTransport([delivery()])
        inconsistent = {
            "status": "accepted",
            "idempotence_key": "wrong",
            "correlation_id": CORRELATION,
            "detail": "",
        }
        with patch.object(
            client.UTILS_Interdomain_Delivery,
            "RecevoirLivraisonSignee",
            return_value=inconsistent,
        ):
            with self.assertRaises(client.MailboxPullError):
                client.SynchroniserMailbox(
                    object(),
                    transport,
                    {"kid": b"x" * 32},
                )
        self.assertEqual([], transport.acks)

    def test_ack_failure_is_not_swallowed_after_local_apply(self):
        transport = FakeTransport(
            [delivery()],
            ack_error=client.MailboxTransportError("offline"),
        )
        receipt = {
            "status": "accepted",
            "idempotence_key": IDEMPOTENCE,
            "correlation_id": CORRELATION,
            "detail": "",
        }
        with patch.object(
            client.UTILS_Interdomain_Delivery,
            "RecevoirLivraisonSignee",
            return_value=receipt,
        ):
            with self.assertRaises(client.MailboxTransportError):
                client.SynchroniserMailbox(
                    object(),
                    transport,
                    {"kid": b"x" * 32},
                )

    def test_other_domain_is_rejected_before_consumer(self):
        transport = FakeTransport(
            [delivery(target="hr_employment")]
        )
        with patch.object(
            client.UTILS_Interdomain_Delivery,
            "RecevoirLivraisonSignee",
        ) as receive:
            with self.assertRaises(client.MailboxPullError):
                client.SynchroniserMailbox(
                    object(),
                    transport,
                    {"kid": b"x" * 32},
                )
        receive.assert_not_called()

    def test_delivery_id_must_be_uuid_before_ack_path(self):
        malformed = delivery()
        malformed["delivery_id"] = "../escape"
        transport = FakeTransport([malformed])
        with self.assertRaisesRegex(
            client.MailboxPullError,
            "delivery_id invalide",
        ):
            client.SynchroniserMailbox(
                object(),
                transport,
                {"kid": b"x" * 32},
            )
        self.assertEqual([], transport.acks)

    def test_http_transport_requires_safe_https_and_header_only_bearer(self):
        for url in (
            "http://example.invalid",
            "https://user:pass@example.invalid",
        ):
            with self.subTest(url=url):
                with self.assertRaises(client.MailboxTransportError):
                    client.TransportMailboxHTTP(url, "secret")

        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.headers.get("Authorization")
            seen["body"] = request.data
            return FakeResponse({"deliveries": []})

        transport = client.TransportMailboxHTTP(
            "https://portal.example.test",
            "mbx1.token.secret-value-long-enough-for-test",
            opener=opener,
        )
        self.assertEqual((), transport.Reclamer(limit=3))
        self.assertEqual(
            "Bearer mbx1.token.secret-value-long-enough-for-test",
            seen["auth"],
        )
        self.assertNotIn(b"secret-value", seen["body"])
        self.assertTrue(seen["url"].endswith(client.CLAIM_PATH))

    def test_default_http_opener_refuses_redirects(self):
        request = __import__(
            "urllib.request",
            fromlist=["Request"],
        ).Request(
            "https://portal.example.test" + client.CLAIM_PATH,
            data=b"{}",
            headers={"Authorization": "Bearer secret"},
            method="POST",
        )
        handler = client._NoRedirectHandler()
        self.assertIsNone(
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {"Location": "http://attacker.invalid/steal"},
                "http://attacker.invalid/steal",
            )
        )

    def test_redirect_error_does_not_expose_location(self):
        def redirecting(request, timeout):
            raise urllib_error.HTTPError(
                request.full_url,
                302,
                "Found",
                {"Location": "http://attacker.invalid/steal"},
                None,
            )

        transport = client.TransportMailboxHTTP(
            "https://portal.example.test",
            "mbx1.token.secret-value-long-enough-for-test",
            opener=redirecting,
        )
        with self.assertRaises(client.MailboxTransportError) as error:
            transport.Reclamer()
        self.assertIn("302", str(error.exception))
        self.assertNotIn("attacker.invalid", str(error.exception))


if __name__ == "__main__":
    unittest.main()
