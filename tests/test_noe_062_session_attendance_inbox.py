# -*- coding: utf-8 -*-
import importlib.util
import sqlite3
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


SCHEMA = _charger_module(
    "noethys/Utils/UTILS_Interventions_Attendance_Inbox_Schema.py",
    "UTILS_Attendance_Inbox_Schema_test",
)
INBOX = _charger_module(
    "noethys/Utils/UTILS_Interventions_Attendance_Inbox.py",
    "UTILS_Attendance_Inbox_test",
)


SESSION_UID = "INT-PROG-ATTENDANCE-001"
ASSIGNMENT_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OPERATION_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


class SQLiteDB(object):
    isNetwork = False

    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.creations = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_update_id = None

    def Close(self):
        self.connexion.close()

    def IsTableExists(self, nom_table):
        self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (nom_table,),
        )
        return self.cursor.fetchone() is not None

    def ExecuterReq(self, req):
        try:
            self.cursor.execute(req)
            return 1
        except Exception:
            return 0

    def ResultatReq(self):
        return self.cursor.fetchall()

    def CreationTable(self, nom_table, dico):
        champs = []
        for nom, type_champ, info in dico[nom_table]:
            if type_champ == "LONGBLOB":
                type_champ = "BLOB"
            if type_champ == "BIGINT":
                type_champ = "INTEGER"
            champs.append("%s %s" % (nom, type_champ))
        self.cursor.execute(
            "CREATE TABLE %s (%s)" % (nom_table, ", ".join(champs))
        )
        self.creations.append(nom_table)

    def Commit(self):
        self.connexion.commit()
        self.commits += 1

    def Rollback(self):
        self.connexion.rollback()
        self.rollbacks += 1

    def ReqInsert(self, nom_table, liste_donnees, commit=True):
        noms = [nom for nom, valeur in liste_donnees]
        valeurs = [valeur for nom, valeur in liste_donnees]
        self.cursor.execute(
            "INSERT INTO %s (%s) VALUES (%s)"
            % (
                nom_table,
                ", ".join(noms),
                ", ".join("?" for nom in noms),
            ),
            tuple(valeurs),
        )
        if commit:
            self.connexion.commit()
        return self.cursor.lastrowid

    def ReqMAJ(
        self,
        nom_table,
        liste_donnees,
        nom_champ_id,
        ID,
        IDestChaine=False,
        commit=True,
    ):
        if (
            nom_table == "consommations"
            and self.fail_update_id is not None
            and int(ID) == int(self.fail_update_id)
        ):
            raise RuntimeError("échec simulé de mise à jour")
        clauses = ["%s=?" % nom for nom, valeur in liste_donnees]
        valeurs = [valeur for nom, valeur in liste_donnees] + [ID]
        self.cursor.execute(
            "UPDATE %s SET %s WHERE %s=?"
            % (nom_table, ", ".join(clauses), nom_champ_id),
            tuple(valeurs),
        )
        if commit:
            self.connexion.commit()
        return True


def _create_prerequisites(db):
    db.cursor.execute(
        """CREATE TABLE interventions (
            IDintervention INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            date TEXT,
            statut TEXT,
            actif INTEGER
        )"""
    )
    db.cursor.execute(
        """CREATE TABLE interventions_programmations (
            IDintervention_programmation INTEGER PRIMARY KEY AUTOINCREMENT,
            IDintervention INTEGER UNIQUE,
            type_source TEXT,
            IDactivite INTEGER,
            IDgroupe_activite INTEGER
        )"""
    )
    db.cursor.execute(
        """CREATE TABLE consommations (
            IDconso INTEGER PRIMARY KEY AUTOINCREMENT,
            IDindividu INTEGER,
            IDactivite INTEGER,
            IDgroupe INTEGER,
            date TEXT,
            etat TEXT
        )"""
    )
    db.connexion.commit()


def _db_pret():
    db = SQLiteDB()
    _create_prerequisites(db)
    assert SCHEMA.AssurerSchemaAttendanceInbox(db, appliquer=True)["ok"] is True
    db.cursor.execute(
        "INSERT INTO interventions (uid,date,statut,actif) VALUES (?,?,?,?)",
        (SESSION_UID, "2026-09-19", "planifiee", 1),
    )
    IDintervention = db.cursor.lastrowid
    db.cursor.execute(
        """INSERT INTO interventions_programmations (
            IDintervention,type_source,IDactivite,IDgroupe_activite
        ) VALUES (?,?,?,?)""",
        (IDintervention, "activite", 7, 3),
    )
    db.cursor.executemany(
        """INSERT INTO consommations (
            IDindividu,IDactivite,IDgroupe,date,etat
        ) VALUES (?,?,?,?,?)""",
        (
            (42, 7, 3, "2026-09-19", "reservation"),
            (43, 7, 3, "2026-09-19", "reservation"),
            (44, 7, 3, "2026-09-19", "absentj"),
            (42, 7, 99, "2026-09-19", "reservation"),
        ),
    )
    db.connexion.commit()
    return db


def payload(**overrides):
    value = {
        "contract_version": "session-attendance/1",
        "event_type": "session_attendance_changed",
        "operation_id": OPERATION_UUID,
        "assignment_uuid": ASSIGNMENT_UUID,
        "session_uid": SESSION_UID,
        "occurred_at": "2026-09-19T09:00:00Z",
        "changes": [
            {"participant_uid": "42", "status": "present"},
            {"participant_uid": "43", "status": "absent"},
        ],
    }
    value.update(overrides)
    return value


def idempotence(operation_uuid=OPERATION_UUID):
    return "session-attendance:%s:activity_users" % operation_uuid


