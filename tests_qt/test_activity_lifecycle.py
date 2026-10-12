from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_lifecycle import ActivityLifecycleRepository


DDL = """
CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, date_creation TEXT,
 psu_unite_prevision INTEGER, psu_unite_presence INTEGER, psu_tarif_forfait INTEGER, psu_etiquette_rtt INTEGER);
CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER);
CREATE TABLE responsables_activite (IDresponsable INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE groupes_activites (IDgroupe_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDtype_groupe_activite INTEGER, IDactivite INTEGER);
CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE agrements (IDagrement INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, agrement TEXT);
CREATE TABLE pieces_activites (IDpiece_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtype_piece INTEGER);
CREATE TABLE cotisations_activites (IDcotisation_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtype_cotisation INTEGER);
CREATE TABLE renseignements_activites (IDrenseignement_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDrenseignement INTEGER);
CREATE TABLE unites (IDunite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE etiquettes (IDetiquette INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, label TEXT, parent INTEGER);
CREATE TABLE unites_remplissage (IDunite_remplissage INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE ouvertures (IDouverture INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDunite INTEGER, IDgroupe INTEGER);
CREATE TABLE remplissage (IDremplissage INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDunite_remplissage INTEGER, IDgroupe INTEGER);
CREATE TABLE categories_tarifs (IDcategorie_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE noms_tarifs (IDnom_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE tarifs (IDtarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDnom_tarif INTEGER, categories_tarifs TEXT, groupes TEXT);
CREATE TABLE tarifs_lignes (IDligne INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtarif INTEGER, montant REAL);
CREATE TABLE portail_periodes (IDperiode INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE portail_unites (IDunite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT, unites_principales TEXT, unites_secondaires TEXT);
CREATE TABLE evenements (IDevenement INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDunite INTEGER, nom TEXT);
CREATE TABLE unites_groupes (IDunite_groupe INTEGER PRIMARY KEY AUTOINCREMENT, IDunite INTEGER, IDgroupe INTEGER);
CREATE TABLE unites_incompat (IDunite_incompat INTEGER PRIMARY KEY AUTOINCREMENT, IDunite INTEGER, IDunite_incompatible INTEGER);
CREATE TABLE unites_remplissage_unites (IDlien INTEGER PRIMARY KEY AUTOINCREMENT, IDunite_remplissage INTEGER, IDunite INTEGER);
CREATE TABLE categories_tarifs_villes (IDville_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDcategorie_tarif INTEGER, ville TEXT);
CREATE TABLE combi_tarifs (IDcombi_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDtarif INTEGER, nom TEXT);
CREATE TABLE combi_tarifs_unites (IDcombi_tarif_unite INTEGER PRIMARY KEY AUTOINCREMENT, IDcombi_tarif INTEGER, IDtarif INTEGER, IDunite INTEGER);
CREATE TABLE questionnaire_filtres (IDfiltre INTEGER PRIMARY KEY AUTOINCREMENT, IDtarif INTEGER, champ TEXT);
"""


def connect(path: Path):
    return closing(sqlite3.connect(path))


