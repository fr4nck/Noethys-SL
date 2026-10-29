# -*- coding: utf-8 -*-
"""Lecture seule Noethys sur base de recette entierement fictive."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Frequentation_collectivites_db import (
    importer_journees, lister_unites, resoudre_villes,
)
from Utils.UTILS_Frequentation_collectivites import (
    ErreurFrequentation, calculer, modele,
)


class SqliteLectureSeule:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
          CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
          CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, IDactivite INTEGER, nom TEXT);
          CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, adresse_auto INTEGER, ville_resid TEXT);
          CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, IDindividu INTEGER,
             date TEXT, IDactivite INTEGER, IDunite INTEGER, etat TEXT);
          INSERT INTO activites VALUES (1, 'Accueil fictif');
          INSERT INTO unites VALUES (101,1,'Journee');
          INSERT INTO unites VALUES (102,1,'Repas');
          INSERT INTO individus VALUES (10,NULL,'Bais');
          INSERT INTO individus VALUES (20,10,NULL);
          INSERT INTO individus VALUES (30,NULL,'Moutiers');
          INSERT INTO individus VALUES (40,999,NULL);
          INSERT INTO consommations VALUES (1,20,'2026-03-02',1,101,'present');
          INSERT INTO consommations VALUES (2,20,'2026-03-02',1,102,'present');
          INSERT INTO consommations VALUES (3,20,'2026-11-02',1,101,'reservation');
          INSERT INTO consommations VALUES (4,20,'2026-03-03',1,101,'reservation');
          INSERT INTO consommations VALUES (5,30,'2026-03-02',1,101,'present');
          INSERT INTO consommations VALUES (6,40,'2026-03-02',1,101,'present');
        """)
        self.queries = []
        self.cursor = None

    def ExecuterReq(self, req):
        self.queries.append(req)
        self.cursor = self.db.execute(req)
        return True

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.db.close()


class LectureTests(unittest.TestCase):
    def setUp(self):
        self.db = SqliteLectureSeule()
        self.mapping = {"1:101": {"convention": "ALSH-2025-2026", "poids": "1"}}

    def tearDown(self):
        self.db.Close()

    def test_unites_avec_noms_et_volume_sans_pii(self):
        unites = lister_unites(2026, db=self.db)
        self.assertEqual([(u["IDunite"], u["nombre"]) for u in unites], [(101, 5), (102, 1)])
        self.assertNotIn("ville_resid", self.db.queries[-1])

    def test_importation_reel_prevision_reservation_passee_et_adresses_auto(self):
        r = importer_journees(2026, "2026-10-29", "Bais", self.mapping, db=self.db)
        self.assertEqual([(x["mois"], x["nature"], x["nombre"]) for x in r["jours"]],
                         [(3, "realise", "1"), (11, "prevision", "1")])
        self.assertEqual(r["exclusions"]["domiciles_indetermines"], 1)
        self.assertEqual(r["exclusions"]["hors_commune"], 1)
        self.assertEqual(r["exclusions"]["reservations_passees"], 1)
        self.assertFalse(r["domiciliation_historique_verifiee"])
        self.assertNotIn("IDindividu", str(r["jours"]))
        self.assertNotIn("commune_residence", str(r["jours"]))
        self.assertTrue(all(s.lstrip().upper().startswith("SELECT") for s in self.db.queries))

    def test_domiciliation_chaussee_vers_reference_et_cycle_refuse(self):
        villes = resoudre_villes({1:(None,"Bais"),2:(1,None),3:(4,None),4:(3,None),5:(99,None)})
        self.assertEqual(villes[2], "Bais")
        self.assertIsNone(villes[3])
        self.assertIsNone(villes[5])

    def test_mapping_impossible_avec_identifiant_sql_injecte(self):
        for mapping in [{"1:101 OR 1=1": self.mapping["1:101"]},
                        {"1:101": {"convention": "ALSH-2025-2026", "poids": "0.5"}},
                        {}]:
            with self.subTest(mapping=mapping), self.assertRaises(ErreurFrequentation):
                importer_journees(2026, "2026-10-29", "Bais", mapping, db=self.db)

    def test_pas_de_conversion_familles_vers_versement_mairie(self):
        r = importer_journees(2026, "2026-10-29", "Bais", self.mapping, db=self.db)
        d = modele("Bais", 2026, "2026-10-29")
        d["jours"] = r["jours"]
        d["controles"] = dict.fromkeys(d["controles"], True)
        for conv in d["conventions"]:
            conv["tarif_confirme"] = True
        d["import_noethys"] = {"domiciles_indetermines": 1,
              "perimetre_unites_confirme": True,
              "domiciliation_historique_verifiee": True}
        result = calculer(d)
        self.assertEqual(result["totaux"]["participation_reelle"], 1154)
        self.assertEqual(result["totaux"]["participation_prevue"], 1154)
        self.assertIsNone(result["totaux"]["solde_verifie"])
        self.assertIn("Domiciles non resolus", " ".join(result["alertes"]))

    def test_calcul_non_verifie_si_unites_incompletes(self):
        d = modele("Moutiers", 2026, "2026-10-29")
        d["jours"] = [{"id": "X", "convention": "ALSH-2025-2026", "mois": 3,
                       "nature": "realise", "nombre": "1", "justificatif": "recette"}]
        d["controles"] = dict.fromkeys(d["controles"], True)
        d["conventions"][0]["tarif_confirme"] = True
        d["import_noethys"] = {"domiciles_indetermines": 0,
              "perimetre_unites_confirme": False,
              "domiciliation_historique_verifiee": True}
        self.assertIsNone(calculer(d)["totaux"]["solde_verifie"])


if __name__ == "__main__":
    unittest.main()