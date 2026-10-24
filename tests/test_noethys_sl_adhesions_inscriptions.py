# -*- coding: utf-8 -*-
"""Association des inscriptions aux adhesions automatiques (Noethys-SL).

Base SQLite temporaire, ni utilisateur reel, ni appel reseau, ni wx.
La participation reste obligatoire pour CREER une prestation financiere.
"""
import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _garde_reseau  # noqa: F401
from test_noethys_sl_adhesions import Env, D
from test_noethys_sl_adhesions_titulaire import completer
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Adhesions_echeances as E

JOUR = D(2026, 10, 15)
DEBUT = D(2026, 9, 1)
FIN = D(2027, 9, 1)


def inscription(e, identifiant, personne=100, activite=2, debut=DEBUT,
                fin=None, statut="ok", payeur=11, famille=1, groupe=1):
    e.base.inserer("inscriptions", [
        "IDinscription", "IDindividu", "IDactivite", "IDfamille",
        "IDcompte_payeur", "IDgroupe", "date_inscription",
        "date_desinscription", "statut",
    ], [(identifiant, personne, activite, famille, payeur, groupe,
         str(debut) if debut else None, str(fin) if fin else None, statut)])
    return identifiant


def auto(e, personne=100, debut=DEBUT, fin=FIN, chaine="1"):
    ID = e.adhesion(personne, debut, fin, observations=A.MARQUEUR_AUTO)
    e.base.db.cursor.execute(
        "UPDATE cotisations SET activites=? WHERE IDcotisation=?", (chaine, ID))
    e.base.db.Commit()
    return ID


def activites(e, personne=100):
    return [row[0] for row in e.lire(
        "SELECT activites FROM cotisations WHERE IDindividu=%d ORDER BY date_debut, IDcotisation;"
        % personne)]


class ModeAssociationTests(unittest.TestCase):
    def test_defaut_est_inscriptions_sans_creer_parametre(self):
        with Env() as e:
            self.assertEqual(e.compte("parametres"), 0)
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_INSCRIPTIONS)
            self.assertEqual(e.compte("parametres"), 0)

    def test_configuration_par_type_et_persistance(self):
        with Env() as e:
            self.assertTrue(A.EnregistrerModeAssociation(1, A.MODE_ASSOCIATION_PARTICIPATIONS))
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_PARTICIPATIONS)
            self.assertEqual(e.compte("parametres"), 1)
            self.assertFalse(A.EnregistrerModeAssociation(1, A.MODE_ASSOCIATION_PARTICIPATIONS))
            self.assertTrue(A.EnregistrerModeAssociation(1, A.MODE_ASSOCIATION_INSCRIPTIONS))
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_INSCRIPTIONS)
            self.assertEqual(e.compte("parametres"), 1)
            self.assertEqual(A.LireModeAssociation(2), A.MODE_ASSOCIATION_INSCRIPTIONS)
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertEqual(e.compte("prestations"), 0)

    def test_mode_invalide_ou_double_fait_echouer_explicitement(self):
        with Env() as e:
            with self.assertRaises(ValueError):
                A.EnregistrerModeAssociation(1, "inconnu")
            e.base.inserer("parametres", ["categorie", "nom", "parametre"], [
                (A.CATEGORIE_MODE_ASSOCIATION, "type_1", "inconnu")])
            with self.assertRaises(A.ConfigurationAdhesionInvalide):
                A.LireModeAssociation(1)
            e.base.inserer("parametres", ["categorie", "nom", "parametre"], [
                (A.CATEGORIE_MODE_ASSOCIATION, "type_1", "inscriptions")])
            with self.assertRaises(A.ConfigurationAdhesionInvalide):
                A.LireModeAssociation(1)

    def test_reparation_d_une_valeur_inconnue(self):
        with Env() as e:
            e.base.inserer("parametres", ["categorie", "nom", "parametre"], [
                (A.CATEGORIE_MODE_ASSOCIATION, "type_1", "inconnu")])
            self.assertTrue(A.EnregistrerModeAssociation(1, A.MODE_ASSOCIATION_INSCRIPTIONS))
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_INSCRIPTIONS)
            self.assertEqual(e.compte("parametres"), 1)


