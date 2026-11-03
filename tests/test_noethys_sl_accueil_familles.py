# -*- coding: utf-8 -*-
"""Lot C : deux fiches famille, données de test jetables SQLite."""
import sqlite3
import unittest
from datetime import date
from Utils import UTILS_Accueil_familles as F


class DBFictive:
    isNetwork = False
    echec = 0
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.conn.executescript("""
            CREATE TABLE familles(IDfamille INTEGER PRIMARY KEY,
                 IDcaisse INTEGER, num_allocataire TEXT);
            CREATE TABLE regimes(IDregime INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE caisses(IDcaisse INTEGER PRIMARY KEY,
                 nom TEXT, IDregime INTEGER);
            CREATE TABLE individus(
                 IDindividu INTEGER PRIMARY KEY, IDcivilite INTEGER,
                 nom TEXT, prenom TEXT, date_naiss TEXT, rue_resid TEXT,
                 cp_resid TEXT, ville_resid TEXT, adresse_auto INTEGER,
                 tel_domicile TEXT, tel_mobile TEXT, travail_tel TEXT,
                 mail TEXT, employeur TEXT);
            CREATE TABLE rattachements(
                 IDrattachement INTEGER PRIMARY KEY, IDfamille INTEGER,
                 IDindividu INTEGER, IDcategorie INTEGER, titulaire INTEGER);
            CREATE TABLE scolarite(
                 IDscolarite INTEGER PRIMARY KEY, IDindividu INTEGER,
                 date_debut TEXT, date_fin TEXT, IDecole INTEGER,
                 IDclasse INTEGER, IDniveau INTEGER);
            CREATE TABLE ecoles(IDecole INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE classes(IDclasse INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE niveaux_scolaires(
                 IDniveau INTEGER PRIMARY KEY, nom TEXT, abrege TEXT);
            INSERT INTO regimes VALUES(1,'CAF');
            INSERT INTO caisses VALUES(3,'Caisse fictive',1);
            INSERT INTO familles VALUES(1,3,'CAF-FICTIF');
            INSERT INTO familles VALUES(2,NULL,NULL);
            INSERT INTO individus VALUES
              (10,1,'RESPONSABLE','Un',NULL,'10 rue Parent','35130','Bais',
               NULL,'02 00 11','06 00 11','01 00 11','un@example.invalid','Employeur fictif'),
              (11,3,'RESPONSABLE','Deux',NULL,'','','',10,
               '02 00 12','06 00 12',NULL,'deux@example.invalid',NULL),
              (20,4,'ENFANT','Fictif','2016-05-12',NULL,NULL,NULL,10,
               NULL,NULL,NULL,NULL,NULL),
              (21,5,'ADO','Fictive','2010-11-03',NULL,NULL,NULL,10,
               NULL,NULL,NULL,NULL,NULL),
              (30,3,'CONTACT','Exclu',NULL,NULL,NULL,NULL,NULL,
               NULL,NULL,NULL,NULL,NULL),
              (60,5,'AUTRE','Famille','2016-05-12',NULL,NULL,NULL,NULL,
               NULL,NULL,NULL,NULL,NULL);
            INSERT INTO rattachements VALUES
              (1,1,10,1,1),(2,1,11,1,0),
              (3,1,20,2,0),(4,1,21,2,0),
              (5,1,30,3,0),(6,2,60,2,0);
            INSERT INTO ecoles VALUES(7,'École fictive');
            INSERT INTO classes VALUES(8,'Classe A');
            INSERT INTO niveaux_scolaires VALUES(9,'CM2','CM2');
            INSERT INTO scolarite VALUES
              (1,20,'2026-09-01','2027-08-31',7,8,9);
        """)
        self.conn.commit()
    def Close(self):
        raise AssertionError("La base injectée ne doit pas être fermée")


