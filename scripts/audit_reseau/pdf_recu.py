"""Génère un vrai PDF avec le moteur d'impression, sur une base de test synthétique.

Usage : CODE_ROOT=<racine du dépôt à tester> [SHIM_SBV=1] xvfb-run -a python3 pdf_recu.py <sortie.pdf>
SHIM_SBV=1 fournit un symbole inerte ShowBoundaryValue au code RC2 pour qu'il s'importe sous ReportLab >= 4."""
import os
import sys, os, traceback
sys.path.insert(0, os.environ["CODE_ROOT"]+"/noethys"); sys.path.insert(0, os.environ["CODE_ROOT"] + "/tests")
if os.environ.get("SHIM_SBV"):
    import reportlab.platypus.frames as _fr
    if not hasattr(_fr, "ShowBoundaryValue"):
        _fr.ShowBoundaryValue = type("ShowBoundaryValue", (), {})
        print("SHIM ShowBoundaryValue actif (code RC2)")
import wx; app = wx.App(False)
import _fixtures_noethys_db as F
import reportlab; print("reportlab", reportlab.Version)
base = F.BaseTest()
F.RedirectionGestionDB(base.chemin).__enter__()
base.inserer("organisateur", ["IDorganisateur","nom","rue","cp","ville","tel","mail"], [(1,"Association Test","1 rue des Tests","00000","Testville","00","t@example.org")])
IDm = F.inserer_modele_document(base, "Modele recu test", "reglement", [
  {"nom":"Cadre principal","categorie":"special","champ":"cadre_principal","ordre":0,"x":13,"y":20,"largeur":182,"hauteur":250},
  {"nom":"Titre","categorie":"bloc_texte","ordre":1,"x":20,"y":270,"largeur":170,"texte":"RECU DE TEST {ORGANISATEUR_NOM}"}])
from Utils import UTILS_Impression_recu as R
import Utils; print('ORIGINE', R.__file__)
out = sys.argv[1]
valeurs = {"date_differe": None, "intro": True, "montant": 12.5, "nomEmetteur": u"Banque Test", "nomMode": u"Chèque",
           "nomPayeur": u"DUPUIS Jean", "numPiece": u"123456", "{DATE_DIFFERE}": u"", "prestations": [], "date": "2026-10-01",
           "IDreglement": 1, "texte_introduction": u"intro", "afficher_intro": True, "afficher_prestations": False}
try:
    R.Impression(dictValeurs=valeurs, IDmodele=IDm, nomDoc=out, afficherDoc=False)
    print("RECU OK", os.path.getsize(out), "octets")
except Exception:
    traceback.print_exc(); sys.exit(1)
