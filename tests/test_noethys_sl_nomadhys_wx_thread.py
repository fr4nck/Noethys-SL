# -*- coding: utf-8 -*-
"""Contrats de thread wx du traitement d'import Nomadhys Noethys SL (#377)."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import queue
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Synchronisation_donnees.py"
DELAI = 10


def arbre_source():
    source = SOURCE.read_text(encoding="utf-8")
    return source, ast.parse(source)


def noeud(nom, conteneur=None):
    source, arbre = arbre_source()
    corps = arbre.body
    if conteneur is not None:
        corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == conteneur).body
    return source, next(
        n for n in corps
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == nom
    )


def segment(nom, conteneur=None):
    source, n = noeud(nom, conteneur)
    return ast.get_source_segment(source, n)


def racine_attribut(expr):
    """Retourne la chaîne 'self.parent.x.y' d'une expression attribut."""
    morceaux = []
    while isinstance(expr, ast.Attribute):
        morceaux.append(expr.attr)
        expr = expr.value
    if isinstance(expr, ast.Name):
        morceaux.append(expr.id)
        return ".".join(reversed(morceaux))
    return None


class FauxThreadUI(object):
    """Boucle d'évènements minimale jouant le rôle du thread wx."""

    def __init__(self):
        self.file = queue.Queue()
        self.thread = threading.Thread(target=self._boucle, daemon=True)
        self.thread.start()

    def _boucle(self):
        while True:
            fonction = self.file.get()
            if fonction is None:
                return
            fonction()

    def CallAfter(self, fonction, *args, **kwds):
        self.file.put(lambda: fonction(*args, **kwds))

    def IsMainThread(self):
        return threading.current_thread() is self.thread

    def executer(self, fonction):
        """Exécute fonction sur le thread UI et attend la fin (pour les tests)."""
        fini = threading.Event()
        retour = {}

        def appel():
            try:
                retour["valeur"] = fonction()
            finally:
                fini.set()

        self.CallAfter(appel)
        assert fini.wait(DELAI), "thread UI bloqué"
        return retour.get("valeur")

    def arreter(self):
        self.file.put(None)
        self.thread.join(DELAI)


def charger(noms, faux_wx, extra=None):
    """Exécute les définitions de module demandées avec un faux wx."""
    source, arbre = arbre_source()
    espace = {
        "wx": faux_wx,
        "threading": threading,
        "Thread": threading.Thread,
        "_": lambda texte: texte,
        "time": types.SimpleNamespace(sleep=lambda duree: None),
    }
    espace.update(extra or {})
    for n in arbre.body:
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in noms:
            exec(compile(ast.Module(body=[n], type_ignores=[]), str(SOURCE), "exec"), espace)
    return espace


