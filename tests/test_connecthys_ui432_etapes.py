# -*- coding: utf-8 -*-
"""P0 Windows : vraies boucles wx, lectures fictives et aucun transport reel."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def scenario(baseline=False, inspecter=False, lecture_unique=False):
    sys.path.insert(0, str(ROOT / "tests"))
    import _garde_reseau
    from unittest import mock
    import socket
    import time
    import threading
    from types import SimpleNamespace as NS
    # Interdiction supplementaire : meme une dependance qui contourne GestionDB.
    for cible in ("connect", "connect_ex"):
        mock.patch.object(socket.socket, cible, side_effect=AssertionError("Reseau interdit")).start()
    mock.patch.object(socket, "create_connection", side_effect=AssertionError("Reseau interdit")).start()
    import wx
    import Noethys
    from Ctrl import CTRL_Grille
    from Dlg import DLG_Badgeage_grille
    from Utils import UTILS_Etapes_ui as Etapes
    from Utils import UTILS_Diagnostic_ui as Diag
    app = wx.App(False)
    Noethys.CUSTOMIZE = Noethys.UTILS_Customize.Customize()
    frame = Noethys.MainFrame(None)
    app.SetTopWindow(frame)
    frame.SetTitle("RECETTE #432 - donnees fictives - " + ("AVANT" if baseline else "CANDIDAT"))
    frame.SetSize((950, 740))
    frame.Maximize(True)
    panel = wx.Panel(frame)
    from Utils import UTILS_AUI_Apparence
    import wx.lib.agw.aui as aui
    frame._mgr = UTILS_AUI_Apparence.NoethysSLAuiManager(frame)
    frame._mgr.AddPane(panel, aui.AuiPaneInfo().CenterPane())
    frame._mgr.Update()
    bouton = wx.Button(panel, label="Tester le chargement fictif (3,5 s)", pos=(40, 60), size=(340, 50))
    wx.StaticText(panel, label="Aucune base PMSL. Aucun email. Aucun reseau.", pos=(40, 30))
    texte = wx.StaticText(panel, label="Pret", pos=(40, 130))
    parent = wx.Dialog(frame, title="Traitement des demandes - FICTIF", size=(800, 670))
    parent._diag_ui = Diag.Diagnostic(parent, actif=True, role="demande")
    frame._diag_ui = Diag.Diagnostic(frame, actif=True, role="principale")
    appels = []
    fermetures = []
    thread_ui = threading.get_ident()

    class DB:
        def Close(self):
            fermetures.append(threading.get_ident())

    grid = NS(IDfamille=3, GetGridWindow=lambda: NS(SetToolTip=lambda *a: None))
    def lecture(nom, resultat=None):
        def lire(*a, **kw):
            assert threading.get_ident() == thread_ui
            appels.append(nom)
            time.sleep((3.465 if nom == "Importation_activites" else 0) if lecture_unique else 0.165)
            return resultat if resultat is not None else {}
        return lire
    grid.InitDonneesEtapes = lambda: CTRL_Grille.CTRL.InitDonneesEtapes(grid)
    grid.MAJDonneesEtapes = lambda: CTRL_Grille.CTRL.MAJDonneesEtapes(grid)
    grid.SetModeIndividuEtapes = lambda *a: CTRL_Grille.CTRL.SetModeIndividuEtapes(grid, *a)
    grid.InitDonnees = lambda: CTRL_Grille.CTRL.InitDonnees(grid)
    grid.MAJ_donnees = lambda: CTRL_Grille.CTRL.MAJ_donnees(grid)
    grid.SetFocus = lambda: None
    grid.MAJ = lambda: CTRL_Grille.CTRL.MAJ(grid)
    grid.SetModeIndividu = lambda *a, **kw: CTRL_Grille.CTRL.SetModeIndividu(grid, *a, **kw)
    for nom in ("Importation_activites", "Importation_individus", "GetDictGroupes",
                "GetQuotientsFamiliaux", "GetAides", "GetDictEtiquettes",
                "Importation_deductions", "Importation_prestations", "Importation_forfaits",
                "Importation_transports", "GetListeTouchesRaccourcis", "GetListeVacances",
                "GetListeFeries", "GetDictMemoJournee", "MAJ_affichage"):
        setattr(grid, nom, lecture(nom))
    grid.GetComptesPayeurs = lecture("GetComptesPayeurs", {3: 3})
    grid.GetDictOuvertures = lecture("GetDictOuvertures", ({}, []))
    grid.GetListeUnites = lecture("GetListeUnites", ({}, {}))
    grid.GetDictRemplissage = lecture("GetDictRemplissage", ({}, {}, {}))
    grid.GetInfosInscriptions = lecture("GetInfosInscriptions", {42: {1: {}}})
    grid.GetInfosIndividus = lecture("GetInfosIndividus", {42: dict(nom="Fictif", prenom="Test")})
    grid.CalcRemplissage = lambda: None
    ctrl = NS(grille=grid, ctrl_titre=NS(SetNom=lambda *a: None))
    battements = []
    timer = wx.Timer(frame)
    frame.Bind(wx.EVT_TIMER, lambda e: battements.append(time.monotonic()), timer)
    timer.Start(50)
    resultat = {}
    erreurs = []
    controles = []
    Original = Etapes.Attente

    class AttenteControlee(Original):
        def _etape(self, event):
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetWindow.restype = wintypes.HWND
            controles.append((not parent.IsEnabled(), frame.IsMaximized(),
                              user32.GetWindow(self.GetHandle(), 4) == parent.GetHandle()))
            fermeture = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW)
            fermeture.SetCanVeto(True)
            self._refuser_fermeture(fermeture)
            assert fermeture.GetVeto()
            super()._etape(event)

    def finir():
        timer.Stop()
        resultat.update(retard_max_ms=round(max((b-a for a, b in zip(battements, battements[1:])), default=0)*1000),
                         battements=len(battements), appels=len(appels), connexions_fermees=len(fermetures),
                         maximise=frame.IsMaximized(), geometrie_identique=tuple(frame.GetRect()) == initial,
                         owner_modal_ok=bool(controles) and all(all(c) for c in controles),
                         parent_reactive=parent.IsEnabled(), reseau=len(_garde_reseau.TENTATIVES))
        print("UI432_RESULT " + json.dumps(resultat), flush=True)
        texte.SetLabel(json.dumps(resultat))
        if not inspecter:
            fermer()

    def fermer():
        parent.Destroy()
        frame.taskBarIcon.Detruire()
        frame._mgr.UnInit()
        frame.Destroy()

    def lancer(event=None):
        nonlocal initial
        bouton.Disable()
        initial = tuple(frame.GetRect())
        def effectuer():
            debut = time.monotonic()
            try:
                with mock.patch.object(CTRL_Grille.GestionDB, "DB", DB), \
                     mock.patch.object(Etapes, "Attente", AttenteControlee):
                    if baseline:
                        DLG_Badgeage_grille.CTRL.InitGrille(ctrl, 42, 3, 1, periode=(None, None))
                    else:
                        etapes = DLG_Badgeage_grille.CTRL.InitGrilleEtapes(ctrl, 42, 3, 1, (None, None))
                        Etapes.Executer(parent, etapes)
                assert len(fermetures) == 3
                assert all(t == thread_ui for t in fermetures)
            except BaseException as err:
                erreurs.append(repr(err))
            resultat["duree_ms"] = round((time.monotonic()-debut)*1000)
            parent.EndModal(wx.ID_OK)
        wx.CallLater(200, effectuer)
        parent.ShowModal()
        wx.CallLater(250, finir)

    initial = None
    bouton.Bind(wx.EVT_BUTTON, lancer)
    frame.Show()
    if not inspecter:
        wx.CallLater(400, lancer)
    else:
        wx.CallLater(120000, fermer)
    app.MainLoop()
    assert not erreurs, erreurs
    assert not _garde_reseau.TENTATIVES
    return resultat


def pannes():
    sys.path.insert(0, str(ROOT / "tests"))
    import _garde_reseau
    import wx
    from unittest import mock
    from types import SimpleNamespace as NS
    from Ctrl import CTRL_Grille
    from Utils import UTILS_Etapes_ui as Etapes
    app = wx.App(False)
    frame = wx.Frame(None)
    frame.Show()
    ferme = []
    grid = NS(Importation_activites=lambda: {},
              Importation_individus=mock.Mock(side_effect=RuntimeError("Panne fictive")),
              GetDictGroupes=lambda: {}, GetComptesPayeurs=lambda: {},
              GetQuotientsFamiliaux=lambda: {}, GetAides=lambda: {}, GetDictEtiquettes=lambda: {})
    with mock.patch.object(CTRL_Grille.GestionDB, "DB", return_value=NS(Close=lambda: ferme.append(True))):
        try:
            Etapes.Executer(frame, CTRL_Grille.CTRL.InitDonneesEtapes(grid))
            raise AssertionError("Panne non propagee")
        except RuntimeError as err:
            assert str(err) == "Panne fictive"
    assert ferme == [True]
    assert frame.IsEnabled()
    # Un EndModal externe ne doit jamais permettre d'appliquer une grille incomplete.
    class Interrompue(Etapes.Attente):
        compteur = 0
        def _etape(self, event):
            if self.compteur:
                self.timer.Stop()
                self.EndModal(wx.ID_CANCEL)
            else:
                self.compteur += 1
                super()._etape(event)
    ferme.clear()
    grid.Importation_individus = lambda: {}
    with mock.patch.object(CTRL_Grille.GestionDB, "DB", return_value=NS(Close=lambda: ferme.append(True))), \
         mock.patch.object(Etapes, "Attente", Interrompue):
        try:
            Etapes.Executer(frame, CTRL_Grille.CTRL.InitDonneesEtapes(grid))
            raise AssertionError("Interruption non propagee")
        except RuntimeError as err:
            assert str(err) == "Chargement de la grille interrompu"
    assert ferme == [True]
    assert frame.IsEnabled()
    assert not _garde_reseau.TENTATIVES
    frame.Destroy()
    print("UI432_PANNES_PASS", flush=True)


def grille_sqlite():
    """Deux vrais controles, meme base artificielle, memes donnees et cellules."""
    sys.path.insert(0, str(ROOT / "tests"))
    import _garde_reseau
    import datetime
    import wx
    from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
    from Data.DATA_Tables import DB_DATA
    from Dlg import DLG_Badgeage_grille
    from Utils import UTILS_Etapes_ui
    app = wx.App(False)
    frame = wx.Frame(None)
    with BaseTest() as base:
        existantes = {r[0] for r in base.db.connexion.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in DB_DATA:
            if table not in existantes:
                base.db.CreationTable(table, DB_DATA)
        base.inserer("familles", ["IDfamille"], [(3,)])
        base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], [(42, "Fictif", "Test", 1)])
        base.inserer("rattachements", ["IDfamille", "IDindividu", "IDcategorie", "titulaire"], [(3, 42, 2, 0)])
        base.inserer("activites", ["IDactivite", "nom"], [(1, "Activite fictive")])
        base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(3, 3)])
        base.inserer("categories_tarifs", ["IDcategorie_tarif", "IDactivite", "nom"], [(1, 1, "Test")])
        base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(1, 1, "Test")])
        base.inserer("inscriptions", ["IDinscription", "IDindividu", "IDfamille", "IDactivite", "IDgroupe", "IDcategorie_tarif", "IDcompte_payeur", "statut"], [(1, 42, 3, 1, 1, 1, 3, "ok")])
        base.inserer("unites", ["IDunite", "IDactivite", "nom", "abrege", "type", "ordre", "heure_debut", "heure_fin"],
                     [(1, 1, "Unite fictive", "UF", "Unitaire", 1, "08:00", "18:00")])
        base.inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], [(1, 1, 1, "2026-11-04")])
        with RedirectionGestionDB(base.chemin):
            a = DLG_Badgeage_grille.CTRL(frame, usage="portail")
            b = DLG_Badgeage_grille.CTRL(frame, usage="portail")
            # Les constructeurs historiques installent leurs parametres par defaut.
            avant = list(base.db.connexion.iterdump())
            arguments = dict(IDindividu=42, IDfamille=3, IDactivite=1,
                             periode=(datetime.date(2026, 11, 4), datetime.date(2026, 11, 4)))
            a.InitGrille(**arguments)
            UTILS_Etapes_ui.Executer(frame, b.InitGrilleEtapes(**arguments))
            for champ in ("dictActivites", "dictIndividus", "dictGroupes", "dictComptesPayeurs",
                          "dictInfosInscriptions", "dictInfosIndividus", "dictUnites", "dictOuvertures",
                          "dictPrestations", "dictDeductions", "dictForfaits", "dict_transports"):
                assert getattr(a.grille, champ) == getattr(b.grille, champ), champ
            assert (a.grille.GetNumberRows(), a.grille.GetNumberCols()) == (b.grille.GetNumberRows(), b.grille.GetNumberCols())
            assert a.dictInfosIndividu == b.dictInfosIndividu
            jour = arguments["periode"][0]
            assert a.GetCase(1, jour) is not None
            assert b.GetCase(1, jour) is not None
            assert a.GetCase(1, jour).ouvert == b.GetCase(1, jour).ouvert
        assert avant == list(base.db.connexion.iterdump()), "Ecriture inattendue pendant la lecture"
    frame.Destroy()
    assert not _garde_reseau.TENTATIVES
    print("UI432_SQLITE_PASS", flush=True)


class ReactiviteWindowsTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Boucle native Windows requise")
    def test_contre_epreuve_lecture_unique_lente_reste_visible_au_diagnostic(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--lente"],
                           cwd=ROOT / "noethys", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=25,
                           env={**os.environ, "NOETHYS_SL_UI_DIAG": "1"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ligne = next(l for l in p.stdout.splitlines() if l.startswith("UI432_RESULT "))
        m = json.loads(ligne.split(" ", 1)[1])
        print("UI432_LIMITE " + json.dumps(m), flush=True)
        self.assertGreater(m["retard_max_ms"], 3000)
        etape = next((l for l in p.stdout.splitlines() if "etape=grille.activites" in l), None)
        self.assertIsNotNone(etape, p.stdout)
        self.assertGreater(int(re.search(r"duree_ms=(\d+)", etape).group(1)), 3000)
        blocages = [x for x in p.stdout.splitlines() if "evenement=blocage_thread" in x]
        self.assertTrue(blocages, p.stdout)
        self.assertTrue(all("point=" in x and "C:" not in x and "Users" not in x for x in blocages))
        self.assertTrue(m["maximise"])
        self.assertTrue(m["geometrie_identique"])
        self.assertTrue(m["owner_modal_ok"])
    @unittest.skipUnless(sys.platform == "win32", "wx reel requis")
    def test_grille_reelle_sqlite_identique_et_sans_ecriture(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--sqlite"],
                           cwd=ROOT / "noethys", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("UI432_SQLITE_PASS", p.stdout)
        self.assertNotIn("Requete SQL incorrecte", p.stdout)
    @unittest.skipUnless(sys.platform == "win32", "Boucle native Windows requise")
    def test_exception_ferme_connexion_et_reactive_parent(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--pannes"],
                           cwd=ROOT / "noethys", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("UI432_PANNES_PASS", p.stdout)
    @unittest.skipUnless(sys.platform == "win32", "Boucle native Windows requise")
    def test_contre_epreuve_etapes_gui_et_proprietaires(self):
        mesures = []
        for argument in ("--baseline", "--corrige"):
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), argument],
                               cwd=ROOT / "noethys", capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            ligne = next(l for l in p.stdout.splitlines() if l.startswith("UI432_RESULT "))
            m = json.loads(ligne.split(" ", 1)[1])
            mesures.append(m)
            self.assertTrue(m["maximise"])
            self.assertTrue(m["geometrie_identique"])
            self.assertTrue(m["parent_reactive"])
            self.assertEqual(m["reseau"], 0)
        avant, apres = mesures
        print("UI432_COMPARE " + json.dumps(mesures), flush=True)
        self.assertGreater(avant["retard_max_ms"], 3000)
        self.assertLess(apres["retard_max_ms"], 800)
        self.assertGreater(apres["battements"], avant["battements"])
        self.assertEqual(avant["appels"], apres["appels"])
        self.assertTrue(apres["owner_modal_ok"])


if __name__ == "__main__":
    if "--sqlite" in sys.argv:
        grille_sqlite()
    elif "--pannes" in sys.argv:
        pannes()
    elif any(a in sys.argv for a in ("--baseline", "--corrige", "--inspect", "--lente")):
        scenario("--baseline" in sys.argv, "--inspect" in sys.argv, "--lente" in sys.argv)
    else:
        unittest.main()
