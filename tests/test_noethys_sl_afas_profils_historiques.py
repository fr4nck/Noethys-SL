# -*- coding: utf-8 -*-
"""Régression des deux anciens profils CAF sans mutation de la base ALSH."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_AFAS_ProfilsHistoriques as P


class ProfilsHistoriquesTests(unittest.TestCase):
    def test_seuls_profils_caf_historiques_sont_cibles(self):
        for nom in ("Caf - Périscolaire", "CAF - EXTRASCOLAIRE",
                    "Caf - Periscolaire", "  Caf   -   Périscolaire  "):
            with self.subTest(nom=nom):
                self.assertTrue(P.EstProfilCAFHistorique(nom))
        for nom in ("", None, "CAF - Autres", "Caf - Périscolaire - 2026",
                    "Caf - Extra", "Etat global", "AFAS V2"):
            with self.subTest(nom=nom):
                self.assertFalse(P.EstProfilCAFHistorique(nom))

    def test_ancien_profil_est_assaini_uniquement_en_memoire(self):
        params = {"etat_consommations": ["reservation", "present", "absentj", "absenti"],
                  "jours_hors_vacances": [2], "forfait_presence_midi": 60}
        avant = {"etat_consommations": list(params["etat_consommations"]),
                 "jours_hors_vacances": [2], "forfait_presence_midi": 60}
        nouveaux, modifie = P.PreparerProfilCAFHistorique("Caf - Périscolaire", params)
        self.assertTrue(modifie)
        self.assertEqual(nouveaux["etat_consommations"], ["present"])
        self.assertEqual(params, avant)
        self.assertEqual(nouveaux["jours_hors_vacances"], [2])
        self.assertEqual(nouveaux["forfait_presence_midi"], 60)
        self.assertIsNot(nouveaux, params)

    def test_absences_et_reservations_exclues_du_realise_caf(self):
        for etats in (["present", "absenti"], ["present", "absentj"],
                      ["reservation", "present"], ["absenti"], [], None):
            with self.subTest(etats=etats):
                self.assertIsNotNone(P.ErreurEtatsProfilCAFHistorique("Caf - Extrascolaire", etats))
        self.assertIsNone(P.ErreurEtatsProfilCAFHistorique("Caf - Extrascolaire", ["present"]))

    def test_autres_profils_restant_libres(self):
        parametres = {"etat_consommations": ["reservation", "present", "absentj", "absenti"]}
        identique, modifie = P.PreparerProfilCAFHistorique("Statistiques de fréquentation", parametres)
        self.assertIs(identique, parametres)
        self.assertFalse(modifie)
        self.assertIsNone(P.ErreurEtatsProfilCAFHistorique(
            "Statistiques de fréquentation", ["reservation", "present", "absentj", "absenti"]))

    def test_ancien_profil_deja_corrige_est_inchange(self):
        parametres = {"etat_consommations": ["present"]}
        identique, modifie = P.PreparerProfilCAFHistorique("Caf - Périscolaire", parametres)
        self.assertIs(identique, parametres)
        self.assertFalse(modifie)

    def test_ecran_guard_charge_et_controle_sans_persistance_implicite(self):
        code = (NOETHYS / "Dlg" / "DLG_Etat_global.py").read_text(encoding="utf-8")
        arbre = ast.parse(code)
        dlg = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "Dialog")
        fonctions = {n.name: n for n in dlg.body if isinstance(n, ast.FunctionDef)}
        chargement = ast.unparse(fonctions["SetParametres"])
        apercu = ast.unparse(fonctions["Apercu"])
        self.assertIn("PreparerProfilCAFHistorique", chargement)
        self.assertIn("ErreurEtatsProfilCAFHistorique", apercu)
        self.assertNotIn("SetParametres(categorie=", chargement)
        self.assertNotIn("ReqInsert", chargement)
        self.assertNotIn("ReqDEL", chargement)
        self.assertNotIn("Enregistrer(", chargement)


if __name__ == "__main__":
    unittest.main()
