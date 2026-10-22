# -*- coding: utf-8 -*-
"""Contrats UI wx des adhesions automatiques : analyse sans ouverture wx.

Les actions reelles seront recettees sur un poste Windows pilote.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContratsUxAssociation(unittest.TestCase):
    def test_ecran_cotisation_propose_mode_et_enregistre_par_type(self):
        source = (ROOT / "noethys" / "Dlg" /
                  "DLG_Saisie_type_cotisation.py").read_text(encoding="utf-8")
        self.assertIn("self.ctrl_mode_adhesion = wx.Choice(", source)
        self.assertIn("self.ctrl_mode_adhesion.SetSelection(0)", source)
        self.assertIn("UTILS_Adhesions.LireModeAssociation(self.IDtype_cotisation)", source)
        self.assertIn("UTILS_Adhesions.EnregistrerModeAssociation(self.IDtype_cotisation, mode)", source)
        self.assertIn("self.ctrl_mode_adhesion.Enable(self.ctrl_type.GetSelection() == 1)", source)

    def test_decocher_un_type_ne_supprime_pas_les_autres_activites(self):
        source = (ROOT / "noethys" / "Dlg" /
                  "DLG_Activite_obligations.py").read_text(encoding="utf-8")
        debut = source.index("class CheckListBoxCotisations(")
        fin = source.index("class CheckListBoxRenseignements(", debut)
        bloc = source[debut:fin]
        self.assertIn('"IDcotisation_activite",', bloc)
        self.assertIn("associations_existantes[IDtype_cotisation]", bloc)
        self.assertNotIn('DB.ReqDEL("cotisations_activites", "IDtype_cotisation"', bloc)

    def test_activite_sans_lien_initialise_les_associations(self):
        source = (ROOT / "noethys" / "Dlg" /
                  "DLG_Activite_obligations.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        cls = next(x for x in arbre.body if isinstance(x, ast.ClassDef)
                   and x.name == "CheckListBoxCotisations")
        sauvegarde = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                          and x.name == "Sauvegarde")
        # L'affectation doit être au niveau de la méthode, avant le for,
        # même quand la liste des associations existantes est vide.
        affectations = [
            i for i, x in enumerate(sauvegarde.body)
            if isinstance(x, ast.Assign)
            and any(isinstance(c, ast.Name) and c.id == "associations_existantes"
                    for c in x.targets)
        ]
        boucles = [
            i for i, x in enumerate(sauvegarde.body)
            if isinstance(x, ast.For) and isinstance(x.target, ast.Tuple)
        ]
        self.assertEqual(len(affectations), 1)
        self.assertTrue(boucles)
        self.assertLess(affectations[0], boucles[0])

    def test_raccordement_wx_apres_commit_pas_dans_la_transaction(self):
        source = (ROOT / "noethys" / "Dlg" /
                  "DLG_Inscription.py").read_text(encoding="utf-8")
        methode = source[source.index("    def Sauvegarde(self):", source.index("class Page_Activite")):
                         source.index("    def GetCompteFamille", source.index("class Page_Activite"))]
        self.assertLess(methode.index("DB.Commit()"),
                        methode.index("ActualiserActivitesApresInscription(self.IDinscription)"))
        self.assertNotIn("CreerAdhesion(", methode)
        self.assertIn("except Exception as err:", methode)


if __name__ == "__main__":
    unittest.main()
