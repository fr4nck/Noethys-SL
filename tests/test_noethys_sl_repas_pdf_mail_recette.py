# -*- coding: utf-8 -*-
"""Recette PDF + brouillon email : valeurs validees, fichier temporaire, zero SMTP."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
try:
    import wx
    from reportlab.platypus import SimpleDocTemplate, Table
except ImportError:
    wx = None

from Utils import UTILS_Repas_validation

CATEGORIES = (
    ("moins_6", 18),
    ("six_plus", 32),
    ("animateurs", 3),
    ("direction", 1),
    ("autres_adultes", 1),
    ("sans_porc", 7),
)


class Case:
    categorieColonne = "numerique_avec_suggestion"
    def __init__(self, valeur):
        self.valeur = valeur
    def GetValeur(self):
        return self.valeur
    def SetValeur(self, valeur):
        self.valeur = valeur


def fausse_commande():
    jour = date(2026, 10, 19)
    colonnes = [
        {"IDcolonne": i + 1, "nom_colonne": "Repas %s" % role,
         "largeur": 85, "categorie": "numerique_avec_suggestion",
         "parametres": {"role_repas": role, "site_directeur": "Site A",
                        "service_directeur": "midi"}}
        for i, (role, _) in enumerate(CATEGORIES)
    ]
    cellules = {(0, i): Case(v) for i, (_, v) in enumerate(CATEGORIES)}
    cellules.update({(1, i): Case(0) for i in range(len(CATEGORIES))})
    donnees = {
        "liste_dates": [jour, "Total"], "liste_colonnes": colonnes,
        "cases": cellules, "erreurs_sans_porc": {},
        "sans_porc": {6: {jour: {"sans_porc": 7, "repas": 50, "non_renseignes": 1}}},
    }
    classe = lambda value: SimpleNamespace(GetValue=lambda: value)
    fake = SimpleNamespace(
        ctrl_repas=SimpleNamespace(GetDonnees=lambda: donnees),
        ctrl_nom=classe("Commande fictive"),
        ctrl_observations=classe(""),
        ctrl_date_debut=SimpleNamespace(GetDate=lambda: jour),
        ctrl_date_fin=SimpleNamespace(GetDate=lambda: jour),
        _controle_repas_snapshot=UTILS_Repas_validation.ResumeDepuisDonnees(donnees))
    return fake, donnees


class FauxOptions:
    def ShowModal(self):
        return wx.ID_OK
    def GetOptions(self):
        return {
            "orientation": "portrait",
            "taille_texte_titre": 9, "taille_texte": 7,
            "largeur_colonne_date": 110, "largeur_colonnes_auto": True,
            "couleur_fond_entetes": wx.Colour(230, 230, 230),
            "couleur_fond_total": wx.Colour(245, 245, 245),
            "masquer_dates_anciennes": False, "afficher_observations": False,
        }
    def Destroy(self):
        pass


@unittest.skipIf(wx is None, "wxPython et ReportLab requis")
class RecettePDFMailerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Saisie_commande
        cls.module = DLG_Saisie_commande

    def exporter(self, fake, output, capture=None):
        from Dlg import DLG_Options_impression_pdf
        from Utils import UTILS_Organisateur
        original = SimpleDocTemplate.build
        def capture_story(pdf, story, *args, **kwargs):
            if capture is not None:
                # Sauver les donnees *avant* que ReportLab les remplace par
                # des _ExpandedCellTuple lors de la mise en page PDF.
                for bloc in story:
                    if isinstance(bloc, Table):
                        capture.append([
                            [getattr(cellule, "text", str(cellule)) for cellule in ligne]
                            for ligne in bloc._cellvalues
                        ])
            return original(pdf, story, *args, **kwargs)
        with patch.object(DLG_Options_impression_pdf, "Dialog", return_value=FauxOptions()), \
                patch.object(UTILS_Organisateur, "GetNom", return_value="Accueil fictif"), \
                patch.object(SimpleDocTemplate, "build", capture_story):
            return self.module.Dialog.CreationPDF(fake, nomDoc=str(output), afficherDoc=False)

    def test_pdf_veritable_reprend_les_valeurs_confirmees_et_fusion_mail(self):
        fake, donnees = fausse_commande()
        self.assertEqual(UTILS_Repas_validation.FusionTotauxPDF(fake._controle_repas_snapshot),
                         {"{REPAS_TOTAL}": "55", "{REPAS_6_PLUS}": "37",
                          "{REPAS_ADULTES}": "5", "{REPAS_SANS_PORC}": "7"})
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            path = Path(tmp) / "commande.pdf"
            story = []
            champs = self.exporter(fake, path, story)
            self.assertEqual(champs["{REPAS_TOTAL}"], "55")
            self.assertEqual(champs["{REPAS_6_PLUS}"], "37")
            self.assertEqual(champs["{REPAS_ADULTES}"], "5")
            self.assertEqual(champs["{REPAS_SANS_PORC}"], "7")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(path.stat().st_size, 1000)
            recap = story[-1]
            line = recap[1]
            self.assertEqual(line, [
                "19/10/2026", "Site A / midi", "18", "32", "3/1/1",
                "37", "7", "55",
            ])

    def test_pdf_refuse_sans_confirmation_recente(self):
        fake, _ = fausse_commande()
        fake._controle_repas_snapshot = None
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            path = Path(tmp) / "interdit.pdf"
            with patch.object(wx, "MessageBox") as avertissement:
                resultat = self.module.Dialog.CreationPDF(fake, nomDoc=str(path), afficherDoc=False)
            self.assertIs(resultat, False)
            self.assertFalse(path.exists())
            avertissement.assert_called_once()

    def test_pdf_refuse_si_valeurs_changees_apres_confirmation(self):
        fake, donnees = fausse_commande()
        donnees["cases"][(0, 2)].SetValeur(8)
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            path = Path(tmp) / "perime.pdf"
            with patch.object(wx, "MessageBox") as avertissement:
                resultat = self.module.Dialog.CreationPDF(fake, nomDoc=str(path), afficherDoc=False)
            self.assertIs(resultat, False)
            self.assertFalse(path.exists())
            avertissement.assert_called_once()

    def test_brouillon_reutilise_pdf_et_champs_valides_sans_envoyer(self):
        from Dlg import DLG_Mailer, DLG_Options_impression_pdf
        from Utils import UTILS_Organisateur, UTILS_Envoi_email
        fake, _ = fausse_commande()
        fake.CreationPDF = lambda **kw: self.module.Dialog.CreationPDF(fake, **kw)

        class MailerSansSMTP:
            donnees = None
            fichier = None
            listeSucces = []
            def __init__(self, *args, **kwargs):
                pass
            def SetDonnees(self, donnees, modificationAutorisee=False):
                self.donnees = donnees
            def SetPiecesJointes(self, fichiers):
                self.fichier = Path(fichiers[0]).read_bytes()
            def ChargerModeleDefaut(self):
                pass
            def ShowModal(self):
                return wx.ID_CANCEL
            def Destroy(self):
                pass

        mailer = MailerSansSMTP()
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            chemin = Path(tmp) / "joint.pdf"
            with patch.object(DLG_Mailer, "Dialog", return_value=mailer), \
                    patch.object(DLG_Options_impression_pdf, "Dialog", return_value=FauxOptions()), \
                    patch.object(UTILS_Organisateur, "GetNom", return_value="Accueil fictif"):
                resultat = UTILS_Envoi_email.EnvoiEmailFamille(
                    parent=fake, nomDoc=str(chemin),
                    categorie="commande_repas", listeAdresses=["exemple@example.invalid"])
            self.assertFalse(resultat)  # aucun envoi, aucun destinataire externe
            self.assertTrue(mailer.fichier.startswith(b"%PDF-"))
            self.assertEqual(mailer.donnees[0]["champs"]["{REPAS_TOTAL}"], "55")
            self.assertEqual(mailer.donnees[0]["champs"]["{REPAS_6_PLUS}"], "37")
            self.assertEqual(mailer.donnees[0]["champs"]["{REPAS_ADULTES}"], "5")
            self.assertEqual(mailer.donnees[0]["champs"]["{REPAS_SANS_PORC}"], "7")


if __name__ == "__main__":
    unittest.main()
