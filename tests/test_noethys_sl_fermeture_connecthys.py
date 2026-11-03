# -*- coding: utf-8 -*-
"""Lot A / #438 : fermeture Connecthys deterministe, sans wx ni reseau.

Les tests isolent les methodes reelles par AST : aucun profil, base,
serveur de production ou processus Noethys installe n'est utilise.
"""
import ast
import datetime
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "noethys" / "Ctrl" / "CTRL_Portail_serveur.py"
APP = ROOT / "noethys" / "Noethys.py"


def _extraire_classe_methode(chemin, classe, methode=None):
    source = chemin.read_text(encoding="utf-8")
    arbre = ast.parse(source, filename=str(chemin))
    cible = next(n for n in arbre.body
                 if isinstance(n, ast.ClassDef) and n.name == classe)
    if methode is None:
        noeud = cible
    else:
        noeud = next(n for n in cible.body
                     if isinstance(n, ast.FunctionDef) and n.name == methode)
    return compile(ast.fix_missing_locations(
        ast.Module(body=[noeud], type_ignores=[])), str(chemin), "exec")


def _serveur():
    ns = {"Thread": threading.Thread, "Event": threading.Event,
          "time": time, "datetime": datetime}
    exec(_extraire_classe_methode(CTRL, "Serveur"), ns)
    return ns["Serveur"]


class _Parent:
    def __init__(self, synchro_ouverture):
        self.last_synchro = None
        self.synchro_ouverture = synchro_ouverture
        self.delai = 60


class FermetureThreadTests(unittest.TestCase):
    def _demarrer_et_fermer(self, synchro_ouverture):
        parent = _Parent(synchro_ouverture)
        worker = _serveur()(parent)
        # Garde du banc : une regression de 30 s ne doit pas bloquer
        # tout le runner Windows lorsqu'un test echoue.
        worker.daemon = True
        worker.Start()
        try:
            limite = time.monotonic() + 2
            while parent.last_synchro is None and time.monotonic() < limite:
                time.sleep(0.01)
            self.assertIsNotNone(parent.last_synchro, "Le cycle n'a pas demarre")
        finally:
            worker.Stop()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive(), "Thread non arrete apres fermeture")
        self.assertFalse(worker.start_synchro, "Une synchro ne doit pas demarrer apres stop")

    def test_veille_interrompue_en_moins_de_deux_secondes(self):
        self._demarrer_et_fermer(False)

    def test_attente_initiale_30_s_interrompue_en_moins_de_deux_secondes(self):
        self._demarrer_et_fermer(True)


class FermetureApplicationTests(unittest.TestCase):
    def _quitter(self, resultat_sauvegarde):
        evenements = []
        ID_CANCEL = 510
        wx = SimpleNamespace(ID_CANCEL=ID_CANCEL)

        class FenetreFictive:
            userConfig = {"nomFichier": "base-fictive", "derniersFichiers": []}
            perspectives = []
            perspective_active = None
            autodeconnect_timer = SimpleNamespace(IsRunning=lambda: False)
            taskBarIcon = SimpleNamespace(
                Cacher=lambda: evenements.append("icone_cachee"),
                Detruire=lambda: evenements.append("icone_detruite"))
            ctrl_serveur_portail = SimpleNamespace(
                StopServeur=lambda: evenements.append("connecthys_arrete"))

            def IsSynchroConnecthys(self):
                return False

            def IsMaximized(self):
                return False

            def GetSize(self):
                return (1024, 768)

            def SauvegardePerspectiveActive(self):
                return None

            def SaveFichierConfig(self):
                evenements.append("config")

            def SauvegardeAutomatique(self):
                evenements.append("sauvegarde")
                return resultat_sauvegarde

        globals_fictifs = {
            "wx": wx,
            "_": lambda texte: texte,
            "UTILS_Historique": SimpleNamespace(InsertActions=lambda actions: None),
            "FonctionsPerso": SimpleNamespace(
                VideRepertoireTemp=lambda: None, VideRepertoireUpdates=lambda: None),
            "GestionDB": SimpleNamespace(AfficheConnexionOuvertes=lambda: None),
        }
        exec(_extraire_classe_methode(APP, "MainFrame", "Quitter"), globals_fictifs)
        resultat = globals_fictifs["Quitter"](FenetreFictive())
        return resultat, evenements

    def test_apres_sauvegarde_acceptee_connecthys_est_arrete(self):
        resultat, evenements = self._quitter(True)
        self.assertIs(resultat, True)
        self.assertLess(evenements.index("sauvegarde"),
                        evenements.index("connecthys_arrete"))
        self.assertLess(evenements.index("connecthys_arrete"),
                        evenements.index("icone_detruite"))

    def test_annulation_sauvegarde_ne_stoppe_pas_connecthys(self):
        resultat, evenements = self._quitter(510)
        self.assertIs(resultat, False)
        self.assertIn("sauvegarde", evenements)
        self.assertNotIn("connecthys_arrete", evenements)
        self.assertNotIn("icone_detruite", evenements)


if __name__ == "__main__":
    unittest.main()
