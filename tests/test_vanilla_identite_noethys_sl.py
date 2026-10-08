# -*- coding: utf-8 -*-
"""Identité publique Noethys SL vs version de compatibilité interne.

Audit préalable (aucune supposition) : tout le mécanisme de version de
Noethys (Noethys.MainFrame.ConvertVersionTuple/ValidationVersionFichier,
UpgradeDB.DB.Upgrade -- 134 paliers --, FonctionsPerso.CompareVersions,
UTILS_Portail_synchro.Update_application) fait un int() par segment après
split(".") sur VERSION_APPLICATION, sans aucune tolérance pour un suffixe
non numérique. Un remplacement naïf de "1.3.4.2" par "0.1.0-rc.2" ferait
planter chaque démarrage (MainFrame.Annonce(), non protégé par try/except)
et chaque ouverture de fichier (ValidationVersionFichier, non protégé non
plus).

Identite.py introduit donc PRODUCT_NAME/PRODUCT_VERSION séparément, sans
jamais toucher VERSION_APPLICATION. Ces tests vérifient que cette
séparation est réelle et reste vérifiée dans le temps.
"""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import re
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

import FonctionsPerso  # noqa: E402
import Identite  # noqa: E402
import Noethys  # noqa: E402


class IdentitePubliqueTests(unittest.TestCase):
    def test_identite_publique_attendue(self):
        self.assertEqual(Identite.PRODUCT_NAME, u"Noethys SL")
        self.assertEqual(Identite.PRODUCT_VERSION, "0.1.0-rc.2")
        self.assertEqual(Identite.PRODUCT_VERSION_DISPLAY, u"0.1.0 RC2")

    def test_titre_fenetre_affiche_identite_publique(self):
        frame = Noethys.MainFrame.__new__(Noethys.MainFrame)
        wx.Frame.__init__(frame, None, id=-1)
        try:
            frame.SetTitleFrame()
            self.assertEqual(frame.GetTitle(), u"Noethys SL 0.1.0 RC2")
            frame.SetTitleFrame(nomFichier="exemple.ndb")
            self.assertEqual(frame.GetTitle(), u"Noethys SL 0.1.0 RC2 - [exemple.ndb]")
        finally:
            frame.Destroy()


class SeparationVersionPubliqueEtInterneTests(unittest.TestCase):
    """ Garde-fou explicite : la version interne (compatibilité, migrations,
    protocole Connecthys) ne doit jamais dériver vers la version publique
    Noethys SL, et réciproquement. """

    def test_version_interne_reste_strictement_numerique(self):
        version_interne = FonctionsPerso.GetVersionLogiciel()
        self.assertRegex(version_interne, r"^\d+(\.\d+)*$")
        self.assertNotEqual(version_interne, Identite.PRODUCT_VERSION)

    def test_version_application_est_bien_la_version_interne(self):
        # VERSION_APPLICATION (Noethys.py) est la valeur qui alimente
        # ConvertVersionTuple/UpgradeDB/Connecthys : elle doit rester celle
        # de Versions.txt, jamais Identite.PRODUCT_VERSION.
        self.assertEqual(Noethys.VERSION_APPLICATION, FonctionsPerso.GetVersionLogiciel())
        self.assertNotEqual(Noethys.VERSION_APPLICATION, Identite.PRODUCT_VERSION)

    def test_convert_version_tuple_reussit_sur_la_version_interne(self):
        """ Reproduit exactement l'appel fait par MainFrame.Annonce() (à
        chaque démarrage, non protégé par try/except) et par
        ValidationVersionFichier() (à chaque ouverture de fichier, non
        protégé non plus) -- c'est l'invariant dont la rupture crasherait
        l'application si VERSION_APPLICATION perdait sa forme numérique. """
        resultat = Noethys.MainFrame.ConvertVersionTuple(None, Noethys.VERSION_APPLICATION)
        self.assertIsInstance(resultat, tuple)
        self.assertTrue(all(isinstance(x, int) for x in resultat))

    def test_convert_version_tuple_echouerait_sur_la_version_publique(self):
        """ Preuve directe de la raison d'être de cette séparation : si on
        avait, par erreur, remplacé VERSION_APPLICATION par
        Identite.PRODUCT_VERSION, ConvertVersionTuple lèverait ici. """
        with self.assertRaises(ValueError):
            Noethys.MainFrame.ConvertVersionTuple(None, Identite.PRODUCT_VERSION)

    def test_versions_txt_garde_le_format_attendu_par_getversionlogiciel(self):
        contenu = (NOETHYS_DIR / "Versions.txt").read_text(encoding="utf-8")
        premiere_ligne = contenu.splitlines()[0]
        self.assertRegex(premiere_ligne, r"^Version \d+(\.\d+)* \(\d{2}/\d{2}/\d{4}\) :$")


if __name__ == "__main__":
    unittest.main()
