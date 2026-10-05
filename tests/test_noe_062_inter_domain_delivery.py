# -*- coding: utf-8 -*-
import hashlib
import hmac
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))


def _charger_module(path, nom):
    spec = importlib.util.spec_from_file_location(nom, str(ROOT / path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DELIVERY = _charger_module(
    "noethys/Utils/UTILS_Interdomain_Delivery.py",
    "UTILS_Interdomain_Delivery_noe062_test",
)
FIXTURE = _charger_module(
    "tests/test_noe_062_session_actual_inbox.py",
    "test_noe_062_session_actual_inbox_fixture",
)
ATTENDANCE_FIXTURE = _charger_module(
    "tests/test_noe_062_session_attendance_inbox.py",
    "test_noe_062_session_attendance_inbox_fixture",
)


SECRET_A = b"a" * 32
SECRET_B = b"b" * 32
KEY_ID = "activity-2026-01"
EXPECTED_VECTOR_SIGNATURE = "5465917b1e13104c0494c562c0458f0751c2fc9947d0c0a55dce82cf04adb5a5"


def _signer(envelope, secret):
    serialise = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(secret, serialise.encode("utf-8"), hashlib.sha256).hexdigest()


def livraison(payload=None, secret=SECRET_A, key_id=KEY_ID, **overrides):
    payload = payload or FIXTURE.payload_realise()
    envelope = {
        "envelope_version": "inter-domain-delivery/1",
        "source_domain": "operations_portal",
        "target_domain": "activity_users",
        "contract_version": "session-actual/1",
        "event_type": "session_actual_validated",
        "idempotence_key": "session-actual:%s:r%d:activity_users" % (
            payload["actual_uuid"], payload["actual_revision"]
        ),
        "correlation_id": payload["actual_uuid"],
        "occurred_at": "2026-09-04T10:46:00Z",
        "key_id": key_id,
        "payload": payload,
    }
    envelope.update(overrides)
    return {"envelope": envelope, "signature": _signer(envelope, secret)}


def livraison_attendance(payload=None, secret=SECRET_A, key_id=KEY_ID, **overrides):
    payload = payload or ATTENDANCE_FIXTURE.payload()
    envelope = {
        "envelope_version": "inter-domain-delivery/1",
        "source_domain": "operations_portal",
        "target_domain": "activity_users",
        "contract_version": "session-attendance/1",
        "event_type": "session_attendance_changed",
        "idempotence_key": ATTENDANCE_FIXTURE.idempotence(
            payload["operation_id"]
        ),
        "correlation_id": payload["operation_id"],
        "occurred_at": "2026-09-19T09:00:00Z",
        "key_id": key_id,
        "payload": payload,
    }
    envelope.update(overrides)
    return {"envelope": envelope, "signature": _signer(envelope, secret)}


class Noe062InterDomainDeliveryTests(unittest.TestCase):

    def test_vecteur_hmac_est_identique_a_la_reference_portail(self):
        signed = livraison()
        self.assertEqual(EXPECTED_VECTOR_SIGNATURE, signed["signature"])
        verified = DELIVERY.VerifierEnveloppe(signed, {KEY_ID: SECRET_A})
        self.assertEqual("activity_users", verified["target_domain"])
        self.assertEqual(FIXTURE.ACTUAL_UUID, verified["correlation_id"])
        self.assertEqual(FIXTURE.payload_realise(), verified["payload"])

    def test_payload_altere_apres_signature_est_refuse(self):
        signed = livraison()
        signed["envelope"]["payload"]["actual_revision"] = 5
        with self.assertRaisesRegex(DELIVERY.DeliveryEnvelopeError, "signature HMAC invalide"):
            DELIVERY.VerifierEnveloppe(signed, {KEY_ID: SECRET_A})

    def test_mauvaise_cible_et_key_id_inconnu_sont_refuses(self):
        wrong_target = livraison(target_domain="hr_employment")
        with self.assertRaisesRegex(DELIVERY.DeliveryEnvelopeError, "domaine cible inattendu"):
            DELIVERY.VerifierEnveloppe(wrong_target, {KEY_ID: SECRET_A})

        signed = livraison()
        with self.assertRaisesRegex(DELIVERY.DeliveryEnvelopeError, "key_id inconnu"):
            DELIVERY.VerifierEnveloppe(signed, {"activity-old": SECRET_A})

    def test_rotation_de_cle_accepte_chaque_secret_associe_a_son_key_id(self):
        old = livraison(secret=SECRET_A, key_id="activity-old")
        new = livraison(secret=SECRET_B, key_id="activity-new")
        keyring = {"activity-old": SECRET_A, "activity-new": SECRET_B}
        self.assertEqual("activity-old", DELIVERY.VerifierEnveloppe(old, keyring)["key_id"])
        self.assertEqual("activity-new", DELIVERY.VerifierEnveloppe(new, keyring)["key_id"])

    def test_livraison_valide_est_appliquee_puis_rejouee_sans_doublon(self):
        db = FIXTURE._db_pret()
        try:
            signed = livraison()
            first = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-09-04 10:46:00",
            )
            second = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-09-04 10:47:00",
            )
            self.assertEqual("accepted", first["status"])
            self.assertEqual("replayed", second["status"])
            self.assertEqual(first["idempotence_key"], second["idempotence_key"])
            self.assertEqual(FIXTURE.ACTUAL_UUID, first["correlation_id"])
            db.cursor.execute("SELECT COUNT(*) FROM interventions")
            self.assertEqual(1, db.cursor.fetchone()[0])
            db.cursor.execute("SELECT COUNT(*) FROM interventions_execution_inbox")
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_erreur_metier_deterministe_est_un_rejet_sans_ecriture(self):
        db = FIXTURE._db_pret()
        try:
            invalid_payload = FIXTURE.payload_realise(actual_duration_minutes=91)
            receipt = DELIVERY.RecevoirLivraisonSignee(
                db,
                livraison(payload=invalid_payload),
                {KEY_ID: SECRET_A},
                date_reception="2026-09-04 10:46:00",
            )
            self.assertEqual("rejected", receipt["status"])
            self.assertIn("durée réelle incohérente", receipt["detail"])
            db.cursor.execute("SELECT COUNT(*) FROM interventions_execution_inbox")
            self.assertEqual(0, db.cursor.fetchone()[0])
            db.cursor.execute("SELECT statut FROM interventions WHERE uid=?", (FIXTURE.SESSION_UID,))
            self.assertEqual("planifiee", db.cursor.fetchone()[0])
        finally:
            db.Close()


    def test_pointage_valide_est_applique_puis_rejoue_et_acke(self):
        db = ATTENDANCE_FIXTURE._db_pret()
        try:
            signed = livraison_attendance()
            first = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-09-19 09:00:01",
            )
            second = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-09-19 09:00:02",
            )
            self.assertEqual("accepted", first["status"])
            self.assertEqual("replayed", second["status"])
            self.assertEqual(
                ATTENDANCE_FIXTURE.OPERATION_UUID,
                first["correlation_id"],
            )
            db.cursor.execute(
                "SELECT IDindividu,etat FROM consommations WHERE IDgroupe=3 ORDER BY IDindividu"
            )
            self.assertEqual(
                [(42, "present"), (43, "absenti"), (44, "absentj")],
                db.cursor.fetchall(),
            )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_pointage_correlation_incoherente_est_rejete_sans_ecriture(self):
        db = ATTENDANCE_FIXTURE._db_pret()
        try:
            signed = livraison_attendance(
                correlation_id="cccccccc-cccc-cccc-cccc-cccccccccccc"
            )
            receipt = DELIVERY.RecevoirLivraisonSignee(
                db,
                signed,
                {KEY_ID: SECRET_A},
                date_reception="2026-09-19 09:00:01",
            )
            self.assertEqual("rejected", receipt["status"])
            self.assertIn("correlation_id", receipt["detail"])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_signature_invalide_produit_un_rejet_et_ne_touche_pas_la_base(self):
        db = FIXTURE._db_pret()
        try:
            signed = livraison()
            signed["signature"] = "0" * 64
            receipt = DELIVERY.RecevoirLivraisonSignee(db, signed, {KEY_ID: SECRET_A})
            self.assertEqual("rejected", receipt["status"])
            self.assertIn("signature HMAC invalide", receipt["detail"])
            db.cursor.execute("SELECT COUNT(*) FROM interventions_execution_inbox")
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_panne_technique_inattendue_n_est_pas_masquee_en_rejected(self):
        signed = livraison()
        with self.assertRaises(AttributeError):
            DELIVERY.RecevoirLivraisonSignee(None, signed, {KEY_ID: SECRET_A})


if __name__ == "__main__":
    unittest.main()
