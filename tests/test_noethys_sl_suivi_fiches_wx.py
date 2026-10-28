# -*- coding: utf-8 -*-
"""#436 B3 : contrats wx non destructifs, sans fenêtre ni base PMSL."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = ROOT / "noethys/Dlg/DLG_Reception_fiche_enfant.py"
IND = ROOT / "noethys/Dlg/DLG_Individu.py"


class SuiviFichesWxContrats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DLG.read_text(encoding="utf-8")
        cls.fiche = IND.read_text(encoding="utf-8")

    def test_reutilise_dialogue_et_onglet_existant(self):
        self.assertIn("class Dialog(wx.Dialog):", self.source)
        self.assertIn("self.bouton_medical", self.source)
        self.assertIn('self.ctrl_notebook.AffichePage("medical")', self.fiche)

    def test_periodes_avec_justificatif_et_confirmation(self):
        self.assertIn("def OnEnregistrerPeriode(self, event):", self.source)
        self.assertIn("self.justificatif.GetValue()", self.source)
        self.assertIn("justificatif_verifie=True", self.source)
        self.assertIn("EnregistrerPeriodeVerifiee(", self.source)
        self.assertIn("wx.YES_NO | wx.ICON_QUESTION", self.source)

    def test_non_fin_seulement_sur_droit_sans_echeance_atteste(self):
        self.assertIn("Le justificatif atteste explicitement un droit sans échéance", self.source)
        self.assertIn("fin_non_precisee_confirmee=self.fin_non_precisee.GetValue()", self.source)

    def test_ancienne_relecture_et_aeeh_tri_etat_conserves(self):
        self.assertIn("def OnReporter(self, event):", self.source)
        self.assertIn('VALEURS_AEEH = ("absent", "oui", "non")', self.source)
        self.assertIn("self._valeur_proposee = resultat", self.source)

    def test_confirmation_parentale_uniquement_si_document_signe(self):
        self.assertIn("def OnHistoriserParent(self, event):", self.source)
        self.assertIn("self.fiche_signee.GetValue()", self.source)
        self.assertIn("self.relecture.GetValue()", self.source)
        self.assertIn("self.rubriques_sante.IsChecked(i)", self.source)
        self.assertIn("EnregistrerConfirmationParentale(", self.source)

    def test_source_document_et_date_signature_distinctes(self):
        self.assertIn('return {1: "papier", 2: "pieces"}', self.source)
        self.assertIn("self.date_signature = CTRL_Saisie_date.Date", self.source)
        self.assertIn("date_parent=date_parent", self.source)
        self.assertIn("GetDerniereConfirmationParentale(", self.source)
        self.assertIn("Dernière réception contrôlée", self.source)

    def test_pas_de_nouveau_dossier_sante_ni_sql_dans_l_interface(self):
        for interdit in ("ReqInsert(", "ReqMAJ(", "UPDATE individus", "CREATE TABLE",
                         "ALTER TABLE", "UploadFichier(", "Envoi_email."):
            self.assertNotIn(interdit, self.source)
        self.assertIn("Ouvrir l'onglet Médical", self.source)

    def test_ne_presume_pas_certification_vaccinale(self):
        self.assertIn("Cela ne valide ni les vaccinations obligatoires ni le PAI", self.source)
        self.assertIn("Les informations médicales restent à vérifier", self.source)

    def test_sauvegarde_periode_immediate_explicite_et_historique(self):
        self.assertIn("indépendamment du bouton Ok de la fiche", self.source)
        self.assertIn("Période AEEH n°%d enregistrée et historisée", self.source)

    def test_erreurs_sql_ne_sont_pas_annoncees_comme_succes(self):
        self.assertIn("Échec de l'enregistrement. Aucun succès n'est présumé", self.source)
        self.assertIn("Enregistrement incertain : vérifiez l'historique", self.source)

    def test_presentation_sur_un_unique_dialogue_deroulant(self):
        self.assertIn("wx.ScrolledWindow(self)", self.source)
        self.assertIn("panneau.SetScrollRate(0, 16)", self.source)
        self.assertIn("self.SetSize((760, 670))", self.source)


if __name__ == "__main__":
    unittest.main()
