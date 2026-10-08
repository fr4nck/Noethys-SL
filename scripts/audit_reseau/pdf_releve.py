"""Génère un vrai PDF avec le moteur d'impression, sur une base de test synthétique.

Usage : CODE_ROOT=<racine du dépôt à tester> [SHIM_SBV=1] xvfb-run -a python3 pdf_releve.py <sortie.pdf>
SHIM_SBV=1 fournit un symbole inerte ShowBoundaryValue au code RC2 pour qu'il s'importe sous ReportLab >= 4."""
import os, sys, traceback, datetime
sys.path.insert(0, os.environ["CODE_ROOT"] + "/noethys"); sys.path.insert(0, os.environ["CODE_ROOT"] + "/tests")
if os.environ.get("SHIM_SBV"):
    import reportlab.platypus.frames as _fr
    if not hasattr(_fr, "ShowBoundaryValue"):
        _fr.ShowBoundaryValue = type("ShowBoundaryValue", (), {}); print("SHIM ShowBoundaryValue actif (code RC2)")
import wx; app = wx.App(False)
import _fixtures_noethys_db as F
import reportlab; print("reportlab", reportlab.Version)
from Data import DATA_Tables as T
base = F.creer_base_ecole_simple()
for t in ("comptes_payeurs", "ventilation", "factures", "tarifs", "noms_tarifs", "categories_tarifs", "reglements", "payeurs", "modes_reglements", "emetteurs", "depots", "titulaires_helios", "parametres", "rappels", "types_pieces", "pieces", "cotisations", "types_cotisations", "unites_cotisations", "caisses", "regimes", "factures_prefixes", "villes", "secteurs", "civilites", "categories_travail", "types_sieste", "scolarite", "ecoles", "classes", "niveaux_scolaires", "organisateur_logo"):
    try: base.db.CreationTable(t, dicoDB=T.DB_DATA)
    except Exception as e: pass
base.db.Commit()
F.RedirectionGestionDB(base.chemin).__enter__()
print("modules:", end=" ")
from Dlg import DLG_Releve_prestations as D
print(D.__file__.replace("/home/user/", "").replace(os.environ["CODE_ROOT"] + "/", ""))
try:
    imp = D.Impression(IDfamille=2, listePeriodes=[{"selection": True, "type": "prestations", "periode": {"date_debut": datetime.date(2026, 1, 1), "date_fin": datetime.date(2026, 12, 31), "label": u"Année 2026"}, "options": {"impayes": False, "regroupement": None, "conso": True}}], dictOptionsImpression={"couleur": False})
    imp.CreationPDF(nomDoc=sys.argv[1], afficherDoc=False)
    print("RELEVE OK", os.path.getsize(sys.argv[1]), "octets")
except Exception:
    traceback.print_exc(); sys.exit(1)
