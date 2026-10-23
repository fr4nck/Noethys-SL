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
        for annee in (2025, 2026, 2027):  # calendrier fictif complet (cinq périodes par année scolaire)
            vacances += [("Hiver", "%d-02-14" % annee, "%d-02-28" % annee), ("Printemps", "%d-04-11" % annee, "%d-04-26" % annee),
                         ("Eté", "%d-07-05" % annee, "%d-08-31" % annee), ("Toussaint", "%d-10-18" % annee, "%d-11-02" % annee),
                         ("Noël", "%d-12-20" % annee, "%d-01-04" % (annee + 1))]
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
        d.plages_declarees = {101: "07:30-08:45", 201: "08:30-17:30"}

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

    def test_statuts_proposes_admissibles_uniquement(self):
        d = self.dlg
        self.assertEqual([d.ctrl_realise.GetString(i) for i in range(d.ctrl_realise.GetCount())], ["Présent"])
        self.assertNotIn("Pointage en attente", [d.ctrl_facture.GetString(i) for i in range(d.ctrl_facture.GetCount())])
        self.assertFalse(hasattr(d, "ctrl_samedis"))  # plus de choix permanent des samedis avec école

    def test_plage_non_declaree_empeche_l_enregistrement(self):
        self.configurer()
        self.dlg.plages_declarees = {101: "07:30-08:45"}
        self.assertFalse(self.dlg.OnEnregistrer(None))
        self.assertTrue(any("plage horaire réellement organisée" in m for m in self.messages))

    def test_classement_des_unites_et_reprise_des_horaires(self):
        from Utils import UTILS_AFAS2_Donnees as Donnees
        unites = Donnees.ChargerUnites([1])
        dlg = self.module.DialogUnites(self.dlg, unites, {101: "accueil", 201: "annexe"}, {})
        self.addCleanup(dlg.Destroy)
        dlg.OnReprendre(None)
        self.assertEqual(dlg.GetClassement(), ({101: "accueil", 201: "annexe"}, {101: "07:30-08:45"}))

    def test_referentiel_samedis_justificatifs_regularisations(self):
        from Utils import UTILS_AFAS2_Referentiel as R
        dlg = self.module.DialogReferentiel(self.dlg, R.ChargerReferentiel())
        self.addCleanup(dlg.Destroy)
        dlg.ctrl_samedis.SetValue("2025 : aucun\n2026 : 2026-11-28")
        dlg.ctrl_justificatifs["Minicamps 6/8"].SetValue("Déclaration fictive n° 1")
        dlg.OnAjouterRegularisation(None, saisie=("9001", "", "Remboursement fictif"))
        ref = dlg.LireReferentiel()
        self.assertEqual(ref["samedis_avec_ecole"], {"2025": [], "2026": ["2026-11-28"]})
        self.assertEqual(ref["justificatifs"], {"Minicamps 6/8": "Déclaration fictive n° 1"})
        self.assertEqual(ref["regularisations"]["9001"]["consommations_annulees"], [])
        R.EnregistrerReferentiel(ref)
        self.assertEqual(R.ChargerReferentiel()["samedis_avec_ecole"]["2026"], ["2026-11-28"])

    def test_preset_format_1_migre_dans_le_dialogue(self):
        import json
        from Utils import UTILS_AFAS2_Presets as P
        from Utils import UTILS_AFAS2_Referentiel as R
        self.configurer()
        self.assertTrue(self.dlg.OnEnregistrer(None))
        ancien = self.dlg.LirePreset()
        ancien.update(format=1, criteres_periodes={"samedis_avec_ecole": True})
        del ancien["plages_declarees"]
        R.EcrireJSONProfil(self.dlg.IDprofil, P.NOM_PARAMETRE, ancien)
        autre = self.module.Dialog(None)
        self.addCleanup(autre.Destroy)
        messages = []
        autre.Message = lambda texte, *a, **k: messages.append(texte)
        autre.Erreur = lambda erreur: messages.append("ERREUR " + str(erreur))
        self.assertFalse(autre.ChargerPreset(self.dlg.IDprofil))
        self.assertTrue(any("samedis avec école" in m for m in messages), messages)
        autre.plages_declarees = {101: "07:30-08:45", 201: "08:30-17:30"}
        self.assertTrue(autre.OnEnregistrer(None), messages)
        self.assertEqual(P.ChargerPreset(autre.IDprofil)["format"], 2)
        self.assertNotIn("samedis_avec_ecole", json.dumps(P.ChargerPreset(autre.IDprofil)))

    def test_annee_et_phase_jamais_dans_le_preset(self):
        self.configurer()
        self.dlg.ctrl_annee.SetValue(2027)
        self.dlg.ctrl_phase.SetSelection(1)
        preset = self.dlg.LirePreset()
        self.assertNotIn("2027", str(preset))
        self.assertNotIn("juin", str(preset))


if __name__ == "__main__":
    unittest.main()
