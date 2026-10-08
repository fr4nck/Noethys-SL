"""Génère un vrai PDF avec le moteur d'impression, sur une base de test synthétique.

Usage : CODE_ROOT=<racine du dépôt à tester> [SHIM_SBV=1] xvfb-run -a python3 pdf_cotisation.py <sortie.pdf>
SHIM_SBV=1 fournit un symbole inerte ShowBoundaryValue au code RC2 pour qu'il s'importe sous ReportLab >= 4."""
import os, sys, traceback
sys.path.insert(0, os.environ["CODE_ROOT"] + "/noethys"); sys.path.insert(0, os.environ["CODE_ROOT"] + "/tests")
if os.environ.get("SHIM_SBV"):
    import reportlab.platypus.frames as _fr
    if not hasattr(_fr, "ShowBoundaryValue"):
        _fr.ShowBoundaryValue = type("ShowBoundaryValue", (), {})
        print("SHIM ShowBoundaryValue actif (code RC2)")
import wx; app = wx.App(False)
import _fixtures_noethys_db as F
import reportlab; print("reportlab", reportlab.Version)
base = F.BaseTest(); F.RedirectionGestionDB(base.chemin).__enter__()
base.inserer("organisateur", ["IDorganisateur","nom","rue","cp","ville","tel","mail"], [(1,"Association Test","1 rue des Tests","00000","Testville","00","t@example.org")])
IDm = F.inserer_modele_document(base, "Modele cotisation test", "cotisation", [
  {"nom":"Cadre principal","categorie":"special","champ":"cadre_principal","ordre":0,"x":13,"y":20,"largeur":182,"hauteur":250},
  {"nom":"Titre","categorie":"bloc_texte","ordre":1,"x":20,"y":270,"largeur":170,"texte":"COTISATION {FAMILLE_NOM} - {ORGANISATEUR_NOM}"}])
from Utils import UTILS_Impression_cotisation as C
import Utils; print('ORIGINE', C.__file__)
valeurs = {7: {"select": True, "{FAMILLE_NOM}": u"DUPUIS Jean", "{ORGANISATEUR_NOM}": u"Association Test"},
           8: {"select": True, "{FAMILLE_NOM}": u"MARTIN Léa", "{ORGANISATEUR_NOM}": u"Association Test"}}
try:
    C.Impression(dictValeurs=valeurs, dictOptions={}, IDmodele=IDm, ouverture=False, nomFichier=sys.argv[1])
    print("COTISATION OK", os.path.getsize(sys.argv[1]), "octets")
except Exception:
    traceback.print_exc(); sys.exit(1)