class SourceContractTests(unittest.TestCase):
    def test_run_n_appelle_plus_aucun_widget_directement(self):
        _, run = noeud("run", "Traitement")
        for n in ast.walk(run):
            if isinstance(n, ast.Call):
                racine = racine_attribut(n.func) or ""
                self.assertFalse(
                    racine.startswith("self.parent."),
                    "appel wx direct depuis le worker : %s" % racine,
                )
            if isinstance(n, ast.Attribute):
                racine = racine_attribut(n) or ""
                self.assertFalse(racine.startswith("wx."), "wx utilisé dans le worker : %s" % racine)

    def test_run_ne_reference_plus_les_widgets(self):
        src = segment("run", "Traitement")
        for interdit in ("label_intro", "ctrl_gauge", "ctrl_grille", "self.parent.parent",
                         "MessageDialog", "DLG_Messagebox", "ShowModal", "wx.Yield"):
            self.assertNotIn(interdit, src)

    def test_run_passe_par_l_appel_synchrone(self):
        src = segment("run", "Traitement")
        for attendu in (
            "AppelSynchroneUI(self.parent.AfficherProgression, texteIntro, self.index+1)",
            'AppelSynchroneUI(self.parent.AppelGrille, "InitGrille"',
            'AppelSynchroneUI(self.parent.AppelGrille, "SaisieConso"',
            'AppelSynchroneUI(self.parent.AppelGrille, "SupprimeConso"',
            'AppelSynchroneUI(self.parent.AppelGrille, "Sauvegarde")',
            "AppelSynchroneUI(self.parent.Fermer, forcer=True)",
            "AppelSynchroneUI(AfficherBilan, nbre_tracks, listeAnomalies)",
        ):
            self.assertIn(attendu, src)

    def test_dialogues_de_fin_construits_hors_du_worker(self):
        bilan = segment("AfficherBilan")
        self.assertIn("wx.MessageDialog(None", bilan)
        self.assertIn("DLG_Messagebox.Dialog(None", bilan)
        self.assertEqual(bilan.count("dlg.Destroy()"), 2)

    def test_callbacks_ui_verifient_le_cycle_de_vie(self):
        self.assertIn("if not EstVivant(self):", segment("Fermer", "Dialog_Traitement"))
        self.assertIn("if not EstVivant(self):", segment("AfficherProgression", "Dialog_Traitement"))
        grille = segment("AppelGrille", "Dialog_Traitement")
        self.assertIn("if not EstVivant(self.ctrl_grille):", grille)
        self.assertIn("raise Abort", grille)

    def test_helper_sans_yield_ni_attente_active(self):
        src = segment("AppelSynchroneUI")
        self.assertIn("if wx.IsMainThread():", src)
        self.assertIn("wx.CallAfter(Executer)", src)
        self.assertIn("termine.wait(", src)
        self.assertNotIn("Yield", src)
        self.assertNotIn("time.sleep", src)


class AppelSynchroneUITests(unittest.TestCase):
    def setUp(self):
        self.ui = FauxThreadUI()
        self.espace = charger({"AppelSynchroneUI"}, self.ui)
        self.appel = self.espace["AppelSynchroneUI"]

    def tearDown(self):
        self.ui.arreter()

    def depuis_worker(self, fonction):
        retour = {}

        def cible():
            try:
                retour["valeur"] = fonction()
            except BaseException as err:
                retour["erreur"] = err

        worker = threading.Thread(target=cible)
        worker.start()
        worker.join(DELAI)
        self.assertFalse(worker.is_alive(), "worker bloqué")
        return retour

    def test_retourne_la_valeur_calculee_sur_le_thread_ui(self):
        threads = []

        def calcul(a, b=0):
            threads.append(threading.current_thread())
            return a + b

        retour = self.depuis_worker(lambda: self.appel(calcul, 2, b=3))
        self.assertEqual(retour, {"valeur": 5})
        self.assertEqual(threads, [self.ui.thread])

    def test_propage_l_exception_du_callback(self):
        erreur = ValueError("grille")

        def echec():
            raise erreur

        retour = self.depuis_worker(lambda: self.appel(echec))
        self.assertIs(retour["erreur"], erreur)

    def test_appel_depuis_le_thread_ui_sans_deadlock(self):
        threads = []

        def calcul():
            threads.append(threading.current_thread())
            return "direct"

        self.assertEqual(self.ui.executer(lambda: self.appel(calcul)), "direct")
        self.assertEqual(threads, [self.ui.thread])


class FauxTrack(object):
    def __init__(self, detail, categorie="consommation", action="ajouter", anomalie=False):
        self.detail = detail
        self.categorie = categorie
        self.action = action
        self.anomalie = anomalie
        self.etat = "reservation"
        self.IDindividu, self.IDfamille, self.IDactivite, self.IDunite = 1, 2, 3, 4
        self.date = "2026-09-23"
        self.heure_debut = self.heure_fin = None
        self.quantite = None
        self.statut = None