class InscriptionsAutoTests(unittest.TestCase):
    def test_inscriptions_sans_participation_ne_creent_rien(self):
        with Env() as e:
            inscription(e, 1, activite=1)
            inscription(e, 2, activite=2)
            self.assertEqual(e.reconcilier(100, JOUR)["cotisations_creees"], [])
            self.assertEqual(E.Proposer(DEBUT, JOUR, date_reference=JOUR,
                                        liste_activites=[1, 2])["propositions"], [])
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertEqual(e.compte("prestations"), 0)

    def test_creation_facturee_une_fois_associe_tous_les_inscrits(self):
        with Env() as e:
            inscription(e, 1, activite=1)
            inscription(e, 2, activite=2)
            inscription(e, 3, activite=3)  # pas une activite declenchante
            e.conso(100, D(2026, 10, 7), activite=1)
            res = e.reconcilier(100, JOUR, D(2026, 10, 7))
            self.assertEqual(res["statut"], A.STATUT_CREE)
            self.assertEqual(activites(e), ["1;2;3"])
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)
            self.assertEqual(len(e.reconcilier(100, JOUR)["cotisations_creees"]), 0)

    def test_enrichissement_en_cours_d_annee_sans_facture_ni_duree(self):
        with Env() as e:
            ID = auto(e)
            inscription(e, 11, activite=2, debut=D(2026, 11, 1))
            avant = e.lire("SELECT IDcotisation, date_debut, date_fin, IDprestation FROM cotisations")
            self.assertEqual(A.ActualiserActivitesApresInscription(11, JOUR), [ID])
            self.assertEqual(activites(e), ["1;2"])
            self.assertEqual(e.lire("SELECT IDcotisation, date_debut, date_fin, IDprestation FROM cotisations"), avant)
            self.assertEqual(e.compte("prestations"), 0)
            self.assertEqual(e.compte("historique"), 1)
            self.assertEqual(A.ActualiserActivitesApresInscription(11, JOUR), [])
            inscription(e, 12, activite=2, groupe=9)
            self.assertEqual(A.ActualiserActivitesApresInscription(12, JOUR), [])
            self.assertEqual(e.compte("historique"), 1)

    def test_modes_alternatifs_par_type(self):
        with Env() as e:
            ID = auto(e)
            A.EnregistrerModeAssociation(1, A.MODE_ASSOCIATION_PARTICIPATIONS)
            inscription(e, 11, activite=2)
            self.assertEqual(A.ActualiserActivitesApresInscription(11, JOUR), [])
            self.assertEqual(activites(e), ["1"])
            e.conso(100, D(2026, 10, 8), activite=2)
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(activites(e), ["1;2"])
            self.assertEqual(e.compte("prestations"), 0)

    def test_inscriptions_refusees_et_hors_validite_exclues(self):
        with Env() as e:
            auto(e)
            inscription(e, 1, activite=2, debut=D(2027, 10, 1))
            inscription(e, 2, activite=3, debut=D(2025, 1, 1),
                        fin=D(2026, 8, 31))
            inscription(e, 3, activite=2, debut=D(2026, 10, 1), statut="refus")
            inscription(e, 4, activite=3, debut=D(2026, 10, 1), statut="attente")
            inscription(e, 5, activite=2, debut=D(2026, 10, 1),
                        fin=D(2026, 9, 30))
            self.assertEqual(A.ActualiserActivitesApresInscription(3, JOUR), [])
            self.assertEqual(A.CompleterActivitesAutomatiques(
                100, 100, A.ResoudreConfiguration(), JOUR), [])
            self.assertEqual(activites(e), ["1"])

    def test_chevauchement_inclusif_et_conservation_historique(self):
        with Env() as e:
            auto(e)
            inscription(e, 1, activite=2, debut=FIN, fin=FIN)
            self.assertEqual(A.ActualiserActivitesApresInscription(1, JOUR), [
                e.lire("SELECT IDcotisation FROM cotisations")[0][0]])
            self.assertEqual(activites(e), ["1;2"])
            e.base.db.cursor.execute("UPDATE inscriptions SET statut='refus' WHERE IDinscription=1")
            e.base.db.Commit()
            self.assertEqual(A.ActualiserActivitesApresInscription(1, JOUR), [])
            self.assertEqual(activites(e), ["1;2"])

    def test_manuelle_intouchable(self):
        with Env() as e:
            ID = e.adhesion(100, DEBUT, FIN, observations="saisie manuelle")
            e.base.db.cursor.execute("UPDATE cotisations SET activites='1' WHERE IDcotisation=?", (ID,))
            e.base.db.Commit()
            inscription(e, 1, activite=2)
            avant = e.lire("SELECT * FROM cotisations")
            self.assertEqual(A.ActualiserActivitesApresInscription(1, JOUR), [])
            self.assertEqual(e.lire("SELECT * FROM cotisations"), avant)
            self.assertEqual(e.compte("prestations"), 0)

    def test_structures_distinctes_ne_se_contaminent_pas(self):
        with Env() as e:
            completer(e)
            auto(e, personne=200, chaine=None)
            auto(e, personne=210, chaine=None)
            inscription(e, 1, personne=201, activite=1, payeur=12, famille=2)
            inscription(e, 2, personne=202, activite=2, payeur=12, famille=2)
            inscription(e, 3, personne=211, activite=3, payeur=14, famille=4)
            self.assertEqual(A.ActualiserActivitesApresInscription(1, JOUR),
                             [e.lire("SELECT IDcotisation FROM cotisations WHERE IDindividu=200")[0][0]])
            self.assertEqual(activites(e, 200), ["1;2"])
            self.assertEqual(activites(e, 210), [None])
            self.assertEqual(len(A.ActualiserActivitesApresInscription(3, JOUR)), 1)
            self.assertEqual(activites(e, 200), ["1;2"])
            self.assertEqual(activites(e, 210), ["3"])
            self.assertEqual(e.compte("prestations"), 0)

    def test_periode_de_gestion_verrouillee_bloque_modification(self):
        with Env() as e:
            auto(e)
            inscription(e, 1, activite=2)
            e.base.inserer("periodes_gestion",
                           ["date_debut", "date_fin", "verrou_cotisations"],
                           [("2026-09-01", "2026-09-30", 1)])
            self.assertEqual(A.ActualiserActivitesApresInscription(1, JOUR), [])
            self.assertEqual(activites(e), ["1"])

    def test_aucun_appel_financier_depuis_evenement_inscription(self):
        with Env() as e:
            auto(e)
            inscription(e, 1, activite=2)
            with mock.patch.object(A, "CreerAdhesion", side_effect=AssertionError("facture interdite")):
                self.assertEqual(len(A.ActualiserActivitesApresInscription(1, JOUR)), 1)
            self.assertEqual(e.compte("prestations"), 0)

if __name__ == "__main__":
    unittest.main()
