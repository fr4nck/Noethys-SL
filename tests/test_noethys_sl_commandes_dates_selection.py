# -*- coding: utf-8 -*-
"""Contrat du sélecteur commun dans les commandes de repas (sans wx ni base)."""
import ast
import datetime
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Saisie_commande.py"
CONTROL = Path(__file__).resolve().parents[1] / "noethys" / "Ctrl" / "CTRL_Grille_periode.py"


def source_ast():
    return ast.parse(SOURCE.read_text(encoding="utf-8"), str(SOURCE))


def selection_validator():
    node = next(x for x in source_ast().body
                if isinstance(x, ast.FunctionDef) and x.name == "VerifierSelectionDatesCommande")
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {"datetime": datetime}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["VerifierSelectionDatesCommande"]


def method_body(class_name, method_name):
    klass = next(x for x in source_ast().body
                 if isinstance(x, ast.ClassDef) and x.name == class_name)
    return next(x for x in klass.body
                if isinstance(x, ast.FunctionDef) and x.name == method_name)


class CommandesDatesSelectionTests(unittest.TestCase):
    def test_reutilise_module_commun_et_onglet_saison(self):
        source = SOURCE.read_text(encoding="utf-8")
        shared = CONTROL.read_text(encoding="utf-8")
        self.assertIn("from Ctrl import CTRL_Grille_periode", source)
        self.assertIn("CTRL_Grille_periode.CTRL(self, selection_multiple=False)", source)
        for label in ('Mois', 'Vacances', 'Année', 'Dates', 'Saison'):
            self.assertIn('_(u"' + label + '")', shared)
        for i in range(1, 6):
            self.assertIn('("periode_%d"' % i, shared)

    def test_valide_uniquement_une_plage_continue(self):
        valid = selection_validator()
        date = datetime.date
        self.assertEqual(valid([(date(2026, 11, 2), date(2026, 12, 19))]),
                         (date(2026, 11, 2), date(2026, 12, 19)))
        self.assertIsNone(valid([]))
        self.assertIsNone(valid([(date(2026, 11, 2), date(2026, 11, 3)),
                                 (date(2026, 11, 4), date(2026, 11, 5))]))
        self.assertIsNone(valid([(date(2026, 12, 19), date(2026, 11, 2))]))
        self.assertIsNone(valid([(None, date(2026, 11, 2))]))
        self.assertIsNone(valid([("2026-11-02", "2026-12-19")]))
        self.assertEqual(valid([(datetime.datetime(2026, 11, 2, 12),
                                 datetime.datetime(2026, 11, 2, 16))]),
                         (date(2026, 11, 2), date(2026, 11, 2)))

    def test_annulation_ne_modifie_ni_dates_ni_grille(self):
        method = method_body("Dialog", "OnBoutonChoisirPeriode")
        body = ast.unparse(method)
        self.assertIn("dlg.ShowModal() != wx.ID_OK", body)
        self.assertIn("dlg.Destroy()", body)
        self.assertIn("self.ctrl_date_debut.SetDate(date_debut)", body)
        self.assertIn("self.ctrl_date_fin.SetDate(date_fin)", body)
        self.assertIn("self.OnChoixDate()", body)
        self.assertLess(body.index("dlg.ShowModal()"), body.index("self.ctrl_date_debut.SetDate"))
        self.assertLess(body.index("self.ctrl_date_debut.SetDate"),
                        body.index("self.OnChoixDate()"))
        # La logique de création / sauvegarde de la commande reste hors du bouton.
        self.assertNotIn("ReqInsert", body)
        self.assertNotIn("ReqMAJ", body)
        self.assertNotIn("Sauvegarde(", body)

    def test_les_dates_existantes_sont_reprises_et_le_choix_est_simple(self):
        init = ast.unparse(method_body("DialogChoixPeriodeCommande", "__init__"))
        self.assertIn("'page': 3", init)
        self.assertIn("'dateDebut': bornes_actuelles[0]", init)
        self.assertIn("'dateFin': bornes_actuelles[1]", init)
        valider = ast.unparse(method_body("DialogChoixPeriodeCommande", "OnValider"))
        self.assertIn("VerifierSelectionDatesCommande(", valider)
        self.assertIn("self.EndModal(wx.ID_OK)", valider)
        dlg = ast.unparse(method_body("Dialog", "__init__"))
        self.assertIn("self.OnBoutonChoisirPeriode", dlg)
        self.assertIn("self.bouton_choisir_periode", dlg)


if __name__ == "__main__":
    unittest.main()
