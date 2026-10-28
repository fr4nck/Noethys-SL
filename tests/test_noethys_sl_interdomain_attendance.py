# -*- coding: utf-8 -*-
import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_Interdomain_Attendance as INBOX
from Utils import UTILS_Interdomain_Attendance_Schema as SCHEMA


SESSION_UID = "PORTAIL-SESSION-001"
ASSIGNMENT_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OPERATION_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


class SQLiteDB(object):
    isNetwork = False

    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.fail_update_id = None
        self.commits = 0
        self.rollbacks = 0

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


def create_prerequisites(db):
    db.cursor.execute(
        "CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY)"
    )
    db.cursor.execute(
        "CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY, IDactivite INTEGER)"
    )
    db.cursor.execute(
        """CREATE TABLE ouvertures (
            IDouverture INTEGER PRIMARY KEY AUTOINCREMENT,
            IDactivite INTEGER, IDunite INTEGER, IDgroupe INTEGER, date TEXT
        )"""
    )
    db.cursor.execute(
        """CREATE TABLE evenements (
            IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
            IDactivite INTEGER, IDunite INTEGER, IDgroupe INTEGER, date TEXT
        )"""
    )
    db.cursor.execute(
        """CREATE TABLE prestations (
            IDprestation INTEGER PRIMARY KEY, IDfacture INTEGER
        )"""
    )
    db.cursor.execute(
        """CREATE TABLE consommations (
            IDconso INTEGER PRIMARY KEY AUTOINCREMENT,
            IDindividu INTEGER, IDactivite INTEGER, date TEXT,
            IDunite INTEGER, IDgroupe INTEGER, etat TEXT,
            IDevenement INTEGER, verrouillage INTEGER, IDprestation INTEGER
        )"""
    )
    db.connexion.commit()


def add_session(db, uid=SESSION_UID, unit=5, event=None, active=1):
    db.cursor.execute(
        """INSERT INTO interdomain_attendance_sessions (
            session_uid,IDactivite,IDgroupe,IDunite,IDevenement,date,actif,date_creation
        ) VALUES (?,?,?,?,?,?,?,?)""",
        (uid, 7, 3, unit, event, "2026-10-28", active, "2026-10-28 09:00:00"),
    )


