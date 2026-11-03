"""C19e: droit facturation_factures/creer controle activite par activite.

Pas de facturation, pas de connexion au profil, pas de droit executable.
"""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from noethys_qt.invoice_scope_contract import (
    InvoiceLineEvidence, InvoiceScopeReport, inspect_invoice_scope,
)
from noethys_qt.legacy_write_barrier import (
    Check, PermissionSnapshot, PeriodSnapshot, PeriodWindow,
)

D = dt.date
GOOD_RULE = {("facturation_factures", "creer"): "autorisation"}


def line(
    prest=301, activity=1, *, family=100, payer=201,
    amount="12.005", invoice=None, day=D(2026, 10, 5),
):
    return InvoiceLineEvidence(
        prest, activity, family, payer, day, amount, invoice,
    )


def snapshot(rule=GOOD_RULE, *, complete=True, actor=7, groups=None):
    return PermissionSnapshot(actor, rule, complete, groups)


def inspect(
    activities=(1, 2), lines=None, permissions=None, periods=None,
    family=100, payer=201,
):
    if lines is None:
        lines = (line(301, 1), line(302, 2, amount="-1.005"))
    if permissions is None:
        permissions = snapshot()
    if periods is None:
        periods = PeriodSnapshot((), True)
    return inspect_invoice_scope(
        selected_activities=activities, lines=lines,
        family_id=family, payer_id=payer,
        permissions=permissions, periods=periods,
    )


