# -*- coding: utf-8 -*-
"""Noedoc, modèles de convention : les blocs flottants sont présentés comme
le générateur PDF les fait couler, sans déborder sous la page, et
l'enregistrement conserve leurs ancrages (le PDF ne change pas).

Régression : le bloc « Corps » des modèles d'exemple, ancré au bas du cadre
principal (y = 20 mm), était dessiné depuis ce point vers le bas, sous la
page, et sans retour à la ligne. Base SQLite temporaire, sans donnée réelle.
"""

import os
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau

import numpy  # noqa: E402
import wx  # noqa: E402

APP = wx.GetApp() or wx.App(False)

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

NOETHYS = TESTS.parent / "noethys"


class NoedocEcoulementTests(unittest.TestCase):

    def setUp(self):
        self.base = BaseTest()
        for nom in ("organisateur", "documents_modeles", "documents_objets", "parametres"):
            if not self.base.db.IsTableExists(nom):
                self.base.db.CreationTable(nom, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("organisateur", ["IDorganisateur", "nom"], [(1, u"Association témoin")])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.cwd = os.getcwd()
        os.chdir(str(NOETHYS))
        from Utils import UTILS_Convention_modeles
        self.modeles = UTILS_Convention_modeles
        self.IDs = UTILS_Convention_modeles.InstallerModelesExemples()

    def tearDown(self):
        os.chdir(self.cwd)
        self.redirection.__exit__(None, None, None)
        self.base.fermer()

    def _positions(self, ID):
        return self.base.db.ExecuterReq("SELECT IDobjet, x, y FROM documents_objets WHERE IDmodele=%d ORDER BY IDobjet;" % ID) and \
            self.base.db.ResultatReq()

    def _ouvrir(self, ID):
        from Dlg import DLG_Noedoc
        infos = self.modeles.GetModele(ID)
        hote = wx.Frame(None)
        dlg = DLG_Noedoc.Dialog(hote, IDmodele=ID, nom=infos["nom"], observations=infos["observations"],
                                IDfond=infos["IDfond"], categorie="convention",
                                taille_page=(infos["largeur"] or 210, infos["hauteur"] or 297))
        return hote, dlg

    def _fermer(self, dlg, hote):
        # Minuteur de redimensionnement de FloatCanvas encore armé juste après
        # l'ouverture : l'arrêter évite qu'il se déclenche sur un canevas
        # détruit pendant un test suivant.
        minuteur = getattr(dlg.ctrl_canvas.canvas, "SizeTimer", None)
        if minuteur is not None:
            minuteur.Stop()
        dlg.Quitter()
        hote.Destroy()
        for _ in range(5):
            wx.Yield()  # la destruction d'une fenêtre de premier niveau est différée
        if minuteur is not None:
            minuteur.Stop()  # réarmé par le dernier événement de taille de la destruction

    def test_blocs_flottants_dans_la_page_et_ancrages_conserves(self):
        self.assertEqual(len(self.IDs), 3)
        for ID in self.IDs:
            with self.subTest(modele=self.modeles.GetModele(ID)["nom"]):
                avant = self._positions(ID)
                hote, dlg = self._ouvrir(ID)
                try:
                    canvas = dlg.ctrl_canvas
                    textes = [o for o in canvas.canvas._ForeDrawList if getattr(o, "categorie", None) == "bloc_texte"]
                    visibles = [o for o in textes if o.Visible]
                    self.assertTrue(visibles)
                    for objet in visibles:
                        (x0, y0), (x1, y1) = objet.BoundingBox
                        self.assertGreaterEqual(float(y0), -0.5, objet.nom)
                        self.assertLessEqual(float(x1), 210.5, objet.nom)
                    masques = len(textes) - len(visibles)
                    self.assertEqual(bool(masques), bool(getattr(canvas, "_indicateurs_ecoulement", [])))
                    canvas.Sauvegarde()
                    self.assertEqual(self._positions(ID), avant)
                finally:
                    self._fermer(dlg, hote)

    def test_bloc_deplace_par_l_utilisateur_garde_sa_position(self):
        ID = self.IDs[0]
        hote, dlg = self._ouvrir(ID)
        try:
            canvas = dlg.ctrl_canvas
            corps = next(o for o in canvas.canvas._ForeDrawList if getattr(o, "nom", None) == "Corps")
            corps.Move(numpy.array((0.0, -10.0)))
            attendu = tuple(float(v) for v in corps.GetXY())
            canvas.Sauvegarde()
            IDobjet = corps.IDobjet
        finally:
            self._fermer(dlg, hote)
        self.base.db.ExecuterReq("SELECT x, y FROM documents_objets WHERE IDobjet=%d;" % IDobjet)
        self.assertEqual(tuple(float(v) for v in self.base.db.ResultatReq()[0]), attendu)


if __name__ == "__main__":
    unittest.main()
