# -*- coding: utf-8 -*-
"""AFAS V2 -- presets permanents (sans année ni phase) et leur persistance.

Validation testée sans base ; persistance testée sur une base SQLite
fictive, relue par un processus distinct pour prouver l'écriture sur disque.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

from Utils import UTILS_AFAS2_Presets as P  # noqa: E402


def preset(**kw):
    p = P.NouveauPreset("ALSH Bais périscolaire", "periscolaire", "BAIS", sites=["Bais +6 ans", "Bais -6 ans"],
                        unites={"101": "accueil", "104": "repas", "105": "garderie_matin"})
    p.update(kw)
    return p


class ValidationTests(unittest.TestCase):
    def test_preset_valide(self):
        self.assertEqual(P.ValiderPreset(preset())["sites"], ["Bais +6 ans", "Bais -6 ans"])

    def test_23_annee_et_phase_refusees_a_tous_les_niveaux(self):
        cas = [
            dict(annee=2026), dict(phase="reel"), dict(date_debut="2026-01-01"), dict(Year=2026),
            dict(criteres_periodes={"samedis_avec_ecole": False, "annee": 2026}),
            dict(criteres_periodes={"samedis_avec_ecole": False, "phase": "actualisation_juin"}),
            dict(choix_conventionnels={"inclure_repas_meridien": True, "inclure_garderie_caf": False, "exercice": 2026}),
            dict(nom="ALSH Bais 2026"), dict(nom="Bais actualisation de juin"), dict(nom="Bais prévisionnel"),
            dict(nom="Bais septembre"), dict(nom="Date limite"),
        ]
        for modif in cas:
            with self.subTest(modif=modif), self.assertRaises(P.PresetInvalide):
                P.ValiderPreset(preset(**modif))

    def test_unites_avec_identifiant_numerique_admises(self):
        # Un IDunite égal à 2026 n'est pas une année : c'est un identifiant.
        P.ValiderPreset(preset(unites={"2026": "accueil"}))

    def test_schema_ferme_et_types(self):
        cas = [dict(format=0), dict(preset_id="abc"), dict(version=0), dict(version=True), dict(activite="ALSH Ados"),
               dict(mode="Périscolaire"), dict(equipement="ADOS"), dict(sites=[]), dict(sites=["Bais +6 ans", "Bais +6 ans"]),
               dict(sites=["Minicamps 6/8"]), dict(sites=["Bais"]), dict(unites={}), dict(unites={"1": "garderie"}),
               dict(unites={"01": "accueil"}), dict(unites={"x": "accueil"}), dict(etats_realise=[]),
               dict(etats_facture=["refus"]), dict(criteres_periodes={"samedis_avec_ecole": "non"}),
               dict(choix_conventionnels={"inclure_repas_meridien": 1, "inclure_garderie_caf": False}),
               dict(champ_libre=1), dict(nom="")]
        for modif in cas:
            with self.subTest(modif=modif), self.assertRaises(P.PresetInvalide):
                P.ValiderPreset(preset(**modif))
        for corrompu in (None, [], "texte", {}):
            with self.subTest(corrompu=corrompu), self.assertRaises(P.PresetInvalide):
                P.ValiderPreset(corrompu)

    def test_27_perimetre_bais_la_guerche_melange_refuse(self):
        with self.assertRaisesRegex(P.PresetInvalide, "périmètres mélangés"):
            P.ValiderPreset(preset(sites=["Bais +6 ans", "La Guerche-de-Bretagne"]))

    def test_minicamp_admis_en_extrascolaire_seulement(self):
        P.ValiderPreset(preset(mode="extrascolaire", sites=["Bais +6 ans", "Minicamps 6/8"]))

    def test_changement_de_mode_retire_les_sites_incompatibles(self):
        self.assertEqual(P.AjusterSitesAuMode(["Bais +6 ans", "Minicamps 6/8"], "ALSH", "periscolaire"), ["Bais +6 ans"])

    def test_bais_plus_et_moins_simultanes(self):
        self.assertEqual(len(P.ValiderPreset(preset())["sites"]), 2)

    def test_duplication_identifiant_distinct_et_source(self):
        original = P.ValiderPreset(preset(version=7))
        copie = P.Dupliquer(original, "Copie Bais")
        self.assertNotEqual(copie["preset_id"], original["preset_id"])
        self.assertEqual((copie["source_preset_id"], copie["version"]), (original["preset_id"], 1))
        with self.assertRaises(P.PresetInvalide):
            P.ValiderPreset(dict(copie, source_preset_id=copie["preset_id"]))

    def test_empreinte_stable_et_sensible(self):
        p = P.ValiderPreset(preset())
        self.assertEqual(P.Empreinte(p), P.Empreinte(json.loads(json.dumps(p))))
        self.assertNotEqual(P.Empreinte(p), P.Empreinte(dict(p, sites=["Bais +6 ans"])))

    def test_validation_renvoie_une_copie(self):
        p = preset()
        copie = P.ValiderPreset(p)
        copie["sites"].append("Moutiers")
        self.assertEqual(len(p["sites"]), 2)


class MigrationTests(unittest.TestCase):
    def test_migration_prototype_lot4(self):
        ancien = {"profile_id": "alsh-peri", "name": "ALSH Bais periscolaire", "activity": "ALSH", "mode": "Périscolaire",
                  "sites": ["Bais +6 ans"], "included_units": [1], "excluded_units": [2], "garderie_units": [3],
                  "realised_states": ["Présent"], "caf_billed_states": ["Présent", "Absence injustifiée"],
                  "period_criteria": {"annee": 2026}, "rules": {"qualified": False}, "version": 3}
        brouillon, a_completer = P.MigrerAncienFormat(ancien)
        self.assertEqual(brouillon["unites"], {"1": "accueil", "2": "exclue", "3": "a_qualifier"})
        self.assertEqual(brouillon["etats_facture"], ["present", "absenti"])
        self.assertIn("équipement", a_completer)
        self.assertNotIn("annee", json.dumps(brouillon))
        with self.assertRaises(P.PresetInvalide):
            P.ValiderPreset(brouillon)  # équipement à compléter
        brouillon["equipement"] = "BAIS"
        brouillon["unites"]["3"] = "garderie_matin"
        P.ValiderPreset(brouillon)

    def test_migration_prototype_lot1(self):
        ancien = {"profile_id": "fixture-01", "activity": "ALSH", "mode": "Extrascolaire", "selected_sites": ["Moutiers"],
                  "included_units": [1], "excluded_units": [], "garderie_units": [], "admissible_states": ["Présent"],
                  "rules": {"qualified": True}, "config_version": 1}
        brouillon, a_completer = P.MigrerAncienFormat(ancien)
        self.assertTrue(any("facturé" in x for x in a_completer))

    def test_migration_refusee_pour_ados_ou_illisible(self):
        for ancien in ({"activity": "ALSH Ados", "mode": "Périscolaire"}, {"activity": "ALSH", "mode": "x"}, None):
            with self.subTest(ancien=ancien), self.assertRaises(P.PresetInvalide):
                P.MigrerAncienFormat(ancien)

    def test_nom_avec_annee_signale(self):
        brouillon, a_completer = P.MigrerAncienFormat({"name": "Bais 2026", "activity": "ALSH", "mode": "Périscolaire"})
        self.assertEqual(brouillon["nom"], "Preset migré")


class PersistanceTests(unittest.TestCase):
    def setUp(self):
        import _garde_reseau  # noqa: F401
        from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
        from Data import DATA_Tables as Tables
        self.base = BaseTest()
        for table in ("profils", "profils_parametres"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def lire_hors_processus(self):
        """Relecture du fichier SQLite par un autre interpréteur (redémarrage réel)."""
        code = ("import json, sqlite3, sys; c = sqlite3.connect(sys.argv[1]); "
                "print(json.dumps([t for (t,) in c.execute(\"SELECT parametre FROM profils_parametres p JOIN profils f ON f.IDprofil=p.IDprofil "
                "WHERE f.categorie='afas_v2_preset'\").fetchall()]))")
        sortie = subprocess.run([sys.executable, "-c", code, self.base.chemin], capture_output=True, text=True, check=True)
        return [json.loads(texte) for texte in json.loads(sortie.stdout)]

    def test_24_persistance_apres_redemarrage(self):
        IDprofil, enregistre = P.EnregistrerPreset(preset())
        relus = self.lire_hors_processus()
        self.assertEqual(relus, [enregistre])
        self.assertEqual(P.ChargerPreset(IDprofil), enregistre)

    def test_versionnement_et_un_seul_parametre(self):
        IDprofil, p = P.EnregistrerPreset(preset())
        p["sites"] = ["Bais +6 ans"]
        IDprofil, p2 = P.EnregistrerPreset(p, IDprofil)
        self.assertEqual(p2["version"], 2)
        self.base.db.ExecuterReq("SELECT nom FROM profils_parametres WHERE IDprofil=%d;" % IDprofil)
        self.assertEqual(self.base.db.ResultatReq(), [("preset_json",)])

    def test_unicite_identifiant_et_nom(self):
        IDprofil, p = P.EnregistrerPreset(preset())
        with self.assertRaisesRegex(P.PresetInvalide, "Identifiant"):
            P.EnregistrerPreset(dict(p, nom="Autre nom"))
        with self.assertRaisesRegex(P.PresetInvalide, "ce nom"):
            P.EnregistrerPreset(preset())

    def test_duplication_renommage_suppression(self):
        IDprofil, p = P.EnregistrerPreset(preset())
        IDcopie, copie = P.DupliquerPreset(IDprofil, "Bais périscolaire bis")
        self.assertEqual(copie["source_preset_id"], p["preset_id"])
        P.RenommerPreset(IDcopie, "Bais périscolaire ter")
        self.assertEqual(dict(P.ListerPresets())[IDcopie], "Bais périscolaire ter")
        P.SupprimerPreset(IDcopie)
        self.assertEqual([ID for ID, nom in P.ListerPresets()], [IDprofil])

    def test_chargement_corrompu_ou_residus_refuse(self):
        IDprofil, p = P.EnregistrerPreset(preset())
        self.base.db.ExecuterReq("UPDATE profils_parametres SET parametre='{\"format\":' WHERE IDprofil=%d;" % IDprofil)
        self.base.db.Commit()
        with self.assertRaises(ValueError):
            P.ChargerPreset(IDprofil)
        self.base.db.ExecuterReq("DELETE FROM profils_parametres WHERE IDprofil=%d;" % IDprofil)
        self.base.inserer("profils_parametres", ["nom", "parametre", "type_donnee", "IDprofil"],
                          [("preset_json", json.dumps(p), "texte", IDprofil), ("annee", "2026", "autre", IDprofil)])
        with self.assertRaisesRegex(ValueError, "résiduels"):
            P.ChargerPreset(IDprofil)

    def test_format_prototype_exige_migration(self):
        IDprofil, p = P.EnregistrerPreset(preset())
        self.base.db.ExecuterReq("UPDATE profils_parametres SET parametre='%s' WHERE IDprofil=%d;"
                                 % (json.dumps({"profile_id": "x", "activity": "ALSH"}), IDprofil))
        self.base.db.Commit()
        with self.assertRaisesRegex(P.PresetInvalide, "migration"):
            P.ChargerPreset(IDprofil)


if __name__ == "__main__":
    unittest.main()
