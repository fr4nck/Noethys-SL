# -*- coding: utf-8 -*-
"""Lot 2C-2 : commandes paniers familiaux, horaires et factures non touchees.

SQLite fictif jetable, aucun email, aucune donnee PMSL.
"""
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch
from Utils import UTILS_Repas_regimes as R
from Utils import UTILS_Repas_source as S
from Utils import UTILS_Repas_validation as V

JOUR = date(2026, 11, 4)
CHOIX_3 = {"standard": 11, "sans_porc": 12, "vegetarien": 13}
CHOIX_4 = dict(CHOIX_3, sans_repas_pmsl=14)
SERVICES = {(1, 10): ("Bais", "midi")}


class FausseBase:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.lignes = []
        self.conn.executescript("""
        CREATE TABLE questionnaire_categories (IDcategorie INTEGER PRIMARY KEY, type TEXT);
        CREATE TABLE questionnaire_questions (IDquestion INTEGER PRIMARY KEY, IDcategorie INTEGER, controle TEXT);
        CREATE TABLE questionnaire_choix (IDchoix INTEGER PRIMARY KEY, IDquestion INTEGER);
        CREATE TABLE questionnaire_reponses (IDreponse INTEGER PRIMARY KEY, IDquestion INTEGER,
                                           IDindividu INTEGER, reponse TEXT);
        CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, heure_debut TEXT, heure_fin TEXT);
        CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, date_naiss TEXT);
        CREATE TABLE consommations (date TEXT, IDgroupe INTEGER, IDunite INTEGER, IDindividu INTEGER,
                                    etat TEXT, heure_debut TEXT, heure_fin TEXT);
        INSERT INTO questionnaire_categories VALUES (1, 'individu');
        INSERT INTO questionnaire_questions VALUES (5, 1, 'liste_deroulante');
        INSERT INTO questionnaire_choix VALUES (11, 5),(12, 5),(13, 5),(14, 5);
        INSERT INTO unites VALUES (10, '08:30:00', '17:30:00');
        """)
        for ident in range(1, 31):
            self.conn.execute("INSERT INTO individus VALUES (?, ?)", (ident, "2017-01-01"))
            self.conn.execute("INSERT INTO consommations VALUES (?,?,?,?,?,?,?)",
                              (JOUR.isoformat(), 1, 10, ident, "reservation", None, None))
        for ident in range(1, 25):
            self.conn.execute("INSERT INTO questionnaire_reponses VALUES (?,?,?,?)",
                              (ident, 5, ident, "11"))
        for ident in range(25, 28):
            self.conn.execute("INSERT INTO questionnaire_reponses VALUES (?,?,?,?)",
                              (ident, 5, ident, "12"))
        for ident in (28, 29):
            self.conn.execute("INSERT INTO questionnaire_reponses VALUES (?,?,?,?)",
                              (ident, 5, ident, "13"))
        self.conn.execute("INSERT INTO questionnaire_reponses VALUES (?,?,?,?)",
                          (30, 5, 30, "14"))
        self.conn.commit()

    def ExecuterReq(self, req):
        self.lignes = self.conn.execute(req).fetchall()
        return True

    def ResultatReq(self):
        return self.lignes

    def Close(self):
        pass


def colonne(role, colonne_id):
    return {"IDcolonne": colonne_id, "nom_colonne": role, "categorie": "numerique_avec_suggestion",
            "parametres": {"role_repas": role, "question_regime": 5,
                           "choix_regimes": CHOIX_4, "site_directeur": "Bais",
                           "service_directeur": "midi", "midi_debut": "12:00",
                           "midi_fin": "13:00", "repas_pmsl_prevu": True,
                           "unites": [(1, 10)]}}