def seed(database: Path) -> int:
    with connect(database) as connection:
        c = connection.cursor()
        c.execute("INSERT INTO activites (nom, date_creation) VALUES ('ALSH', '2026-09-01')")
        activity_id = int(c.lastrowid)
        c.execute("INSERT INTO responsables_activite (IDactivite, nom) VALUES (?, 'Direction')", (activity_id,))
        c.execute("INSERT INTO groupes_activites (IDtype_groupe_activite, IDactivite) VALUES (7, ?)", (activity_id,))
        c.execute("INSERT INTO groupes (IDactivite, nom) VALUES (?, '6-8 ans')", (activity_id,)); group_id = int(c.lastrowid)
        c.execute("INSERT INTO agrements (IDactivite, agrement) VALUES (?, '035ORG')", (activity_id,))
        c.execute("INSERT INTO pieces_activites (IDactivite, IDtype_piece) VALUES (?, 1)", (activity_id,))
        c.execute("INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (?, 2)", (activity_id,))
        c.execute("INSERT INTO renseignements_activites (IDactivite, IDrenseignement) VALUES (?, 3)", (activity_id,))
        c.execute("INSERT INTO unites (IDactivite, nom) VALUES (?, 'Journée')", (activity_id,)); unit1 = int(c.lastrowid)
        c.execute("INSERT INTO unites (IDactivite, nom) VALUES (?, 'Repas')", (activity_id,)); unit2 = int(c.lastrowid)
        c.execute("INSERT INTO unites_groupes (IDunite, IDgroupe) VALUES (?, ?)", (unit1, group_id))
        c.execute("INSERT INTO unites_incompat (IDunite, IDunite_incompatible) VALUES (?, ?)", (unit1, unit2))
        c.execute("INSERT INTO etiquettes (IDactivite, label, parent) VALUES (?, 'Racine', NULL)", (activity_id,)); root = int(c.lastrowid)
        c.execute("INSERT INTO etiquettes (IDactivite, label, parent) VALUES (?, 'Enfant', ?)", (activity_id, root)); child = int(c.lastrowid)
        c.execute("INSERT INTO unites_remplissage (IDactivite, nom) VALUES (?, 'Capacité')", (activity_id,)); fill = int(c.lastrowid)
        c.execute("INSERT INTO unites_remplissage_unites (IDunite_remplissage, IDunite) VALUES (?, ?)", (fill, unit1))
        c.execute("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe) VALUES (?, ?, ?)", (activity_id, unit1, group_id))
        c.execute("INSERT INTO remplissage (IDactivite, IDunite_remplissage, IDgroupe) VALUES (?, ?, ?)", (activity_id, fill, group_id))
        c.execute("INSERT INTO categories_tarifs (IDactivite, nom) VALUES (?, 'Habitant')", (activity_id,)); category = int(c.lastrowid)
        c.execute("INSERT INTO categories_tarifs_villes (IDcategorie_tarif, ville) VALUES (?, 'Bais')", (category,))
        c.execute("INSERT INTO noms_tarifs (IDactivite, nom) VALUES (?, 'Journée')", (activity_id,)); tariff_name = int(c.lastrowid)
        c.execute("INSERT INTO tarifs (IDactivite, IDnom_tarif, categories_tarifs, groupes) VALUES (?, ?, ?, ?)", (activity_id, tariff_name, str(category), str(group_id))); tariff = int(c.lastrowid)
        c.execute("INSERT INTO tarifs_lignes (IDactivite, IDtarif, montant) VALUES (?, ?, 12.5)", (activity_id, tariff))
        c.execute("INSERT INTO combi_tarifs (IDtarif, nom) VALUES (?, 'Journée')", (tariff,)); combo = int(c.lastrowid)
        c.execute("INSERT INTO combi_tarifs_unites (IDcombi_tarif, IDtarif, IDunite) VALUES (?, ?, ?)", (combo, tariff, unit1))
        c.execute("INSERT INTO questionnaire_filtres (IDtarif, champ) VALUES (?, 'QF')", (tariff,))
        c.execute("INSERT INTO portail_periodes (IDactivite, nom) VALUES (?, 'Été')", (activity_id,))
        c.execute("INSERT INTO portail_unites (IDactivite, nom, unites_principales, unites_secondaires) VALUES (?, 'Journée + repas', ?, ?)", (activity_id, str(unit1), str(unit2)))
        c.execute("INSERT INTO evenements (IDactivite, IDunite, nom) VALUES (?, ?, 'Sortie')", (activity_id, unit1))
        c.execute("UPDATE activites SET psu_unite_prevision=?, psu_unite_presence=?, psu_tarif_forfait=?, psu_etiquette_rtt=? WHERE IDactivite=?", (unit1, unit2, tariff, child, activity_id))
        connection.commit(); c.close()
        return activity_id


class ActivityLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database = Path(self.temp.name) / "activities.db"
        with connect(self.database) as connection:
            connection.executescript(DDL); connection.commit()
        editor = NativeActivityEditorRepository(self.database)
        self.lifecycle = ActivityLifecycleRepository(editor)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_and_discard_do_not_leave_provisional_row(self) -> None:
        activity_id = self.lifecycle.create_activity()
        with connect(self.database) as connection:
            row = connection.execute("SELECT nom, date_creation FROM activites WHERE IDactivite=?", (activity_id,)).fetchone()
        self.assertIsNone(row[0]); self.assertTrue(row[1])
        self.lifecycle.discard_new_activity(activity_id)
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activites WHERE IDactivite=?", (activity_id,)).fetchone()[0], 0)

    def test_duplicate_copies_only_configuration_and_remaps_internal_ids(self) -> None:
        source = seed(self.database); copy_id = self.lifecycle.duplicate_activity(source)
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT nom FROM activites WHERE IDactivite=?", (copy_id,)).fetchone()[0], "Copie de ALSH")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM inscriptions WHERE IDactivite=?", (copy_id,)).fetchone()[0], 0)
            source_units = {r[0] for r in connection.execute("SELECT IDunite FROM unites WHERE IDactivite=?", (source,))}
            copy_units = {r[0] for r in connection.execute("SELECT IDunite FROM unites WHERE IDactivite=?", (copy_id,))}
            self.assertEqual(len(copy_units), 2); self.assertTrue(copy_units.isdisjoint(source_units))
            copy_group = connection.execute("SELECT IDgroupe FROM groupes WHERE IDactivite=?", (copy_id,)).fetchone()[0]
            copy_category = connection.execute("SELECT IDcategorie_tarif FROM categories_tarifs WHERE IDactivite=?", (copy_id,)).fetchone()[0]
            tariff = connection.execute("SELECT IDtarif, categories_tarifs, groupes FROM tarifs WHERE IDactivite=?", (copy_id,)).fetchone()
            self.assertEqual((tariff[1], tariff[2]), (str(copy_category), str(copy_group)))

            incompat = connection.execute(
                "SELECT IDunite, IDunite_incompatible FROM unites_incompat WHERE IDunite IN (?, ?)",
                tuple(copy_units),
            ).fetchone()
            self.assertIsNotNone(incompat)
            self.assertIn(incompat[0], copy_units); self.assertIn(incompat[1], copy_units)

            source_combo = connection.execute(
                "SELECT IDcombi_tarif FROM combi_tarifs WHERE IDtarif IN (SELECT IDtarif FROM tarifs WHERE IDactivite=?)",
                (source,),
            ).fetchone()[0]
            copy_combo = connection.execute("SELECT IDcombi_tarif FROM combi_tarifs WHERE IDtarif=?", (tariff[0],)).fetchone()[0]
            self.assertNotEqual(source_combo, copy_combo)
            combo_link = connection.execute(
                "SELECT IDcombi_tarif, IDtarif, IDunite FROM combi_tarifs_unites WHERE IDtarif=?",
                (tariff[0],),
            ).fetchone()
            self.assertEqual(combo_link[0], copy_combo)
            self.assertEqual(combo_link[1], tariff[0])
            self.assertIn(combo_link[2], copy_units)

            portal = connection.execute("SELECT unites_principales, unites_secondaires FROM portail_unites WHERE IDactivite=?", (copy_id,)).fetchone()
            self.assertEqual({int(portal[0]), int(portal[1])}, copy_units)
            labels = connection.execute("SELECT IDetiquette, label, parent FROM etiquettes WHERE IDactivite=?", (copy_id,)).fetchall()
            root = next(r for r in labels if r[1] == "Racine"); child = next(r for r in labels if r[1] == "Enfant")
            self.assertEqual(child[2], root[0])
            psu = connection.execute("SELECT psu_unite_prevision, psu_unite_presence, psu_tarif_forfait, psu_etiquette_rtt FROM activites WHERE IDactivite=?", (copy_id,)).fetchone()
            self.assertIn(psu[0], copy_units); self.assertIn(psu[1], copy_units); self.assertEqual(psu[2], tariff[0]); self.assertEqual(psu[3], child[0])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM questionnaire_filtres WHERE IDtarif=?", (tariff[0],)).fetchone()[0], 1)

    def test_delete_guard_and_atomic_rollback(self) -> None:
        activity_id = seed(self.database)
        with connect(self.database) as connection:
            connection.execute("INSERT INTO inscriptions (IDactivite) VALUES (?)", (activity_id,)); connection.commit()
        self.assertEqual(self.lifecycle.delete_check(activity_id).registrations, 1)
        with self.assertRaisesRegex(ValueError, "déjà inscrits"):
            self.lifecycle.delete_activity(activity_id)
        with connect(self.database) as connection:
            connection.execute("DELETE FROM inscriptions WHERE IDactivite=?", (activity_id,))
            connection.execute("CREATE TRIGGER refuse_agreement_delete BEFORE DELETE ON agrements BEGIN SELECT RAISE(FAIL, 'refus test'); END")
            before_links = connection.execute("SELECT COUNT(*) FROM unites_groupes").fetchone()[0]; connection.commit()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "refus test"):
            self.lifecycle.delete_activity(activity_id)
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activites WHERE IDactivite=?", (activity_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM unites_groupes").fetchone()[0], before_links)
            connection.execute("DROP TRIGGER refuse_agreement_delete"); connection.commit()
        self.lifecycle.delete_activity(activity_id)
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activites WHERE IDactivite=?", (activity_id,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM questionnaire_filtres").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM evenements").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM combi_tarifs_unites").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM combi_tarifs").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
