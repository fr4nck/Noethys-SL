# -*- coding: utf-8 -*-
"""AFAS V2 -- entrée de menu, séparation moteur/interface et recette du dialogue.

Les contrôles statiques s'exécutent sans wx. La recette du dialogue exige
wxPython réel (CI Windows) : base SQLite fictive, aucune boîte modale
(messages et confirmations interceptés).
"""
import ast
import datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
NOETHYS = RACINE / "noethys"
for chemin in (NOETHYS, RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))


def _imports(fichier):
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.add(noeud.module.split(".")[0])
            noms.update("%s.%s" % (noeud.module, alias.name) for alias in noeud.names)
    return noms


class StructureTests(unittest.TestCase):
    def test_entree_autonome_du_menu_consommations(self):
        source = (NOETHYS / "Noethys.py").read_text(encoding="utf-8")
        debut = source.index('"code" : "menu_consommations"')
        fin = source.index('"code" : "menu_facturation"')
        self.assertIn('"code" : "declarations_afas"', source[debut:fin])
        arbre = ast.parse(source)
        methode = next(n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == "On_conso_declarations_afas")
        texte = ast.unparse(methode)
        self.assertIn("DLG_AFAS2_Declarations", texte)
        self.assertNotIn("DLG_Etat_global", texte)

    def test_moteur_sans_wx_ni_etat_global(self):
        for fichier in sorted((NOETHYS / "Utils").glob("UTILS_AFAS2_*.py")):
            with self.subTest(fichier=fichier.name):
                imports = _imports(fichier)
                self.assertNotIn("wx", imports)
                self.assertFalse(any(nom.startswith(("Dlg", "Ctrl")) for nom in imports))

    def test_dialogue_independant_de_l_etat_global(self):
        imports = _imports(NOETHYS / "Dlg" / "DLG_AFAS2_Declarations.py")
        self.assertFalse(any("Etat_global" in nom or "AFAS_Actualisation" in nom for nom in imports))

    def test_bouton_afas_v1_non_reactive(self):
        # Le module V2 n'ajoute rien à l'état global (sur wx, le bouton V1 reste masqué).
        source = (NOETHYS / "Dlg" / "DLG_Etat_global.py").read_text(encoding="utf-8")
        self.assertNotIn("AFAS2", source)


try:
    import wx
    WX_REEL = not getattr(wx, "VERSION_STRING", "").endswith("-stub") and hasattr(wx, "App")
except ImportError:  # pragma: no cover
    wx = None
    WX_REEL = False


