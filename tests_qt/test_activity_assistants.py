from __future__ import annotations

import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

from noethys_qt.activity_assistants_core import (
    ActivityAssistantRepository,
    AssistantConfiguration,
)
from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_simulation import ActivitySimulationRepository


DDL = """
CREATE TABLE activites (
    IDactivite INTEGER PRIMARY KEY AUTOINCREMENT,
    date_creation TEXT, nom TEXT, abrege TEXT, date_debut TEXT, date_fin TEXT,
    nbre_inscrits_max INTEGER
);
CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER);
CREATE TABLE types_groupes_activites (IDtype_groupe_activite INTEGER PRIMARY KEY, nom TEXT);
CREATE TABLE groupes_activites (IDgroupe_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDtype_groupe_activite INTEGER, IDactivite INTEGER);
CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT, ordre INTEGER, abrege TEXT, nbre_inscrits_max INTEGER);
CREATE TABLE agrements (IDagrement INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, agrement TEXT, date_debut TEXT, date_fin TEXT);
CREATE TABLE responsables_activite (IDresponsable INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, sexe TEXT, nom TEXT, fonction TEXT, defaut INTEGER);
CREATE TABLE types_pieces (IDtype_piece INTEGER PRIMARY KEY, nom TEXT);
CREATE TABLE pieces_activites (IDpiece_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtype_piece INTEGER);
CREATE TABLE types_cotisations (IDtype_cotisation INTEGER PRIMARY KEY, nom TEXT);
CREATE TABLE cotisations_activites (IDcotisation_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtype_cotisation INTEGER);
CREATE TABLE renseignements_activites (IDrenseignement_activite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtype_renseignement INTEGER);
CREATE TABLE unites (IDunite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT, abrege TEXT, type TEXT, date_debut TEXT, date_fin TEXT, repas INTEGER, ordre INTEGER);
CREATE TABLE unites_remplissage (IDunite_remplissage INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT, abrege TEXT, seuil_alerte INTEGER, date_debut TEXT, date_fin TEXT, afficher_page_accueil INTEGER, afficher_grille_conso INTEGER, ordre INTEGER);
CREATE TABLE unites_remplissage_unites (IDlien INTEGER PRIMARY KEY AUTOINCREMENT, IDunite_remplissage INTEGER, IDunite INTEGER);
CREATE TABLE ouvertures (IDouverture INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDunite INTEGER, IDgroupe INTEGER, date TEXT);
CREATE TABLE remplissage (IDremplissage INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDunite_remplissage INTEGER, IDgroupe INTEGER, date TEXT, places INTEGER);
CREATE TABLE categories_tarifs (IDcategorie_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE categories_tarifs_villes (IDville INTEGER PRIMARY KEY AUTOINCREMENT, IDcategorie_tarif INTEGER, cp TEXT, nom TEXT);
CREATE TABLE noms_tarifs (IDnom_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE tarifs (
    IDtarif INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDnom_tarif INTEGER,
    date_debut TEXT, date_fin TEXT, type TEXT, methode TEXT, categories_tarifs TEXT,
    groupes TEXT, jours_scolaires TEXT, jours_vacances TEXT, tva REAL,
    label_prestation TEXT, etats TEXT, options TEXT,
    forfait_saisie_manuelle INTEGER, forfait_saisie_auto INTEGER, forfait_suppression_auto INTEGER
);
CREATE TABLE tarifs_lignes (IDligne INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, IDtarif INTEGER, code TEXT, num_ligne INTEGER, tranche TEXT, montant_unique REAL);
CREATE TABLE combi_tarifs (IDcombi_tarif INTEGER PRIMARY KEY AUTOINCREMENT, IDtarif INTEGER, type TEXT, date TEXT, quantite_max INTEGER);
CREATE TABLE combi_tarifs_unites (IDcombi_tarif_unite INTEGER PRIMARY KEY AUTOINCREMENT, IDcombi_tarif INTEGER, IDtarif INTEGER, IDunite INTEGER);
CREATE TABLE unites_groupes (IDunite_groupe INTEGER PRIMARY KEY AUTOINCREMENT, IDunite INTEGER, IDgroupe INTEGER);
CREATE TABLE unites_incompat (IDunite_incompat INTEGER PRIMARY KEY AUTOINCREMENT, IDunite INTEGER, IDunite_incompatible INTEGER);
CREATE TABLE etiquettes (IDetiquette INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, label TEXT);
CREATE TABLE portail_periodes (IDperiode INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE portail_unites (IDportail_unite INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE evenements (IDevenement INTEGER PRIMARY KEY AUTOINCREMENT, IDactivite INTEGER, nom TEXT);
CREATE TABLE questionnaire_filtres (IDfiltre INTEGER PRIMARY KEY AUTOINCREMENT, IDtarif INTEGER);
"""


class ActivityAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database = Path(self.temp.name) / "assistants.db"
        with sqlite3.connect(self.database) as connection:
            connection.executescript(DDL)
            connection.execute("INSERT INTO types_groupes_activites VALUES (1, 'Sports')")
            connection.execute("INSERT INTO types_pieces VALUES (1, 'Certificat')")
            connection.execute("INSERT INTO types_cotisations VALUES (1, 'Adhésion')")
            connection.commit()
        editor = NativeActivityEditorRepository(self.database)
        self.repository = ActivityAssistantRepository(editor)
        self.simulation = ActivitySimulationRepository(editor)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_preview_is_read_only(self) -> None:
        config = AssistantConfiguration(
            code="stage", name="Stage théâtre", start_date=dt.date(2026, 10, 19),
            end_date=dt.date(2026, 10, 23), pricing_mode="fixed", amount=35.0,
        )
        report = self.repository.preview(config)
        self.assertIn("5 ouverture", report.as_text())
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activites").fetchone()[0], 0)

    def test_sejour_generates_historic_structure_atomically(self) -> None:
        config = AssistantConfiguration(
            code="sejour", name="Mini-camp", start_date=dt.date(2026, 10, 20),
            end_date=dt.date(2026, 10, 22), max_members=12,
            activity_group_type_ids=(1,), agreement_number="035ORG123",
            responsible_name="Direction", responsible_function="Directeur",
            piece_ids=(1,), cotisation_ids=(1,), information_ids=(1, 12),
            pricing_mode="fixed", pricing_categories=("Commune", "Hors commune"), amount=75.0,
        )
        activity_id = self.repository.generate(config)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT nom FROM activites WHERE IDactivite=?", (activity_id,)).fetchone()[0], "Mini-camp")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM groupes WHERE IDactivite=?", (activity_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM agrements WHERE IDactivite=?", (activity_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ouvertures WHERE IDactivite=?", (activity_id,)).fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM remplissage WHERE IDactivite=?", (activity_id,)).fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM categories_tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tarifs_lignes WHERE IDactivite=?", (activity_id,)).fetchone()[0], 2)

    def test_cantine_creates_services_repas_and_daily_combination_without_openings(self) -> None:
        config = AssistantConfiguration(
            code="cantine", name="Cantine scolaire", group_names=("Service 1", "Service 2"),
            pricing_mode="fixed", amount=4.25,
        )
        activity_id = self.repository.generate(config)
        with sqlite3.connect(self.database) as connection:
            groups = connection.execute("SELECT nom FROM groupes WHERE IDactivite=? ORDER BY ordre", (activity_id,)).fetchall()
            self.assertEqual([row[0] for row in groups], ["Service 1", "Service 2"])
            unit = connection.execute("SELECT IDunite, nom FROM unites WHERE IDactivite=?", (activity_id,)).fetchone()
            self.assertEqual(unit[1], "Repas")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ouvertures WHERE IDactivite=?", (activity_id,)).fetchone()[0], 0)
            tariff_id = connection.execute("SELECT IDtarif FROM tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0]
            combo = connection.execute("SELECT IDcombi_tarif FROM combi_tarifs WHERE IDtarif=?", (tariff_id,)).fetchone()[0]
            link = connection.execute("SELECT IDcombi_tarif, IDunite FROM combi_tarifs_unites WHERE IDtarif=?", (tariff_id,)).fetchone()
            self.assertEqual(link, (combo, unit[0]))

    def test_annual_free_with_weekday_tracking_creates_only_expected_openings(self) -> None:
        config = AssistantConfiguration(
            code="annuelle", name="Yoga", start_date=dt.date(2026, 9, 7),
            end_date=dt.date(2026, 9, 20), track_sessions=True, session_weekdays=(0,),
            pricing_mode="free",
        )
        activity_id = self.repository.generate(config)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ouvertures WHERE IDactivite=?", (activity_id,)).fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM categories_tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0], 0)

    def test_sorties_creates_event_tariff_without_amount_line(self) -> None:
        activity_id = self.repository.generate(AssistantConfiguration(code="sorties", name="Sorties familles"))
        with sqlite3.connect(self.database) as connection:
            unit = connection.execute("SELECT type FROM unites WHERE IDactivite=?", (activity_id,)).fetchone()[0]
            method = connection.execute("SELECT methode FROM tarifs WHERE IDactivite=?", (activity_id,)).fetchone()[0]
            self.assertEqual(unit, "Evenement")
            self.assertEqual(method, "montant_evenement")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tarifs_lignes WHERE IDactivite=?", (activity_id,)).fetchone()[0], 0)

    def test_simulation_reports_duplicate_and_blocked_delete_without_writing(self) -> None:
        activity_id = self.repository.generate(
            AssistantConfiguration(code="cantine", name="Cantine", pricing_mode="fixed", amount=4.0)
        )
        duplicate = self.simulation.duplicate_report(activity_id)
        self.assertIn("Ne copierait aucune inscription", duplicate.as_text())
        with sqlite3.connect(self.database) as connection:
            before = connection.execute("SELECT COUNT(*) FROM activites").fetchone()[0]
            connection.execute("INSERT INTO inscriptions (IDactivite) VALUES (?)", (activity_id,))
            connection.commit()
        deletion = self.simulation.delete_report(activity_id)
        self.assertTrue(deletion.blocked)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activites").fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
