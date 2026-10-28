# -*- coding: utf-8 -*-
"""Qualification session-attendance/1 sur MySQL 5.7 local jetable.

La garde réseau n'autorise que le serveur déclaré sur 127.0.0.1. Chaque test
crée une base zz_test_attendance_* inexistante, utilise les vraies définitions
DATA_Tables de Noethys, puis supprime entièrement la base.
"""
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "noethys", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import _garde_reseau  # noqa: E402
import GestionDB  # noqa: E402
from Data import DATA_Tables as TABLES  # noqa: E402
from Utils import UTILS_Interdomain_Attendance as ATTENDANCE  # noqa: E402
from Utils import UTILS_Interdomain_Attendance_Schema as SCHEMA  # noqa: E402


PREFIX = "zz_test_attendance_"
SESSION_UID = "PORTAIL-MYSQL-SESSION-001"
ASSIGNMENT_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OPERATION_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _payload(operation=OPERATION_UUID, changes=None):
    return {
        "contract_version": "session-attendance/1",
        "event_type": "session_attendance_changed",
        "operation_id": operation,
        "assignment_uuid": ASSIGNMENT_UUID,
        "session_uid": SESSION_UID,
        "occurred_at": "2026-10-28T09:00:00+01:00",
        "changes": changes
        or [
            {"participant_uid": "42", "status": "present"},
            {"participant_uid": "43", "status": "absent"},
        ],
    }


def _idempotence(operation=OPERATION_UUID):
    return "session-attendance:%s:activity_users" % operation


def _create_domain_schema(db):
    for table in (
        "activites",
        "groupes",
        "ouvertures",
        "evenements",
        "prestations",
        "consommations",
    ):
        db.CreationTable(table, TABLES.DB_DATA)

    db.ReqInsert(
        "activites",
        [("IDactivite", 7), ("nom", u"Activité fictive pointage")],
    )
    db.ReqInsert(
        "groupes",
        [
            ("IDgroupe", 3),
            ("IDactivite", 7),
            ("nom", u"Groupe fictif"),
        ],
    )
    db.ReqInsert(
        "ouvertures",
        [
            ("IDactivite", 7),
            ("IDunite", 5),
            ("IDgroupe", 3),
            ("date", "2026-10-28"),
        ],
    )


def _insert_consumption(
    db,
    participant,
    status="reservation",
    locked=0,
    prestation=None,
):
    db.ReqInsert(
        "consommations",
        [
            ("IDindividu", participant),
            ("IDactivite", 7),
            ("date", "2026-10-28"),
            ("IDunite", 5),
            ("IDgroupe", 3),
            ("etat", status),
            ("verrouillage", locked),
            ("IDprestation", prestation),
        ],
    )


@unittest.skipUnless(
    _garde_reseau.ParametresMySQLDeTest(),
    "serveur MySQL local jetable non déclaré",
)
class InterdomainAttendanceMySQLTests(unittest.TestCase):
    def setUp(self):
        self.server = _garde_reseau.ServeurMySQLDeTest()
        params = self.server.__enter__()
        self.base = PREFIX + uuid.uuid4().hex[:12]
        self.root = "%d;%s;%s;%s[RESEAU]" % (
            params["port"],
            params["hote"],
            params["utilisateur"],
            GestionDB.EncodeMdpReseau(params["motdepasse"]),
        )
        self.nom = self.root + self.base

        root_db = GestionDB.DB(nomFichier=self.root, suffixe=None)
        self.assertEqual(
            0,
            root_db.echec,
            getattr(root_db, "erreur", ""),
        )
        root_db.cursor.execute("SHOW DATABASES;")
        self.assertNotIn(
            self.base,
            [row[0] for row in root_db.cursor.fetchall()],
        )
        root_db.Close()

        db = GestionDB.DB(
            nomFichier=self.nom,
            suffixe=None,
            modeCreation=True,
        )
        self.assertEqual(0, db.echec, getattr(db, "erreur", ""))
        _create_domain_schema(db)
        result = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
        self.assertTrue(result["ok"], result)
        db.ReqInsert(
            "interdomain_attendance_sessions",
            [
                ("session_uid", SESSION_UID),
                ("IDactivite", 7),
                ("IDgroupe", 3),
                ("IDunite", 5),
                ("IDevenement", None),
                ("date", "2026-10-28"),
                ("actif", 1),
                ("date_creation", "2026-10-28 09:00:00"),
            ],
        )
        _insert_consumption(db, 42)
        _insert_consumption(db, 43)
        db.Close()

    def tearDown(self):
        try:
            if self.base.startswith(PREFIX):
                db = GestionDB.DB(nomFichier=self.root, suffixe=None)
                if db.echec == 0:
                    db.cursor.execute("DROP DATABASE %s;" % self.base)
                    db.Close()
        finally:
            self.server.__exit__(None, None, None)

    def _db(self):
        db = GestionDB.DB(nomFichier=self.nom, suffixe=None)
        self.assertEqual(0, db.echec, getattr(db, "erreur", ""))
        return db

    def test_schema_consumer_and_exact_replay_on_mysql57(self):
        db = self._db()
        try:
            second = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
            self.assertTrue(second["ok"])
            self.assertEqual((), second["tables_creees"])

            service = ATTENDANCE.GestionnaireInboxAttendance(db)
            first = service.AppliquerMessage(
                _payload(),
                _idempotence(),
                date_reception="2026-10-28 09:00:01",
            )
            replay = service.AppliquerMessage(
                _payload(),
                _idempotence(),
                date_reception="2026-10-28 09:00:02",
            )
            self.assertTrue(first["applique"])
            self.assertEqual(2, first["applied_rows"])
            self.assertTrue(replay["replay"])

            db.ExecuterReq(
                "SELECT IDindividu,etat FROM consommations "
                "WHERE IDunite=5 ORDER BY IDindividu;"
            )
            self.assertEqual(
                [(42, "present"), (43, "absenti")],
                list(db.ResultatReq()),
            )
            db.ExecuterReq(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox;"
            )
            self.assertEqual(1, int(db.ResultatReq()[0][0]))
        finally:
            db.Close()

    def test_locked_and_billed_consumptions_fail_closed_on_mysql57(self):
        db = self._db()
        try:
            _insert_consumption(db, 44, locked=1)
            db.ReqInsert(
                "prestations",
                [
                    ("IDprestation", 100),
                    ("IDcompte_payeur", 1),
                    ("date", "2026-10-28"),
                    ("categorie", "consommation"),
                    ("label", u"Prestation fictive"),
                    ("montant_initial", 1.0),
                    ("montant", 1.0),
                    ("IDfacture", 200),
                ],
            )
            _insert_consumption(db, 45, prestation=100)

            service = ATTENDANCE.GestionnaireInboxAttendance(db)
            for operation, participant, expected in (
                (
                    "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    "44",
                    "verrouillée",
                ),
                (
                    "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "45",
                    "déjà facturée",
                ),
            ):
                with self.subTest(participant=participant):
                    with self.assertRaisesRegex(
                        ATTENDANCE.AttendanceInboxError,
                        expected,
                    ):
                        service.AppliquerMessage(
                            _payload(
                                operation=operation,
                                changes=[
                                    {
                                        "participant_uid": participant,
                                        "status": "present",
                                    }
                                ],
                            ),
                            _idempotence(operation),
                            date_reception="2026-10-28 09:00:03",
                        )

            db.ExecuterReq(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox;"
            )
            self.assertEqual(0, int(db.ResultatReq()[0][0]))
        finally:
            db.Close()


if __name__ == "__main__":
    unittest.main()
