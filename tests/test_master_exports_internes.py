# -*- coding: utf-8 -*-
"""Exports internes : encodage, erreurs et donnees absentes.

Repris de origin/master :
- a6a960bf + 8bef9bf1 : encodage UTF-8 et erreurs des exports generiques
  (UTILS_Export), familles et NoethysWeb ;
- 6f7eb0a9 : un export NoethysWeb en echec n'est plus annonce comme reussi ;
- b829f184 : exports documents/NoethysWeb proteges contre les donnees
  absentes (IndexError).

Dialogues remplaces par des mocks (aucune fenetre), fichiers temporaires
uniquement, aucune base reelle, aucun reseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.App(False) if not wx.GetApp() else wx.GetApp()

NOETHYS = Path(__file__).resolve().parents[1] / "noethys"


class _FauxDialogue:
    """Dialogue factice : enregistre les messages, repond sans s'afficher."""

    messages = []

    def __init__(self, parent=None, message="", *args, reponse=None, chemin=None, **kwargs):
        _FauxDialogue.messages.append(message)
        self._reponse = reponse
        self._chemin = chemin

    def ShowModal(self):
        return self._reponse

    def SetFilterIndex(self, *args):
        pass

    def GetPath(self):
        return self._chemin

    def Destroy(self):
        pass


def _fabrique(reponse, chemin=None):
    return lambda *a, **k: _FauxDialogue(*a, reponse=reponse, chemin=chemin, **k)


COLONNES = [(u"Nom", "left", 100, "nom"), (u"Ville", "left", 100, "ville")]
VALEURS = [[u"Zoë ŝ", u"Sète"], [u"Crèche – Noël", None]]


class ExportTexteTests(unittest.TestCase):
    """a6a960bf + 8bef9bf1"""

    def setUp(self):
        _FauxDialogue.messages = []
        self._rep = tempfile.TemporaryDirectory(prefix="noethys-export-")

    def tearDown(self):
        self._rep.cleanup()

    def _exporter(self, chemin):
        from Utils import UTILS_Export
        with mock.patch.object(UTILS_Export.wx, "FileDialog", _fabrique(wx.ID_OK, chemin)), \
                mock.patch.object(UTILS_Export.wx, "MessageDialog", _fabrique(wx.ID_NO)), \
                mock.patch.object(UTILS_Export.FonctionsPerso, "LanceFichierExterne") as lance:
            resultat = UTILS_Export.ExportTexte(listeColonnes=COLONNES, listeValeurs=VALEURS,
                                                autoriseSelections=False)
        lance.assert_not_called()
        return resultat

    def test_export_texte_ecrit_en_utf8_explicite(self):
        chemin = os.path.join(self._rep.name, "export.txt")
        self._exporter(chemin)
        # Fichier texte : fins de ligne de la plate-forme (CRLF sous Windows)
        contenu = Path(chemin).read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(contenu, u"Nom;Ville\nZoë ŝ;Sète\nCrèche – Noël;")

    def test_echec_d_ecriture_signale_sans_exception_ni_succes(self):
        chemin = os.path.join(self._rep.name, "absent", "export.txt")
        resultat = self._exporter(chemin)
        self.assertIs(resultat, False)
        self.assertTrue(any(u"Impossible d'enregistrer" in m for m in _FauxDialogue.messages))
        self.assertFalse(any(u"créé avec succès" in m for m in _FauxDialogue.messages))

    def test_utils_export_sans_except_nu(self):
        arbre = ast.parse((NOETHYS / "Utils" / "UTILS_Export.py").read_text(encoding="utf-8"))
        nus = [n.lineno for n in ast.walk(arbre) if isinstance(n, ast.ExceptHandler) and n.type is None]
        self.assertEqual(nus, [])

    def test_core_json_noethysweb_ouvert_en_utf8(self):
        arbre = ast.parse((NOETHYS / "Utils" / "UTILS_Export_noethysweb.py").read_text(encoding="utf-8"))
        for fonction in ast.walk(arbre):
            if isinstance(fonction, ast.FunctionDef) and fonction.name == "Finaliser":
                ouvertures = [n for n in ast.walk(fonction) if isinstance(n, ast.Call)
                              and getattr(n.func, "id", None) == "open"]
                break
        else:
            self.fail("Export.Finaliser introuvable")
        self.assertTrue(ouvertures)
        for appel in ouvertures:
            mode = appel.args[1].value if len(appel.args) > 1 else "r"
            if "b" not in mode:
                self.assertIn("encoding", [kw.arg for kw in appel.keywords])


if __name__ == "__main__":
    unittest.main()
