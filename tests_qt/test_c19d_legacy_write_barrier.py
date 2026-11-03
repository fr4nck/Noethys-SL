"""C19d : regles wx observees, interpretation Qt fail-closed, aucune ecriture."""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from noethys_qt.billing_preflight_core import BillingObservation
from noethys_qt.legacy_write_barrier import (
    PermissionSnapshot, PeriodWindow, PeriodSnapshot, WriteBarrierReport,
    check_declared_permission, check_declared_period,
    check_historical_invoice_boundary, audit_before_write,
)

D = dt.date
REPO = Path(__file__).resolve().parents[1]
OP = "consumption_state_change"
PERM = {("consommations_conso", "modifier"): "autorisation"}


def period(start=D(2026, 10, 1), end=D(2026, 10, 31),
           *, conso=False, prestation=False, invoice=False):
    return PeriodWindow(start, end, conso, prestation, invoice)


def observation(*, state="present", invoice_id=501):
    return BillingObservation(
        1, 501, 10, 100, state, 301, "12.005", invoice_id,
        28, 1, ("PRESTATION_PARTAGEE",),
    )


class C19dLegacyContractTests(unittest.TestCase):
    def test_source_contract_is_explicitly_pinned(self):
        users = (REPO / "noethys/Utils/UTILS_Utilisateurs.py").read_text(
            encoding="utf-8"
        )
        gestion = (REPO / "noethys/Utils/UTILS_Gestion.py").read_text(
            encoding="utf-8"
        )
        grid = (REPO / "noethys/Ctrl/CTRL_Grille_cases.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('def VerificationDroits(dictUtilisateur=None', users)
        self.assertIn('if dictUtilisateur == None or ("droits" in dictUtilisateur) == False :\n        return True', users)
        self.assertIn('key = (categorie, action)', users)
        self.assertIn('        return resultat\n    return True', users)
        self.assertIn('\ndef AfficheDLGInterdiction():', users)
        self.assertIn('listeCategories.append("prestations")', gestion)
        self.assertIn('if date >= periode.date_debut and date <= periode.date_fin', gestion)
        self.assertIn('verrou_consommations, verrou_prestations, verrou_factures', gestion)
        self.assertGreaterEqual(grid.count('def ModifieEtat(self, conso=None, etat="reservation"):'), 3)
        self.assertIn('self.grid.gestion.Verification("consommations", self.date)', grid)
        self.assertIn('if prestation["IDfacture"] and not prestation["forfait_date_debut"]:', grid)

    def test_missing_identity_or_rights_are_not_grants(self):
        for snap in (
            None, PermissionSnapshot(None, PERM, True),
            PermissionSnapshot(5, None, True),
            PermissionSnapshot(5, {}, True),
            PermissionSnapshot(5, PERM, False),
            PermissionSnapshot(True, PERM, True),
        ):
            with self.subTest(snapshot=snap):
                self.assertEqual(
                    check_declared_permission(snap, activity_id=1, operation=OP).status,
                    "INCONNU",
                )

    def test_unknown_or_malformed_activity_does_not_allow(self):
        snap = PermissionSnapshot(5, PERM, True)
        for value in (None, 0, -1, True, "1"):
            self.assertEqual(
                check_declared_permission(snap, activity_id=value, operation=OP).status,
                "INCONNU",
            )

    def test_declared_authorisation_is_not_a_real_session(self):
        rights = check_declared_permission(
            PermissionSnapshot(5, PERM, True), activity_id=10, operation=OP,
        )
        self.assertEqual(rights.status, "DECLARE")
        report = audit_before_write(
            operation=OP, permissions=PermissionSnapshot(5, PERM, True),
            periods=PeriodSnapshot((), True),
            activity_id=10, consumption_date=D(2026, 10, 15),
            observation=observation(invoice_id=None), target_state="present",
        )
        self.assertEqual(report.permission.status, "DECLARE")
        self.assertEqual(report.period.status, "DECLARE_OUVERT")
        self.assertFalse(report.executable)
        self.assertIn("VERDICT : BLOQUE", report.report)

    def test_interdiction_is_refused(self):
        snap = PermissionSnapshot(
            5, {("consommations_conso", "modifier"): "interdiction"}, True,
        )
        self.assertEqual(
            check_declared_permission(snap, activity_id=10, operation=OP).status,
            "REFUSE",
        )

    def test_unrecognized_prefix_is_not_a_grant(self):
        for val in ("autorisation_anything", "interdiction_exception",
                    "restriction_pas_de_regle", "autorisation:10"):
            snap = PermissionSnapshot(5, {("consommations_conso", "modifier"): val}, True)
            self.assertEqual(
                check_declared_permission(snap, activity_id=10, operation=OP).status,
                "INCONNU",
            )

    def test_restriction_activity_exact_ids(self):
        snap = PermissionSnapshot(
            5, {("consommations_conso", "modifier"): "restriction_activites:10;20"},
            True,
        )
        self.assertEqual(
            check_declared_permission(snap, activity_id=20, operation=OP).status,
            "DECLARE",
        )
        self.assertEqual(
            check_declared_permission(snap, activity_id=21, operation=OP).status,
            "REFUSE",
        )

    def test_restriction_activity_malformed(self):
        for val in (
            "restriction_activites:", "restriction_activites:abc",
            "restriction_activites:10;", "restriction_activites:10;10",
            "restriction_activites:0", "restriction_autres:10",
        ):
            snap = PermissionSnapshot(5, {("consommations_conso", "modifier"): val}, True)
            self.assertEqual(
                check_declared_permission(snap, activity_id=10, operation=OP).status,
                "INCONNU",
            )

    def test_restriction_groups_require_resolved_map(self):
        snap = PermissionSnapshot(
            5, {("consommations_conso", "modifier"): "restriction_groupes:4;6"},
            True,
        )
        self.assertEqual(
            check_declared_permission(snap, activity_id=10, operation=OP).status,
            "INCONNU",
        )
        good = PermissionSnapshot(5, snap.rules, True, {4: (9, 10), 6: (15,)})
        self.assertEqual(
            check_declared_permission(good, activity_id=10, operation=OP).status,
            "DECLARE",
        )
        self.assertEqual(
            check_declared_permission(good, activity_id=2, operation=OP).status,
            "REFUSE",
        )

    def test_restriction_groups_with_partial_or_invalid_map(self):
        for mapping in ({4: (10,)}, {4: (True,), 6: (12,)}, {4: [], 6: "10"}):
            snap = PermissionSnapshot(
                5, {("consommations_conso", "modifier"): "restriction_groupes:4;6"},
                True, mapping,
            )
            self.assertEqual(
                check_declared_permission(snap, activity_id=10, operation=OP).status,
                "INCONNU",
            )

    def test_incomplete_period_inventory_is_not_open(self):
        for periods in (None, PeriodSnapshot(None, True), PeriodSnapshot((), False)):
            self.assertEqual(
                check_declared_period(
                    periods, consumption_date=D(2026, 10, 2), operation=OP
                ).status,
                "INCONNU",
            )

    def test_inclusive_boundaries_and_consumption_lock(self):
        periods = PeriodSnapshot((period(conso=True),), True)
        for day in (D(2026, 10, 1), D(2026, 10, 31)):
            self.assertEqual(
                check_declared_period(
                    periods, consumption_date=day, operation=OP
                ).status, "VERROUILLE",
            )
        self.assertEqual(
            check_declared_period(
                periods, consumption_date=D(2026, 11, 1), operation=OP
            ).status, "DECLARE_OUVERT",
        )

    def test_consumption_inherits_prestation_lock(self):
        periods = PeriodSnapshot((period(prestation=True),), True)
        self.assertEqual(
            check_declared_period(
                periods, consumption_date="2026-10-15", operation=OP
            ).status, "VERROUILLE",
        )

    def test_invoice_uses_conservative_both_categories(self):
        periods = PeriodSnapshot((period(invoice=True),), True)
        self.assertEqual(
            check_declared_period(
                periods, consumption_date=D(2026, 10, 15),
                operation="invoice_creation",
            ).status, "VERROUILLE",
        )
        self.assertEqual(
            check_declared_period(
                PeriodSnapshot((period(prestation=True),), True),
                consumption_date=D(2026, 10, 15),
                operation="invoice_creation",
            ).status, "VERROUILLE",
        )

    def test_invalid_dates_and_inconsistent_periods(self):
        for date in (None, "2026-14-20", True, dt.datetime(2026, 10, 1), 2):
            self.assertEqual(
                check_declared_period(
                    PeriodSnapshot((), True),
                    consumption_date=date, operation=OP,
                ).status, "INCONNU",
            )
        bad = PeriodSnapshot((
            PeriodWindow(D(2026, 10, 31), D(2026, 10, 1), True, False, False),
        ), True)
        self.assertEqual(
            check_declared_period(
                bad, consumption_date=D(2026, 10, 2), operation=OP
            ).status, "INCONNU",
        )

    def test_unknown_lock_cannot_be_treated_as_open(self):
        periods = PeriodSnapshot((
            PeriodWindow(D(2026, 10, 1), D(2026, 10, 31),
                         None, False, False),
        ), True)
        self.assertEqual(
            check_declared_period(
                periods, consumption_date=D(2026, 10, 5), operation=OP
            ).status, "INCONNU",
        )

    def test_invoice_boundary_crossing_requires_old_and_new_groups(self):
        result = check_historical_invoice_boundary(
            old_state="attente", target_state="present",
            invoice_id=501, forfait_start=None,
        )
        self.assertEqual(result.status, "BLOQUE_WX")
        same_family = check_historical_invoice_boundary(
            old_state="reservation", target_state="present",
            invoice_id=501, forfait_start=None,
        )
        self.assertEqual(same_family.status, "NON_SUFFISANT")
        self.assertEqual(
            check_historical_invoice_boundary(
                old_state="present", target_state="absentj",
                invoice_id=501, forfait_start="2026-09-01",
            ).status, "NON_SUFFISANT",
        )

    def test_unknown_invoice_or_state_is_not_qualified(self):
        self.assertEqual(
            check_historical_invoice_boundary(
                old_state="bogus", target_state="present",
                invoice_id=None, forfait_start=None,
            ).status, "INCONNU",
        )
        self.assertEqual(
            check_historical_invoice_boundary(
                old_state="present", target_state="absentj",
                invoice_id=True, forfait_start=None,
            ).status, "INCONNU",
        )

    def test_invoice_creation_has_no_invented_permission(self):
        rights = check_declared_permission(
            PermissionSnapshot(
                5, {("facturation_factures", "creer"): "autorisation"}, True,
            ), activity_id=10, operation="invoice_creation",
        )
        self.assertEqual(rights.status, "INCONNU")
        report = audit_before_write(
            operation="invoice_creation", permissions=PermissionSnapshot(5, PERM, True),
            periods=PeriodSnapshot((), True),
            consumption_date=D(2026, 10, 14),
        )
        self.assertFalse(report.executable)
        self.assertEqual(report.financial.status, "NON_RACCORDE")

    def test_even_perfect_looking_snapshots_cannot_issue_write(self):
        report = audit_before_write(
            operation=OP, permissions=PermissionSnapshot(5, PERM, True),
            periods=PeriodSnapshot((), True),
            activity_id=10, consumption_date=D(2026, 10, 14),
            observation=observation(invoice_id=None),
            target_state="present",
        )
        self.assertFalse(report.executable)
        self.assertIn("AUCUNE_AUTORISATION_DE_FACTURER", report.reasons)
        with self.assertRaises(ValueError):
            WriteBarrierReport(
                OP, report.permission, report.period, report.financial,
                report.reasons, executable=True,
            )

    def test_crossing_is_reported_and_still_no_write(self):
        report = audit_before_write(
            operation=OP, permissions=PermissionSnapshot(5, PERM, True),
            periods=PeriodSnapshot((), True),
            activity_id=10, consumption_date=D(2026, 10, 14),
            observation=observation(state="attente"),
            target_state="present",
        )
        self.assertEqual(report.financial.status, "BLOQUE_WX")
        self.assertIn("FRONTIERE_FACTURATION", report.reasons)
        self.assertFalse(report.executable)

    def test_unsupported_operation_fail_closed(self):
        with self.assertRaises(ValueError):
            audit_before_write(operation="force_invoice")
        with self.assertRaises(ValueError):
            check_declared_permission(None, activity_id=1, operation="force_invoice")
        with self.assertRaises(ValueError):
            check_declared_period(None, consumption_date=D(2026, 10, 1),
                                  operation="force_invoice")


if __name__ == "__main__":
    unittest.main()
