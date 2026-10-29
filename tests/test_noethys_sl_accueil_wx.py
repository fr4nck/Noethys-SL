# -*- coding: utf-8 -*-
"""#436 : fenetre fiche enfant, comportement sans base ni documents reels."""
import inspect
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

try:
    import wx
except ImportError:
    wx = None


@unittest.skipIf(wx is None, "wxPython absent")
class EcranAccueilTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from Dlg import DLG_Fiche_accueil_enfant as UI
        cls.UI = UI

    def controle(self, valeur=0):
        return NS(GetSelection=Mock(return_value=valeur),
                  SetSelection=Mock(), Enable=Mock())

    def base(self, acces=True, ecriture=True):
        controles = {code: self.controle() for code, label in self.UI.PRINCIPALES}
        return NS(
            IDindividu=10, acces=acces, ecriture=ecriture,
            administrateur=ecriture, registre_pret=False, historique=[],
            perimetre=NS(GetValue=Mock(return_value="ALSH 2026-2027")),
            choix_autorisations=controles, etat_registre=NS(SetLabel=Mock()),
            bouton_initialiser=NS(Enable=Mock()),
            bouton_sauver=NS(Enable=Mock()),
            signataires=[(99, "Parent fictif")],
            perimetre_charge="ALSH 2026-2027",
            etats_initiaux={code: 0 for code in controles},
            attendus={(code, "ALSH 2026-2027"): None for code in controles},
            utilisateur={"IDutilisateur": 3, "actif": 1, "profil": "administrateur"},
            OnActualiser=Mock(return_value=True),
        )

    def test_etat_non_renseigne_ou_refus_ne_devient_pas_oui(self):
        self.assertEqual(self.UI.ETAT.get("non_renseigne", 0), 0)
        self.assertEqual(self.UI.ETAT["non"], 2)
        self.assertEqual(self.UI.ETAT["oui"], 1)

    def test_formulaire_original_meme_ordre(self):
        source = inspect.getsource(self.UI.Dialog.__init__)
        positions = [source.index('u"%s"' % nom) for nom in (
            "IDENTITÉ", "RESPONSABLE LÉGAL n°1", "RESPONSABLE LÉGAL n°2",
            "ACCOMPAGNANTS", "VACCINATIONS", "MÉDECIN TRAITANT",
            "MALADIES ET ALLERGIES", "AUTORISATIONS DIVERSES")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual([c for c, _ in self.UI.PRINCIPALES], [
            "photos_site_imprimes", "maquillage",
            "piscine_baignade", "activites_physiques"])

    def test_medical_reutilise_onglet_existant(self):
        f = NS(EndModal=Mock())
        self.UI.Dialog.OnMedical(f)
        f.EndModal.assert_called_once_with(wx.ID_APPLY)

    def test_repas_reutilise_questionnaire(self):
        f = NS(EndModal=Mock())
        self.UI.Dialog.OnRepas(f)
        f.EndModal.assert_called_once_with(wx.ID_YES)

    def test_pas_d_acces_ne_lit_aucun_registre(self):
        f = self.base(acces=False, ecriture=False)
        with patch.object(self.UI.registre, "VerifierRegistre") as verif:
            self.assertFalse(self.UI.Dialog.OnActualiser(f))
        verif.assert_not_called()
        f.bouton_sauver.Enable.assert_called_with(False)

    def test_registre_absent_ne_permet_pas_enregistrement(self):
        f = self.base()
        with patch.object(self.UI.registre, "VerifierRegistre",
                          side_effect=self.UI.registre.RegistreAbsent), \
             patch.object(self.UI.registre, "LireHistorique") as lecture:
            self.assertFalse(self.UI.Dialog.OnActualiser(f))
        lecture.assert_not_called()
        f.bouton_sauver.Enable.assert_called_with(False)

    def test_aucune_ecriture_apres_changement_perimetre(self):
        f = self.base()
        f.registre_pret = True
        f.perimetre.GetValue.return_value = "BAIS 2026-2027"
        with patch.object(self.UI.wx, "MessageBox"), \
             patch.object(self.UI.registre, "EnregistrerLot") as save:
            self.assertFalse(self.UI.Dialog.OnEnregistrer(f))
        save.assert_not_called()

    def test_aucune_ecriture_sans_responsable(self):
        f = self.base()
        f.registre_pret = True
        f.signataire = NS(GetSelection=Mock(return_value=0))
        with patch.object(self.UI.wx, "MessageBox"), \
             patch.object(self.UI.registre, "EnregistrerLot") as save:
            self.assertFalse(self.UI.Dialog.OnEnregistrer(f))
        save.assert_not_called()

    def test_enregistrement_explicite_avec_preuve(self):
        f = self.base()
        f.registre_pret = True
        f.choix_autorisations["piscine_baignade"].GetSelection.return_value = 2
        f.signataire = NS(GetSelection=Mock(return_value=1))
        f.source = NS(GetSelection=Mock(return_value=0))
        f.date_signature = NS(GetValue=Mock(return_value="2026-10-10"))
        f.date_debut = NS(GetValue=Mock(return_value="2026-09-01"))
        f.date_fin = NS(GetValue=Mock(return_value="2027-08-31"))
        f.autorite = NS(GetValue=Mock(return_value=True))
        f.texte_version = NS(GetValue=Mock(return_value="Fiche Enfant 2026-06"))
        f.reference_preuve = NS(GetValue=Mock(return_value="piece-fictive-01"))
        with patch.object(self.UI.wx, "MessageBox",
                          return_value=self.UI.wx.YES), \
             patch.object(self.UI.registre, "EnregistrerLot",
                          return_value={}) as save:
            self.assertTrue(self.UI.Dialog.OnEnregistrer(f))
        args, kwargs = save.call_args
        self.assertEqual(args[0:2], (10, 3))
        self.assertEqual(len(args[2]), 1)
        self.assertEqual(args[2][0]["type"], "piscine_baignade")
        self.assertEqual(args[2][0]["valeur"], 0)
        self.assertEqual(args[2][0]["IDsignataire"], 99)
        self.assertTrue(kwargs["autorise"])
        f.OnActualiser.assert_called_once()

    def test_impression_interdite_sans_acces(self):
        f = self.base(acces=False)
        with patch.object(self.UI.impression, "GenererPDF") as pdf:
            self.assertFalse(self.UI.Dialog.OnImprimer(f))
        pdf.assert_not_called()

    def test_impression_sans_medical_par_defaut(self):
        f = self.base()
        f.lecture_medicale = True
        f.medical = {
            "vaccins_enregistres": 3, "medecin": None,
            "problemes": [{"intitule": "SECRET", "description": "NE_PAS_COPIER"}]}
        f.inclure_medical = NS(GetValue=Mock(return_value=False))
        f.entete = {"nom": "FICTIF"}
        f.registre_pret = False
        f.signataire = NS(GetSelection=Mock(return_value=0))
        f.date_signature = NS(GetValue=Mock(return_value=""))
        fenetre = NS(ShowModal=Mock(return_value=wx.ID_OK),
                     GetPath=Mock(return_value="fictif.pdf"), Destroy=Mock())
        with patch.object(self.UI.wx, "FileDialog", return_value=fenetre), \
             patch.object(self.UI.wx, "MessageBox"), \
             patch.object(self.UI.impression, "GenererPDF") as export:
            self.assertTrue(self.UI.Dialog.OnImprimer(f))
        self.assertEqual(export.call_args.args[1]["medical"], [])
        fenetre.Destroy.assert_called_once()

    def test_impression_medicale_exige_accord(self):
        f = self.base()
        f.lecture_medicale = True
        f.medical = {"problemes": []}
        f.inclure_medical = NS(GetValue=Mock(return_value=True))
        with patch.object(self.UI.wx, "MessageBox", return_value=wx.NO), \
             patch.object(self.UI.wx, "FileDialog") as chooser:
            self.assertFalse(self.UI.Dialog.OnImprimer(f))
        chooser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
