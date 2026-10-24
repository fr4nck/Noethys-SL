# -*- coding: utf-8 -*-
"""Diagnostic de démarrage, inactif par défaut.

Activé uniquement si la variable d'environnement NOETHYS_DIAGNOSTIC_DEMARRAGE
désigne un fichier journal (recette ou CI). Il consigne alors, sans rien
modifier au comportement de Noethys :
- l'identité du processus (exécutable, mode figé, répertoire courant) ;
- chaque module importé, horodaté : le dernier import consigné avant un
  blocage désigne le module en cours de chargement ;
- les étapes du démarrage (main, profil utilisateur, initialisation wx) ;
- les exceptions non interceptées, y compris dans les threads, qu'un
  exécutable fenêtré n'affiche que dans une boîte de dialogue invisible ;
- la pile de tous les threads, périodiquement (faulthandler), pour situer
  un blocage sans exception.

Ce module n'importe que la bibliothèque standard : il doit pouvoir être
chargé avant tout autre module de Noethys.
"""
import faulthandler
import os
import sys
import threading
import time
import traceback

VARIABLE = "NOETHYS_DIAGNOSTIC_DEMARRAGE"
VARIABLE_DELAI = "NOETHYS_DIAGNOSTIC_DELAI_PILES"
DELAI_PILES_DEFAUT = 20

_fichier = None
_debut = None
_hooks_origine = None
_verrou = threading.Lock()


def Actif():
    return _fichier is not None


def _ecrire(texte):
    if _fichier is None:
        return
    with _verrou:
        try:
            _fichier.write("%9.3f %s\n" % (time.time() - _debut, texte))
            _fichier.flush()
        except Exception:
            pass


class _JournalImports(object):
    """Chercheur de modules qui consigne chaque import puis laisse faire les autres."""

    def find_spec(self, fullname, path=None, target=None):
        _ecrire("IMPORT %s" % fullname)
        return None

    def find_module(self, fullname, path=None):  # Python < 3.4
        _ecrire("IMPORT %s" % fullname)
        return None


def _excepthook(precedent):
    def hook(type_erreur, valeur, trace):
        _ecrire("EXCEPTION NON INTERCEPTEE\n" + "".join(traceback.format_exception(type_erreur, valeur, trace)))
        if precedent is not None:
            precedent(type_erreur, valeur, trace)
    return hook


def _threading_excepthook(precedent):
    def hook(args):
        _ecrire("EXCEPTION THREAD %s\n" % getattr(args.thread, "name", "?")
                + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
        if precedent is not None:
            precedent(args)
    return hook


def Activer(chemin, delai_piles=None):
    """Ouvre le journal et installe les sondes. Sans effet si déjà actif."""
    global _fichier, _debut, _hooks_origine
    if _fichier is not None:
        return False
    _hooks_origine = (sys.excepthook, getattr(threading, "excepthook", None))
    _debut = time.time()
    _fichier = open(chemin, "a", encoding="utf-8", buffering=1)
    _ecrire("DEBUT pid=%d executable=%r frozen=%r argv=%r cwd=%r python=%s"
            % (os.getpid(), sys.executable, getattr(sys, "frozen", False), sys.argv, os.getcwd(),
               sys.version.split()[0]))
    sys.meta_path.insert(0, _JournalImports())
    sys.excepthook = _excepthook(sys.excepthook)
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook(threading.excepthook)
    faulthandler.enable(file=_fichier, all_threads=True)
    if delai_piles is None:
        try:
            delai_piles = int(os.environ.get(VARIABLE_DELAI, DELAI_PILES_DEFAUT))
        except ValueError:
            delai_piles = DELAI_PILES_DEFAUT
    if delai_piles > 0:
        # Pile de tous les threads toutes les N secondes : un blocage reste visible.
        faulthandler.dump_traceback_later(delai_piles, repeat=True, file=_fichier)
    import atexit
    atexit.register(lambda: _ecrire("FIN_PROCESSUS"))
    return True


def ActiverDepuisEnvironnement():
    chemin = os.environ.get(VARIABLE, "").strip()
    if not chemin:
        return False
    try:
        return Activer(chemin)
    except Exception:
        return False


def Etape(nom, **infos):
    """Marque une étape du démarrage (aucun effet si le diagnostic est inactif)."""
    if _fichier is None:
        return
    details = " ".join("%s=%r" % (cle, infos[cle]) for cle in sorted(infos))
    _ecrire("ETAPE %s %s" % (nom, details))


def Profil(chemins_module, fichiers_module):
    """Consigne la résolution du profil : mode portable détecté ou profil Windows réel."""
    if _fichier is None:
        return
    try:
        portable = chemins_module.GetMainPath("Portable")
        infos = {"rep_courant": chemins_module.REP_COURANT, "portable": portable,
                 "portable_present": os.path.isdir(portable),
                 "rep_utilisateur": fichiers_module.GetRepUtilisateur()}
        try:
            import appdirs
            infos["appdirs_user_config"] = appdirs.user_config_dir(appname=None, appauthor=False, roaming=True)
        except Exception as erreur:
            infos["appdirs_user_config"] = "indisponible : %s" % erreur
        Etape("profil", **infos)
    except Exception:
        _ecrire("PROFIL ILLISIBLE\n" + traceback.format_exc())


def Desactiver():
    """Pour les tests : retire les sondes et ferme le journal."""
    global _fichier
    if _fichier is None:
        return
    faulthandler.cancel_dump_traceback_later()
    faulthandler.disable()
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _JournalImports)]
    sys.excepthook = _hooks_origine[0]
    if _hooks_origine[1] is not None:
        threading.excepthook = _hooks_origine[1]
    fichier, _fichier = _fichier, None
    fichier.close()
