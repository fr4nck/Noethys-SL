# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_Interdomain_Delivery as DELIVERY
from tests import test_noethys_sl_interdomain_attendance as FIXTURE


SECRET_A = b"a" * 32
SECRET_B = b"b" * 32
KEY_ID = "activity-2026-10"
EXPECTED_VECTOR_SIGNATURE = (
    "582830ad244bf3e31acdc92bd87156b85d1a97f8941215c849637061f6368df9"
)


def signer(envelope, secret):
    serialise = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hmac.new(secret, serialise.encode("utf-8"), hashlib.sha256).hexdigest()


def livraison(payload=None, secret=SECRET_A, key_id=KEY_ID, **overrides):
    payload = payload or FIXTURE.payload()
    envelope = {
        "envelope_version": "inter-domain-delivery/1",
        "source_domain": "operations_portal",
        "target_domain": "activity_users",
        "contract_version": "session-attendance/1",
        "event_type": "session_attendance_changed",
        "idempotence_key": FIXTURE.idempotence(payload["operation_id"]),
        "correlation_id": payload["operation_id"],
        "occurred_at": "2026-10-28T08:00:00Z",
        "key_id": key_id,
        "payload": payload,
    }
    envelope.update(overrides)
    return {
        "envelope": envelope,
        "signature": signer(envelope, secret),
    }


class InterdomainDeliveryTests(unittest.TestCase):
    def test_vecteur_hmac_est_compatible_avec_portails(self):
        signed = livraison()
        self.assertEqual(EXPECTED_VECTOR_SIGNATURE, signed["signature"])
        verified = DELIVERY.VerifierEnveloppe(
            signed, {KEY_ID: SECRET_A}
        )
        self.assertEqual("activity_users", verified["target_domain"])
        self.assertEqual(FIXTURE.OPERATION_UUID, verified["correlation_id"])
        self.assertEqual(FIXTURE.payload(), verified["payload"])

    def test_pointage_signe_est_accepte_puis_rejoue_sans_doublon(self):
        db = FIXTURE.ready_db()
        try:
            signed = livraison()
            first = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-10-28 09:00:01",
            )
            second = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-10-28 09:00:02",
            )
            self.assertEqual("accepted", first["status"])
            self.assertEqual("replayed", second["status"])
            self.assertEqual(
                FIXTURE.OPERATION_UUID, first["correlation_id"]
            )
            db.cursor.execute(
                "SELECT IDindividu,etat FROM consommations "
                "WHERE IDunite=5 ORDER BY IDconso"
            )
            self.assertEqual(
                [(42, "present"), (43, "absenti"), (44, "absentj")],
                db.cursor.fetchall(),
            )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_payload_modifie_apres_signature_est_rejete_sans_ecriture(self):
        db = FIXTURE.ready_db()
        try:
            signed = livraison()
            signed["envelope"]["payload"]["changes"][0]["status"] = "absent"
            receipt = DELIVERY.RecevoirLivraisonSignee(
                db, signed, {KEY_ID: SECRET_A}
            )
            self.assertEqual("rejected", receipt["status"])
            self.assertIn("signature HMAC invalide", receipt["detail"])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_correlation_incoherente_est_rejetee_sans_ecriture(self):
        db = FIXTURE.ready_db()
        try:
            receipt = DELIVERY.RecevoirLivraisonSignee(
                db,
                livraison(
                    correlation_id="cccccccc-cccc-cccc-cccc-cccccccccccc"
                ),
                {KEY_ID: SECRET_A},
            )
            self.assertEqual("rejected", receipt["status"])
            self.assertIn("correlation_id", receipt["detail"])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_cible_incorrecte_et_key_id_inconnu_sont_refuses(self):
        with self.assertRaisesRegex(
            DELIVERY.DeliveryEnvelopeError, "domaine cible inattendu"
        ):
            DELIVERY.VerifierEnveloppe(
                livraison(target_domain="hr_employment"),
                {KEY_ID: SECRET_A},
            )
        with self.assertRaisesRegex(
            DELIVERY.DeliveryEnvelopeError, "key_id inconnu"
        ):
            DELIVERY.VerifierEnveloppe(
                livraison(),
                {"activity-old": SECRET_A},
            )

    def test_rotation_de_cle_accepte_les_deux_key_ids(self):
        old = livraison(secret=SECRET_A, key_id="activity-old")
        new = livraison(secret=SECRET_B, key_id="activity-new")
        keyring = {
            "activity-old": SECRET_A,
            "activity-new": SECRET_B,
        }
        self.assertEqual(
            "activity-old",
            DELIVERY.VerifierEnveloppe(old, keyring)["key_id"],
        )
        self.assertEqual(
            "activity-new",
            DELIVERY.VerifierEnveloppe(new, keyring)["key_id"],
        )

    def test_panne_technique_locale_n_est_pas_masquee_en_rejected(self):
        with self.assertRaises(AttributeError):
            DELIVERY.RecevoirLivraisonSignee(
                None,
                livraison(),
                {KEY_ID: SECRET_A},
            )


if __name__ == "__main__":
    unittest.main()
