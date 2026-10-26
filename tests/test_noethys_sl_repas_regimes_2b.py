# -*- coding: utf-8 -*-
"""Lot 2B #430 : controle, PDF et brouillon d'email des regimes (fictif).

Dialogues crees sans affichage ; PDF ReportLab reel dans un dossier
temporaire ; mailer simule, aucun SMTP ; aucune donnee reelle.
"""
import builtins
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT / "noethys", ROOT / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
from Utils import UTILS_Repas_validation as V  # noqa: E402

try:
    import wx  # seule absence toleree : wxPython / ReportLab eux-memes
    from reportlab.platypus import SimpleDocTemplate, Table
except ImportError:
    wx = None

JOUR = date(2026, 11, 4)
# (role, site, service, valeur) : Site A midi = 42 + 8 + 5 + 0 = 55 ;
# Site B soir = 2 standards + 1 non renseigne = 3.
CELLULES = [
    ("moins_6", "Site A", "midi", 18), ("six_plus", "Site A", "midi", 32),
    ("animateurs", "Site A", "midi", 3), ("direction", "Site A", "midi", 1),
    ("autres_adultes", "Site A", "midi", 1),
    ("regime_standard", "Site A", "midi", 42), ("regime_sans_porc", "Site A", "midi", 8),
    ("regime_vegetarien", "Site A", "midi", 5), ("regime_non_renseigne", "Site A", "midi", 0),
    ("six_plus", "Site B", "soir", 3),
    ("regime_standard", "Site B", "soir", 2), ("regime_sans_porc", "Site B", "soir", 0),
    ("regime_vegetarien", "Site B", "soir", 0), ("regime_non_renseigne", "Site B", "soir", 1),
]


class Case:
    categorieColonne = "numerique_avec_suggestion"

    def __init__(self, valeur):
        self.valeur = valeur

    def GetValeur(self):
        return self.valeur

    def SetValeur(self, valeur):
        self.valeur = valeur


def donnees_regimes(cellules=CELLULES, regimes_source=None):
    colonnes = [{"IDcolonne": i + 1, "nom_colonne": "C%d" % (i + 1), "largeur": 60,
                 "categorie": "numerique_avec_suggestion",
                 "parametres": {"role_repas": role, "site_directeur": site, "service_directeur": service}}
                for i, (role, site, service, _v) in enumerate(cellules)]
    cases = dict(((0, i), Case(v)) for i, (_r, _s, _sv, v) in enumerate(cellules))
    cases.update(((1, i), Case(0)) for i in range(len(cellules)))
    return {"liste_dates": [JOUR, "Total"], "liste_colonnes": colonnes, "cases": cases,
            "erreurs_sans_porc": {}, "erreurs_regimes": {}, "regimes": regimes_source or {}}