def ready_db():
    db = SQLiteDB()
    create_prerequisites(db)
    result = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
    assert result["ok"] is True
    db.cursor.execute("INSERT INTO activites (IDactivite) VALUES (7)")
    db.cursor.execute("INSERT INTO groupes (IDgroupe,IDactivite) VALUES (3,7)")
    db.cursor.executemany(
        "INSERT INTO ouvertures (IDactivite,IDunite,IDgroupe,date) VALUES (?,?,?,?)",
        (
            (7, 5, 3, "2026-10-28"),
            (7, 6, 3, "2026-10-28"),
        ),
    )
    add_session(db)
    db.cursor.executemany(
        """INSERT INTO consommations (
            IDindividu,IDactivite,date,IDunite,IDgroupe,etat,IDevenement,
            verrouillage,IDprestation
        ) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            (42, 7, "2026-10-28", 5, 3, "reservation", None, 0, None),
            (43, 7, "2026-10-28", 5, 3, "reservation", None, 0, None),
            (44, 7, "2026-10-28", 5, 3, "absentj", None, 0, None),
            (42, 7, "2026-10-28", 6, 3, "reservation", None, 0, None),
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
        "occurred_at": "2026-10-28T09:00:00+01:00",
        "changes": [
            {"participant_uid": "42", "status": "present"},
            {"participant_uid": "43", "status": "absent"},
        ],
    }
    value.update(overrides)
    return value


def idempotence(operation_uuid=OPERATION_UUID):
    return "session-attendance:%s:activity_users" % operation_uuid


class InterdomainAttendanceTests(unittest.TestCase):
    def test_schema_is_explicit_additive_idempotent_and_rollbackable_when_empty(self):
        db = SQLiteDB()
        try:
            missing = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
            self.assertFalse(missing["ok"])
            self.assertIn("consommations", missing["prerequis_absents"])

            create_prerequisites(db)
            first = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
            second = SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
            self.assertTrue(first["ok"])
            self.assertEqual(
                (
                    "interdomain_attendance_sessions",
                    "interdomain_attendance_inbox",
                ),
                first["tables_creees"],
            )
            self.assertTrue(second["ok"])
            self.assertEqual((), second["tables_creees"])

            rollback = SCHEMA.RetirerSchemaAttendance(db, appliquer=True)
            self.assertTrue(rollback["ok"])
            self.assertEqual(
                (
                    "interdomain_attendance_inbox",
                    "interdomain_attendance_sessions",
                ),
                rollback["tables_supprimees"],
            )
        finally:
            db.Close()

    def test_present_and_absent_only_touch_the_explicit_unit(self):
        db = ready_db()
        try:
            result = INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                payload(), idempotence(), date_reception="2026-10-28 09:00:01"
            )
            self.assertTrue(result["applique"])
            self.assertEqual(2, result["applied_rows"])
            db.cursor.execute(
                "SELECT IDindividu,IDunite,etat FROM consommations ORDER BY IDconso"
            )
            self.assertEqual(
                [
                    (42, 5, "present"),
                    (43, 5, "absenti"),
                    (44, 5, "absentj"),
                    (42, 6, "reservation"),
                ],
                db.cursor.fetchall(),
            )
        finally:
            db.Close()

    def test_exact_replay_is_noop(self):
        db = ready_db()
        try:
            service = INBOX.GestionnaireInboxAttendance(db)
            first = service.AppliquerMessage(
                payload(), idempotence(), date_reception="2026-10-28 09:00:01"
            )
            second = service.AppliquerMessage(
                payload(), idempotence(), date_reception="2026-10-28 09:00:02"
            )
            self.assertTrue(first["applique"])
            self.assertTrue(second["replay"])
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(1, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_same_operation_with_different_payload_is_rejected(self):
        db = ready_db()
        try:
            service = INBOX.GestionnaireInboxAttendance(db)
            service.AppliquerMessage(
                payload(), idempotence(), date_reception="2026-10-28 09:00:01"
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError, "payload différent"
            ):
                service.AppliquerMessage(
                    payload(
                        changes=[
                            {"participant_uid": "42", "status": "absent"}
                        ]
                    ),
                    idempotence(),
                    date_reception="2026-10-28 09:00:02",
                )
        finally:
            db.Close()

    def test_absent_preserves_justified_absence(self):
        db = ready_db()
        try:
            one = payload(
                changes=[{"participant_uid": "44", "status": "absent"}]
            )
            result = INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                one, idempotence(), date_reception="2026-10-28 09:00:01"
            )
            self.assertEqual(0, result["applied_rows"])
            db.cursor.execute(
                "SELECT etat FROM consommations WHERE IDindividu=44 AND IDunite=5"
            )
            self.assertEqual("absentj", db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_present_cannot_remove_justified_absence(self):
        db = ready_db()
        try:
            one = payload(
                changes=[{"participant_uid": "44", "status": "present"}]
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError,
                "correction administrative requise",
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    one, idempotence(), date_reception="2026-10-28 09:00:01"
                )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_missing_participant_rejects_whole_batch_before_write(self):
        db = ready_db()
        try:
            invalid = payload(
                changes=[
                    {"participant_uid": "42", "status": "present"},
                    {"participant_uid": "99", "status": "absent"},
                ]
            )
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError, "participant absent"
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    invalid,
                    idempotence(),
                    date_reception="2026-10-28 09:00:01",
                )
            db.cursor.execute(
                "SELECT etat FROM consommations WHERE IDindividu=42 AND IDunite=5"
            )
            self.assertEqual("reservation", db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_inactive_or_too_broad_session_mapping_is_rejected(self):
        for active, unit, message in (
            (0, 5, "inactive"),
            (1, None, "trop large"),
        ):
            with self.subTest(active=active, unit=unit):
                db = SQLiteDB()
                try:
                    create_prerequisites(db)
                    SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
                    db.cursor.execute("INSERT INTO activites (IDactivite) VALUES (7)")
                    db.cursor.execute(
                        "INSERT INTO groupes (IDgroupe,IDactivite) VALUES (3,7)"
                    )
                    db.cursor.execute(
                        "INSERT INTO ouvertures (IDactivite,IDunite,IDgroupe,date) VALUES (7,5,3,'2026-10-28')"
                    )
                    add_session(db, unit=unit, active=active)
                    db.connexion.commit()
                    with self.assertRaisesRegex(
                        INBOX.AttendanceInboxError, message
                    ):
                        INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                            payload(),
                            idempotence(),
                            date_reception="2026-10-28 09:00:01",
                        )
                finally:
                    db.Close()

    def test_ambiguous_consumption_is_rejected(self):
        db = ready_db()
        try:
            db.cursor.execute(
                """INSERT INTO consommations (
                    IDindividu,IDactivite,date,IDunite,IDgroupe,etat,IDevenement
                ) VALUES (42,7,'2026-10-28',5,3,'reservation',NULL)"""
            )
            db.connexion.commit()
            with self.assertRaisesRegex(
                INBOX.AttendanceInboxError, "ambigu"
            ):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    payload(changes=[{"participant_uid": "42", "status": "present"}]),
                    idempotence(),
                    date_reception="2026-10-28 09:00:01",
                )
        finally:
            db.Close()

    def test_event_scope_is_supported_without_unit(self):
        db = SQLiteDB()
        try:
            create_prerequisites(db)
            SCHEMA.AssurerSchemaAttendance(db, appliquer=True)
            db.cursor.execute("INSERT INTO activites (IDactivite) VALUES (7)")
            db.cursor.execute(
                "INSERT INTO groupes (IDgroupe,IDactivite) VALUES (3,7)"
            )
            db.cursor.execute(
                "INSERT INTO evenements (IDevenement,IDactivite,IDunite,IDgroupe,date) VALUES (12,7,5,3,'2026-10-28')"
            )
            add_session(db, uid=SESSION_UID, unit=None, event=12)
            db.cursor.execute(
                """INSERT INTO consommations (
                    IDindividu,IDactivite,date,IDunite,IDgroupe,etat,IDevenement
                ) VALUES (42,7,'2026-10-28',5,3,'reservation',12)"""
            )
            db.connexion.commit()
            result = INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                payload(changes=[{"participant_uid": "42", "status": "present"}]),
                idempotence(),
                date_reception="2026-10-28 09:00:01",
            )
            self.assertEqual(1, result["applied_rows"])
        finally:
            db.Close()

    def test_failure_rolls_back_inbox_and_all_consumption_changes(self):
        db = ready_db()
        try:
            db.cursor.execute(
                "SELECT IDconso FROM consommations WHERE IDindividu=43 AND IDunite=5"
            )
            db.fail_update_id = db.cursor.fetchone()[0]
            with self.assertRaises(RuntimeError):
                INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                    payload(),
                    idempotence(),
                    date_reception="2026-10-28 09:00:01",
                )
            db.cursor.execute(
                "SELECT IDindividu,etat FROM consommations WHERE IDunite=5 ORDER BY IDconso"
            )
            self.assertEqual(
                [(42, "reservation"), (43, "reservation"), (44, "absentj")],
                db.cursor.fetchall(),
            )
            db.cursor.execute(
                "SELECT COUNT(*) FROM interdomain_attendance_inbox"
            )
            self.assertEqual(0, db.cursor.fetchone()[0])
        finally:
            db.Close()

    def test_locked_or_billed_consumption_is_rejected_before_inbox(self):
        for case in ("locked", "billed"):
            with self.subTest(case=case):
                db = ready_db()
                try:
                    if case == "locked":
                        db.cursor.execute(
                            "UPDATE consommations SET verrouillage=1 "
                            "WHERE IDindividu=42 AND IDunite=5"
                        )
                        expected = "verrouillée"
                    else:
                        db.cursor.execute(
                            "INSERT INTO prestations (IDprestation,IDfacture) "
                            "VALUES (100,200)"
                        )
                        db.cursor.execute(
                            "UPDATE consommations SET IDprestation=100 "
                            "WHERE IDindividu=42 AND IDunite=5"
                        )
                        expected = "déjà facturée"
                    db.connexion.commit()
                    with self.assertRaisesRegex(
                        INBOX.AttendanceInboxError, expected
                    ):
                        INBOX.GestionnaireInboxAttendance(db).AppliquerMessage(
                            payload(
                                changes=[
                                    {
                                        "participant_uid": "42",
                                        "status": "present",
                                    }
                                ]
                            ),
                            idempotence(),
                            date_reception="2026-10-28 09:00:01",
                        )
                    db.cursor.execute(
                        "SELECT etat FROM consommations "
                        "WHERE IDindividu=42 AND IDunite=5"
                    )
                    self.assertEqual("reservation", db.cursor.fetchone()[0])
                    db.cursor.execute(
                        "SELECT COUNT(*) FROM interdomain_attendance_inbox"
                    )
                    self.assertEqual(0, db.cursor.fetchone()[0])
                finally:
                    db.Close()

    def test_backup_restore_roundtrip_preserves_integration_schema_and_data(self):
        source = ready_db()
        restored = SQLiteDB()
        try:
            source.connexion.backup(restored.connexion)
            restored.cursor.execute(
                "SELECT session_uid,IDactivite,IDgroupe,IDunite,date,actif "
                "FROM interdomain_attendance_sessions"
            )
            self.assertEqual(
                [(SESSION_UID, 7, 3, 5, "2026-10-28", 1)],
                restored.cursor.fetchall(),
            )
            restored.cursor.execute("SELECT COUNT(*) FROM consommations")
            self.assertEqual(4, restored.cursor.fetchone()[0])
        finally:
            restored.Close()
            source.Close()

    def test_schema_rollback_refuses_non_empty_integration_tables(self):
        db = ready_db()
        try:
            rollback = SCHEMA.RetirerSchemaAttendance(db, appliquer=True)
            self.assertFalse(rollback["ok"])
            self.assertIn(
                "interdomain_attendance_sessions",
                rollback["tables_non_vides"],
            )
            self.assertTrue(db.IsTableExists("interdomain_attendance_sessions"))
        finally:
            db.Close()


if __name__ == "__main__":
    unittest.main()
