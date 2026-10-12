# -*- coding: utf-8 -*-
"""Imports invalides geres sans crash.

Repris de origin/master :
- 1ec5c6dd : DLG_Importation_individus (classeur Excel invalide) et
  DLG_Importation_vacances (organisateur sans coordonnees -> IndexError) ;
- 9a0b010f : DLG_Badgeage_importation (NameError si xlrd absent, imports
  Excel/CSV securises).

Dialogues remplaces par des mocks (aucune fenetre), fichiers temporaires,
base simulee, aucun reseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import os  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.App(False) if not wx.GetApp() else wx.GetApp()


class _FauxDialogue:
    messages = []

    def __init__(self, parent=None, message="", *args, reponse=wx.ID_OK, **kwargs):
        _FauxDialogue.messages.append(message)
        self._reponse = reponse

    def ShowModal(self):
        return self._reponse

    def GetSelection(self):
        return 0

    def Destroy(self):
        pass


class _DBVide:
    def __init__(self, *args, **kwargs):
        self.ferme = False

    def ExecuterReq(self, req, *args, **kwargs):
        return True

    def ResultatReq(self):
        return []

    def Close(self):
        self.ferme = True


class ImportsInvalidesTests(unittest.TestCase):
    """1ec5c6dd"""

    def setUp(self):
        _FauxDialogue.messages = []

    def test_classeur_individus_invalide_sans_exception(self):
        from Dlg import DLG_Importation_individus
        with tempfile.TemporaryDirectory(prefix="noethys-import-") as rep:
            chemin = os.path.join(rep, "pas_un_classeur.xls")
            with open(chemin, "wb") as f:
                f.write(b"ceci n'est pas un fichier Excel")
            importation = DLG_Importation_individus.Importation_Excel(nomFichier=chemin)
        self.assertFalse(importation.fichierValide)
        self.assertIsNone(importation.classeur)
        self.assertIsNone(importation.feuille)

    def test_zone_vacances_sans_organisateur_sans_index_error(self):
        from Dlg import DLG_Importation_vacances as module
        faux = SimpleNamespace(SetZone=mock.Mock())
        with mock.patch.object(module.GestionDB, "DB", _DBVide), \
                mock.patch.object(module.wx, "MessageDialog", _FauxDialogue), \
                mock.patch.object(module, "RechercherZone") as recherche:
            resultat = module.Dialog.ImportationZone(faux)
        self.assertIsNone(resultat)
        recherche.assert_not_called()
        faux.SetZone.assert_not_called()
        self.assertTrue(any(u"coordonnées de l'organisateur" in m for m in _FauxDialogue.messages))


if __name__ == "__main__":
    unittest.main()
