# -*- coding: utf-8 -*-
"""P1 #426 : vraie base SQLite fictive ; aucune base PMSL, aucun wx/SMTP."""
import datetime
import unittest
from unittest.mock import patch

from tests.test_noethys_sl_adhesions import Env, D
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Adhesions_echeances as E

JOUR = D(2026, 10, 19)


class EcheancesTests(unittest.TestCase):
    def proposer(self, debut=D(2026, 9, 1), fin=D(2026, 9, 30),
                 ref=JOUR, activites=None, payeur=None):
        return E.Proposer(debut, fin, date_reference=ref,
                          liste_activites=activites or [1, 2],
                          IDcompte_payeur=payeur)

    def test_audit_rc7_anticipees_sans_ecriture_ni_suppression(self):
        with Env() as e:
            e.base.inserer("prestations",
                           ["IDprestation", "IDcompte_payeur", "IDindividu", "categorie", "date", "montant", "IDfacture"],
                           [(801, 11, 100, "cotisation", "2026-10-01", 7.5, None),
                            (802, 11, 100, "cotisation", "2026-10-01", 7.5, 99)])
            e.base.inserer("cotisations",
                           ["IDcotisation", "IDindividu", "IDtype_cotisation", "IDunite_cotisation",
                            "date_saisie", "date_debut", "date_fin", "IDprestation", "observations"],
                           [(701, 100, 1, 11, "2026-10-01", "2027-01-06", "2028-01-06", 801,
                             A.MARQUEUR_AUTO),
                            (702, 100, 1, 11, "2026-10-01", "2027-03-06", "2028-03-06", 802,
                             A.MARQUEUR_AUTO),
                            (703, 100, 1, 11, "2026-10-01", "2027-02-06", "2028-02-06",
                             None, "adhesion manuelle")])
            avant = (e.compte("cotisations"), e.compte("prestations"))
            rapport = E.AuditerCotisationsAnticipees(JOUR)
            self.assertEqual(len(rapport), 2)
            self.assertEqual([row["IDcotisation"] for row in rapport], [701, 702])
            self.assertEqual(rapport[0]["statut"], "a_verifier_avant_regularisation")
            self.assertEqual(rapport[1]["statut"], "reglement_ou_facture_a_regolariser")
            self.assertIn("prestation_anticipee", rapport[0]["motifs"])
            self.assertEqual((e.compte("cotisations"), e.compte("prestations")), avant)

    def test_audit_ne_touche_pas_aux_adhesions_manuelles(self):
        with Env() as e:
            e.adhesion(100, D(2027, 1, 1), D(2028, 1, 1),
                       observations="saisie manuelle")
            self.assertEqual(E.AuditerCotisationsAnticipees(JOUR), [])

    def test_reservation_future_jamais_financee(self):
        with Env() as e:
            e.conso(100, D(2027, 1, 6))
            p = self.proposer(D(2026, 10, 1), D(2027, 1, 31))
            self.assertFalse(p["propositions"])
            self.assertEqual(E.Executer(p, confirmation=True), [])
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertEqual(e.compte("prestations"), 0)

    def test_cloture_cree_apres_participation_a_date_de_fin_de_mois(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5))
            e.conso(100, D(2026, 9, 7), activite=2)
            p = self.proposer()
            self.assertEqual(len(p["propositions"]), 1)
            self.assertEqual(e.compte("cotisations"), 0, "la prévisualisation doit rester en lecture seule")
            self.assertEqual(e.compte("prestations"), 0)
            r = E.Executer(p, confirmation=True)
            self.assertEqual([v["statut"] for v in r], [A.STATUT_CREE])
            self.assertEqual(e.lire("SELECT date_debut, date_fin FROM cotisations;"),
                             [("2026-09-05", "2027-09-05")])
            self.assertEqual(e.lire("SELECT date, date_valeur, montant, categorie FROM prestations;"),
                             [("2026-09-30", "2026-09-30", 7.5, "cotisation")])
            self.assertEqual(self.proposer()["propositions"], [])

    def test_facture_anticipee_echeance_aujourdhui(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 12), etat="present")
            e.conso(100, D(2026, 10, 25), etat="reservation")
            p = self.proposer(D(2026, 10, 1), D(2026, 10, 31))
            self.assertEqual(len(p["propositions"]), 1)
            self.assertEqual(p["propositions"][0]["date_debut"], D(2026, 10, 12))
            self.assertEqual(p["propositions"][0]["date_prestation"], JOUR)
            self.assertEqual(E.Executer(p, confirmation=True)[0]["statut"], A.STATUT_CREE)
            self.assertEqual(e.lire("SELECT date FROM prestations WHERE categorie='cotisation';"),
                             [("2026-10-19",)])

    def test_annulations_successives_rapide_et_nouveau_mois(self):
        with Env() as e:
            x = e.conso(100, D(2026, 9, 7))
            y = e.conso(100, D(2026, 9, 9), activite=2)
            e.supprimer_conso(x)
            e.supprimer_conso(y)
            self.assertEqual(self.proposer()["propositions"], [])
            e.conso(100, D(2026, 10, 8))
            octobre = self.proposer(D(2026, 10, 1), D(2026, 10, 31))
            self.assertEqual(octobre["propositions"][0]["date_debut"], D(2026, 10, 8))
            E.Executer(octobre, confirmation=True)
            self.assertEqual(e.lire("SELECT date_debut FROM cotisations;"), [("2026-10-08",)])

    def test_absent_refus_et_reservation_confirmee_passee(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 8), etat="absent")
            e.conso(100, D(2026, 9, 13), etat="reservation")
            p = self.proposer()
            self.assertEqual(p["propositions"][0]["date_debut"], D(2026, 9, 13))

    def test_adhesion_manuelle_est_conservee(self):
        with Env() as e:
            e.adhesion(100, D(2026, 1, 1), D(2027, 1, 1), observations="manuelle")
            e.conso(100, D(2026, 9, 15))
            p = self.proposer()
            self.assertFalse(p["propositions"])
            E.Executer(p, confirmation=True)
            self.assertEqual(e.compte("cotisations"), 1)

    def test_chevauchement_d_une_adhesion_future_manuelle_signale(self):
        with Env() as e:
            e.adhesion(100, D(2027, 1, 1), D(2028, 1, 1), observations="manuelle")
            e.conso(100, D(2026, 9, 15))
            p = self.proposer()
            self.assertEqual(p["propositions"], [])
            self.assertIn("chevauchement", [a["motif"] for a in p["a_verifier"]])

    def test_historique_incomplet_ne_decale_pas_le_debut(self):
        with Env() as e:
            e.conso(100, D(2026, 8, 10))
            e.conso(100, D(2026, 9, 12))
            p = self.proposer()
            self.assertEqual(p["propositions"], [])
            self.assertIn("premiere_participation_anterieure",
                          [a["motif"] for a in p["a_verifier"]])

    def test_annulation_apres_apercu_empeche_toute_creation(self):
        with Env() as e:
            conso = e.conso(100, D(2026, 9, 5))
            p = self.proposer()
            e.supprimer_conso(conso)
            with self.assertRaises(ValueError):
                E.Executer(p, confirmation=True)
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertEqual(e.compte("prestations"), 0)

    def test_validation_expresse_obligatoire(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5))
            p = self.proposer()
            with self.assertRaises(ValueError):
                E.Executer(p)
            self.assertEqual(e.compte("cotisations"), 0)

    def test_periode_verrouillee_bloque_avant_toute_ecriture(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5))
            e.base.inserer("periodes_gestion",
                           ["date_debut", "date_fin", "verrou_cotisations", "verrou_prestations"],
                           [("2026-09-01", "2026-09-30", 1, 1)])
            p = self.proposer()
            resultat = E.Executer(p, confirmation=True)
            self.assertEqual(resultat[0]["statut"], A.STATUT_A_VERIFIER)
            self.assertEqual(resultat[0]["motif"], "periode_verrouillee")
            self.assertEqual(e.compte("cotisations"), 0)

    def test_actes_sans_facture_ni_ventilation(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5))
            p = self.proposer()
            E.Executer(p, confirmation=True)
            self.assertEqual(e.lire("SELECT IDfacture FROM prestations WHERE categorie='cotisation';"),
                             [(None,)])
            self.assertEqual(e.compte("ventilation"), 0)

    def test_une_personne_une_adhesion_toutes_activites(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5), activite=2)
            e.conso(100, D(2026, 9, 6), activite=1)
            p = self.proposer(activites=[1, 2])
            self.assertEqual(len(p["propositions"]), 1)
            self.assertEqual(E.Executer(p, confirmation=True)[0]["statut"], A.STATUT_CREE)
            self.assertEqual(e.compte("cotisations"), 1)

    def test_date_future_de_traitement_refusee(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 5))
            with self.assertRaises(ValueError):
                self.proposer(ref=D(2099, 1, 1))
            self.assertEqual(e.compte("cotisations"), 0)

    def test_preuve_participation_recontrolee_sous_verrou(self):
        with Env() as e:
            cid = e.conso(100, D(2026, 9, 5))
            p = self.proposer()
            old = A._Verrouiller
            def annuler_apres_verrou(db, titulaire, type_cotisation):
                unlock = old(db, titulaire, type_cotisation)
                db.cursor.execute("UPDATE consommations SET etat='absent' WHERE IDconso=%d" % cid)
                return unlock
            with patch.object(A, "_Verrouiller", side_effect=annuler_apres_verrou):
                result = E.Executer(p, confirmation=True)
            self.assertEqual(result[0]["motif"], "participation_modifiee")
            self.assertEqual(e.compte("cotisations"), 0)


if __name__ == "__main__":
    unittest.main()
