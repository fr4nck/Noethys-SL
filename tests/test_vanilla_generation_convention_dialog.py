# -*- coding: utf-8 -*-
"""Dialogue DLG_Generation_convention : préremplissage automatique
(représentant, tarif), overrides manuels (fonction, signature, tarif),
et bouton "Imprimer le planning" (réutilisation du moteur Réservations
historique, jamais un second moteur PDF, jamais une fusion avec la
Convention).

Couvre aussi un défaut latent réel : CTRL_Grille_periode.MyDatePickerCtrl
appelle self.GetParent().OnSelection() à chaque changement de date -- un
dialogue qui n'implémente pas OnSelection() plante donc dès que
l'utilisateur touche une date. Le premier jalon ne définissait pas cette
méthode ; ce test la vérifie explicitement pour éviter une régression.
"""
from __future__ import annotations

import datetime
import sys
import unittest
import unittest.mock
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
    creer_base_ecole_simple,
)
from Dlg import DLG_Generation_convention  # noqa: E402


class DialogGenerationConventionTests(unittest.TestCase):
    def test_dialog_se_construit_sans_planter(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                dlg.Destroy()

    def test_onselection_existe_et_ne_plante_pas_sur_changement_de_date(self):
        """ Régression : voir docstring du module. """
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                self.assertTrue(hasattr(dlg, "OnSelection"))
                dlg.ctrl_date_debut.SetDate(datetime.date(2026, 9, 1))
                dlg.OnSelection()  # ce que MyDatePickerCtrl.OnDateChanged appelle réellement
                dlg.Destroy()

    def test_representant_et_tarif_sont_prerempli_automatiquement(self):
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(
                    None, IDfamille=2,
                    date_debut=datetime.date(2026, 8, 1), date_fin=datetime.date(2027, 7, 31),
                )
                representant = dlg.ctrl_representant_nom_complet.GetValue()
                tarif = dlg.ctrl_tarif_horaire.GetValue()
                dlg.Destroy()
        self.assertIn("MARTIN", representant)
        self.assertEqual(tarif, "20.00")

    def test_valeur_manuelle_n_est_pas_ecrasee_par_un_recalcul(self):
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(
                    None, IDfamille=2,
                    date_debut=datetime.date(2026, 8, 1), date_fin=datetime.date(2027, 7, 31),
                )
                dlg.ctrl_tarif_horaire.SetValue("999.99")
                dlg.ctrl_representant_nom_complet.SetValue("Corrigé manuellement")
                dlg.RecalculerValeursAutomatiques()
                tarif = dlg.ctrl_tarif_horaire.GetValue()
                representant = dlg.ctrl_representant_nom_complet.GetValue()
                dlg.Destroy()
        self.assertEqual(tarif, "999.99")
        self.assertEqual(representant, "Corrigé manuellement")

    def test_get_overrides_reflete_les_champs_saisis(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                dlg.ctrl_representant_nom_complet.SetValue("Mme TEST Alice")
                dlg.ctrl_representant_fonction.SetValue("Trésorière")
                dlg.ctrl_lieu_signature.SetValue("TESTVILLE")
                dlg.ctrl_date_signature.SetDate(datetime.date(2026, 9, 21))
                dlg.ctrl_tarif_horaire.SetValue("18,50")
                overrides = dlg.GetOverrides()
                dlg.Destroy()
        self.assertEqual(overrides["{CONVENTION_REPRESENTANT_NOM_COMPLET}"], "Mme TEST Alice")
        self.assertEqual(overrides["{CONVENTION_REPRESENTANT_FONCTION}"], "Trésorière")
        self.assertEqual(overrides["{CONVENTION_LIEU_SIGNATURE}"], "TESTVILLE")
        self.assertEqual(overrides["{CONVENTION_DATE_SIGNATURE}"], "21/09/2026")
        self.assertEqual(overrides["{CONVENTION_TARIF_HORAIRE}"], 18.5)

    def test_bouton_planning_reutilise_get_donnees_et_impression_avec_la_meme_periode(self):
        """ Ne recopie pas UTILS_Impression_reservations, ne crée pas de
        second moteur PDF : le bouton se contente d'appeler GetDonnees()
        puis Impression() avec exactement la période affichée dans le
        dialogue. """
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(
                    None, IDfamille=2,
                    date_debut=datetime.date(2026, 8, 1), date_fin=datetime.date(2027, 7, 31),
                )
                with unittest.mock.patch("Utils.UTILS_Impression_reservations.GetDonnees") as faux_get, \
                     unittest.mock.patch("Utils.UTILS_Impression_reservations.Impression") as faux_impression:
                    faux_get.return_value = {1: {"nom": "x", "prenom": "y", "activites": {}}}
                    dlg.OnBoutonPlanning(None)
                dlg.Destroy()

        faux_get.assert_called_once()
        _args, kwargs = faux_get.call_args
        self.assertEqual(kwargs["date_debut"], "2026-08-01")
        self.assertEqual(kwargs["date_fin"], "2027-07-31")
        self.assertEqual(sorted(kwargs["listeIDindividus"]), [10, 11, 20, 21, 22])
        faux_impression.assert_called_once_with(faux_get.return_value)

    def test_bouton_planning_sans_donnees_naffiche_pas_derreur_et_nappelle_pas_impression(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                with unittest.mock.patch("Utils.UTILS_Impression_reservations.GetDonnees") as faux_get, \
                     unittest.mock.patch("Utils.UTILS_Impression_reservations.Impression") as faux_impression, \
                     unittest.mock.patch("wx.MessageDialog") as faux_message:
                    faux_get.return_value = {}
                    faux_message.return_value.ShowModal.return_value = wx.ID_OK
                    dlg.OnBoutonPlanning(None)
                dlg.Destroy()
        faux_impression.assert_not_called()
        faux_message.assert_called_once()


    def test_periode_par_defaut_est_la_periode_reelle_des_seances(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(None, IDfamille=1)
                debut = str(dlg.ctrl_date_debut.GetDate())
                fin = str(dlg.ctrl_date_fin.GetDate())
                dlg.Destroy()
        self.assertEqual(debut, "2026-09-02")
        self.assertEqual(fin, "2026-09-21")
        self.assertNotEqual(debut, fin)

    def test_tarifs_adulte_enfant_sont_visibles_avec_provenance(self):
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                dlg = DLG_Generation_convention.Dialog(
                    None, IDfamille=1,
                    date_debut=datetime.date(2026, 9, 1),
                    date_fin=datetime.date(2026, 9, 30),
                )
                unique = dlg.ctrl_tarif_horaire.GetValue()
                adulte = dlg.ctrl_tarif_adulte.GetValue()
                enfant = dlg.ctrl_tarif_enfant.GetValue()
                prov_adulte = dlg.label_tarif_adulte_provenance.GetLabel()
                prov_enfant = dlg.label_tarif_enfant_provenance.GetLabel()
                dlg.Destroy()
        self.assertEqual(unique, "")
        self.assertEqual(adulte, "36.50")
        self.assertEqual(enfant, "24.00")
        self.assertIn("36,50 €/h", prov_adulte)
        self.assertIn("24,00 €/h", prov_enfant)


if __name__ == "__main__":
    unittest.main()