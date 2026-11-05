# -*- coding: utf-8 -*-
"""Recette graphique réelle de l'État global des consommations (wx).

Ouvre la vraie fenêtre DLG_Etat_global.Dialog sur une base Noethys SQLite
FICTIVE complète, puis parcourt ce que fait un utilisateur : période Du/Au,
choix de l'activité, paramètres de calcul des unités, options, sélecteur
multiple natif des états, enregistrement et rechargement d'un profil,
aperçu PDF (formats horaire et décimal).

Réservé au runner GitHub Actions Windows isolé : la fenêtre est affichée et
ne doit jamais l'être sur un poste de travail. Les captures d'écran et les
PDF sont écrits dans NOETHYS_SL_RECETTE_SORTIE (artefact du workflow).
"""
import datetime
import faulthandler
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

SUR_RUNNER = sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"

OPTIONS_ORIGINALES = {
    "regroupement_principal", "regroupement_age", "tranches_qf_perso", "periodes_detaillees",
    "format_donnees", "afficher_regime_inconnu", "associer_regime_inconnu",
    "plafond_journalier_individu", "jours_hors_vacances", "jours_vacances",
    "etat_consommations", "orientation", "couleur_ligne_age", "couleur_ligne_total",
    "couleur_case_regroupement", "couleur_texte_regroupement",
}


