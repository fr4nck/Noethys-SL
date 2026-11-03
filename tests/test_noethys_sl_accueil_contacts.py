# -*- coding: utf-8 -*-
"""Lot C : destinataires et accompagnants de la fiche enfant, base fictive."""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Utils import UTILS_Accueil_contacts as C


class Base:
    isNetwork = False
    echec = 0

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.conn.executescript("""
            CREATE TABLE individus (
                IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
                IDcivilite INTEGER, rue_resid TEXT, cp_resid TEXT,
                ville_resid TEXT, tel_domicile TEXT, tel_mobile TEXT,
                travail_tel TEXT, adresse_auto INTEGER);
            CREATE TABLE rattachements (IDindividu INTEGER, IDfamille INTEGER,
                                       IDcategorie INTEGER);
            CREATE TABLE liens (IDfamille INTEGER, IDindividu_sujet INTEGER,
                               IDindividu_objet INTEGER, IDautorisation INTEGER,
                               IDtype_lien INTEGER);
            INSERT INTO individus VALUES
              (10,'ENFANT','Test',4,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
              (11,'PARENT','Un',3,'','', '', '02 01 01', '06 11 11','01 99',40),
              (12,'PARENT','Deux',1,'Rue Deux','35000','Rennes','02 12 12',NULL,NULL,NULL),
              (20,'CONTACT','Trois',3,'','','','02 20 20','06 20 20',NULL,NULL),
              (21,'CONTACT','Sans Accord',1,'','','',NULL,'06 21 21',NULL,NULL),
              (22,'CONTACT','Interdit',1,'','','',NULL,'06 22 22',NULL,NULL),
              (23,'CONTACT','Hors Famille',1,'','','',NULL,'06 23 23',NULL,NULL),
              (40,'ADRESSE','Famille',3,'5 rue Fictive','35130','La Guerche',NULL,NULL,NULL,NULL);
            INSERT INTO rattachements VALUES
              (10,1,2), (11,1,1), (12,1,1),
              (20,1,3), (21,1,3), (22,1,3),
              (23,2,3), (10,2,2), (11,2,1);
            INSERT INTO liens VALUES
              (1,11,10,1,1),
              (1,12,10,1,1),
              (1,20,10,3,4),
              (1,21,10,2,22),
              (1,22,10,4,23),
              (1,23,10,3,22),
              (2,11,10,1,1);
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()


class ContactsExistantsTests(unittest.TestCase):
    def setUp(self):
        self.db = Base()
        self.addCleanup(self.db.close)

    def test_deux_responsables_et_un_raccompagnant_sans_doublon(self):
        data = C.LireContactsEnfant(10, self.db)
        self.assertEqual([x["IDindividu"] for x in data["responsables"]], [11, 12])
        self.assertEqual([x["IDindividu"] for x in data["accompagnants"]], [20])
        self.assertEqual(data["accompagnants"][0]["lien"], "grand-mère")
        self.assertEqual(data["accompagnants"][0]["telephone_court"], "06 20 20")

    def test_adresse_auto_et_telephones_existants(self):
        parent = C.LireContactsEnfant(10, self.db)["responsables"][0]
        self.assertEqual(parent["adresse"], "5 rue Fictive, 35130 La Guerche")
        self.assertIn("Mobile : 06 11 11", parent["telephone"])
        self.assertIn("Domicile : 02 01 01", parent["telephone"])
        self.assertIn("Travail : 01 99", parent["telephone"])

    def test_contact_non_autorise_et_interdit_exclus(self):
        data = C.LireContactsEnfant(10, self.db)
        ids = [x["IDindividu"] for groupe in data.values() for x in groupe]
        for ident in (21, 22, 23, 40):
            self.assertNotIn(ident, ids)

    def test_rattachement_seul_ne_vaut_pas_autorisation(self):
        self.db.conn.execute("DELETE FROM liens")
        self.db.conn.commit()
        self.assertEqual(C.LireContactsEnfant(10, self.db),
                         {"responsables": [], "accompagnants": []})

    def test_lecture_sql_uniquement(self):
        requetes = []
        self.db.conn.set_trace_callback(requetes.append)
        avant = self.db.conn.total_changes
        C.LireContactsEnfant(10, self.db)
        self.assertEqual(self.db.conn.total_changes, avant)
        self.assertTrue(requetes)
        self.assertTrue(all(x.lstrip().upper().startswith("SELECT") for x in requetes))

    def test_id_invalide_refuse(self):
        for ident in (None, 0, -1, True, "10"):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                C.LireContactsEnfant(ident, self.db)


if __name__ == "__main__":
    unittest.main()