class LectureFamilleTests(unittest.TestCase):
    def setUp(self):
        self.db = DBFictive()
        self.addCleanup(self.db.conn.close)

    def charger(self, ident=1, jour="2026-11-03"):
        return F.LireFamille(ident, jour, self.db)

    def test_repres_children_sans_contacts_tiers(self):
        d = self.charger()
        self.assertEqual([x["IDindividu"] for x in d["responsables"]], [10,11])
        self.assertEqual([x["IDindividu"] for x in d["enfants"]], [21,20])
        self.assertEqual(d["regime"], "CAF")
        self.assertEqual(d["num_allocataire"], "CAF-FICTIF")
        self.assertEqual(d["caisse"], "Caisse fictive")

    def test_adresse_partagee_et_coordonnees_preservees(self):
        d = self.charger()
        second = d["responsables"][1]
        self.assertEqual(second["adresse"], "10 rue Parent")
        self.assertEqual(second["ville"], "Bais")
        self.assertEqual(second["mail"], "deux@example.invalid")
        self.assertEqual(d["responsables"][0]["employeur"], "Employeur fictif")

    def test_niveau_ecole_et_absence_d_inference(self):
        d = self.charger()
        children = {x["IDindividu"]:x for x in d["enfants"]}
        self.assertEqual(children[20]["ecole"], "École fictive")
        self.assertEqual(children[20]["classe"], "CM2 (Classe A)")
        self.assertEqual(children[21]["classe"], "")
        self.assertEqual(d["responsables"][0]["situation"], "")
        self.assertEqual(d["responsables"][0]["statut"], "")

    def test_selection_ados_et_alsh_sans_doubler_dossier(self):
        d = self.charger()
        ados = F.SelectionnerEnfants(d, [21])
        alsh = F.SelectionnerEnfants(d, [20])
        self.assertEqual([x["nom"] for x in ados["enfants"]], ["ADO"])
        self.assertEqual([x["nom"] for x in alsh["enfants"]], ["ENFANT"])
        self.assertEqual(len(d["enfants"]), 2)
        self.assertEqual(ados["IDfamille"], alsh["IDfamille"])

    def test_fiche_unique_melange_alsh_et_club_ados(self):
        donnees = self.charger()
        fiche = F.AffecterAccueils(donnees, {
            20: ["ALSH MOUTIERS"],
            21: ["ALSH BAIS", "CLUB ADOS BAIS"],
        })
        enfants = {e["IDindividu"]: e for e in fiche["enfants"]}
        self.assertEqual(enfants[20]["accueils"], ["ALSH MOUTIERS"])
        self.assertEqual(enfants[21]["accueils"],
                         ["ALSH BAIS", "CLUB ADOS BAIS"])
        self.assertNotIn("accueils", donnees["enfants"][0])
        self.assertEqual(fiche["IDfamille"], donnees["IDfamille"])

    def test_accueils_obligatoires_par_enfant_et_site_alsh_unique(self):
        donnees = self.charger()
        for choix in (
            {20: ["ALSH BAIS"]},
            {20: ["ALSH BAIS"], 21: []},
            {20: ["ALSH BAIS"], 21: ["ALSH LA GUERCHE", "ALSH MOUTIERS"]},
            {20: ["ALSH BAIS"], 21: ["CLUB ADOS LA GUERCHE"]},
            {20: ["ALSH BAIS"], 21: ["CLUB ADOS BAIS", "CLUB ADOS BAIS"]},
        ):
            with self.subTest(choix=choix), self.assertRaises(ValueError):
                F.AffecterAccueils(donnees, choix)

    def test_selection_vide_doublon_et_hors_famille_refuses(self):
        d = self.charger()
        for ids in ([], [20,20], [999], [20,60]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                F.SelectionnerEnfants(d, ids)

    def test_aucune_modification_sql(self):
        trace = []
        self.db.conn.set_trace_callback(trace.append)
        changes = self.db.conn.total_changes
        self.charger()
        self.assertEqual(self.db.conn.total_changes, changes)
        self.assertTrue(trace)
        self.assertTrue(all(t.lstrip().upper().startswith("SELECT")
                            for t in trace))

    def test_famille_inexistante_ou_identifiant_invalide(self):
        with self.assertRaises(ValueError):
            self.charger(999)
        for ident in (0, -1, None, True, "1"):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                self.charger(ident)

    def test_date_de_consultation_change_la_scolarite(self):
        ancienne = self.charger(jour="2026-08-31")
        courante = self.charger(jour="2026-09-01")
        enfants1 = {x["IDindividu"]:x for x in ancienne["enfants"]}
        enfants2 = {x["IDindividu"]:x for x in courante["enfants"]}
        self.assertEqual(enfants1[20]["classe"], "")
        self.assertEqual(enfants2[20]["niveau"] if "niveau" in enfants2[20]
                         else enfants2[20]["classe"], "CM2 (Classe A)")


if __name__ == "__main__":
    unittest.main()
