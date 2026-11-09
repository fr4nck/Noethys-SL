# -*- coding: utf-8 -*-
"""UI-432K : preparation de facture worker sur sources fictives, sans reseau."""
import sys
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import _garde_reseau  # noqa: F401,E402
import wx  # noqa: E402
from Utils import UTILS_Facturation, UTILS_Travail_long  # noqa: E402


class FacturesLectureKTests(unittest.TestCase):
    def faire_fac(self):
        fac = UTILS_Facturation.Facturation.__new__(
            UTILS_Facturation.Facturation)
        fac._source_db = "CHEMIN_FICTIF_DATA"
        return fac

    def test_lecture_avec_parent_visible_passe_au_worker(self):
        fac = self.faire_fac()
        fac._GetDonneesImpression_core = mock.Mock(return_value=("ok",))
        owner = mock.Mock(spec=wx.Window)
        owner.IsShownOnScreen.return_value = True
        with mock.patch.object(wx, "IsMainThread", return_value=True), \
             mock.patch.object(UTILS_Travail_long, "ExecuterLecture",
                               side_effect=lambda parent, fn, **kw: fn()) as travail:
            self.assertEqual(
                fac.GetDonneesImpression([42], {"afficher_classes": False},
                                         parent=owner), ("ok",))
        self.assertIs(travail.call_args.args[0], owner)
        arguments = fac._GetDonneesImpression_core.call_args
        self.assertEqual(arguments.args, ([42], {"afficher_classes": False}))
        self.assertEqual(arguments.kwargs, {
            "source_db": "CHEMIN_FICTIF_DATA", "hors_interface": True,
        })

    def test_annulation_lecture_ne_produit_aucun_pdf(self):
        fac = self.faire_fac()
        owner = mock.Mock(spec=wx.Window)
        owner.IsShownOnScreen.return_value = True
        with mock.patch.object(wx, "IsMainThread", return_value=True), \
             mock.patch.object(UTILS_Travail_long, "ExecuterLecture",
                               side_effect=UTILS_Travail_long.LectureAnnulee):
            self.assertIs(fac.GetDonneesImpression([42], {}, parent=owner),
                          False)

    def test_db_explicite_nouvelle_connexion_sans_pool_partage(self):
        fac = self.faire_fac()
        db = mock.Mock()
        db.ResultatReq.return_value = []
        with mock.patch.object(UTILS_Facturation.GestionDB, "DB",
                               return_value=db) as ouvrir:
            self.assertIs(fac._GetDonneesImpression_core(
                [42], {"afficher_classes": False},
                source_db=fac._source_db, hors_interface=True), False)
        ouvrir.assert_called_once_with(
            nomFichier="CHEMIN_FICTIF_DATA", suffixe=None, pooling=False)
        db.Close.assert_called_once()

    def test_exception_db_ferme_la_connexion_worker(self):
        fac = self.faire_fac()
        db = mock.Mock()
        db.ExecuterReq.side_effect = RuntimeError("SQL fictif")
        with mock.patch.object(UTILS_Facturation.GestionDB, "DB",
                               return_value=db):
            with self.assertRaisesRegex(RuntimeError, "SQL fictif"):
                fac._GetDonneesImpression_core(
                    [42], {"afficher_classes": False},
                    source_db=fac._source_db, hors_interface=True)
        db.Close.assert_called_once()

    def test_pas_de_worker_sans_proprietaire_visible(self):
        fac = self.faire_fac()
        owner = object()
        db = mock.Mock()
        db.ResultatReq.return_value = []
        with mock.patch.object(UTILS_Facturation.GestionDB, "DB",
                               return_value=db), \
             mock.patch.object(UTILS_Facturation.UTILS_Attente, "BusyInfo"), \
             mock.patch.object(UTILS_Travail_long, "ExecuterLecture") as travail:
            self.assertIs(fac.GetDonneesImpression(
                [42], {"afficher_classes": False}, parent=owner), False)
        travail.assert_not_called()
        db.Close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
