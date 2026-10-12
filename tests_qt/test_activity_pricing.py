import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_pricing import ActivityPricingPage, TariffEditDialog
from noethys_qt.activity_pricing_core import (
    ActivityPricingRepository,
    PricingCategory,
    TariffDetails,
    TariffLine,
    UnitCombination,
)


class ActivityPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE categories_tarifs (
                    IDcategorie_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    nom TEXT
                );
                CREATE TABLE categories_tarifs_villes (
                    IDville INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDcategorie_tarif INTEGER,
                    cp TEXT,
                    nom TEXT
                );
                CREATE TABLE noms_tarifs (
                    IDnom_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    nom TEXT
                );
                CREATE TABLE tarifs (
                    IDtarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDnom_tarif INTEGER,
                    date_debut TEXT,
                    date_fin TEXT,
                    type TEXT,
                    methode TEXT,
                    categories_tarifs TEXT,
                    groupes TEXT,
                    etiquettes TEXT,
                    cotisations TEXT,
                    caisses TEXT,
                    description TEXT,
                    jours_scolaires TEXT,
                    jours_vacances TEXT,
                    observations TEXT,
                    tva REAL,
                    code_compta TEXT,
                    code_produit_local TEXT,
                    IDtype_quotient INTEGER,
                    label_prestation TEXT,
                    etats TEXT,
                    date_facturation TEXT,
                    options TEXT,
                    forfait_saisie_manuelle INTEGER,
                    forfait_saisie_auto INTEGER,
                    forfait_suppression_auto INTEGER,
                    forfait_duree TEXT,
                    forfait_beneficiaire TEXT
                );
                CREATE TABLE tarifs_lignes (
                    IDligne INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, IDtarif INTEGER, code TEXT, num_ligne INTEGER,
                    tranche TEXT, qf_min INTEGER, qf_max INTEGER, montant_unique REAL,
                    montant_questionnaire REAL, montant_enfant_1 REAL, montant_enfant_2 REAL,
                    montant_enfant_3 REAL, montant_enfant_4 REAL, montant_enfant_5 REAL,
                    montant_enfant_6 REAL, nbre_enfants INTEGER, coefficient REAL,
                    montant_min REAL, montant_max REAL, heure_debut_min TEXT,
                    heure_debut_max TEXT, heure_fin_min TEXT, heure_fin_max TEXT,
                    duree_min INTEGER, duree_max INTEGER, date TEXT, label TEXT,
                    temps_facture REAL, unite_horaire REAL, duree_seuil REAL,
                    duree_plafond REAL, taux REAL, ajustement REAL, revenu_min INTEGER,
                    revenu_max INTEGER, IDmodele INTEGER
                );
                CREATE TABLE groupes (
                    IDgroupe INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, nom TEXT, ordre INTEGER
                );
                CREATE TABLE types_cotisations (IDtype_cotisation INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE caisses (IDcaisse INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE types_quotients (IDtype_quotient INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE unites (
                    IDunite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, nom TEXT, ordre INTEGER
                );
                CREATE TABLE unites_incompat (
                    IDunite_incompat INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDunite INTEGER, IDunite_incompatible INTEGER
                );
                CREATE TABLE ouvertures (
                    IDouverture INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER, IDunite INTEGER, date TEXT
                );
                CREATE TABLE combi_tarifs (
                    IDcombi_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER, type TEXT, date TEXT, quantite_max INTEGER
                );
                CREATE TABLE combi_tarifs_unites (
                    IDcombi_tarif_unite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDcombi_tarif INTEGER, IDtarif INTEGER, IDunite INTEGER
                );
                CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, IDtarif INTEGER);
                CREATE TABLE questionnaire_filtres (
                    IDfiltre INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );
                """
            )
            connection.execute("INSERT INTO groupes (IDactivite, nom, ordre) VALUES (7, 'Petits', 1)")
            connection.execute("INSERT INTO groupes (IDactivite, nom, ordre) VALUES (7, 'Grands', 2)")
            connection.execute("INSERT INTO types_cotisations VALUES (1, 'Adhésion')")
            connection.execute("INSERT INTO caisses VALUES (1, 'CAF')")
            connection.execute("INSERT INTO types_quotients VALUES (1, 'QF CAF')")
            connection.execute("INSERT INTO unites (IDactivite, nom, ordre) VALUES (7, 'Journée', 1)")
            connection.execute("INSERT INTO unites (IDactivite, nom, ordre) VALUES (7, 'Repas', 2)")
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def _repo(self, database: Path) -> ActivityPricingRepository:
        return ActivityPricingRepository(NativeActivityEditorRepository(database))

    def _base_tariff(self, name_id: int, category_id: int) -> TariffDetails:
        return TariffDetails(
            tariff_id=None,
            activity_id=7,
            name_id=name_id,
            date_start=dt.date(2026, 9, 1),
            date_end=None,
            type_code="JOURN",
            method_code="montant_unique",
            category_ids=(category_id,),
            group_ids=None,
            cotisation_ids=None,
            caisse_ids=None,
            school_days=(0, 1, 2, 3, 4),
            vacation_days=(0, 1, 2, 3, 4),
            description="Journée ALSH",
            observations="",
            vat=0.0,
            accounting_code="706",
            local_product_code="ALSH",
            quotient_type_id=1,
            prestation_label="nom_tarif",
            etats="reservation;present;absenti",
        )

    def test_category_crud_and_used_category_cannot_be_deleted(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Commune", (("35130", "La Guerche"),)))
        category = repo.list_categories(7)[0]
        self.assertEqual(category.category_id, category_id)
        self.assertIn("La Guerche", category.cities_label)

        name_id = repo.save_name(7, "Journée")
        tariff_id = repo.save_tariff(
            self._base_tariff(name_id, category_id),
            [TariffLine(None, {"montant_unique": 12.5})],
        )
        self.assertGreater(tariff_id, 0)
        with self.assertRaises(ValueError):
            repo.delete_category(7, category_id)

    def test_tariff_roundtrip_and_calculation_line(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Extérieur"))
        name_id = repo.save_name(7, "Journée")
        group_id = repo.list_groups(7)[0][0]
        details = replace(
            self._base_tariff(name_id, category_id),
            group_ids=(group_id,),
            cotisation_ids=(1,),
            caisse_ids=(0, 1),
        )
        tariff_id = repo.save_tariff(details, [TariffLine(None, {"montant_unique": 18.75})])
        loaded = repo.load_tariff(7, tariff_id)
        self.assertEqual(loaded.description, "Journée ALSH")
        self.assertEqual(loaded.group_ids, (group_id,))
        self.assertEqual(loaded.caisse_ids, (0, 1))
        lines = repo.list_lines(tariff_id)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].values["montant_unique"], 18.75)

    def test_business_validations_date_method_and_required_values(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Base"))
        name_id = repo.save_name(7, "Prestation")
        base = self._base_tariff(name_id, category_id)

        with self.assertRaises(ValueError):
            repo.validate_tariff(
                replace(base, date_end=dt.date(2026, 8, 31)),
                [TariffLine(None, {"montant_unique": 10.0})],
            )
        with self.assertRaises(ValueError):
            repo.validate_tariff(
                replace(base, type_code="CREDIT", method_code="horaire_qf"),
                [TariffLine(None, {
                    "qf_min": 0, "qf_max": 1000,
                    "heure_debut_min": "08:00", "heure_debut_max": "09:00",
                    "heure_fin_min": "17:00", "heure_fin_max": "18:00",
                    "montant_unique": 5,
                })],
            )
        with self.assertRaises(ValueError):
            repo.validate_tariff(base, [TariffLine(None, {"montant_unique": None})])
        with self.assertRaises(ValueError):
            repo.validate_tariff(replace(base, group_ids=()), [TariffLine(None, {"montant_unique": 10})])

    def test_credit_duration_cannot_be_zero_when_enabled(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Base"))
        name_id = repo.save_name(7, "Crédit")
        details = replace(
            self._base_tariff(name_id, category_id),
            type_code="CREDIT",
            method_code="montant_unique",
            forfait_duree="j0-m0-a0",
        )
        with self.assertRaises(ValueError):
            repo.validate_tariff(details, [TariffLine(None, {"montant_unique": 100})])

    def test_combination_rejects_incompatible_duplicate_and_closed_forfait_date(self):
        database = self._make_database()
        repo = self._repo(database)
        units = repo.list_units(7)
        first, second = units[0][0], units[1][0]
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO unites_incompat (IDunite, IDunite_incompatible) VALUES (?, ?)",
                (first, second),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            repo.validate_combination(7, (first, second))
        existing = [UnitCombination(1, (first,), None, None)]
        with self.assertRaises(ValueError):
            repo.validate_combination(7, (first,), existing, type_code="JOURN")
        with self.assertRaises(ValueError):
            repo.validate_combination(7, (first,), (), dt.date(2026, 9, 3), "FORFAIT")

    def test_used_tariff_cannot_be_deleted(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Base"))
        name_id = repo.save_name(7, "Journée")
        tariff_id = repo.save_tariff(
            self._base_tariff(name_id, category_id),
            [TariffLine(None, {"montant_unique": 10})],
        )
        connection = sqlite3.connect(database)
        try:
            connection.execute("INSERT INTO prestations VALUES (1, ?)", (tariff_id,))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            repo.delete_tariff(tariff_id)

    def test_tariff_editor_smoke_exposes_four_historic_pages(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Base"))
        name_id = repo.save_name(7, "Journée")
        tariff_id = repo.save_tariff(
            self._base_tariff(name_id, category_id),
            [TariffLine(None, {"montant_unique": 10})],
        )
        dialog = TariffEditDialog(repo, 7, name_id, tariff_id)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.tabs.count(), 4)
        self.assertEqual(dialog.tabs.tabText(0), "Généralités")
        self.assertEqual(dialog.tabs.tabText(3), "Calcul du tarif")
        self.assertEqual(dialog.method_combo.currentData(), "montant_unique")
        self.assertEqual(dialog.calculation_table.table.rowCount(), 1)

    def test_pricing_page_smoke_loads_categories_and_tariff_tree(self):
        database = self._make_database()
        repo = self._repo(database)
        category_id = repo.save_category(PricingCategory(0, 7, "Base"))
        name_id = repo.save_name(7, "Journée")
        repo.save_tariff(
            self._base_tariff(name_id, category_id),
            [TariffLine(None, {"montant_unique": 10})],
        )
        page = ActivityPricingPage(NativeActivityEditorRepository(database), 7)
        self.addCleanup(page.close)
        self.assertEqual(page.category_table.rowCount(), 1)
        self.assertEqual(page.tree.topLevelItemCount(), 1)
        self.assertEqual(page.tree.topLevelItem(0).childCount(), 1)


if __name__ == "__main__":
    unittest.main()
