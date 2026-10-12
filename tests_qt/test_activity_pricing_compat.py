import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from noethys_qt.activity_pricing_compat import (
    LEGACY_HHMM_FIELDS,
    LegacyCalculationTable,
    TariffEditDialog,
    historic_credit_beneficiary,
    historic_forfait_mode,
    list_amount_questions,
    parse_legacy_hhmm,
)
from noethys_qt.activity_pricing_core import (
    PricingCategory,
    TariffDetails,
    TariffLine,
    TariffName,
    UnitCombination,
)


class FakePricingRepository:
    def __init__(self, database: Path, details: TariffDetails, combinations=None):
        self.database = database
        self.details = details
        self.combinations = combinations or {}
        self.saved_details = None
        self.saved_lines = None
        self.saved_combinations = []

    def _connect(self):
        return sqlite3.connect(self.database), "?"

    def load_tariff(self, activity_id, tariff_id):
        return self.details

    def list_lines(self, tariff_id):
        return [TariffLine(1, {"montant_unique": 10.0, "montant_questionnaire": 12})]

    def list_combinations(self, tariff_id, type_code):
        return list(self.combinations.get(type_code, ()))

    def list_names(self, activity_id):
        return [TariffName(self.details.name_id, activity_id, "Prestation test")]

    def list_categories(self, activity_id):
        return [PricingCategory(1, activity_id, "Base")]

    def list_groups(self, activity_id):
        return []

    def list_cotisations(self):
        return []

    def list_caisses(self):
        return [(0, "Caisse non spécifiée")]

    def list_quotient_types(self):
        return []

    def list_units(self, activity_id):
        return [(10, "Journée")]

    def save_tariff(self, details, lines):
        self.saved_details = details
        self.saved_lines = list(lines)
        return details.tariff_id or 50

    def save_combinations(self, tariff_id, type_code, combinations):
        self.saved_combinations.append((tariff_id, type_code, tuple(combinations)))


class ActivityPricingCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _question_database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE questionnaire_categories (
                    IDcategorie INTEGER PRIMARY KEY,
                    type TEXT
                );
                CREATE TABLE questionnaire_questions (
                    IDquestion INTEGER PRIMARY KEY,
                    IDcategorie INTEGER,
                    label TEXT,
                    controle TEXT,
                    ordre INTEGER
                );
                INSERT INTO questionnaire_categories VALUES (1, 'famille');
                INSERT INTO questionnaire_categories VALUES (2, 'individu');
                INSERT INTO questionnaire_questions VALUES (12, 1, 'Participation', 'montant', 1);
                INSERT INTO questionnaire_questions VALUES (13, 2, 'Coefficient', 'decimal', 2);
                INSERT INTO questionnaire_questions VALUES (14, 1, 'Commentaire', 'ligne_texte', 3);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def _details(self, type_code="JOURN", beneficiary="individu", options=None):
        return TariffDetails(
            tariff_id=42,
            activity_id=7,
            name_id=3,
            date_start=dt.date(2026, 9, 1),
            date_end=None,
            type_code=type_code,
            method_code="montant_unique",
            category_ids=(1,),
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
            etats="reservation;present;absenti",
            date_facturation="date_debut_forfait" if type_code in {"FORFAIT", "CREDIT"} else None,
            options=options,
            forfait_saisie_manuelle=False,
            forfait_saisie_auto=False,
            forfait_suppression_auto=False,
            forfait_duree=None,
            forfait_beneficiaire=beneficiary,
            etiquettes=None,
        )

    def test_forfait_personnalise_is_detected_and_not_deleted_on_save(self):
        database = self._question_database()
        combination = UnitCombination(8, (10,), dt.date(2026, 9, 9), None)
        repo = FakePricingRepository(
            database,
            self._details("FORFAIT", options=None),
            {"FORFAIT": [combination]},
        )
        dialog = TariffEditDialog(repo, 7, 3, 42)
        self.addCleanup(dialog.close)

        self.assertEqual(historic_forfait_mode(None, [combination]), "custom")
        self.assertEqual(dialog.forfait_mode.currentData(), "custom")

        dialog._save()
        saved_forfait = [call for call in repo.saved_combinations if call[1] == "FORFAIT"]
        self.assertEqual(len(saved_forfait), 1)
        self.assertEqual(saved_forfait[0][2], (combination,))

    def test_historic_duration_fields_roundtrip_as_hhmm(self):
        self.assertIn("duree_min", LEGACY_HHMM_FIELDS)
        self.assertIn("temps_facture", LEGACY_HHMM_FIELDS)
        self.assertEqual(parse_legacy_hhmm("24:59", "duree_max"), "24:59")
        with self.assertRaises(ValueError):
            parse_legacy_hhmm("25:00", "duree_max")

        table = LegacyCalculationTable(())
        self.addCleanup(table.close)
        line = TariffLine(
            5,
            {
                "duree_min": "01:30",
                "duree_max": "24:00",
                "temps_facture": "02:15",
                "montant_unique": 8.5,
                "montant_questionnaire": None,
                "label": "Test",
            },
        )
        table.set_method("duree_montant_unique", [line])
        values = table.lines()[0].values
        self.assertEqual(values["duree_min"], "01:30")
        self.assertEqual(values["duree_max"], "24:00")
        self.assertEqual(values["temps_facture"], "02:15")

    def test_montant_questionnaire_is_a_question_reference_not_a_number(self):
        table = LegacyCalculationTable(((12, "Participation (Famille)"), (13, "Coefficient (Individu)")))
        self.addCleanup(table.close)
        table.set_method(
            "montant_unique",
            [TariffLine(6, {"montant_unique": 9.5, "montant_questionnaire": 12})],
        )
        column = table.fields.index("montant_questionnaire")
        combo = table.table.cellWidget(0, column)
        self.assertIsInstance(combo, QComboBox)
        self.assertEqual(combo.currentData(), 12)
        self.assertEqual(table.lines()[0].values["montant_questionnaire"], 12)

        # Un ID historique devenu indisponible doit rester round-trippable.
        table.set_method(
            "montant_unique",
            [TariffLine(7, {"montant_unique": 9.5, "montant_questionnaire": 99})],
        )
        combo = table.table.cellWidget(0, column)
        self.assertEqual(combo.currentData(), 99)
        self.assertEqual(table.lines()[0].values["montant_questionnaire"], 99)

    def test_only_amount_and_decimal_questions_are_offered(self):
        database = self._question_database()
        repo = FakePricingRepository(database, self._details())
        self.assertEqual(
            list_amount_questions(repo),
            ((12, "Participation (Famille)"), (13, "Coefficient (Individu)")),
        )

    def test_credit_null_beneficiary_keeps_historic_family_semantics(self):
        database = self._question_database()
        repo = FakePricingRepository(database, self._details("CREDIT", beneficiary=None))
        dialog = TariffEditDialog(repo, 7, 3, 42)
        self.addCleanup(dialog.close)

        self.assertEqual(historic_credit_beneficiary(None), "famille")
        self.assertEqual(dialog.credit_beneficiary.currentData(), "famille")

        dialog._save()
        self.assertIsNotNone(repo.saved_details)
        self.assertEqual(repo.saved_details.forfait_beneficiaire, "famille")


if __name__ == "__main__":
    unittest.main()