class ContratPurTests(unittest.TestCase):
    def test_lecture_des_parametres_sans_eval(self):
        def interdit(*args, **kwargs):
            raise AssertionError("eval() ne doit jamais etre appele")
        with patch.object(builtins, "eval", interdit):
            self.assertEqual(V.LireParametres("{'unites': [(1, 10)], 'role_repas': 'regime_standard', 'x': None}"),
                             {"unites": [(1, 10)], "role_repas": "regime_standard", "x": None})
            self.assertEqual(V.LireParametres({"a": 1}), {"a": 1})
            self.assertIsNone(V.LireParametres(None))
            self.assertIsNone(V.LireParametres("  "))
            for texte in ("__import__('os').system('echo x')", "[1, 2]", "{'a': len('x')}", "{", 12):
                with self.subTest(texte=texte), self.assertRaises(ValueError):
                    V.LireParametres(texte)

    def test_parametres_de_la_base_d_exemple_restent_lisibles(self):
        base = ROOT / "noethys" / "Static" / "Exemples" / "EXEMPLE_alsh_DATA.dat"
        connexion = sqlite3.connect("file:%s?mode=ro" % base.as_posix(), uri=True)
        self.addCleanup(connexion.close)
        lignes = connexion.execute("SELECT parametres FROM modeles_commandes_colonnes "
                                   "UNION ALL SELECT parametres FROM modeles_commandes").fetchall()
        self.assertTrue(lignes)
        for (texte,) in lignes:
            resultat = V.LireParametres(texte)
            self.assertTrue(resultat is None or isinstance(resultat, dict))

    def test_ancien_sans_porc_et_regimes_jamais_combines(self):
        cellules = CELLULES[:9] + [("sans_porc", "Site B", "soir", 1)]
        with self.assertRaises(ValueError) as ctx:
            V.ConstruireControle(donnees_regimes(cellules))
        self.assertIn("Ne combinez pas", str(ctx.exception))

    def test_fusion_des_quatre_categories_validees(self):
        resume = V.ResumeDepuisDonnees(donnees_regimes(CELLULES[:9]))
        self.assertEqual(V.FusionTotauxPDF(resume), {
            "{REPAS_TOTAL}": "55", "{REPAS_6_PLUS}": "37", "{REPAS_ADULTES}": "5",
            "{REPAS_STANDARD}": "42", "{REPAS_SANS_PORC}": "8", "{REPAS_VEGETARIEN}": "5",
            "{REPAS_NON_RENSEIGNE}": "0"})
        complet = V.FusionTotauxPDF(V.ResumeDepuisDonnees(donnees_regimes()))
        self.assertEqual((complet["{REPAS_TOTAL}"], complet["{REPAS_STANDARD}"],
                          complet["{REPAS_NON_RENSEIGNE}"]), ("58", "44", "1"))

    def test_correction_explicite_des_regimes_reportee_dans_la_grille(self):
        d = donnees_regimes(CELLULES[:9])
        lignes = V.ConstruireControle(d)
        lignes[0]["regimes"]["standard"] = 41
        lignes[0]["regimes"]["non_renseignes"] = 1
        V.AppliquerControle(lignes)
        self.assertEqual((d["cases"][(0, 5)].valeur, d["cases"][(0, 8)].valeur), (41, 1))
        self.assertEqual(d["cases"][(0, 1)].valeur, 32)

    def test_acquittements(self):
        cle = (JOUR, "Site A", "midi")
        source = {"standard": 40, "sans_porc": 7, "vegetarien": 3, "non_renseignes": 0, "total_repas": 50,
                  "adultes_avec_conso": 1, "ages_inconnus": 0, "multisites": 0, "complet": True}
        d = donnees_regimes(regimes_source=dict((i, {cle: source}) for i in range(6, 10)))
        messages = V.AcquittementsRegimes(V.ConstruireControle(d))
        self.assertTrue(any("18 ans et plus" in m for m in messages))
        self.assertTrue(any("Site B soir : 1 repas a preference non renseignee" in m for m in messages))
        self.assertEqual(V.AcquittementsRegimes(V.ConstruireControle(donnees_regimes(CELLULES[:9]))), [])


