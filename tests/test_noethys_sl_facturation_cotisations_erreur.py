# -*- coding: utf-8 -*-
"""Facturation : échec du contrôle des adhésions sans base ni wx réels."""
import ast
import datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

CHEMIN = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Factures_generation.py"


def extraire_preparation():
    racine = ast.parse(CHEMIN.read_text(encoding="utf-8"), filename=str(CHEMIN))
    dialogue = next(n for n in racine.body if isinstance(n, ast.ClassDef) and n.name == "Dialog")
    fonction = next(n for n in dialogue.body
                    if isinstance(n, ast.FunctionDef) and n.name == "PreparerCotisationsPourApercu")
    return compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                   str(CHEMIN), "exec")


class FacturationControleCotisationsTests(unittest.TestCase):
    def executer(self, choix, panne=True, cotisations=True):
        appels = []
        wx = types.SimpleNamespace(YES=1, NO=2, YES_NO=4, NO_DEFAULT=8, ICON_WARNING=16)
        def message_box(message, titre, style, parent):
            appels.append((message, titre, style))
            return choix
        wx.MessageBox = message_box

        def proposer(**params):
            if panne:
                raise TypeError("object of type 'NoneType' has no len()")
            return {"propositions": [], "a_verifier": []}

        utils = types.ModuleType("Utils")
        utils.UTILS_Adhesions_echeances = types.SimpleNamespace(Proposer=proposer)
        utils.UTILS_Identification = types.SimpleNamespace(GetIDutilisateur=lambda: 1)
        environnement = {"wx": wx, "_": lambda texte: texte, "datetime": datetime}
        with patch.dict(sys.modules, {"Utils": utils}):
            exec(extraire_preparation(), environnement)
            contexte = types.SimpleNamespace(dictParametres={
                "prestations": ["cotisation"] if cotisations else ["consommation"],
                "date_debut": datetime.date(2026, 10, 1),
                "date_fin": datetime.date(2026, 10, 31),
                "listeActivites": [1], "IDcompte_payeur": None,
            })
            resultat = environnement["PreparerCotisationsPourApercu"](contexte)
        return resultat, appels

    def test_refus_par_defaut_en_cas_d_erreur(self):
        resultat, appels = self.executer(choix=2)
        self.assertFalse(resultat)
        self.assertEqual(len(appels), 1)
        self.assertIn("AUCUNE nouvelle cotisation", appels[0][0])
        self.assertIn("Certaines cotisations peuvent manquer", appels[0][0])
        self.assertIn("NoneType", appels[0][0])
        self.assertEqual(appels[0][2], 4 | 8 | 16)

    def test_accord_explicite_permet_factures_prestations_existantes(self):
        resultat, appels = self.executer(choix=1)
        self.assertTrue(resultat)
        self.assertEqual(len(appels), 1)

    def test_controle_nominal_ne_demande_pas_de_confirmation(self):
        resultat, appels = self.executer(choix=2, panne=False)
        self.assertTrue(resultat)
        self.assertEqual(appels, [])

    def test_cotisations_non_selectionnees_ne_lancent_pas_de_controle(self):
        resultat, appels = self.executer(choix=2, cotisations=False)
        self.assertTrue(resultat)
        self.assertEqual(appels, [])


if __name__ == "__main__":
    unittest.main()
