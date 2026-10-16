# -*- coding: utf-8 -*-
"""RC8 #430 : +1 repas directeur detache, sans schema ni reseau."""
import ast
import sys
import unittest
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "noethys"))
from Utils.UTILS_Commandes_directeur import SupplementDirecteur


class RepasDirecteurTests(unittest.TestCase):
    def setUp(self):
        self.deja = set()
        self.jour = date(2026, 10, 19)
        self.param = {"repas_directeur_detache": True, "site_directeur": "Site A", "service_directeur": "midi"}

    def test_desactive_par_defaut_et_options_anciennes(self):
        self.assertEqual(SupplementDirecteur({"unites": [(1, 2)]}, self.jour, self.deja), 0)
        self.assertEqual(SupplementDirecteur({}, self.jour, self.deja), 0)
        self.assertFalse(self.deja)

    def test_un_repas_par_site_date_service(self):
        self.assertEqual(SupplementDirecteur(self.param, self.jour, self.deja), 1)
        self.assertEqual(SupplementDirecteur(self.param, self.jour, self.deja), 0)
        self.assertEqual(SupplementDirecteur(dict(self.param, site_directeur=" site a "), self.jour, self.deja), 0)
        self.assertEqual(SupplementDirecteur(dict(self.param, site_directeur="Site B"), self.jour, self.deja), 1)
        self.assertEqual(SupplementDirecteur(dict(self.param, service_directeur="soir"), self.jour, self.deja), 1)
        self.assertEqual(SupplementDirecteur(self.param, date(2026, 10, 20), self.deja), 1)

    def test_site_ou_service_absent_ne_donne_pas_de_bonus(self):
        for cle in ("site_directeur", "service_directeur"):
            with self.subTest(cle=cle):
                self.assertEqual(SupplementDirecteur(dict(self.param, **{cle: "  "}), self.jour, self.deja), 0)
        self.assertFalse(self.deja)

    def test_une_option_false_ne_modifie_pas_le_total(self):
        self.assertEqual(SupplementDirecteur(dict(self.param, repas_directeur_detache=False), self.jour, self.deja), 0)
        self.assertEqual(37 + SupplementDirecteur(self.param, self.jour, self.deja), 38)

    def test_gui_ajoute_bonus_uniquement_sur_unite_ouverte(self):
        ctrl = (RACINE / "noethys/Ctrl/CTRL_Commande_repas.py").read_text(encoding="utf-8")
        page = (RACINE / "noethys/Dlg/DLG_Saisie_commandes_colonne.py").read_text(encoding="utf-8")
        ast.parse(ctrl)
        ast.parse(page)
        self.assertIn('if ouvert:\n                            suggestion += UTILS_Commandes_directeur.SupplementDirecteur', ctrl)
        self.assertIn('self.check_directeur.GetValue()', page)
        self.assertIn('self.ctrl_site_directeur.GetValue().strip()', page)


if __name__ == "__main__":
    unittest.main()
