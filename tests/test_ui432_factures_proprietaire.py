# -*- coding: utf-8 -*-
"""UI-432I : proprietaires des fenetres de facturation et nettoyage, sans reseau.

Les lectures SQL, la generation PDF et le transport d'emails sont simules.
Les tests ne chargent jamais le profil de production.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import _garde_reseau  # noqa: F401,E402

from Dlg import DLG_Factures_email, DLG_Mailer  # noqa: E402
from Utils import UTILS_Facturation, UTILS_Envoi_email  # noqa: E402


def _selection():
    return SimpleNamespace(
        IDfacture=42, etat="emission", numero="42", IDfamille=1,
        email=True, email_factures="famille@example.org",
        nomsTitulaires="Famille fictive",
    )


def _dialogue():
    return SimpleNamespace(
        ctrl_liste_factures=SimpleNamespace(GetTracksCoches=lambda: [_selection()]),
        ctrl_options=SimpleNamespace(GetOptions=lambda: {"repertoire_copie": ""}),
    )


class FacturesProprietaireTests(unittest.TestCase):
    def test_transfert_passe_le_dialogue_visible_a_la_facturation(self):
        dlg = _dialogue()
        with mock.patch.object(UTILS_Facturation, "Facturation") as fac:
            fac.return_value.Impression.return_value = False
            DLG_Factures_email.Dialog.OnBoutonOk(dlg, None)
        self.assertIs(fac.return_value.Impression.call_args.kwargs["parent"], dlg)
        self.assertTrue(fac.return_value.Impression.call_args.kwargs["repertoireTemp"])

    def test_lecture_sql_attente_parentee_et_connexion_fermee(self):
        owner = object()
        db = mock.Mock()
        db.ResultatReq.return_value = []
        fac = UTILS_Facturation.Facturation.__new__(UTILS_Facturation.Facturation)
        with mock.patch.object(UTILS_Facturation.GestionDB, "DB", return_value=db), \
             mock.patch.object(UTILS_Facturation.UTILS_Attente, "BusyInfo") as attente:
            resultat = fac.GetDonneesImpression([42], {"afficher_classes": False}, parent=owner)
        self.assertIs(resultat, False)
        self.assertIs(attente.call_args.args[1], owner)
        db.Close.assert_called_once_with()

    def _impression_pdf_fictive(self, erreur=False):
        owner = object()
        fac = UTILS_Facturation.Facturation.__new__(UTILS_Facturation.Facturation)
        fac.GetDonneesImpression = mock.Mock(return_value=(
            {42: {"select": True, "num_facture": "000042", "nomSansCivilite": "Fictive"}},
            {42: {"{NUMERO_FACTURE}": "000042"}},
        ))
        fac.EcritStatusbar = mock.Mock()

        def rendu_fictif(*args, **kwargs):
            if erreur:
                raise RuntimeError("PDF fictif en echec")
            Path(kwargs["nomFichier"]).write_bytes(
                b"%PDF-1.4\\n" + b"fictif" * 20 + b"\\n%%EOF\\n")

        with tempfile.TemporaryDirectory(
                prefix="ui432-facture-", dir=_garde_reseau.PROFIL_TEST) as rep:
            with mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp",
                                   return_value=rep), \
                 mock.patch.object(UTILS_Facturation.wx, "ProgressDialog") as progress, \
                 mock.patch.object(UTILS_Facturation.wx, "MessageDialog") as erreur_dlg, \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression",
                                   side_effect=rendu_fictif) as pdf, \
                 mock.patch.object(UTILS_Facturation.traceback, "print_exc"):
                resultat = fac.Impression(
                    listeFactures=[42], dictOptions={"IDmodele": 3},
                    afficherDoc=False, repertoireTemp=True, parent=owner)
                self.assertIs(fac.GetDonneesImpression.call_args.kwargs["parent"], owner)
                self.assertIs(progress.call_args.kwargs["parent"], owner)
                progress.return_value.Destroy.assert_called_once()
                pdf.assert_called_once()
                if erreur:
                    self.assertIs(resultat, False)
                    self.assertIs(erreur_dlg.call_args.args[0], owner)
                    self.assertEqual(os.listdir(rep), [])
                else:
                    self.assertIn(42, resultat[1])
                    self.assertTrue(Path(resultat[1][42]).is_file())
                    erreur_dlg.assert_not_called()

    def test_pdf_fictif_proprietaire_conserve(self):
        self._impression_pdf_fictive()

    def test_echec_pdf_fictif_dialogue_erreur_parent(self):
        self._impression_pdf_fictive(erreur=True)

    def test_exception_mailer_nettoie_pdf_et_detruit_dialogue(self):
        fd, chemin = tempfile.mkstemp(prefix="ui432-facture-", suffix=".pdf",
                                     dir=_garde_reseau.PROFIL_TEST)
        os.close(fd)
        dlg = _dialogue()
        try:
            db = mock.Mock()
            db.ResultatReq.return_value = [(1, "famille@example.org", None)]
            with mock.patch.object(UTILS_Facturation, "Facturation") as fac, \
                 mock.patch.object(DLG_Factures_email.GestionDB, "DB", return_value=db), \
                 mock.patch.object(UTILS_Envoi_email, "GetRattachementsFamilles", return_value={}), \
                 mock.patch.object(UTILS_Envoi_email, "ResoudreAdresseConfiguree",
                                   return_value=("famille@example.org", None)), \
                 mock.patch.object(DLG_Mailer, "Dialog") as mailer:
                fac.return_value.Impression.return_value = (
                    {42: {"{NUMERO_FACTURE}": "000042"}}, {42: chemin}
                )
                mailer.return_value.ShowModal.side_effect = RuntimeError("arret fictif")
                with self.assertRaisesRegex(RuntimeError, "arret fictif"):
                    DLG_Factures_email.Dialog.OnBoutonOk(dlg, None)
                mailer.return_value.Destroy.assert_called_once()
                db.Close.assert_called_once()
                self.assertFalse(os.path.exists(chemin))
        finally:
            if os.path.exists(chemin):
                os.remove(chemin)


    def test_erreur_sql_libere_toujours_la_fenetre_attente(self):
        fac = UTILS_Facturation.Facturation.__new__(UTILS_Facturation.Facturation)
        fenetre = mock.MagicMock()
        fenetre.__enter__ = mock.Mock(return_value=fenetre)
        fenetre.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(UTILS_Facturation.UTILS_Attente, "BusyInfo",
                               return_value=fenetre), \
             mock.patch.object(UTILS_Facturation.GestionDB, "DB",
                               side_effect=RuntimeError("SQL fictif")):
            with self.assertRaisesRegex(RuntimeError, "SQL fictif"):
                fac.GetDonneesImpression([42], {"afficher_classes": False}, parent=object())
        fenetre.__exit__.assert_called_once()

    def test_pdf_temp_partiel_efface_si_generation_echoue(self):
        fac = UTILS_Facturation.Facturation.__new__(UTILS_Facturation.Facturation)
        fac.GetDonneesImpression = mock.Mock(return_value=(
            {42: {"select": True, "num_facture": "000042", "nomSansCivilite": "Fictive"}},
            {42: {"{NUMERO_FACTURE}": "000042"}},
        ))
        fac.EcritStatusbar = mock.Mock()
        traces = []
        with tempfile.TemporaryDirectory(prefix="ui432-pdf-", dir=_garde_reseau.PROFIL_TEST) as rep:
            def ecriture_partielle(*args, **kwargs):
                chemin = kwargs["nomFichier"]
                Path(chemin).write_bytes(b"%PDF-1.4\\npartiel")
                traces.append(chemin)
                raise RuntimeError("PDF fictif incomplet")
            with mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp",
                                   return_value=rep), \
                 mock.patch.object(UTILS_Facturation.wx, "ProgressDialog"), \
                 mock.patch.object(UTILS_Facturation.wx, "MessageDialog"), \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression",
                                   side_effect=ecriture_partielle), \
                 mock.patch.object(UTILS_Facturation.traceback, "print_exc"):
                resultat = fac.Impression(
                    listeFactures=[42], dictOptions={"IDmodele": 3},
                    afficherDoc=False, repertoireTemp=True, parent=object())
            self.assertIs(resultat, False)
            self.assertEqual(len(traces), 1)
            self.assertFalse(Path(traces[0]).exists())


    def test_generation_de_lot_yield_entre_factures_sans_worker_pdf(self):
        # Le parent se comporte comme une wx.Window visible ; les widgets
        # et les PDF demeurent simules, aucune connexion n'est permise.
        import wx
        owner = mock.Mock(spec=wx.Window)
        self.assertIsInstance(owner, wx.Window)
        owner.IsShownOnScreen.return_value = True
        fac = UTILS_Facturation.Facturation.__new__(UTILS_Facturation.Facturation)
        fac.GetDonneesImpression = mock.Mock(return_value=(
            {
                42: {"select": True, "num_facture": "000042",
                     "nomSansCivilite": "Fictive"},
                43: {"select": True, "num_facture": "000043",
                     "nomSansCivilite": "Fictive"},
            },
            {42: {}, 43: {}},
        ))
        fac.EcritStatusbar = mock.Mock()
        etapes = []
        commandes = []

        def executer(parent, generateur, **options):
            self.assertIs(parent, owner)
            self.assertEqual(options["total"], 2)
            etapes.extend(list(generateur))

        def generer_pdf(*args, **kwargs):
            commandes.append(kwargs["nomFichier"])
            Path(kwargs["nomFichier"]).write_bytes(
                b"%PDF-1.4\\n" + b"fictif" * 20 + b"\\n%%EOF\\n")

        with tempfile.TemporaryDirectory(
                prefix="ui432-lot-", dir=_garde_reseau.PROFIL_TEST) as rep:
            with mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp",
                                   return_value=rep), \
                 mock.patch.object(UTILS_Facturation.wx, "IsMainThread", return_value=True), \
                 mock.patch.object(UTILS_Facturation.wx, "ProgressDialog") as progression, \
                 mock.patch.object(UTILS_Facturation.UTILS_Etapes_ui, "Executer",
                                   side_effect=executer) as attente, \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression",
                                   side_effect=generer_pdf):
                resultat = fac.Impression(
                    listeFactures=[42, 43], dictOptions={"IDmodele": 3},
                    afficherDoc=False, repertoireTemp=True, parent=owner)
                self.assertTrue(all(Path(p).is_file() for p in resultat[1].values()))
        self.assertEqual(etapes, ["factures.generation_pdf"] * 2)
        self.assertEqual(len(commandes), 2)
        self.assertEqual(len(resultat[1]), 2)
        progression.assert_not_called()
        attente.assert_called_once()


if __name__ == "__main__":
    unittest.main()
