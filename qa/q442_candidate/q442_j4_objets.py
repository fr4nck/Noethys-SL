"""Test-only Q442 compatibility bridge; wx is never imported in this bench."""
from pathlib import Path
import sys
import types
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'noethys'))
modele = types.ModuleType('Utils.UTILS_Stats_modeles')
class _Tableau:
    def __init__(self):
        self.dictParametres = {}
        self.colonnes = []
        self.lignes = []
        self.totaux = []
class _Graphe:
    def __init__(self):
        self.dictParametres = {}
modele.Tableau = _Tableau
modele.Graphe = _Graphe
sys.modules.setdefault('Utils.UTILS_Stats_modeles', modele)
from Utils.UTILS_Stats_qf_objets import *