@unittest.skipUnless(WX_REEL, "wxPython réel requis (recette exécutée sur la CI Windows)")
class DialogueTests(unittest.TestCase):
    def setUp(self):
        import _garde_reseau  # noqa: F401
        from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
        from Data import DATA_Tables as Tables
        from Utils import UTILS_AFAS2_Referentiel as R
        self.app = wx.GetApp() or wx.App(False)
        self.base = BaseTest()
        for table in ("ouvertures", "factures", "aeeh_periodes", "vacances", "profils", "profils_parametres"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        b = self.base
        b.inserer("activites", ["IDactivite", "nom"], [(1, "ALSH")])
        b.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], [(11, 1, "Bais +6 ans"), (12, 1, "Bais -6 ans"), (15, 1, "Minicamps 6/8")])
        b.inserer("unites", ["IDunite", "IDactivite", "nom", "type", "heure_debut", "heure_fin"],
                  [(101, 1, "Matin", "Unitaire", "07:30", "08:45"), (201, 1, "Journée", "Unitaire", "08:30", "17:30")])
        b.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], [(1, "FICTIF", "Lea", 1)])
        vacances = []
        for annee in (2025, 2026, 2027):
            vacances += [("Eté", "%d-07-05" % annee, "%d-08-31" % annee), ("Toussaint", "%d-10-18" % annee, "%d-11-02" % annee)]
        b.inserer("vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
                  [(i, nom, int(d[:4]), d, f) for i, (nom, d, f) in enumerate(vacances, 1)])
        b.inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], [(1, 101, 11, "2026-03-03"), (1, 101, 11, "2026-03-04")])
        b.inserer("consommations", ["IDconso", "IDindividu", "date", "IDunite", "IDactivite", "IDgroupe", "heure_debut", "heure_fin", "etat"],
                  [(1, 1, "2026-03-03", 101, 1, 11, "07:40", "08:30", "present"), (2, 1, "2026-03-04", 101, 1, 11, "07:40", "08:30", "xyz")])
        self.redirection = RedirectionGestionDB(b.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(b.fermer)
        R.EnregistrerReferentiel({"format": 1, "moutiers_rattachement_confirme": False, "sejours": [], "sites": {
            "Bais +6 ans": {"IDactivite": 1, "IDgroupe": 11, "nom_groupe": "Bais +6 ans", "equipement": "BAIS"},
            "Minicamps 6/8": {"IDactivite": 1, "IDgroupe": 15, "nom_groupe": "Minicamps 6/8", "equipement": "BAIS"}}})
        from Dlg import DLG_AFAS2_Declarations
        self.module = DLG_AFAS2_Declarations
        self.dlg = DLG_AFAS2_Declarations.Dialog(None)
        self.messages = []
        self.dlg.Message = lambda texte, *a, **k: self.messages.append(texte)
        self.dlg.Erreur = lambda erreur: self.messages.append("ERREUR " + str(erreur))
        self.dlg.Confirmer = lambda texte: True
        self.addCleanup(self.dlg.Destroy)

    def configurer(self):
        d = self.dlg
        d.ctrl_nom.SetValue("Bais périscolaire")
        d.ctrl_mode.SetSelection(0)
        d.OnContexte(None)
        sites = [d.ctrl_sites.GetString(i) for i in range(d.ctrl_sites.GetCount())]
        self.assertNotIn("Minicamps 6/8", sites)  # aucun minicamp en périscolaire
        d.ctrl_sites.Check(sites.index("Bais +6 ans"), True)
        d.unites_classees = {101: "accueil", 201: "journee"}

    def test_parcours_complet(self):
        d = self.dlg
        self.configurer()
        self.assertTrue(d.OnEnregistrer(None), self.messages)
        self.assertEqual(d.ctrl_preset.GetStringSelection(), "Bais périscolaire")
        d.ctrl_annee.SetValue(2026)
        d.ctrl_phase.SetSelection(3)
        rapport = d.OnCalculer(None)
        self.assertIsNotNone(rapport, self.messages)
        self.assertEqual(d.ctrl_resultats.GetItemCount(), len(rapport["indicateurs"]))
        self.assertEqual(d.ctrl_anomalies.GetItemCount(), 1)  # statut inconnu
        self.assertFalse(rapport["validable"])
        self.assertIsNone(d.OnExporterDeclaration(None, dossier=tempfile.gettempdir()))
        with tempfile.TemporaryDirectory() as dossier:
            chemins = d.OnExporterControle(None, dossier=dossier)
            self.assertTrue(os.path.exists(chemins["anomalies"]))
        self.assertTrue(d.OnDupliquer(None, nom="Bais périscolaire copie"))
        self.assertTrue(d.OnRenommer(None, nom="Bais périscolaire ter"))
        self.assertTrue(d.OnSupprimer(None))
        self.assertEqual(d.ctrl_preset.GetCount(), 2)  # (nouveau preset) + l'original

    def test_changement_de_mode_retire_les_sites_incompatibles(self):
        d = self.dlg
        d.ctrl_mode.SetSelection(1)
        d.OnContexte(None)
        sites = [d.ctrl_sites.GetString(i) for i in range(d.ctrl_sites.GetCount())]
        d.ctrl_sites.Check(sites.index("Minicamps 6/8"), True)
        d.ctrl_mode.SetSelection(0)
        d.OnContexte(None)
        self.assertEqual(d.SitesCoches(), [])

    def test_preset_rouvert_identique_apres_fermeture(self):
        self.configurer()
        self.assertTrue(self.dlg.OnEnregistrer(None))
        attendu = self.dlg.LirePreset()
        autre = self.module.Dialog(None)
        self.addCleanup(autre.Destroy)
        autre.ctrl_preset.SetSelection(1)
        autre.OnChoixPreset(None)
        self.assertEqual(autre.LirePreset(), attendu)

    def test_annee_et_phase_jamais_dans_le_preset(self):
        self.configurer()
        self.dlg.ctrl_annee.SetValue(2027)
        self.dlg.ctrl_phase.SetSelection(1)
        preset = self.dlg.LirePreset()
        self.assertNotIn("2027", str(preset))
        self.assertNotIn("juin", str(preset))


if __name__ == "__main__":
    unittest.main()
