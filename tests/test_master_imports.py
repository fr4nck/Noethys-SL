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
import sys  # noqa: E402
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


def _ctrl(valeur):
    return SimpleNamespace(GetValue=lambda: valeur, SetFocus=lambda: None)


class BadgeageImportationTests(unittest.TestCase):
    """9a0b010f"""

    def setUp(self):
        _FauxDialogue.messages = []
        self._tmp = tempfile.TemporaryDirectory(prefix="noethys-badgeage-")
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _fichier(self, nom, contenu):
        chemin = os.path.join(self.tmp, nom)
        with open(chemin, "wb") as f:
            f.write(contenu)
        return chemin

    def test_module_importable_sans_xlrd(self):
        import importlib.util
        from pathlib import Path
        chemin = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Badgeage_importation.py"
        spec = importlib.util.spec_from_file_location("_badgeage_sans_xlrd", str(chemin))
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"xlrd": None}):
            spec.loader.exec_module(module)
        self.assertIsNone(module.xlrd)

    def test_import_excel_sans_xlrd_message_explicite(self):
        from Dlg import DLG_Badgeage_importation as module
        faux = SimpleNamespace(ctrl_fichier=_ctrl(self._fichier("badges.xls", b"x")))
        with mock.patch.object(module, "xlrd", None), \
                mock.patch.object(module.wx, "MessageDialog", _FauxDialogue):
            self.assertIs(module.Page_excel.Lire(faux), False)
        self.assertEqual(len(_FauxDialogue.messages), 1)
        self.assertIn(u"xlrd", _FauxDialogue.messages[0])

    def test_import_excel_choix_de_feuille_annule_sans_erreur(self):
        from Dlg import DLG_Badgeage_importation as module
        faux = SimpleNamespace(ctrl_fichier=_ctrl(self._fichier("badges.xls", b"x")))
        classeur = mock.Mock()
        classeur.sheet_names.return_value = ["Feuil1", "Feuil2"]
        annuler = lambda *a, **k: _FauxDialogue(*a, reponse=wx.ID_CANCEL, **k)
        with mock.patch.object(module.xlrd, "open_workbook", return_value=classeur), \
                mock.patch.object(module.wx, "SingleChoiceDialog", annuler), \
                mock.patch.object(module.wx, "MessageDialog", _FauxDialogue):
            self.assertIs(module.Page_excel.Lire(faux), False)
        classeur.sheet_by_index.assert_not_called()
        # Annulation volontaire : aucun message d'erreur de lecture
        self.assertFalse(any(u"pas réussi à lire" in m for m in _FauxDialogue.messages[1:]))
        self.assertEqual(_FauxDialogue.messages[1:], [])

    def test_import_csv_lu_et_fichier_ferme(self):
        import datetime
        import gc
        import warnings
        from Dlg import DLG_Badgeage_importation as module
        chemin = self._fichier("badges.csv", b"ABC123;2026-09-01 08:30\r\nXYZ9;2026-09-02 17:05\r\n")
        faux = SimpleNamespace(ctrl_fichier=_ctrl(chemin),
                               ctrl_delimiteur=SimpleNamespace(GetSelection=lambda: 0),
                               listeDelimiteurs=[";"], ctrl_format=_ctrl(u"CODE;AAAA-MM-JJ HH:MN"))
        with warnings.catch_warnings(record=True) as alertes, \
                mock.patch.object(module.wx, "MessageDialog", _FauxDialogue):
            warnings.simplefilter("always")
            resultat = module.Page_csv.Lire(faux)
            gc.collect()
        self.assertEqual(resultat, [(u"ABC123", datetime.date(2026, 9, 1), u"08:30"),
                                    (u"XYZ9", datetime.date(2026, 9, 2), u"17:05")])
        self.assertEqual(_FauxDialogue.messages, [])
        fuites = [a for a in alertes if issubclass(a.category, ResourceWarning)]
        self.assertEqual(fuites, [], [str(a.message) for a in fuites])


if __name__ == "__main__":
    unittest.main()
