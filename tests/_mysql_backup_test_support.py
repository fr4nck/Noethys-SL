"""Charger le moteur pur dans un isolat ; jamais wx/GestionDB/Config."""
import importlib.util
import itertools
from pathlib import Path
import types


def moteur(env=None):
    chemin = Path(__file__).resolve().parents[1] / "noethys/Utils/UTILS_MySQL_backup.py"
    spec = importlib.util.spec_from_file_location("moteur_backup_isole", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if env:
        module.subprocess = env["subprocess"]
        module.time = env["time"]
    return module


def horloge_repetable(instants):
    # Le bilan mesure aussi la durée après la sortie du processus.
    valeurs = list(instants)
    iterator = itertools.chain(valeurs, itertools.repeat(valeurs[-1]))
    return types.SimpleNamespace(monotonic=lambda: next(iterator))
