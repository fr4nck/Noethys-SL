# -*- coding: utf-8 -*-
"""Paiement en ligne TIPI : facture sans regie ni compte bancaire.

Repris de origin/master 08baa60e : DLG_Saisie_portail_demande levait un
IndexError quand la requete du compte bancaire de la regie ne renvoyait
aucune ligne (facture supprimee ou introuvable).

Base simulee, dialogue de saisie de reglement remplace par un mock (aucune
fenetre), aucun reseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import unittest  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.App(False) if not wx.GetApp() else wx.GetApp()


class _DBSimulee:
    """Renvoie [] pour toutes les requetes, sauf le compte de la regie si
    compte_regie est fourni."""

    compte_regie = None

    def __init__(self, *args, **kwargs):
        self._dernier = []

    def ExecuterReq(self, req, *args, **kwargs):
        if "factures_regies.IDcompte_bancaire" in req and _DBSimulee.compte_regie is not None:
            self._dernier = [(_DBSimulee.compte_regie,)]
        else:
            self._dernier = []
        return True

    def ResultatReq(self):
        return self._dernier

    def Close(self):
        pass


def _traitement(mode):
    track = SimpleNamespace(IDfamille=3, IDcompte_payeur=4, IDpaiement=5, ventilation="F12#10.00")
    return SimpleNamespace(
        mode=mode, parent=None, track=track,
        dict_parametres={"systeme_paiement": "tipi", "IDtransaction": "TX_998",
                         "montant": "10.00", "numauto": "A1"},
    )


class PaiementTipiTests(unittest.TestCase):

    def _lancer(self, mode, compte_regie=None, saisie=None):
        from Dlg import DLG_Saisie_portail_demande as module
        _DBSimulee.compte_regie = compte_regie
        patches = [mock.patch.object(module.GestionDB, "DB", _DBSimulee),
                   mock.patch.object(module.UTILS_Parametres, "Parametres", return_value=2)]
        if saisie is not None:
            from Dlg import DLG_Saisie_reglement
            patches.append(mock.patch.object(DLG_Saisie_reglement, "Dialog", return_value=saisie))
        for p in patches:
            p.start()
        try:
            return module.Traitement.Traitement_paiement_en_ligne(_traitement(mode))
        finally:
            for p in reversed(patches):
                p.stop()

    def _saisie(self):
        saisie = mock.Mock()
        saisie.ctrl_ventilation.ctrl_ventilation.listeLignesPrestations = []
        saisie.ShowModal.return_value = wx.ID_CANCEL
        return saisie

    def test_mode_automatique_facture_sans_compte_sans_index_error(self):
        self.assertEqual(self._lancer("automatique"), {"etat": False, "reponse": ""})

    def test_mode_manuel_facture_sans_compte_ne_force_aucun_compte(self):
        saisie = self._saisie()
        self.assertIs(self._lancer("manuel", saisie=saisie), False)
        saisie.ctrl_numero.SetValue.assert_called_once_with("auth_num-A1")
        saisie.ctrl_compte.SetID.assert_not_called()

    def test_mode_manuel_compte_de_la_regie_conserve(self):
        saisie = self._saisie()
        self.assertIs(self._lancer("manuel", compte_regie=7, saisie=saisie), False)
        saisie.ctrl_compte.SetID.assert_called_once_with(7)


if __name__ == "__main__":
    unittest.main()