class FauxDialogTraitement(object):
    """Enregistre chaque opération UI et le thread qui l'exécute."""

    def __init__(self, ui, listeTracks, resultats=None, arret_apres=None, grille_detruite=False):
        self.ui = ui
        self.listeTracks = listeTracks
        self.resultats = resultats or {}
        self.arret_apres = arret_apres
        self.grille_detruite = grille_detruite
        self.journal = []
        self.traitement = None

    def _note(self, *evenement):
        assert threading.current_thread() is self.ui.thread, evenement
        self.journal.append(evenement)

    def AfficherProgression(self, texte=u"", valeur=None):
        self._note("progression", texte, valeur)

    def EcritLog(self, message=u""):
        self._note("log", message)

    def SetStatut(self, track=None, statut=None):
        self._note("statut", track.detail, statut)
        if self.arret_apres == track.detail:
            self.traitement.abort()

    def AppelGrille(self, nomMethode, **kwds):
        if self.grille_detruite:
            raise self.Abort
        self._note("grille", nomMethode)
        return self.resultats.get(nomMethode, True)

    def Fermer(self, forcer=False):
        self._note("fermer", forcer)


class OrdreMetierTests(unittest.TestCase):
    def setUp(self):
        self.ui = FauxThreadUI()
        self.bilans = []

        def AfficherBilan(nbre_tracks, listeAnomalies):
            assert threading.current_thread() is self.ui.thread
            self.bilans.append((nbre_tracks, list(listeAnomalies)))

        self.espace = charger({"Abort", "AppelSynchroneUI", "Traitement"}, self.ui,
                              {"AfficherBilan": AfficherBilan})

    def tearDown(self):
        self.ui.arreter()

    def lancer(self, parent):
        parent.Abort = self.espace["Abort"]
        traitement = self.espace["Traitement"](parent)
        parent.traitement = traitement
        traitement.start()
        traitement.join(DELAI)
        self.assertFalse(traitement.is_alive(), "traitement bloqué")
        return traitement

    def test_sequence_grille_puis_journal_et_fin_succes(self):
        tracks = [
            FauxTrack("A"),
            FauxTrack("B", action="supprimer"),
            FauxTrack("C", anomalie=u"anomalie C"),
        ]
        parent = FauxDialogTraitement(self.ui, tracks, resultats={"SupprimeConso": u"refus"})
        traitement = self.lancer(parent)

        self.assertTrue(traitement.succes)
        self.assertEqual(parent.journal, [
            ("progression", u"[1/3] A", 1),
            ("grille", "InitGrille"),
            ("grille", "SaisieConso"),
            ("grille", "Sauvegarde"),
            ("log", u"A -> ok"),
            ("statut", "A", "ok"),
            ("progression", u"[2/3] B", 2),
            ("grille", "InitGrille"),
            ("grille", "SupprimeConso"),
            ("log", u"B -> refus"),
            ("statut", "B", "erreur"),
            ("progression", u"[3/3] C", 3),
            ("log", u"anomalie C"),
            ("statut", "C", "erreur"),
            ("progression", u"Traitement terminé", None),
            ("log", u"Traitement terminé"),
            ("fermer", True),
        ])
        self.assertEqual(self.bilans, [(3, [u"B -> refus", u"anomalie C"])])

    def test_interruption_utilisateur_conservee(self):
        tracks = [FauxTrack("A"), FauxTrack("B")]
        parent = FauxDialogTraitement(self.ui, tracks, arret_apres="A")
        traitement = self.lancer(parent)

        self.assertFalse(traitement.succes)
        self.assertNotIn(("fermer", True), parent.journal)
        self.assertNotIn(("progression", u"[2/2] B", 2), parent.journal)
        self.assertEqual(parent.journal[-2:], [
            ("progression", u"Traitement interrompu par l'utilisateur", None),
            ("log", u"Traitement interrompu par l'utilisateur"),
        ])
        self.assertEqual(self.bilans, [(2, [])])

    def test_grille_detruite_interrompt_sans_sauvegarde(self):
        parent = FauxDialogTraitement(self.ui, [FauxTrack("A")], grille_detruite=True)
        traitement = self.lancer(parent)

        self.assertFalse(traitement.succes)
        self.assertNotIn(("grille", "Sauvegarde"), parent.journal)
        self.assertNotIn(("log", u"A -> ok"), parent.journal)
        self.assertEqual(parent.journal[-1], ("log", u"Traitement interrompu par l'utilisateur"))


if __name__ == "__main__":
    unittest.main()