class C19eInvoiceScopeTests(unittest.TestCase):
    def test_historical_key_and_source_are_pinned(self):
        repo = Path(__file__).resolve().parents[1]
        wx = (repo / "noethys/Dlg/DLG_Factures_generation_parametres.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('VerificationDroitsUtilisateurActuel("facturation_factures", "creer"', wx)
        self.assertIn('for IDactivite in listeActivites:', wx)

    def test_all_declared_rights_still_do_not_authorize_writing(self):
        report = inspect()
        self.assertEqual([c.status for _, c in report.permissions], ["DECLARE"] * 2)
        self.assertEqual([c.status for _, c in report.periods], ["DECLARE_OUVERT"] * 2)
        self.assertFalse(report.executable)
        self.assertIn("AUCUNE_FACTURATION_POSSIBLE", report.findings)
        self.assertIn("DECISION : BLOQUE", report.summary)

    def test_no_activities_refused_even_with_perfect_rights(self):
        report = inspect(activities=())
        self.assertIn("PERIMETRE_ACTIVITES_VIDE_OU_INVALIDE", report.findings)
        self.assertFalse(report.permissions)
        self.assertFalse(report.executable)

    def test_malformed_activities_fail_closed(self):
        for value in ((1, 1), (0,), (-1,), (True,), ("1",), [1, 2], None):
            with self.subTest(value=value):
                report = inspect(activities=value)
                self.assertIn("PERIMETRE_ACTIVITES_VIDE_OU_INVALIDE", report.findings)
                self.assertFalse(report.executable)

    def test_one_forbidden_activity_blocks_entire_scope(self):
        rights = snapshot({
            ("facturation_factures", "creer"): "restriction_activites:1"
        })
        report = inspect(permissions=rights)
        self.assertEqual(
            [c.status for _, c in report.permissions], ["DECLARE", "REFUSE"]
        )
        self.assertIn("DROIT_INTERDIT_POUR_AU_MOINS_UNE_ACTIVITE", report.findings)

    def test_explicit_interdiction_for_every_activity(self):
        rights = snapshot({("facturation_factures", "creer"): "interdiction"})
        report = inspect(permissions=rights)
        self.assertEqual(
            [c.status for _, c in report.permissions], ["REFUSE", "REFUSE"]
        )

    def test_missing_rights_and_actor_fail_closed(self):
        for rights in (
            snapshot({}), snapshot(None), snapshot(complete=False),
            snapshot(actor=None), snapshot(actor=True), snapshot(actor=0),
            None,
        ):
            with self.subTest(rights=rights):
                # Pass explicit null rather than the convenience inspect default.
                report = inspect_invoice_scope(
                    selected_activities=(1,), lines=(line(),),
                    family_id=100, payer_id=201, permissions=rights,
                    periods=PeriodSnapshot((), True),
                )
                self.assertEqual(report.permissions[0][1].status, "INCONNU")
                self.assertFalse(report.executable)

    def test_unrecognized_and_ambiguous_grants_never_count(self):
        for value in (
            "autorisation:1", "autorisation_override",
            "interdiction_exception", "restriction_all:1",
            "restriction_groupes:", "restriction_activites:1;",
            "restriction_activites:1;1", "restriction_activites:01;X",
            "restriction_activites:True", "restriction_activites:0",
        ):
            with self.subTest(value=value):
                report = inspect(
                    permissions=snapshot({("facturation_factures", "creer"): value})
                )
                self.assertTrue(all(c.status == "INCONNU" for _, c in report.permissions))

    def test_declared_activity_restriction_exhaustive(self):
        rights = snapshot({("facturation_factures", "creer"):
                           "restriction_activites:1;2"})
        report = inspect(permissions=rights)
        self.assertEqual([c.status for _, c in report.permissions], ["DECLARE"] * 2)

    def test_group_restriction_needs_complete_resolution(self):
        rights = snapshot(
            {("facturation_factures", "creer"): "restriction_groupes:8;9"},
            groups={8: (1,), 9: (2,)},
        )
        report = inspect(permissions=rights)
        self.assertTrue(all(c.status == "DECLARE" for _, c in report.permissions))
        self.assertFalse(report.executable)

    def test_group_restriction_missing_map_fails_closed(self):
        for mapping in (None, {}, {8: (1,)},
                        {8: (1,), 9: ()}, {8: (True,), 9: (2,)}):
            with self.subTest(mapping=mapping):
                rights = snapshot(
                    {("facturation_factures", "creer"): "restriction_groupes:8;9"},
                    groups=mapping,
                )
                report = inspect(permissions=rights)
                self.assertTrue(all(c.status == "INCONNU" for _, c in report.permissions))

    def test_unrelated_right_cannot_authorize_invoicing(self):
        rights = snapshot({("consommations_conso", "modifier"): "autorisation"})
        report = inspect(permissions=rights)
        self.assertTrue(all(c.status == "INCONNU" for _, c in report.permissions))

    def test_selected_activities_must_exactly_match_prestations(self):
        for activities, lines in (
            ((1,), (line(301, 1), line(302, 2))),
            ((1, 2), (line(301, 1),)),
            ((1, 2), (line(301, 1), line(302, 3))),
        ):
            with self.subTest(activities=activities, lines=lines):
                report = inspect(activities=activities, lines=lines)
                self.assertIn("ACTIVITES_PRESTATIONS_NON_EXHAUSTIVES", report.findings)

    def test_duplicate_or_invalid_prestations_never_validated(self):
        for lines in (
            (line(301, 1), line(301, 2)),
            (line(0, 1), line(302, 2)),
            (line(True, 1), line(302, 2)),
        ):
            with self.subTest(lines=lines):
                report = inspect(lines=lines)
                self.assertIn("PRESTATION_INVALIDE_OU_DOUBLON", report.findings)

    def test_empty_or_non_tuple_lines_fail_closed(self):
        for lines in ((), [], "line", (line(301, 1), None)):
            with self.subTest(lines=lines):
                report = inspect(lines=lines)
                self.assertIn("PRESTATIONS_ABSENTES_OU_INVALIDES", report.findings)
                self.assertFalse(report.executable)

    def test_payer_and_family_must_match_every_line(self):
        for kw in ({"family": 101}, {"payer": 202}):
            with self.subTest(kw=kw):
                report = inspect(lines=(line(301, 1, **kw), line(302, 2)))
                self.assertIn("COMPTE_PAYEUR_OU_FAMILLE_INCOHERENT", report.findings)
        report = inspect(family=True)
        self.assertIn("FAMILLE_OU_COMPTE_PAYEUR_NON_QUALIFIE", report.findings)

    def test_already_invoiced_prestation_is_excluded(self):
        report = inspect(lines=(
            line(301, 1, invoice=501), line(302, 2),
        ))
        self.assertIn("PRESTATION_DEJA_FACTUREE", report.findings)

    def test_invalid_invoice_reference_is_not_ignored(self):
        report = inspect(lines=(
            line(301, 1, invoice=True), line(302, 2),
        ))
        self.assertIn("ID_FACTURE_INVALIDE", report.findings)

    def test_fractional_negative_zero_amounts_not_rounded(self):
        values = ("12.005", "-1.005", "0.00", "1000.0003")
        for value in values:
            with self.subTest(value=value):
                source = (line(301, 1, amount=value), line(302, 2))
                report = inspect(lines=source)
                self.assertFalse(
                    any(code.startswith("MONTANT_BRUT_") for code in report.findings)
                )
                self.assertEqual(source[0].raw_amount, value)
                self.assertFalse(report.executable)

    def test_invalid_or_nonfinite_amounts_refused(self):
        for value in ("nan", "NaN", "Infinity", "bad"):
            report = inspect(lines=(line(301, 1, amount=value), line(302, 2)))
            self.assertTrue(
                any(code.startswith("MONTANT_BRUT_") for code in report.findings)
            )
        report = inspect(lines=(line(301, 1, amount=None), line(302, 2)))
        self.assertIn("MONTANT_BRUT_NON_QUALIFIE", report.findings)

    def test_period_locks_at_both_inclusive_endpoints(self):
        p = PeriodSnapshot((
            PeriodWindow(D(2026, 10, 1), D(2026, 10, 5), False, True, False),
        ), True)
        report = inspect(lines=(line(301, 1), line(302, 2)), periods=p)
        self.assertTrue(all(c.status == "VERROUILLE" for _, c in report.periods))
        self.assertIn("PERIODES_MANQUANTES_OU_VERROUILLEES", report.findings)

    def test_missing_periods_never_inferred_open(self):
        report = inspect_invoice_scope(
            selected_activities=(1,), lines=(line(),), family_id=100,
            payer_id=201, permissions=snapshot(), periods=None,
        )
        self.assertEqual(report.periods[0][1].status, "INCONNU")
        self.assertIn("PERIODES_MANQUANTES_OU_VERROUILLEES", report.findings)

    def test_invalid_date_reports_unknown(self):
        report = inspect(lines=(
            line(301, 1, day="2026-10-05"), line(302, 2),
        ), periods=PeriodSnapshot((), True))
        self.assertEqual(report.periods[0][1].status, "DECLARE_OUVERT")
        report2 = inspect(lines=(
            line(301, 1, day=None), line(302, 2),
        ), periods=PeriodSnapshot((), True))
        self.assertEqual(report2.periods[0][1].status, "INCONNU")

    def test_no_mutation_of_permission_or_prestation_sources(self):
        rule = dict(GOOD_RULE)
        source = (line(301, 1), line(302, 2))
        original = tuple(source)
        report = inspect(permissions=snapshot(rule), lines=source)
        self.assertEqual(rule, GOOD_RULE)
        self.assertEqual(source, original)
        self.assertEqual(report.checked_prestation_ids, (301, 302))

    def test_executable_true_cannot_be_constructed(self):
        report = inspect()
        with self.assertRaises(ValueError):
            InvoiceScopeReport(
                report.selected_activity_ids,
                report.checked_prestation_ids,
                report.permissions,
                report.periods,
                report.findings, executable=True,
            )

    def test_unknown_actor_is_not_promoted_by_fake_group(self):
        rights = snapshot(
            {("facturation_factures", "creer"): "restriction_groupes:8"},
            groups={8: (1, 2)}, actor=0,
        )
        report = inspect(permissions=rights)
        self.assertTrue(all(c.status == "INCONNU" for _, c in report.permissions))


if __name__ == "__main__":
    unittest.main()
