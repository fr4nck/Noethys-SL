# -*- coding: utf-8 -*-
"""ALSH 2C-3 : audit non nominatif SQL et accord avant facturation (fictif)."""
import sqlite3
import unittest
from datetime import date
from decimal import Decimal

from Utils import UTILS_Repas_tarifs_audit_2c as A


class BaseFictive:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.executed = []
        self.result = []
        self.db.executescript("""
          CREATE TABLE noms_tarifs(IDnom_tarif INTEGER,nom TEXT);
          CREATE TABLE tarifs(IDtarif INTEGER PRIMARY KEY,IDactivite INTEGER,
            type TEXT,methode TEXT,date_debut TEXT,date_fin TEXT,IDnom_tarif INTEGER);
          CREATE TABLE combi_tarifs(IDcombi_tarif INTEGER PRIMARY KEY,IDtarif INTEGER,type TEXT);
          CREATE TABLE combi_tarifs_unites(IDcombi_tarif INTEGER,IDunite INTEGER);
          CREATE TABLE unites(IDunite INTEGER PRIMARY KEY,IDactivite INTEGER,repas INTEGER);
          CREATE TABLE tarifs_lignes(IDtarif INTEGER);
          CREATE TABLE prestations(IDprestation INTEGER PRIMARY KEY,IDtarif INTEGER,
            IDfacture INTEGER,forfait INTEGER);
          CREATE TABLE ventilation(IDprestation INTEGER);
          INSERT INTO noms_tarifs VALUES
            (1,'Repas separable'),(2,'Journee composee'),(3,'Credit'),(4,'Unite ambigue');
          INSERT INTO tarifs VALUES
            (10,100,'JOURN','montant_unique','2026-09-01','2027-08-31',1),
            (20,100,'JOURN','qf','2026-09-01','2027-08-31',2),
            (30,100,'CREDIT','montant_unique','2026-09-01','2027-08-31',3),
            (40,100,'JOURN','montant_unique','2026-09-01','2027-08-31',4),
            (50,999,'JOURN','montant_unique','2026-09-01','2027-08-31',1);
          INSERT INTO combi_tarifs VALUES
            (101,10,'JOURN'),(201,20,'JOURN'),(301,30,'CREDIT'),
            (401,40,'JOURN'),(501,50,'JOURN');
          INSERT INTO combi_tarifs_unites VALUES
            (101,501),(201,601),(201,501),(301,701),(401,502),(501,999);
          INSERT INTO unites VALUES
            (501,100,1),(601,100,0),(701,100,1),(502,100,0),(999,999,1);
          INSERT INTO tarifs_lignes VALUES(10),(10),(20),(30),(40),(50);
          INSERT INTO prestations VALUES
            (8001,10,123,NULL),
            (8002,10,NULL,NULL),
            (8003,20,124,NULL),
            (8004,30,NULL,1),
            (8005,50,125,NULL);
          INSERT INTO ventilation VALUES(8002),(8002),(8003),(8005);
        """)

    def ExecuterReq(self, sql):
        # The production code can never perform a write through this adapter.
        if not sql.lstrip().upper().startswith("SELECT "):
            raise AssertionError("Ecriture SQL interdite pendant audit")
        self.executed.append(sql)
        self.result = self.db.execute(sql).fetchall()
        return True

    def ResultatReq(self):
        return list(self.result)


def accord(**kw):
    r = {
        "IDactivite": 100, "IDtarif_repas": 10, "IDunite_repas": 501,
        "IDquestion": 5, "IDchoix_panier": 14,
        "date_debut": "2026-11-01", "date_fin": "2027-06-30",
        "site": "Bais", "service": "midi",
        "tarif_repas_dedie_confirme": True,
        "accueil_facture_independamment_confirme": True,
        "approbateur": "responsable-test",
        "preuve_tarif": "contrat ALSH fictif / deliberation",
        "approuve_le": "2026-10-26T20:00:00+01:00",
    }
    r.update(kw)
    return r


def decision(**kw):
    r = {
        "IDindividu": 42, "IDactivite": 100,
        "IDtarif_repas": 10, "IDunite_repas": 501,
        "site": "Bais", "service": "midi",
        "date": "2026-11-04", "type_repas": "sans_repas_pmsl",
        "IDquestion": 5, "IDchoix_panier": 14,
        "presence_midi_qualifiee": True,
        "origine_plage": "demi_journee_avec_midi",
        "etat_accueil": "reservation",
        "provenance": "exception_datee",
        "horodatage": "2026-10-26T20:05:00+01:00",
    }
    r.update(kw)
    return r


class AuditTarifsSansEcritureTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseFictive()
        self.addCleanup(self.base.db.close)
        self.rapport = A.AuditerTarifsALSH(self.base, [100])

    def trouver(self, ident):
        return next(x for x in self.rapport["tarifs"] if x["IDtarif"] == ident)

    def test_rapport_restreint_et_anonyme(self):
        self.assertEqual(self.rapport["activites"], (100,))
        self.assertEqual([x["IDtarif"] for x in self.rapport["tarifs"]],
                         [10,20,30,40])
        self.assertEqual(self.rapport["tarifs_a_qualifier"], 4)
        self.assertEqual(self.trouver(10)["statut"], "A_QUALIFIER")
        self.assertFalse(any("IDindividu" in str(x) or "IDfamille" in str(x)
                             for x in self.rapport["tarifs"]))
        self.assertTrue(self.base.executed)
        self.assertTrue(all(sql.startswith("SELECT ") for sql in self.base.executed))
        self.assertEqual(self.base.db.execute(
            "SELECT COUNT(*) FROM prestations").fetchone(), (5,))

    def test_tarifs_combines_identifies_sans_conclure_du_flag_repas(self):
        self.assertEqual(len(self.trouver(10)["combinaisons"]), 1)
        self.assertEqual(self.trouver(10)["combinaisons"][0]["unites"][0]["repas_inclus"], 1)
        self.assertIn("COMBINAISON_COMPOSITE", self.trouver(20)["risques"])
        self.assertIn("TARIF_NON_JOURNALIER_OU_CREDIT", self.trouver(30)["risques"])
        self.assertIn("REPAS_INCLUS_NON_CONFIRME", self.trouver(40)["risques"])
        self.assertEqual(self.trouver(10)["nombre_lignes_prix"], 2)

    def test_etats_comptables_sans_acces_aux_familles(self):
        self.assertEqual((self.trouver(10)["prestations_existantes"],
                          self.trouver(10)["prestations_facturees"],
                          self.trouver(10)["prestations_ventilees"]), (2,1,1))
        self.assertIn("FACTURES_EXISTANTES_A_PRESERVER", self.trouver(10)["risques"])
        self.assertIn("REGLEMENTS_EXISTANTS_A_PRESERVER", self.trouver(10)["risques"])
        self.assertEqual(self.trouver(30)["prestations_forfait"], 1)

    def test_aucun_tarif_et_table_absente(self):
        vide = A.AuditerTarifsALSH(self.base, [888])
        self.assertEqual(vide["tarifs"], ())
        self.base.db.execute("DROP TABLE tarifs_lignes")
        with self.assertRaises(sqlite3.OperationalError):
            A.AuditerTarifsALSH(self.base, [100])

    def test_refus_des_identifiants_injectes_ou_non_valides(self):
        for ident in ("100", "100 OR 1=1", 0, -1, True, None, 1.0):
            with self.subTest(ident=ident), self.assertRaises(A.AuditTarifs2CInvalide):
                A.AuditerTarifsALSH(self.base, [ident])
        with self.assertRaises(A.AuditTarifs2CInvalide):
            A.AuditerTarifsALSH(self.base, [])
        with self.assertRaises(A.AuditTarifs2CInvalide):
            A.AuditerTarifsALSH(self.base, range(51))

    def test_tarif_journalier_isole_avec_accord_explicitement_signe(self):
        p = A.ValiderAccordTarifSepare(self.rapport, accord())
        self.assertEqual((p["IDtarif_repas"],p["IDunite_repas"]), (10,501))
        self.assertEqual(p["etat"], "PREVOL_MANUEL_NON_ACTIF")
        self.assertEqual(p["date_debut"], date(2026,11,1))
        self.assertNotIn("prix_auto", p)

    def test_prevol_exclut_forfait_credit_et_unite_ambigue(self):
        for params in (
            {"IDtarif_repas":20,"IDunite_repas":601},
            {"IDtarif_repas":30,"IDunite_repas":701},
            {"IDtarif_repas":40,"IDunite_repas":502},
            {"IDtarif_repas":50,"IDactivite":999},
            {"IDtarif_repas":10,"IDunite_repas":601},
        ):
            with self.subTest(params=params), self.assertRaises(A.AuditTarifs2CInvalide):
                A.ValiderAccordTarifSepare(self.rapport, accord(**params))

    def test_prevol_exige_approbation_et_periode_bornee(self):
        mauvais = (
            {"tarif_repas_dedie_confirme":False},
            {"accueil_facture_independamment_confirme":False},
            {"approbateur":""}, {"preuve_tarif":""},
            {"approuve_le":"2026-10-26T20:00:00"},
            {"date_debut":"2026-08-31"},
            {"date_fin":"2027-09-01"},
            {"date_debut":"2027-05-01","date_fin":"2026-11-01"},
            {"IDquestion":None}, {"IDchoix_panier":True},
            {"site":"Bais "},
        )
        for options in mauvais:
            with self.subTest(options=options), self.assertRaises(A.AuditTarifs2CInvalide):
                A.ValiderAccordTarifSepare(self.rapport, accord(**options))

    def test_prevol_impossible_sans_combinaison_ou_prix(self):
        self.base.db.execute("DELETE FROM tarifs_lignes WHERE IDtarif=10")
        r = A.AuditerTarifsALSH(self.base, [100])
        with self.assertRaises(A.AuditTarifs2CInvalide):
            A.ValiderAccordTarifSepare(r, accord())
        self.base.db.execute("INSERT INTO tarifs_lignes VALUES (10)")
        self.base.db.execute("DELETE FROM combi_tarifs_unites WHERE IDcombi_tarif=101")
        r = A.AuditerTarifsALSH(self.base, [100])
        with self.assertRaises(A.AuditTarifs2CInvalide):
            A.ValiderAccordTarifSepare(r, accord())


class SimulationDecisionDateeTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseFictive()
        self.addCleanup(self.base.db.close)
        self.accord = A.ValiderAccordTarifSepare(
            A.AuditerTarifsALSH(self.base, [100]), accord())

    def test_panier_zero_sur_repas_accueil_maintenu(self):
        p = A.SimulerNouvellePrestationPanier(
            self.accord, decision(), "14.50", "4.50")
        self.assertEqual(p["action"], "NE_PAS_CREER_PRESTATION_REPAS_PAYANTE")
        self.assertEqual(p["statut"], "SIMULATION_SANS_ECRITURE")
        self.assertEqual((p["montant_repas"], p["montant_accueil"],
                          p["montant_total"]),
                         (Decimal("0.00"), Decimal("14.50"), Decimal("14.50")))
        self.assertEqual(self.base.db.execute(
            "SELECT COUNT(*) FROM prestations").fetchone(), (5,))

    def test_dated_snapshot_allowed(self):
        result = A.SimulerNouvellePrestationPanier(
            self.accord, decision(provenance="snapshot_date"), "14.50", "4.50")
        self.assertEqual(result["montant_repas"], Decimal("0.00"))

    def test_refus_questionnaire_courant_sans_historique(self):
        for provenance in (None, "questionnaire", "questionnaire_actuel", ""):
            with self.subTest(provenance=provenance), self.assertRaises(A.AuditTarifs2CInvalide):
                A.SimulerNouvellePrestationPanier(
                    self.accord, decision(provenance=provenance), "14.50", "4.50")

    def test_facture_reglement_et_prestation_existante_bloques(self):
        for kwargs in ({"facture_emise":True},
                       {"prestation_reglee":True},
                       {"prestation_existante":8001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(A.AuditTarifs2CInvalide):
                A.SimulerNouvellePrestationPanier(
                    self.accord, decision(), "14.50", "4.50", **kwargs)

    def test_autre_regime_et_autre_activite_pas_exoneres(self):
        for params in ({"type_repas":"standard"}, {"IDactivite":999},
                       {"IDtarif_repas":20}, {"IDunite_repas":601},
                       {"site":"Autre site"}, {"service":"soir"},
                       {"date":"2027-10-01"}, {"IDindividu":0},
                       {"IDquestion": 6}, {"IDchoix_panier": 11},
                       {"presence_midi_qualifiee": False},
                       {"origine_plage": "demi_journee_sans_midi"},
                       {"etat_accueil": "absentj"},
                       {"horodatage":"2026-10-26T20:05:00"}):
            with self.subTest(params=params), self.assertRaises(A.AuditTarifs2CInvalide):
                A.SimulerNouvellePrestationPanier(
                    self.accord, decision(**params), "14.50", "4.50")

    def test_montants_imprecis_ou_negatifs_bloques(self):
        for valeur in (1.25, "NaN", "-1.00", "2.345", None):
            with self.subTest(montant=valeur), self.assertRaises(A.AuditTarifs2CInvalide):
                A.SimulerNouvellePrestationPanier(
                    self.accord, decision(), "14.50", valeur)


if __name__ == "__main__":
    unittest.main()