@unittest.skipIf(wx is None, "wxPython et ReportLab requis")
class DialogueControleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Controle_repas
        cls.M = DLG_Controle_repas

    def dialogue(self, d):
        dlg = self.M.Dialog(None, d)
        self.addCleanup(dlg.Destroy)
        return dlg

    def valider(self, dlg, reponse=None):
        with patch.object(self.M.wx, "MessageBox", return_value=reponse) as message, \
                patch.object(dlg, "EndModal") as fin:
            dlg.OnValider(None)
        return message, fin

    def test_affiche_les_quatre_categories_sans_double_sans_porc(self):
        dlg = self.dialogue(donnees_regimes(CELLULES[:9]))
        R = self.M.COL_REGIMES
        self.assertEqual([dlg.grid.GetColLabelValue(R + k) for k in range(4)],
                         [u"Standard", u"Sans porc", u"Végétarien", u"Non renseigné"])
        self.assertEqual([dlg.grid.GetCellValue(0, R + k) for k in range(4)], ["42", "8", "5", "0"])
        self.assertEqual(dlg.grid.GetCellValue(0, 11), "55")
        self.assertEqual(dlg.grid.GetCellValue(0, self.M.COL_ECART), "0")
        self.assertFalse(dlg.grid.IsColShown(8))  # ancien « dont sans porc » masque
        message, fin = self.valider(dlg)
        message.assert_not_called()
        fin.assert_called_once_with(wx.ID_OK)

    def test_effectif_corrige_jamais_reporte_sur_les_regimes(self):
        dlg = self.dialogue(donnees_regimes(CELLULES[:9]))
        dlg.grid.SetCellValue(0, 4, "33")  # enfants 6+ corriges
        dlg.LireValeurs()
        self.assertEqual(dlg.grid.GetCellValue(0, 11), "56")
        self.assertEqual(dlg.grid.GetCellValue(0, self.M.COL_REGIMES), "42")  # inchange
        self.assertEqual(dlg.grid.GetCellValue(0, self.M.COL_ECART), "-1")
        message, fin = self.valider(dlg)
        message.assert_called_once()
        self.assertIn("55 repas repartis pour 56", message.call_args.args[0])
        fin.assert_not_called()
        # Correction explicite de la repartition : validation possible.
        dlg.grid.SetCellValue(0, self.M.COL_REGIMES, "43")
        message, fin = self.valider(dlg)
        fin.assert_called_once_with(wx.ID_OK)
        dlg.Appliquer()

    def test_non_renseignes_exigent_un_acquittement(self):
        dlg = self.dialogue(donnees_regimes())
        message, fin = self.valider(dlg, reponse=wx.NO)
        self.assertIn("non renseignee", message.call_args.args[0])
        fin.assert_not_called()
        message, fin = self.valider(dlg, reponse=wx.YES)
        fin.assert_called_once_with(wx.ID_OK)

    def test_ancien_modele_sans_colonnes_de_regime(self):
        cellules = [("moins_6", "Site A", "midi", 18), ("six_plus", "Site A", "midi", 32),
                    ("sans_porc", "Site A", "midi", 7)]
        dlg = self.dialogue(donnees_regimes(cellules))
        self.assertTrue(dlg.grid.IsColShown(8))
        self.assertFalse(dlg.grid.IsColShown(self.M.COL_REGIMES))
        self.assertEqual(dlg.grid.GetCellValue(0, 8), "7")
        message, fin = self.valider(dlg)
        fin.assert_called_once_with(wx.ID_OK)

    def test_anomalie_bloquante_de_la_source(self):
        d = donnees_regimes(CELLULES[:9])
        d["erreurs_regimes"] = {6: "Reponses alimentaires a corriger : 0 inconnue(s), 1 contradictoire(s)"}
        with self.assertRaises(ValueError):
            self.M.Dialog(None, d)


class FauxOptions:
    def ShowModal(self):
        return wx.ID_OK

    def GetOptions(self):
        return {"orientation": "portrait", "taille_texte_titre": 9, "taille_texte": 7,
                "largeur_colonne_date": 110, "largeur_colonnes_auto": True,
                "couleur_fond_entetes": wx.Colour(230, 230, 230),
                "couleur_fond_total": wx.Colour(245, 245, 245),
                "masquer_dates_anciennes": False, "afficher_observations": False}

    def Destroy(self):
        pass