@unittest.skipUnless(SUR_RUNNER, "Recette graphique réservée au runner Windows isolé")
class RecetteEtatGlobalWx(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import _garde_reseau  # noqa: F401  (aucune connexion réseau)
        import wx
        import GestionDB
        from Data import DATA_Tables as Tables
        from _fixtures_noethys_db import RedirectionGestionDB, _sql_valeur

        cls.wx = wx
        from test_noethys_sl_etat_global_historique import application_wx
        cls.app = application_wx(wx)
        cls.sortie = Path(os.environ.get("NOETHYS_SL_RECETTE_SORTIE") or tempfile.mkdtemp(prefix="recette-etat-global-"))
        cls.sortie.mkdir(parents=True, exist_ok=True)

        cls._tmp = tempfile.TemporaryDirectory(prefix="noethys-recette-etat-global-")
        cls.chemin = str(Path(cls._tmp.name) / "Recette_DATA.dat")
        db = GestionDB.DB(nomFichier=cls.chemin, suffixe=None, modeCreation=True)
        for table in Tables.DB_DATA:
            db.CreationTable(nomTable=table, dicoDB=Tables.DB_DATA)

        cls.annee = datetime.date.today().year
        A = cls.annee

        def inserer(table, colonnes, lignes):
            for ligne in lignes:
                db.ExecuterReq("INSERT INTO %s (%s) VALUES (%s);" % (
                    table, ", ".join(colonnes), ", ".join(_sql_valeur(v) for v in ligne)))

        inserer("organisateur", ["IDorganisateur", "nom"], [(1, "Organisateur fictif")])
        inserer("regimes", ["IDregime", "nom"], [(1, u"Régime général")])
        inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "Caisse fictive", 1)])
        inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1)])
        inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
        inserer("individus", ["IDindividu", "IDcivilite", "nom", "prenom", "date_naiss"],
                [(1, 4, "FICTIF", "Enfant", "%d-03-01" % (A - 8))])
        inserer("rattachements", ["IDrattachement", "IDindividu", "IDfamille", "IDcategorie", "titulaire"],
                [(1, 1, 1, 2, 0)])
        inserer("activites", ["IDactivite", "nom", "abrege", "date_debut", "date_fin"],
                [(10, "Accueil fictif", "AF", "%d-01-01" % A, "%d-12-31" % A)])
        inserer("groupes", ["IDgroupe", "IDactivite", "nom", "ordre"], [(1, 10, "Groupe fictif", 1)])
        inserer("unites", ["IDunite", "IDactivite", "nom", "abrege", "type", "ordre"],
                [(100, 10, u"Journée", "J", "Horaire", 1), (101, 10, "Repas", "R", "Unitaire", 2)])
        jour = "%d-03-04" % A
        inserer("consommations", [
            "IDconso", "IDindividu", "IDactivite", "IDgroupe", "IDcompte_payeur", "date", "IDunite",
            "heure_debut", "heure_fin", "etat", "quantite",
        ], [
            (1, 1, 10, 1, 1, jour, 100, "07:30", "18:30", "present", 1),
            (2, 1, 10, 1, 1, jour, 101, None, None, "present", 1),
            (3, 1, 10, 1, 1, "%d-03-11" % A, 100, "09:00", "12:00", "reservation", 1),
        ])
        db.Commit()
        db.Close()

        cls.redirection = RedirectionGestionDB(cls.chemin)
        cls.redirection.__enter__()

        from Dlg import DLG_Etat_global
        cls.module = DLG_Etat_global
        cls.dlg = DLG_Etat_global.Dialog(None)
        cls.dlg.Show()
        cls.patienter()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.dlg.Destroy()
            cls.patienter()
        finally:
            cls.redirection.__exit__()
            cls._tmp.cleanup()

    def setUp(self):
        # Chien de garde : un dialogue modal resté ouvert (boîte native
        # comprise) ne doit pas bloquer le runner sans diagnostic. Après 90 s,
        # capture de l'écran, pile Python de tous les fils, puis arrêt.
        def blocage():
            try:
                from PIL import ImageGrab
                ImageGrab.grab().save(str(self.sortie / ("blocage_%s.png" % self._testMethodName)))
            except Exception as erreur:
                print("Capture du blocage impossible : %r" % (erreur,), file=sys.stderr)
            print("BLOCAGE dans %s" % self._testMethodName, file=sys.stderr)
            faulthandler.dump_traceback(all_threads=True)
            sys.stderr.flush()
            os._exit(3)
        self._garde = threading.Timer(90, blocage)
        self._garde.daemon = True
        self._garde.start()

    def tearDown(self):
        self._garde.cancel()

    # ------------------------------------------------------------------ outils

    @classmethod
    def patienter(cls, duree=0.3):
        fin = datetime.datetime.now() + datetime.timedelta(seconds=duree)
        while datetime.datetime.now() < fin:
            cls.wx.YieldIfNeeded()
            cls.wx.MilliSleep(20)

    def capturer(self, fenetre, nom):
        wx = self.wx
        fenetre.Raise()
        fenetre.Update()
        self.patienter()
        import ctypes
        largeur, hauteur = fenetre.GetSize()
        # 1. Rendu complet de la fenêtre par Windows (PW_RENDERFULLCONTENT).
        image = wx.Bitmap(largeur, hauteur)
        memoire = wx.MemoryDC(image)
        ctypes.windll.user32.PrintWindow(fenetre.GetHandle(), memoire.GetHandle(), 2)
        memoire.SelectObject(wx.NullBitmap)
        chemin = self.sortie / nom
        self.assertTrue(image.SaveFile(str(chemin), wx.BITMAP_TYPE_PNG))
        # 2. Pixels réellement affichés à l'écran, pour comparaison.
        x, y = fenetre.GetScreenPosition()
        ecran = wx.Bitmap(largeur, hauteur)
        memoire = wx.MemoryDC(ecran)
        memoire.Blit(0, 0, largeur, hauteur, wx.ScreenDC(), x, y)
        memoire.SelectObject(wx.NullBitmap)
        self.assertTrue(ecran.SaveFile(str(self.sortie / nom.replace(".png", "_ecran.png")), wx.BITMAP_TYPE_PNG))
        return chemin

    def descendants(self, fenetre):
        for enfant in fenetre.GetChildren():
            yield enfant
            for petit in self.descendants(enfant):
                yield petit

    def parametrer_unites(self):
        parametres = self.dlg.ctrl_parametres
        tracks = {t.IDunite: t for t in parametres.listeTracks}
        self.assertEqual(sorted(tracks), [100, 101])
        tracks[100].SetParametres({"typeCalcul": 1, "heure_seuil": "08:00", "arrondi": 0})
        tracks[101].SetParametres({"typeCalcul": 0, "coeff": "1"})
        return tracks

    def apercu(self, nom_pdf):
        from reportlab.platypus import SimpleDocTemplate, Table
        build_original = SimpleDocTemplate.build
        recit = []

        def construire(document, story, *args, **kwargs):
            recit.extend(story)
            return build_original(document, story, *args, **kwargs)

        with mock.patch.object(SimpleDocTemplate, "build", construire), \
                mock.patch.object(self.module.FonctionsPerso, "LanceFichierExterne") as lancer:
            self.dlg.Apercu(None)
        self.assertTrue(lancer.called, "Aucun PDF produit")
        pdf = Path(lancer.call_args.args[0])
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
        shutil.copy(str(pdf), str(self.sortie / nom_pdf))
        lignes = []
        for element in recit:
            if isinstance(element, Table):
                lignes.extend([list(l) for l in element._cellvalues])
        return lignes

    # ------------------------------------------------------------------ recette

    def test_01_fenetre_d_origine(self):
        wx = self.wx
        panel = self.dlg.panel_parametres
        self.assertEqual(panel.ctrl_date_debut.GetDate(), datetime.date(self.annee, 1, 1))
        self.assertEqual(panel.ctrl_date_fin.GetDate(), datetime.date(self.annee, 12, 31))
        libelles = [e.GetLabel() for e in self.descendants(self.dlg) if isinstance(e, wx.Control)]
        self.assertFalse([l for l in libelles if "AFAS" in l or "CAF /" in l], libelles)
        self.assertEqual(set(self.dlg.ctrl_options.GetParametres()), OPTIONS_ORIGINALES)
        self.capturer(self.dlg, "01_ouverture.png")

    def test_02_activite_et_parametres_de_calcul(self):
        panel = self.dlg.panel_parametres
        panel.ctrl_activites.SetActivites([10])
        panel.OnCheckActivites()
        self.patienter()
        self.assertEqual(panel.GetActivites(), [10])
        self.parametrer_unites()
        donnees = self.dlg.ctrl_parametres.GetDonnees()
        self.assertEqual(donnees[100]["typeCalcul"], 1)
        self.assertEqual(donnees[100]["heure_seuil"], "08:00")
        self.assertEqual(donnees[101]["typeCalcul"], 0)
        self.assertEqual(donnees[101]["coeff"], 1.0)
        self.capturer(self.dlg, "02_activite_et_unites.png")

    def ouvrir_selecteur(self, nom, initial, a_cocher, capture):
        """ Ouvre le vrai MultiChoiceDialog du champ, lit les coches affichées,
        coche/décoche comme l'utilisateur puis clique sur le bouton OK. """
        wx = self.wx
        options = self.dlg.ctrl_options
        options.SetParametres({nom: initial})
        propriete = options.GetPropertyByName(nom)
        constat = {}

        def repondre():
            dialogues = [w for w in wx.GetTopLevelWindows() if isinstance(w, wx.MultiChoiceDialog)]
            constat["dialogues"] = len(dialogues)
            constat["essais"] = constat.get("essais", 0) + 1
            if not dialogues and constat["essais"] < 20:
                # Le dialogue peut s'ouvrir après le clic : nouvel essai.
                wx.CallLater(300, repondre)
                return
            if not dialogues:
                # Autre dialogue (éditeur C++ de wx) : on le ferme pour ne pas
                # bloquer la recette et on le signale.
                autres = [w for w in wx.GetTopLevelWindows() if isinstance(w, wx.Dialog) and w.IsModal()]
                constat["autres"] = [type(w).__name__ + " " + w.GetTitle() for w in autres]
                for autre in autres:
                    autre.EndModal(wx.ID_CANCEL)
                return
            dialogue = dialogues[0]
            liste = [e for e in self.descendants(dialogue) if isinstance(e, wx.CheckListBox)][0]
            constat["lignes"] = [liste.GetString(i) for i in range(liste.GetCount())]
            # GetSelections() du dialogue n'est fiable qu'après l'interaction
            # sous MSW : on lit les coches réellement affichées.
            constat["coches"] = [i for i in range(liste.GetCount()) if liste.IsChecked(i)]
            for i in range(liste.GetCount()):
                liste.Check(i, i in a_cocher)
            self.capturer(dialogue, capture)
            bouton = dialogue.FindWindowById(wx.ID_OK)
            evenement = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, wx.ID_OK)
            evenement.SetEventObject(bouton)
            bouton.GetEventHandler().ProcessEvent(evenement)

        # Chemin utilisateur : ligne sélectionnée dans la grille, clic sur le
        # bouton « ... » de l'éditeur, validation par la grille elle-même.
        self.assertTrue(options.SelectProperty(propriete, True))
        self.patienter()
        boutons = [e for e in self.descendants(options) if isinstance(e, wx.Button) and e.IsShown()]
        self.assertEqual(len(boutons), 1, nom)
        # Les erreurs levées dans les gestionnaires wx (assertions C++ comprises)
        # ne font qu'afficher une trace : on les collecte pour les refuser.
        erreurs = []
        wx.CallLater(800, repondre)
        clic = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, boutons[0].GetId())
        clic.SetEventObject(boutons[0])
        with mock.patch.object(sys, "excepthook", lambda *e: erreurs.append(repr(e[1]))):
            boutons[0].GetEventHandler().ProcessEvent(clic)
            self.patienter()
            options.CommitChangesFromEditor()
            self.patienter()
        self.assertEqual(erreurs, [], nom)
        self.assertEqual(constat.get("dialogues"), 1, (nom, constat))
        return propriete, constat

    def test_03b_tranches_d_age_saisies_dans_la_grille(self):
        wx = self.wx
        options = self.dlg.ctrl_options
        propriete = options.GetPropertyByName("regroupement_age")
        self.assertTrue(options.SelectProperty(propriete, True))
        self.patienter()
        editeur = options.GetEditorControl()
        self.assertIsInstance(editeur, wx.TextCtrl)
        erreurs = []
        with mock.patch.object(sys, "excepthook", lambda *e: erreurs.append(repr(e[1]))):
            editeur.SetValue(u"6, 12")
            options.CommitChangesFromEditor()
            self.patienter()
        self.assertEqual(erreurs, [])
        self.assertEqual(options.GetParametres()["regroupement_age"], [6, 12])
        self.capturer(self.dlg, "03b_tranches_age.png")
        options.SetParametres({"regroupement_age": []})

    def test_03_selecteurs_multiples_natifs(self):
        jours = [u"Lundi", u"Mardi", u"Mercredi", u"Jeudi", u"Vendredi", u"Samedi", u"Dimanche"]
        cas = [
            ("jours_hors_vacances", [0, 1, 2, 3, 4], [2, 5], jours, [2, 5], u"Mercredi, Samedi"),
            ("jours_vacances", [0, 1, 2, 3, 4, 5, 6], [0, 6], jours, [0, 6], u"Lundi, Dimanche"),
            ("etat_consommations", ["present"], [1, 3],
             [u"Pointage en attente", u"Présent", u"Absence justifiée", u"Absence injustifiée"],
             ["present", "absenti"], u"Présent, Absence injustifiée"),
        ]
        initiales = {"jours_hors_vacances": [0, 1, 2, 3, 4], "jours_vacances": [0, 1, 2, 3, 4, 5, 6],
                     "etat_consommations": [1]}
        for nom, initial, a_cocher, lignes, attendu, affichage in cas:
            with self.subTest(champ=nom):
                propriete, constat = self.ouvrir_selecteur(nom, initial, a_cocher, "03_%s.png" % nom)
                self.assertEqual(constat["lignes"], lignes)
                self.assertEqual(constat["coches"], initiales[nom])
                self.assertEqual(self.dlg.ctrl_options.GetParametres()[nom], attendu)
                self.assertEqual(propriete.GetValueAsString(), affichage)
        self.capturer(self.dlg, "03_selecteurs_valides.png")
        self.dlg.ctrl_options.SetParametres({"jours_hors_vacances": [0, 1, 2, 3, 4, 5, 6],
                                             "jours_vacances": [0, 1, 2, 3, 4, 5, 6],
                                             "etat_consommations": ["present"]})

    def test_04_profil_enregistre_puis_recharge(self):
        wx = self.wx
        panel = self.dlg.panel_parametres
        panel.ctrl_activites.SetActivites([10])
        panel.OnCheckActivites()
        self.parametrer_unites()
        self.dlg.ctrl_options.SetParametres({
            "etat_consommations": ["present"], "plafond_journalier_individu": 600,
            "afficher_regime_inconnu": False, "format_donnees": "horaire"})
        attendu = self.dlg.GetParametres()

        question = mock.MagicMock()
        question.return_value.ShowModal.return_value = wx.ID_YES
        saisie = mock.MagicMock()
        saisie.return_value.ShowModal.return_value = wx.ID_OK
        saisie.return_value.GetValue.return_value = "Profil de recette"
        with mock.patch.object(wx, "MessageDialog", question), mock.patch.object(wx, "TextEntryDialog", saisie):
            panel.ctrl_profil.OnBoutonEnregistrer()
        IDprofil = panel.ctrl_profil.GetIDprofil()
        self.assertIsNotNone(IDprofil)

        # Autre réglage, puis « Aucun » (réinitialisation), puis le profil.
        self.dlg.ctrl_options.SetParametres({"etat_consommations": ["reservation", "present", "absentj", "absenti"],
                                             "plafond_journalier_individu": 0})
        panel.ctrl_profil.ctrl_choix_profil.SetID(None)
        panel.ctrl_profil.OnChoixProfil()
        self.assertEqual(self.dlg.ctrl_options.GetParametres()["plafond_journalier_individu"], 0)
        panel.ctrl_profil.ctrl_choix_profil.SetID(IDprofil)
        panel.ctrl_profil.OnChoixProfil()
        self.patienter()
        recharge = self.dlg.GetParametres()
        for cle in ("etat_consommations", "plafond_journalier_individu", "format_donnees",
                    "parametres_unite_100", "parametres_unite_101"):
            self.assertEqual(recharge[cle], attendu[cle], cle)
        self.capturer(self.dlg, "04_profil_recharge.png")

    def test_05_apercu_pdf_horaire_et_decimal(self):
        panel = self.dlg.panel_parametres
        panel.ctrl_activites.SetActivites([10])
        panel.OnCheckActivites()
        self.parametrer_unites()
        self.dlg.ctrl_options.SetParametres({
            "etat_consommations": ["present"], "plafond_journalier_individu": 600,
            "afficher_regime_inconnu": False, "format_donnees": "horaire"})
        lignes = self.apercu("etat_global_horaire.pdf")
        # 07:30-18:30 avec heure seuil 08:00 = 10h30, repas coeff 1 = 1h00,
        # plafond journalier 600 min = 10h00 ; la réservation est exclue.
        self.assertIn(["Hors vacances", "10h00", "10h00"], lignes)

        self.dlg.ctrl_options.SetParametres({"format_donnees": "decimal"})
        lignes = self.apercu("etat_global_decimal.pdf")
        self.assertIn(["Hors vacances", 10.0, 10.0], lignes)
        self.capturer(self.dlg, "05_apres_apercu.png")


if __name__ == "__main__":
    unittest.main()
