#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import unittest

from scripts import audit_branch_assignment_gaps as branch_audit


SOURCE = branch_audit.NOETHYS / "Dlg" / "DLG_Saisie_portail_demande.py"


def load_parser():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "ParseVentilationPaiement"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["ParseVentilationPaiement"]


class PortailPaymentVentilationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parse = staticmethod(load_parser())

    def test_mixed_invoice_and_period_ventilation_is_parsed(self):
        self.assertEqual(
            self.parse("F12#10.50,P7#3.25"),
            {"facture": {12: 10.5}, "periode": {7: 3.25}},
        )

    def test_trailing_empty_segment_is_tolerated(self):
        self.assertEqual(
            self.parse("F12#10.50,"),
            {"facture": {12: 10.5}, "periode": {}},
        )

    def test_leading_and_interior_empty_segments_are_rejected(self):
        for value in (",F12#10.50", "F12#10.50,,P7#3.25", "F12#10.50,,"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_unknown_prefix_is_rejected_instead_of_reusing_previous_type(self):
        with self.assertRaises(ValueError):
            self.parse("F12#10.50,X7#3.25")

    def test_empty_or_malformed_ventilation_is_rejected(self):
        for value in (None, "", ",", "F12", "P#3.25", "F12#abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_both_payment_paths_use_the_shared_parser(self):
        source = SOURCE.read_text(encoding="utf-8")
        # Une occurrence est la définition ; les deux autres sont les appels de
        # l'affichage et de l'application effective du paiement.
        self.assertEqual(source.count("ParseVentilationPaiement("), 3)

    def test_confirmed_unbound_candidates_are_gone_from_portal_file(self):
        findings = branch_audit.scan_file(SOURCE)
        forbidden = {
            ("MAJ_informations", "type_impaye"),
            ("Traitement_paiement_en_ligne", "type_impaye"),
            ("Appliquer_reservations", "texte"),
        }
        remaining = {
            (item["function"], item["name"])
            for item in findings
            if (item["function"], item["name"]) in forbidden
        }
        self.assertEqual(remaining, set())


if __name__ == "__main__":
    unittest.main()