class AttendanceInboxTests(unittest.TestCase):
    def test_schema_is_explicit_additive_and_idempotent(self):
        db = SQLiteDB()
        try:
            missing = SCHEMA.AssurerSchemaAttendanceInbox(db, appliquer=True)
            self.assertFalse(missing["ok"])
            self.assertIn("interventions", missing["prerequis_absents"])

            _create_prerequisites(db)
            first = SCHEMA.AssurerSchemaAttendanceInbox(db, appliquer=True)
            second = SCHEMA.AssurerSchemaAttendanceInbox(db, appliquer=True)
            self.assertTrue(first["ok"])
            self.assertEqual(
                ("interventions_attendance_inbox",),
                first["tables_creees"],
            )
            self.assertTrue(second["ok"])
            self.assertEqual((), second["tables_creees"])
        finally:
            db.Close()

    def test_present_and_absent_are_applied_only_to_session_group(self):
        db = _db_pret()
        try:
            result = INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                payload(),
                idempotence(),
                date_reception="2026-09-19 09:00:01",
            )
            self.assertTrue(result["applique"])
            self.assertEqual(2, result["change_count"])
            self.assertEqual(2, result["applied_rows"])

            db.cursor.execute(
                "SELECT IDindividu,IDgroupe,etat FROM consommations ORDER BY IDconso"
            )
            rows = db.cursor.fetchall()
            self.assertEqual((42, 3, "present"), rows[0])
            self.assertEqual((43, 3, "absenti"), rows[1])
            self.assertEqual((44, 3, "absentj"), rows[2])
            self.assertEqual((42, 99, "reservation"), rows[3])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_absent_preserves_an_already_justified_absence(self):
        db = _db_pret()
        try:
            one = payload(
                changes=[{"participant_uid": "44", "status": "absent"}]
            )
            result = INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                one,
                idempotence(),
                date_reception="2026-09-19 09:00:01",
            )
            self.assertTrue(result["applique"])
            self.assertEqual(0, result["applied_rows"])
            db.cursor.execute(
                "SELECT etat FROM consommations WHERE IDindividu=44 AND IDgroupe=3"
            )
            self.assertEqual("absentj", db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_present_on_justified_absence_requires_admin_correction(self):
        db = _db_pret()
        try:
            one = payload(
                changes=[{"participant_uid": "44", "status": "present"}]
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError,
                "correction administrative requise",
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    one,
                    idempotence(),
                    date_reception="2026-09-19 09:00:01",
                )
            db.cursor.execute(
                "SELECT etat FROM consommations WHERE IDindividu=44 AND IDgroupe=3"
            )
            self.assertEqual("absentj", db.cursor.fetchone()[0])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_missing_participant_rejects_whole_batch_before_write(self):
        db = _db_pret()
        try:
            invalid = payload(
                changes=[
                    {"participant_uid": "42", "status": "present"},
                    {"participant_uid": "99", "status": "absent"},
                ]
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError,
                "participant absent",
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    invalid,
                    idempotence(),
                    date_reception="2026-09-19 09:00:01",
                )
            db.cursor.execute(
                "SELECT etat FROM consommations WHERE IDindividu=42 AND IDgroupe=3"
            )
            self.assertEqual("reservation", db.cursor.fetchone()[0])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_exact_replay_is_noop(self):
        db = _db_pret()
        try:
            service = INBOX.GestionnaireInboxAttendance(db)
            first = service.AppliquerMessage(
                payload(),
                idempotence(),
                date_reception="2026-09-19 09:00:01",
            )
            second = service.AppliquerMessage(
                payload(),
                idempotence(),
                date_reception="2026-09-19 09:00:02",
            )
            self.assertTrue(first["applique"])
            self.assertTrue(second["replay"])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_same_operation_with_different_payload_is_conflict(self):
        db = _db_pret()
        try:
            service = INBOX.GestionnaireInboxAttendance(db)
            service.AppliquerMessage(
                payload(),
                idempotence(),
                date_reception="2026-09-19 09:00:01",
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError,
                "payload différent",
            ):
                service.AppliquerMessage(
                    payload(
                        changes=[
                            {"participant_uid": "42", "status": "absent"}
                        ]
                    ),
                    idempotence(),
                    date_reception="2026-09-19 09:00:02",
                )
        finally:
            db.Close()

    def test_relation_session_is_rejected(self):
        db = _db_pret()
        try:
            db.cursor.execute(
                "UPDATE interventions_programmations SET type_source='relation'"
            )
            db.connexion.commit()
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError,
                "hors activité",
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    payload(),
                    idempotence(),
                    date_reception="2026-09-19 09:00:01",
                )
        finally:
            db.Close()

    def test_failure_during_consumption_updates_rolls_back_inbox_and_states(self):
        db = _db_pret()
        try:
            db.cursor.execute(
                "SELECT IDconso FROM consommations WHERE IDindividu=43 AND IDgroupe=3"
            )
            db.fail_update_id = db.cursor.fetchone()[0]
            with self.assertRaises(RuntimeError):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    payload(),
                    idempotence(),
                    date_reception="2026-09-19 09:00:01",
                )
            self.assertGreaterEqual(db.rollbacks, 1)
            db.cursor.execute(
                "SELECT IDindividu,etat FROM consommations WHERE IDgroupe=3 ORDER BY IDindividu"
            )
            self.assertEqual(
                [(42, "reservation"), (43, "reservation"), (44, "absentj")],
                db.cursor.fetchall(),
            )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interventions_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()


if __name__ == "__main__":
    unittest.main()