@unittest.skipIf(wx is None, "wxPython et ReportLab requis")
class DocumentsRestaurateurTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Saisie_commande
        cls.module = DLG_Saisie_commande

    def commande(self):
        d = donnees_regimes()
        texte = lambda valeur: SimpleNamespace(GetValue=lambda: valeur)
        fake = SimpleNamespace(
            ctrl_repas=SimpleNamespace(GetDonnees=lambda: d), ctrl_nom=texte("Commande fictive"),
            ctrl_observations=texte(""), ctrl_date_debut=SimpleNamespace(GetDate=lambda: JOUR),
            ctrl_date_fin=SimpleNamespace(GetDate=lambda: JOUR),
            _controle_repas_snapshot=V.ResumeDepuisDonnees(d))
        fake.CreationPDF = lambda **kw: self.module.Dialog.CreationPDF(fake, **kw)
        return fake, d

    def exporter(self, fake, chemin, capture):
        from Dlg import DLG_Options_impression_pdf
        from Utils import UTILS_Organisateur
        original = SimpleDocTemplate.build

        def capture_story(pdf, story, *args, **kwargs):
            for bloc in story:
                if isinstance(bloc, Table):
                    capture.append([[getattr(c, "text", str(c)) for c in ligne] for ligne in bloc._cellvalues])
            return original(pdf, story, *args, **kwargs)
        with patch.object(DLG_Options_impression_pdf, "Dialog", return_value=FauxOptions()), \
                patch.object(UTILS_Organisateur, "GetNom", return_value="Accueil fictif"), \
                patch.object(SimpleDocTemplate, "build", capture_story):
            return self.module.Dialog.CreationPDF(fake, nomDoc=str(chemin), afficherDoc=False)

    def test_pdf_reel_quatre_categories_par_site_et_service(self):
        fake, _d = self.commande()
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            chemin = Path(tmp) / "commande.pdf"
            tableaux = []
            champs = self.exporter(fake, chemin, tableaux)
            self.assertTrue(chemin.read_bytes().startswith(b"%PDF-"))
            recap = tableaux[-1]
            self.assertEqual(recap[0][6:], [u"Standard", u"Sans porc", u"Végétarien", u"Non renseigné", u"Total"])
            self.assertNotIn(u"Dont sans porc", recap[0])
            self.assertEqual(recap[1], ["04/11/2026", "Site A / midi", "18", "32", "3/1/1", "37",
                                        "42", "8", "5", "0", "55"])
            self.assertEqual(recap[2], ["04/11/2026", "Site B / soir", "0", "3", "0/0/0", "3",
                                        "2", "0", "0", "1", "3"])
            self.assertEqual((champs["{REPAS_TOTAL}"], champs["{REPAS_VEGETARIEN}"]), ("58", "5"))
            texte = " ".join(c for ligne in recap for c in ligne)
            self.assertNotIn("FICTIF", texte)  # aucune donnee nominative

    def test_brouillon_email_meme_jeu_que_le_pdf_sans_smtp(self):
        from Dlg import DLG_Mailer, DLG_Options_impression_pdf
        from Utils import UTILS_Organisateur, UTILS_Envoi_email
        fake, _d = self.commande()

        class MailerSansSMTP:
            donnees = fichier = None
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
            with patch.object(DLG_Mailer, "Dialog", return_value=mailer), \
                    patch.object(DLG_Options_impression_pdf, "Dialog", return_value=FauxOptions()), \
                    patch.object(UTILS_Organisateur, "GetNom", return_value="Accueil fictif"):
                resultat = UTILS_Envoi_email.EnvoiEmailFamille(
                    parent=fake, nomDoc=str(Path(tmp) / "joint.pdf"),
                    categorie="commande_repas", listeAdresses=["exemple@example.invalid"])
        self.assertFalse(resultat)  # aucun envoi
        self.assertTrue(mailer.fichier.startswith(b"%PDF-"))
        self.assertEqual(dict((k, v) for k, v in mailer.donnees[0]["champs"].items() if k.startswith("{REPAS_")),
                         V.FusionTotauxPDF(fake._controle_repas_snapshot))

    def test_modification_apres_validation_bloque_pdf_et_email(self):
        fake, d = self.commande()
        d["cases"][(0, 7)].SetValeur(6)  # vegetarien modifie apres validation
        with tempfile.TemporaryDirectory(prefix="noethys-repas-fictif-") as tmp:
            chemin = Path(tmp) / "perime.pdf"
            with patch.object(wx, "MessageBox") as avertissement:
                self.assertIs(self.module.Dialog.CreationPDF(fake, nomDoc=str(chemin), afficherDoc=False), False)
            self.assertFalse(chemin.exists())
            avertissement.assert_called_once()


if __name__ == "__main__":
    unittest.main()
