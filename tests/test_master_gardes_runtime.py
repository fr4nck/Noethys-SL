# -*- coding: utf-8 -*-
"""Gardes d'exécution reprises de master : chargement confiné des extensions
(9f9a39c2), type d'hébergement Connecthys inconnu (1bd709d7), création
récursive du répertoire de données (fa4d3ca1), nomFichier vide sans
configuration (d1d8b70b, 85d42ba5).

Doublures et dossiers temporaires uniquement : aucune fenêtre, aucun réseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import os  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.GetApp() or wx.App(False)

from Dlg import DLG_Extensions  # noqa: E402
from Utils import UTILS_Config  # noqa: E402
from Utils import UTILS_Fichiers  # noqa: E402
from Utils import UTILS_Portail_synchro  # noqa: E402


class _Liste(object):
    def __init__(self, nom):
        self.nom = nom

    def GetSelection(self):
        return 0

    def GetStringSelection(self):
        return self.nom


class _Dialogue(object):
    instances = []

    def __init__(self, *args, **kwargs):
        _Dialogue.instances.append(args)

    def ShowModal(self):
        return wx.ID_OK

    def Destroy(self):
        pass


class ExtensionsTests(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory(prefix="noethys-ext-")
        self.rep = Path(self._dossier.name) / "Extensions"
        self.rep.mkdir()
        _Dialogue.instances = []
        self.patches = [
            mock.patch.object(DLG_Extensions.UTILS_Fichiers, "GetRepExtensions",
                              side_effect=lambda fichier="": str(self.rep / fichier) if fichier else str(self.rep)),
            mock.patch.object(DLG_Extensions.wx, "MessageDialog", _Dialogue),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._dossier.cleanup()

    def _executer(self, nom):
        return DLG_Extensions.CTRL_Extensions.Executer(_Liste(nom))

    def test_nom_avec_chemin_relatif_refuse(self):
        (Path(self._dossier.name) / "evasion.py").write_text("def Extension():\n    raise SystemExit(9)\n", encoding="utf-8")
        self.assertIs(self._executer("../evasion"), False)
        self.assertEqual(len(_Dialogue.instances), 1)

    def test_extension_absente_refusee(self):
        self.assertIs(self._executer("absente"), False)

    def test_extension_valide_executee_sans_modifier_sys_path(self):
        marque = Path(self._dossier.name) / "executee.txt"
        (self.rep / "bonjour.py").write_text(
            "def Extension():\n    with open(%r, 'w') as f:\n        f.write('ok')\n" % str(marque),
            encoding="utf-8")
        chemin_avant = list(sys.path)
        self._executer("bonjour")
        self.assertEqual(marque.read_text(), "ok")
        self.assertEqual(sys.path, chemin_avant)

    def test_extension_sans_fonction_extension_refusee(self):
        (self.rep / "vide.py").write_text("x = 1\n", encoding="utf-8")
        self.assertIs(self._executer("vide"), False)


class _Log(object):
    def __init__(self):
        self.lignes = []

    def EcritLog(self, texte):
        self.lignes.append(texte)


class HebergementInconnuTests(unittest.TestCase):
    def test_type_inconnu_signale_au_lieu_de_lever_typeerror(self):
        synchro = UTILS_Portail_synchro.Synchro.__new__(UTILS_Portail_synchro.Synchro)
        synchro.dict_parametres = {"hebergement_type": 99}
        synchro.log = _Log()
        self.assertIs(synchro.TelechargeFichier(ftp=None, nomFichier="models.py"), False)
        self.assertTrue(any("99" in ligne for ligne in synchro.log.lignes))


def _UtilsFichiersOriginal():
    """_garde_reseau remplace UTILS_Fichiers.GetRepData par le profil de test :
    charge une copie séparée du module pour tester la vraie fonction."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("utils_fichiers_original", UTILS_Fichiers.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepertoireDonneesTests(unittest.TestCase):
    def test_chaine_de_dossiers_creee_recursivement(self):
        module = _UtilsFichiersOriginal()
        with tempfile.TemporaryDirectory() as dossier:
            base = Path(dossier) / "inexistant" / "partage"
            with mock.patch.object(module.Chemins, "GetMainPath", return_value=str(Path(dossier) / "pas_de_portable")), \
                    mock.patch.object(module.UTILS_Customize, "GetValeur", return_value=""), \
                    mock.patch.object(module.appdirs, "site_data_dir", return_value=str(base)), \
                    mock.patch.object(module.appdirs, "user_data_dir", return_value=str(base)):
                chemin = module.GetRepData("demo_DATA.dat")
            self.assertTrue(os.path.isdir(os.path.dirname(chemin)))
            self.assertTrue(chemin.startswith(str(base)))


class NomFichierConfigTests(unittest.TestCase):
    def test_nomfichier_vide_sans_configuration(self):
        with tempfile.TemporaryDirectory() as dossier:
            config = UTILS_Config.FichierConfig()
            config.nomFichier = str(Path(dossier) / "Config.json")
            self.assertEqual(config.GetItemConfig("nomFichier"), "")
            self.assertIsNone(config.GetItemConfig("autre_cle"))


if __name__ == "__main__":
    unittest.main()
