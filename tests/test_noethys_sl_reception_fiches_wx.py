# -*- coding: utf-8 -*-
"""#436 : garde-fous du raccordement wx (aucune base ni wx.App ouverte)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReceptionFichesWxContrats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fiche = (ROOT / 'noethys/Dlg/DLG_Individu.py').read_text(encoding='utf-8')
        cls.dialogue = (ROOT / 'noethys/Dlg/DLG_Reception_fiche_enfant.py').read_text(encoding='utf-8')

    def test_entree_outils_et_perimetre_enfant(self):
        self.assertIn('Contrôler une fiche enfant reçue', self.fiche)
        self.assertIn('def MenuControlerFicheEnfant(self, event):', self.fiche)
        self.assertIn('page_identite.ctrl_civilite.GetID() in (4, 5)', self.fiche)

    def test_saisie_ne_modifie_pas_directement_la_base(self):
        methode = self.fiche.split('    def MenuControlerFicheEnfant(self, event):', 1)[1].split('    def OnClose(self, event):', 1)[0]
        self.assertIn('page.ctrl_aeeh.SetSelection(', methode)
        self.assertIn('self.ctrl_notebook.AffichePage("identite")', methode)
        self.assertNotIn('ReqMAJ(', methode)
        self.assertNotIn('ReqInsert(', methode)
        self.assertNotIn('Sauvegarde(', methode)
        self.assertNotIn('UPDATE individus', methode)

    def test_valeur_explicitement_proposee_et_message_sauvegarde(self):
        methode = self.fiche.split('    def MenuControlerFicheEnfant(self, event):', 1)[1].split('    def OnClose(self, event):', 1)[0]
        self.assertIn('proposition = dlg.GetValeurProposee()', methode)
        self.assertIn('cliquez sur Ok pour enregistrer', methode)

    def test_dialogue_nutilise_ni_base_ni_ocr(self):
        self.assertNotIn('GestionDB', self.dialogue)
        self.assertNotIn('ReqMAJ', self.dialogue)
        self.assertNotIn('PyPDF', self.dialogue)
        self.assertNotIn('pytesseract', self.dialogue)
        self.assertIn('from Utils import UTILS_Reception_fiches as reception', self.dialogue)

    def test_pas_daccord_automatique_et_relecture_explicite(self):
        self.assertIn('self.choix.SetSelection(0)', self.dialogue)
        self.assertIn('self.relecture.GetValue()', self.dialogue)
        self.assertIn('if resultat["action"] == "relecture_requise":', self.dialogue)
        self.assertIn('if index < 0 or index >= len(VALEURS_AEEH):', self.dialogue)

    def test_rappel_medical_non_converti_en_validation(self):
        for mot in ('vaccinations', 'allergies', 'traitements', 'PAI', 'consignes de sortie'):
            self.assertIn(mot, self.dialogue)
        self.assertIn("Aucun de ces points n'est validé automatiquement", self.dialogue)


if __name__ == '__main__':
    unittest.main()
