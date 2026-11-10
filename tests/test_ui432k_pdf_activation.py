# -*- coding: utf-8 -*-
"""UI-432K : activation explicite du PDF isole dans le dialogue des emails.

Bases et noms fictifs seulement ; aucune connexion reseau ou transmission.
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
import _garde_reseau  # noqa: E402,F401
import wx  # noqa: E402
from Dlg import DLG_Factures_email  # noqa: E402
from Utils import UTILS_Etapes_ui, UTILS_Facturation  # noqa: E402

PDF = b"%PDF-1.4\n" + b"document de test sans donnee personelle " * 10 + b"\n%%EOF\n"


class ActivationPDFKTests(unittest.TestCase):
    def _dialogue(self, active):
        return SimpleNamespace(
            ctrl_liste_factures=SimpleNamespace(
                GetTracksCoches=lambda: [SimpleNamespace(
                    IDfacture=42, etat="emission")]),
            ctrl_options=SimpleNamespace(GetOptions=lambda: {
                "repertoire_copie": "", "IDmodele": 2}),
            case_pdf_isole=SimpleNamespace(GetValue=lambda: active),
        )

    def test_case_active_passe_par_les_options_sans_variable_environnement(self):
        dlg = self._dialogue(True)
        with mock.patch.dict(os.environ, {"NOETHYS_SL_PDF_PROCESSUS": "0"}), \
             mock.patch.object(UTILS_Facturation, "Facturation") as facture, \
             mock.patch.object(DLG_Factures_email.UTILS_Config, "SetParametre") as sauver:
            facture.return_value.Impression.return_value = False
            DLG_Factures_email.Dialog.OnBoutonOk(dlg, None)
            options = facture.return_value.Impression.call_args.kwargs["dictOptions"]
        self.assertIs(options["pdf_processus_isole"], True)
        sauver.assert_not_called()

    def test_case_inactive_preserve_le_mode_historique(self):
        dlg = self._dialogue(False)
        with mock.patch.object(UTILS_Facturation, "Facturation") as facture:
            facture.return_value.Impression.return_value = False
            DLG_Factures_email.Dialog.OnBoutonOk(dlg, None)
            options = facture.return_value.Impression.call_args.kwargs["dictOptions"]
        self.assertIs(options["pdf_processus_isole"], False)

    def _facturation(self, source):
        facture = UTILS_Facturation.Facturation.__new__(
            UTILS_Facturation.Facturation)
        facture._source_db = source
        facture.GetDonneesImpression = mock.Mock(return_value=(
            {42: {"select": True, "num_facture": "000042",
                  "nomSansCivilite": "Famille fictive"}},
            {42: {"{NUMERO_FACTURE}": "000042"}},
        ))
        facture.EcritStatusbar = mock.Mock()
        return facture

    def _owner(self):
        owner = mock.Mock(spec=wx.Window)
        owner.IsShownOnScreen.return_value = True
        return owner

    @staticmethod
    def _executer(parent, gener, **kwargs):
        try:
            step = next(gener)
            while True:
                if isinstance(step, UTILS_Etapes_ui.TravailFond):
                    step = gener.send(step.calcul())
                else:
                    step = next(gener)
        except StopIteration:
            return
        finally:
            gener.close()

    def test_sqlite_explicite_choisit_processus_et_produit_un_pdf_valide(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-activation-") as rep:
            source = Path(rep) / "Fictif_DATA.dat"
            source.write_bytes(b"SQLite fictif non ouvert par les mocks")
            fac = self._facturation(str(source))
            def rendu(*args, **kw):
                Path(args[3]).write_bytes(PDF)
                return args[3]
            with mock.patch.dict(os.environ, {"NOETHYS_SL_PDF_PROCESSUS": "0"}), \
                 mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp", return_value=rep), \
                 mock.patch.object(wx, "IsMainThread", return_value=True), \
                 mock.patch.object(UTILS_Etapes_ui, "Executer", side_effect=self._executer), \
                 mock.patch.object(UTILS_Facturation.UTILS_PDF_processus, "Generer", side_effect=rendu) as spawn, \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression") as historique, \
                 mock.patch.object(wx, "MessageDialog") as erreur_dlg:
                result = fac.Impression(
                    listeFactures=[42], dictOptions={
                        "IDmodele": 2, "pdf_processus_isole": True},
                    afficherDoc=False, repertoireTemp=True, parent=self._owner())
                self.assertNotEqual(result, False)
                pdf = Path(result[1][42])
                self.assertEqual(pdf.read_bytes(), PDF)
                spawn.assert_called_once()
                historique.assert_not_called()
                erreur_dlg.assert_not_called()

    def test_source_mysql_malformee_rejetee_sans_rendu_ni_email(self):
        # Chaine fictive invalide : manque le port et l'utilisateur.
        fac = self._facturation("source-invalide[RESEAU]test_DATA")
        with tempfile.TemporaryDirectory(prefix="ui432k-mysql-refus-") as rep:
            with mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp", return_value=rep), \
                 mock.patch.object(wx, "IsMainThread", return_value=True), \
                 mock.patch.object(UTILS_Etapes_ui, "Executer") as executer, \
                 mock.patch.object(UTILS_Facturation.UTILS_PDF_processus, "Generer") as spawn, \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression") as ancien, \
                 mock.patch.object(wx, "MessageDialog") as erreur:
                resultat = fac.Impression(
                    listeFactures=[42], dictOptions={
                        "IDmodele": 2, "pdf_processus_isole": True},
                    afficherDoc=False, repertoireTemp=True, parent=self._owner())
        self.assertIs(resultat, False)
        ancien.assert_not_called()
        spawn.assert_not_called()
        executer.assert_not_called()
        erreur.assert_called_once()
        self.assertNotIn("secret", str(erreur.call_args))

    def test_timeout_pdf_refuse_et_ne_rejoue_pas_automatiquement(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-timeout-") as rep:
            source = Path(rep) / "Fictif_DATA.dat"
            source.write_bytes(b"SQLite fictif non ouvert")
            fac = self._facturation(str(source))
            with mock.patch.object(UTILS_Facturation.UTILS_Fichiers, "GetRepTemp", return_value=rep), \
                 mock.patch.object(wx, "IsMainThread", return_value=True), \
                 mock.patch.object(UTILS_Etapes_ui, "Executer", side_effect=self._executer), \
                 mock.patch.object(UTILS_Facturation.UTILS_PDF_processus, "Generer", side_effect=TimeoutError("PDF expire")) as spawn, \
                 mock.patch.object(UTILS_Facturation.UTILS_Impression_facture, "Impression") as ancien, \
                 mock.patch.object(wx, "MessageDialog") as erreur:
                resultat = fac.Impression(
                    listeFactures=[42], dictOptions={
                        "IDmodele": 2, "pdf_processus_isole": True},
                    afficherDoc=False, repertoireTemp=True, parent=self._owner())
            self.assertIs(resultat, False)
            spawn.assert_called_once()
            ancien.assert_not_called()
            erreur.assert_called_once()
            self.assertEqual(sorted(os.listdir(rep)), ["Fictif_DATA.dat"])

if __name__ == "__main__":
    unittest.main()
