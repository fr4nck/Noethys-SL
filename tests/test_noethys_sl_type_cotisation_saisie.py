# -*- coding: utf-8 -*-
"""Saisie d'un type de cotisation (wx réel, base SQLite fictive).

- Un nouvel OK après l'échec de l'enregistrement du mode d'association ne
  doit pas insérer une seconde fois les unités déjà enregistrées.
- Un mode d'association en double ou inconnu ne doit pas empêcher d'ouvrir
  le type ; il est signalé puis corrigé par la validation de la fenêtre.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import wx  # noqa: E402
APP = wx.GetApp() or wx.App(False)
import _garde_reseau  # noqa: E402,F401
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Dlg import DLG_Saisie_type_cotisation  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402


def _modale_inattendue(*args, **kwargs):
    raise AssertionError("Fenêtre modale inattendue : %r" % (args[:3],))


def _unite(nom):
    return {"IDunite_cotisation": None, "date_debut": None, "date_fin": None, "defaut": 1, "nom": nom,
            "montant": 12.0, "label_prestation": None, "etat": "MODIF", "duree": "j0-m0-a1"}


class SaisieTypeCotisationTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for nom in ("MessageBox", "MessageDialog"):
            garde = patch.object(wx, nom, side_effect=_modale_inattendue)
            garde.start()
            self.addCleanup(garde.stop)
        for table in ("types_cotisations", "unites_cotisations"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)

    def dialogue(self, IDtype_cotisation=None):
        dlg = DLG_Saisie_type_cotisation.Dialog(None, IDtype_cotisation=IDtype_cotisation)
        self.addCleanup(dlg.Destroy)
        return dlg

    def lignes(self, req):
        self.base.db.ExecuterReq(req)
        return self.base.db.ResultatReq()

    def test_nouvel_ok_apres_echec_du_mode_sans_doublon_d_unite(self):
        dlg = self.dialogue()
        dlg.ctrl_nom.SetValue(u"Adhésion fictive")
        dlg.ctrl_type.Select(1)
        dlg.ctrl_unites.SetListeDonnees([_unite(u"Annuelle")])
        erreur = RuntimeError("base verrouillée (fictif)")
        with patch.object(A, "EnregistrerModeAssociation", side_effect=erreur), \
                patch.object(wx, "MessageDialog") as message, patch.object(dlg, "EndModal") as fermeture:
            self.assertFalse(dlg.OnBoutonOk(None))
        message.return_value.ShowModal.assert_called_once_with()
        fermeture.assert_not_called()
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 1)

        with patch.object(dlg, "EndModal") as fermeture:
            dlg.OnBoutonOk(None)
        fermeture.assert_called_once_with(wx.ID_OK)
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM types_cotisations")[0][0], 1)
        self.assertEqual(self.lignes("SELECT nom FROM unites_cotisations"), [(u"Annuelle",)])
        self.assertEqual(A.LireModeAssociation(dlg.IDtype_cotisation), A.MODE_ASSOCIATION_INSCRIPTIONS)

    def test_suppression_non_rejouee_apres_echec_du_mode(self):
        self.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                          [(1, u"Adhésion fictive", "individu", 0, 0)])
        self.base.inserer("unites_cotisations", ["IDunite_cotisation", "IDtype_cotisation", "nom", "defaut", "duree"],
                          [(1, 1, u"Ancienne", 0, "j0-m0-a1"), (2, 1, u"Conservée", 1, "j0-m0-a1")])
        dlg = self.dialogue(1)
        unites = dlg.ctrl_unites.GetListeDonnees()
        next(u for u in unites if u["IDunite_cotisation"] == 1)["etat"] = "SUPPR"
        with patch.object(A, "EnregistrerModeAssociation", side_effect=RuntimeError("fictif")), \
                patch.object(wx, "MessageDialog"):
            self.assertFalse(dlg.OnBoutonOk(None))
        self.assertTrue(all(u["etat"] != "SUPPR" or u["IDunite_cotisation"] is None for u in unites))
        with patch.object(dlg, "EndModal") as fermeture:
            dlg.OnBoutonOk(None)
        fermeture.assert_called_once_with(wx.ID_OK)
        self.assertEqual(self.lignes("SELECT IDunite_cotisation FROM unites_cotisations"), [(2,)])

    def test_mode_en_double_signale_puis_corrige_par_la_validation(self):
        self.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                          [(1, u"Adhésion fictive", "individu", 0, 0)])
        self.base.inserer("unites_cotisations", ["IDunite_cotisation", "IDtype_cotisation", "nom", "defaut", "duree"],
                          [(1, 1, u"Annuelle", 1, "j0-m0-a1")])
        self.base.inserer("parametres", ["categorie", "nom", "parametre"], [
            (A.CATEGORIE_MODE_ASSOCIATION, "type_1", "inscriptions"),
            (A.CATEGORIE_MODE_ASSOCIATION, "type_1", "participations")])
        with patch.object(wx, "CallAfter") as differe:
            dlg = self.dialogue(1)  # l'ouverture ne lève plus d'exception
        differe.assert_called_once_with(dlg.SignalerModeAssociationInvalide)
        self.assertIsNotNone(dlg.mode_association_invalide)
        with patch.object(wx, "MessageDialog") as message:
            dlg.SignalerModeAssociationInvalide()
        self.assertIn(u"reste bloquée", message.call_args[0][1])

        dlg.ctrl_mode_adhesion.SetSelection(1)
        with patch.object(dlg, "EndModal") as fermeture:
            dlg.OnBoutonOk(None)
        fermeture.assert_called_once_with(wx.ID_OK)
        self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_PARTICIPATIONS)
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM parametres WHERE categorie='%s'"
                                     % A.CATEGORIE_MODE_ASSOCIATION)[0][0], 1)
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 1)

    def test_mode_valide_relu_sans_avertissement(self):
        self.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                          [(1, u"Adhésion fictive", "individu", 0, 0)])
        self.base.inserer("parametres", ["categorie", "nom", "parametre"],
                          [(A.CATEGORIE_MODE_ASSOCIATION, "type_1", "participations")])
        with patch.object(wx, "CallAfter") as differe:
            dlg = self.dialogue(1)
        differe.assert_not_called()
        self.assertIsNone(dlg.mode_association_invalide)
        self.assertEqual(dlg.ctrl_mode_adhesion.GetSelection(), 1)


if __name__ == "__main__":
    unittest.main()