class PanierSourceTests(unittest.TestCase):
    def setUp(self):
        self.base = FausseBase()
        self.addCleanup(self.base.conn.close)
        p = patch.object(S.GestionDB, "DB", return_value=self.base)
        p.start()
        self.addCleanup(p.stop)

    def charger(self, offre=True):
        return S.ChargerRepartitionRegimes(5, CHOIX_4, SERVICES, JOUR, JOUR,
                                          plage_midi=("12:00", "13:00"),
                                          repas_pmsl_prevu=offre)

    def test_trente_presences_mais_vingt_neuf_repas_fournisseur(self):
        ligne = self.charger()[(JOUR, "Bais", "midi")]
        self.assertEqual((ligne["enfants_presents_midi_classes"], ligne["total_repas"],
                          ligne["repas_apportes"], ligne["standard"], ligne["sans_porc"],
                          ligne["vegetarien"]), (30, 29, 1, 24, 3, 2))
        self.assertEqual(ligne["repas_apportes_six_plus"], 1)
        self.assertTrue(ligne["complet"])

    def test_un_accueil_hors_midi_ne_cree_pas_de_repas(self):
        self.base.conn.execute("UPDATE unites SET heure_debut='13:00:00', heure_fin='17:30:00'")
        self.base.conn.commit()
        self.assertEqual(self.charger(), {})

    def test_intersection_partielle_refusee(self):
        self.base.conn.execute("UPDATE unites SET heure_debut='08:30:00', heure_fin='12:30:00'")
        self.base.conn.commit()
        with self.assertRaises(ValueError):
            self.charger()

    def test_default_standard_seulement_si_offre_confirmee(self):
        self.base.conn.execute("DELETE FROM questionnaire_reponses WHERE IDindividu=1")
        self.base.conn.commit()
        ligne = self.charger()[(JOUR, "Bais", "midi")]
        self.assertEqual((ligne["standard"], ligne["non_renseignes"]), (24, 0))
        with self.assertRaises(R.RegimeInvalide):
            self.charger(offre=False)

    def test_ancien_modele_sans_changement(self):
        # L'ancienne categorie reste non renseignee en l'absence de reponse.
        # Un nouveau choix inconnu (panier) dans l'ancien modele est bloque.
        with self.assertRaises(R.RegimeInvalide):
            S.ChargerRepartitionRegimes(5, CHOIX_3, SERVICES, JOUR, JOUR)
        self.base.conn.execute("DELETE FROM questionnaire_reponses WHERE IDindividu=30")
        self.base.conn.commit()
        resultat = S.ChargerRepartitionRegimes(5, CHOIX_3, SERVICES, JOUR, JOUR)
        ligne = resultat[(JOUR, "Bais", "midi")]
        self.assertEqual((ligne["total_repas"], ligne["repas_apportes"],
                          ligne["non_renseignes"]), (30, 0, 1))
        self.assertEqual(ligne["standard"], 24)

    def test_deux_demi_journees_jointives_une_presence(self):
        self.base.conn.execute("DELETE FROM consommations")
        self.base.conn.execute("INSERT INTO unites VALUES (20,'08:30:00','12:30:00')")
        self.base.conn.execute("INSERT INTO unites VALUES (21,'12:30:00','17:30:00')")
        for uid in (20, 21):
            self.base.conn.execute("INSERT INTO consommations VALUES (?,?,?,?,?,?,?)",
                                   (JOUR.isoformat(), 1, uid, 30, "reservation", None, None))
        self.base.conn.commit()
        s = {(1, 20): ("Bais", "midi"), (1, 21): ("Bais", "midi")}
        r = S.ChargerRepartitionRegimes(5, CHOIX_4, s, JOUR, JOUR,
                                       plage_midi=("12:00", "13:00"),
                                       repas_pmsl_prevu=True)
        self.assertEqual((r[JOUR, "Bais", "midi"]["repas_apportes"],
                          r[JOUR, "Bais", "midi"]["total_repas"]), (1, 0))

    def test_parametre_horaire_obligatoire_et_roles_panier(self):
        c = colonne("regime_standard", 1)
        _, erreurs = R.GroupesColonnesRegimes([c])
        self.assertIn(1, erreurs)  # pas de colonne paniers
        cols = [colonne("regime_standard", 1), colonne("regime_repas_apporte", 2)]
        groupes, erreurs = R.GroupesColonnesRegimes(cols)
        self.assertEqual(erreurs, {})
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]["plage_midi"], ("12:00", "13:00"))
        del cols[0]["parametres"]["midi_debut"]
        groupes, erreurs = R.GroupesColonnesRegimes(cols)
        self.assertTrue(erreurs)

    def test_validation_totaux_et_panier_hors_fournisseur(self):
        class Case:
            def __init__(self, n):
                self.n=n
            def GetValeur(self):
                return self.n
            def SetValeur(self, n):
                self.n=n
        roles = ("six_plus", "regime_standard", "regime_sans_porc",
                 "regime_vegetarien", "regime_non_renseigne", "regime_repas_apporte")
        colonnes = [colonne(role, i + 1) for i, role in enumerate(roles)]
        valeurs = (29, 24, 3, 2, 0, 1)
        cases = {(0, i): Case(n) for i,n in enumerate(valeurs)}
        key = (JOUR, "Bais", "midi")
        source = self.charger()
        d = {"liste_dates": [JOUR, "Total"], "liste_colonnes": colonnes,
             "cases": cases, "regimes": {i: source for i in range(1,7)},
             "erreurs_regimes": {}, "erreurs_sans_porc": {}}
        lignes = V.ConstruireControle(d)
        self.assertEqual(V.ErreursRegimes(lignes), [])
        self.assertEqual(lignes[0]["totaux"]["total_repas"], 29)
        self.assertEqual(lignes[0]["regimes"]["repas_apportes"], 1)
        cases[(0, 0)].SetValeur(30)
        self.assertTrue(V.ErreursRegimes(V.ConstruireControle(d)))


if __name__ == "__main__":
    unittest.main()
