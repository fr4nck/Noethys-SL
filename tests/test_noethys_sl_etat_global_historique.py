# -*- coding: utf-8 -*-
"""Contrat de non-regression : Etat global des consommations historique.

La direction demande de garder la page de controle independante d'AFAS :
- les quatre statuts sont modifiables sans transformation ;
- le profil sauvegarde est recharge sans forcer Present ;
- aucun avertissement CAF n'apparait au chargement ou a l'apercu ;
- le selecteur multiple natif de l'ancienne version reste disponible ;
- les evolutions AFAS se font dans leur propre module.

Ces tests n'accedent a aucune donnee de production.
"""
import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))


def methode(fichier, classe, fonction):
    source = (NOETHYS / fichier).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    objet = next(
        n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe
    )
    return next(
        n for n in objet.body if isinstance(n, ast.FunctionDef) and n.name == fonction
    )


class ContratPageHistoriqueTests(unittest.TestCase):
    def test_etats_a_l_origine_et_selection_libre(self):
        fonction = methode("Ctrl/CTRL_Etat_global_options.py", "CTRL", "Remplissage")
        listes = [
            n for n in ast.walk(fonction)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "liste_codes_etats"
                    for t in n.targets)
        ]
        self.assertEqual(len(listes), 1)
        self.assertEqual(ast.literal_eval(listes[0].value),
                         ["reservation", "present", "absentj", "absenti"])
        texte = ast.unparse(fonction)
        for titre in ("Pointage en attente", "Présent",
                      "Absence justifiée", "Absence injustifiée"):
            self.assertIn(titre, texte)

    def test_profil_recharge_fidelement_sans_alerte_ni_filtre_caf(self):
        rechargement = ast.unparse(
            methode("Dlg/DLG_Etat_global.py", "Dialog", "SetParametres"))
        self.assertIn("self.ctrl_options.SetParametres(dictParametres)", rechargement)
        self.assertIn("self.ctrl_parametres.SetParametres(dictParametres)", rechargement)
        self.assertNotIn("UTILS_AFAS_ProfilsHistoriques", rechargement)
        self.assertNotIn("PreparerProfilCAFHistorique", rechargement)
        self.assertNotIn("MessageBox", rechargement)

    def test_apercu_ne_change_pas_les_quatre_etats(self):
        apercu = ast.unparse(
            methode("Dlg/DLG_Etat_global.py", "Dialog", "Apercu"))
        self.assertIn("self.ctrl_options.GetParametres()", apercu)
        self.assertNotIn("ErreurEtatsProfilCAFHistorique", apercu)
        self.assertNotIn("Profil CAF : états incompatibles", apercu)
        self.assertNotIn("PreparerProfilCAFHistorique", apercu)

    def test_fenetre_historique_reste_independante_d_afas_v2(self):
        initialisation = ast.unparse(
            methode("Dlg/DLG_Etat_global.py", "Dialog", "__init__"))
        disposition = ast.unparse(
            methode("Dlg/DLG_Etat_global.py", "Dialog", "__do_layout"))
        self.assertIn("self.bouton_afas = wx.Button", initialisation)
        self.assertIn("self.Bind(wx.EVT_BUTTON, self.OnAFAS, self.bouton_afas)",
                      initialisation)
        self.assertNotIn("self.bouton_afas.Hide", initialisation)
        self.assertIn("grid_sizer_boutons.Add(self.bouton_afas", disposition)
        self.assertNotIn("UTILS_AFAS_ProfilsHistoriques",
                         (NOETHYS / "Dlg/DLG_Etat_global.py").read_text(encoding="utf-8"))

    def test_editeur_multiple_natif_pas_le_remplacement_vide(self):
        fonction = ast.unparse(methode(
            "Ctrl/CTRL_Propertygrid.py", "Propriete_multichoix", "OnEvent"))
        self.assertIn("wx.MultiChoiceDialog", fonction)
        self.assertIn("dlg.SetSelections(", fonction)
        self.assertIn("dlg.GetSelections()", fonction)
        self.assertIn("self.SetValueInEvent(", fonction)
        self.assertNotIn("wx.CheckListBox(", fonction)


class ContratEditeurWxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import wx
            from Ctrl import CTRL_Propertygrid
        except (ImportError, RuntimeError):
            raise unittest.SkipTest("wxPython indisponible sur ce runner")
        cls.wx = wx
        cls.controle = CTRL_Propertygrid.Propriete_multichoix

    def test_dialogue_recoit_les_quatre_libelles_et_initialise_les_coches(self):
        etats = [(0, "Pointage en attente"), (1, "Présent"),
                 (2, "Absence justifiée"), (3, "Absence injustifiée")]

        class FauxPropriete:
            liste_choix = etats
            valeur = [1, 3]

            def GetValue(self):
                return list(self.valeur)

            def SetValueInEvent(self, valeurs):
                self.valeur = valeurs

        class FauxEvenement:
            def GetEventType(self):
                return wx.wxEVT_COMMAND_BUTTON_CLICKED

        wx = self.wx
        faux = FauxPropriete()
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            dialogue = cree_dialogue.return_value
            dialogue.ShowModal.return_value = wx.ID_OK
            dialogue.GetSelections.return_value = [0, 1, 2, 3]
            resultat = self.controle.OnEvent(faux, None, FauxEvenement())
            self.assertTrue(resultat)
            self.assertEqual(faux.valeur, [0, 1, 2, 3])
            arguments = cree_dialogue.call_args.args
            self.assertEqual(arguments[3], [libelle for _, libelle in etats])
            dialogue.SetSelections.assert_called_once_with([1, 3])
            dialogue.Destroy.assert_called_once()

    def test_annuler_ne_change_pas_les_etats_enregistres(self):
        wx = self.wx

        class FauxPropriete:
            liste_choix = [(0, "Réservation"), (1, "Présent")]
            valeur = [0, 1]

            def GetValue(self):
                return list(self.valeur)

            def SetValueInEvent(self, valeurs):
                raise AssertionError("Annuler ne doit rien modifier")

        class FauxEvenement:
            def GetEventType(self):
                return wx.wxEVT_COMMAND_BUTTON_CLICKED

        faux = FauxPropriete()
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            cree_dialogue.return_value.ShowModal.return_value = wx.ID_CANCEL
            self.assertFalse(self.controle.OnEvent(faux, None, FauxEvenement()))
        self.assertEqual(faux.valeur, [0, 1])


if __name__ == "__main__":
    unittest.main()
