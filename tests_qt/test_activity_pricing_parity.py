import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_pricing_core import TariffDetails, TariffLine
from noethys_qt.activity_pricing_parity import (
    HistoricalActivityPricingRepository,
    HistoricalCalculationTable,
    parse_legacy_number,
)


class ActivityPricingParityTests(unittest.TestCase):
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
                    cotisations TEXT,
                    caisses TEXT,
                    jours_scolaires TEXT,
                    jours_vacances TEXT,
                    description TEXT,
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
                    forfait_beneficiaire TEXT,
                    etiquettes TEXT
                );
                CREATE TABLE tarifs_lignes (
                    IDligne INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDtarif INTEGER,
                    code TEXT,
                    num_ligne INTEGER,
                    tranche TEXT,
                    qf_min REAL,
                    qf_max REAL,
                    montant_unique REAL,
                    montant_questionnaire REAL,
                    montant_enfant_1 REAL,
                    montant_enfant_2 REAL,
                    montant_enfant_3 REAL,
                    montant_enfant_4 REAL,
                    montant_enfant_5 REAL,
                    montant_enfant_6 REAL,
                    nbre_enfants INTEGER,
                    coefficient REAL,
                    montant_min REAL,
                    montant_max REAL,
                    heure_debut_min TEXT,
                    heure_debut_max TEXT,
                    heure_fin_min TEXT,
                    heure_fin_max TEXT,
                    duree_min TEXT,
                    duree_max TEXT,
                    date TEXT,
                    label TEXT,
                    temps_facture TEXT,
                    unite_horaire TEXT,
                    duree_seuil TEXT,
                    duree_plafond TEXT,
                    taux REAL,
                    ajustement REAL,
                    revenu_min REAL,
                    revenu_max REAL,
                    IDmodele INTEGER
                );
                CREATE TABLE combi_tarifs (
                    IDcombi_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER,
                    type TEXT,
                    date TEXT,
                    quantite_max INTEGER
                );
                CREATE TABLE combi_tarifs_unites (
                    IDcombi_tarif_unite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDcombi_tarif INTEGER,
                    IDtarif INTEGER,
                    IDunite INTEGER
                );
                CREATE TABLE questionnaire_filtres (
                    IDfiltre INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER,
                    type TEXT,
                    champ TEXT,
                    operateur TEXT,
                    valeur TEXT
                );
                CREATE TABLE prestations (
                    IDprestation INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def _repo(self, database: Path) -> HistoricalActivityPricingRepository:
        return HistoricalActivityPricingRepository(NativeActivityEditorRepository(database))

    def _details(self, method_code="qf") -> TariffDetails:
        return TariffDetails(
            tariff_id=None,
            activity_id=7,
            name_id=3,
            date_start=dt.date(2026, 9, 1),
            date_end=None,
            type_code="BAREME" if method_code.startswith("psu_") else "JOURN",
            method_code=method_code,
            category_ids=(),
            group_ids=None,
            cotisation_ids=None,
            caisse_ids=None,
            school_days=(0, 1, 2, 3, 4, 5, 6),
            vacation_days=(0, 1, 2, 3, 4, 5, 6),
            description="",
            observations="",
            vat=0.0,
            accounting_code="",
            local_product_code="",
            quotient_type_id=None,
            prestation_label="nom_tarif",
            etats="reservation;present",
        )

    def test_qf_and_revenue_decimals_are_not_truncated(self):
        self.assertEqual(parse_legacy_number("845,75", "qf_min"), 845.75)
        self.assertEqual(parse_legacy_number("1234.56", "revenu_min"), 1234.56)
        self.assertEqual(parse_legacy_number("4", "nbre_enfants"), 4)

        table = HistoricalCalculationTable(())
        self.addCleanup(table.close)
        table.set_method(
            "psu_revenu",
            [TariffLine(None, {
                "revenu_min": 1234.56,
                "revenu_max": 2345.67,
                "taux": 0.061234,
                "montant_min": 1.25,
                "montant_max": 17.80,
                "ajustement": -0.15,
            })],
        )
        values = table.lines()[0].values
        self.assertAlmostEqual(values["revenu_min"], 1234.56)
        self.assertAlmostEqual(values["revenu_max"], 2345.67)
        self.assertAlmostEqual(values["taux"], 0.061234)

    def test_saved_lines_keep_historic_zero_based_num_ligne_and_tranche(self):
        database = self._make_database()
        repo = self._repo(database)
        tariff_id = repo.save_tariff(
            self._details("qf"),
            [
                TariffLine(None, {"qf_min": 845.50, "qf_max": 900.75, "montant_unique": 10.0}),
                TariffLine(None, {"qf_min": 900.76, "qf_max": 1000.25, "montant_unique": 12.0}),
            ],
        )
        connection = sqlite3.connect(database)
        try:
            rows = connection.execute(
                "SELECT num_ligne, tranche, qf_min, qf_max "
                "FROM tarifs_lignes WHERE IDtarif=? ORDER BY num_ligne, IDligne",
                (tariff_id,),
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual([(row[0], row[1]) for row in rows], [(0, "1"), (1, "2")])
        self.assertAlmostEqual(rows[0][2], 845.50)
        self.assertAlmostEqual(rows[0][3], 900.75)
        self.assertAlmostEqual(rows[1][2], 900.76)
        self.assertAlmostEqual(rows[1][3], 1000.25)

    def test_duplicate_tariff_copies_questionnaire_filters_with_new_ids(self):
        database = self._make_database()
        repo = self._repo(database)
        source_id = repo.save_tariff(
            self._details("qf"),
            [TariffLine(None, {"qf_min": 0.0, "qf_max": 999.99, "montant_unique": 9.5})],
        )
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO questionnaire_filtres (IDtarif, type, champ, operateur, valeur) "
                "VALUES (?, 'famille', 'QUESTION_12', '>=', '10')",
                (source_id,),
            )
            connection.execute(
                "INSERT INTO questionnaire_filtres (IDtarif, type, champ, operateur, valeur) "
                "VALUES (?, 'individu', 'QUESTION_18', '=', 'oui')",
                (source_id,),
            )
            connection.commit()
        finally:
            connection.close()

        duplicate_id = repo.duplicate_tariff(7, source_id)
        self.assertNotEqual(duplicate_id, source_id)

        connection = sqlite3.connect(database)
        try:
            source_rows = connection.execute(
                "SELECT type, champ, operateur, valeur FROM questionnaire_filtres "
                "WHERE IDtarif=? ORDER BY IDfiltre",
                (source_id,),
            ).fetchall()
            duplicate_rows = connection.execute(
                "SELECT type, champ, operateur, valeur FROM questionnaire_filtres "
                "WHERE IDtarif=? ORDER BY IDfiltre",
                (duplicate_id,),
            ).fetchall()
            source_ids = {
                row[0] for row in connection.execute(
                    "SELECT IDfiltre FROM questionnaire_filtres WHERE IDtarif=?",
                    (source_id,),
                ).fetchall()
            }
            duplicate_ids = {
                row[0] for row in connection.execute(
                    "SELECT IDfiltre FROM questionnaire_filtres WHERE IDtarif=?",
                    (duplicate_id,),
                ).fetchall()
            }
        finally:
            connection.close()

        self.assertEqual(duplicate_rows, source_rows)
        self.assertTrue(source_ids.isdisjoint(duplicate_ids))


if __name__ == "__main__":
    unittest.main()
