# -*- coding: utf-8 -*-
"""Titulaire de l'adhésion automatique.

- Structure adhérente (association...) : UNE adhésion pour la structure,
  portée par sa personne morale titulaire, quelles que soient les sections,
  activités ou représentants qui participent.
- Famille de personnes physiques : UNE adhésion par personne qui participe,
  couvrant toutes ses activités, jamais commune à toute la famille.

Base SQLite temporaire uniquement, données fictives.
"""
import datetime
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _garde_reseau  # noqa: E402,F401

from test_noethys_sl_adhesions import Env  # noqa: E402
from test_noethys_sl_adhesions_concurrence import _Concurrence  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402

D = datetime.date
JOUR = D(2026, 10, 1)

# Données ajoutées à la base de test_noethys_sl_adhesions :
#   famille 2 = « ASSOCIATION TEST » (individu 200, civilité 6, titulaire),
#               sections 201 et 202, représentant 203 (personne physique) ;
#   famille 4 = « CLUB AUTRE » (individu 210, civilité 7, titulaire), section 211 ;
#   famille 5 = parent 500 (titulaire), enfants 501 et 502 ;
#   famille 6 = deux personnes morales titulaires (titulaire ambigu), section 611.
INDIVIDUS = [
    (201, "SECTION FOOT", "", 7), (202, "SECTION DANSE", "", 7), (203, "PRESIDENT", "Paul", 1),
    (210, "CLUB AUTRE", "", 7), (211, "SECTION JUDO", "", 7),
    (500, "PARENT", "Lea", 3), (501, "ENFANT", "Arthur", 4), (502, "ENFANT", "Lina", 5),
    (600, "STRUCTURE A", "", 6), (601, "STRUCTURE B", "", 8), (611, "SECTION X", "", 7),
]
RATTACHEMENTS = [
    (20, 2, 201, 2, 0), (21, 2, 202, 2, 0), (22, 2, 203, 1, 1),
    (40, 4, 210, 1, 1), (41, 4, 211, 2, 0),
    (50, 5, 500, 1, 1), (51, 5, 501, 2, 0), (52, 5, 502, 2, 0),
    (60, 6, 600, 1, 1), (61, 6, 601, 1, 1), (62, 6, 611, 2, 0),
]
COMPTES = [(14, 4), (15, 5), (16, 6)]  # (IDcompte_payeur, IDfamille) ; famille 2 -> 12 existant


def completer(e):
    e.base.inserer("familles", ["IDfamille"], [(4,), (5,), (6,)])
    e.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], COMPTES)
    e.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], INDIVIDUS)
    e.base.inserer("rattachements", ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"], RATTACHEMENTS)


class TitulaireTests(unittest.TestCase):

    def _bilan(self, e):
        cotisations = e.lire("SELECT IDindividu, date_debut FROM cotisations ORDER BY IDindividu, date_debut;")
        prestations = e.lire("""SELECT IDindividu, IDfamille, IDcompte_payeur, montant FROM prestations
                                WHERE categorie='cotisation' ORDER BY IDindividu;""")
        liens = e.lire("""SELECT COUNT(*) FROM cotisations c JOIN prestations p ON p.IDprestation = c.IDprestation
                          WHERE p.IDindividu = c.IDindividu;""")[0][0]
        self.assertEqual(liens, len(cotisations))  # chaque adhésion a sa prestation, au même titulaire
        return cotisations, prestations

    def test_association_plusieurs_sections_et_activites_une_seule_adhesion(self):
        with Env() as e:
            completer(e)
            e.conso(201, D(2026, 10, 7), activite=1, payeur=12)
            e.conso(202, D(2026, 10, 8), activite=2, payeur=12)
            e.conso(200, D(2026, 10, 9), activite=1, payeur=12)
            for ID in (201, 202, 200):
                A.ReconcilierIndividu(ID, date_reference=JOUR, depuis=D(2026, 10, 7))
            A.ReconcilierIndividus([201, 202, 203, 200], date_reference=JOUR, depuis=D(2026, 10, 7))
            cotisations, prestations = self._bilan(e)
            self.assertEqual(cotisations, [(200, "2026-10-07")])
            self.assertEqual(prestations, [(200, 2, 12, 7.5)])

    def test_personne_plusieurs_activites_une_seule_adhesion(self):
        with Env() as e:
            completer(e)
            e.conso(100, D(2026, 10, 7), activite=1)
            e.conso(100, D(2026, 10, 8), activite=2)
            A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
            cotisations, prestations = self._bilan(e)
            self.assertEqual(cotisations, [(100, "2026-10-07")])
            self.assertEqual(len(prestations), 1)

    def test_deux_enfants_meme_famille_une_adhesion_chacun(self):
        with Env() as e:
            completer(e)
            e.conso(501, D(2026, 10, 7), activite=1, payeur=15)
            e.conso(501, D(2026, 10, 9), activite=2, payeur=15)
            e.conso(502, D(2026, 10, 8), activite=1, payeur=15)
            A.ReconcilierIndividus([501, 502], date_reference=JOUR, depuis=D(2026, 10, 7))
            A.ReconcilierIndividus([501, 502], date_reference=JOUR, depuis=D(2026, 10, 7))
            cotisations, prestations = self._bilan(e)
            self.assertEqual(cotisations, [(501, "2026-10-07"), (502, "2026-10-08")])
            self.assertEqual([(p[0], p[1], p[2]) for p in prestations], [(501, 5, 15), (502, 5, 15)])
            self.assertEqual(e.compte("cotisations", "IDindividu=500 OR IDindividu IS NULL"), 0)

    def test_deux_associations_distinctes_deux_adhesions(self):
        with Env() as e:
            completer(e)
            e.conso(201, D(2026, 10, 7), payeur=12)
            e.conso(211, D(2026, 10, 7), payeur=14)
            A.ReconcilierIndividus([201, 211], date_reference=JOUR, depuis=D(2026, 10, 7))
            cotisations, prestations = self._bilan(e)
            self.assertEqual(cotisations, [(200, "2026-10-07"), (210, "2026-10-07")])
            self.assertEqual([(p[0], p[1], p[2]) for p in prestations], [(200, 2, 12), (210, 4, 14)])

    def test_adhesion_existante_de_la_structure_couvre_ses_sections(self):
        with Env() as e:
            completer(e)
            e.adhesion(200, D(2026, 9, 1), D(2027, 8, 31), observations="saisie manuelle")
            e.conso(202, D(2026, 10, 8), activite=2, payeur=12)
            res = A.ReconcilierIndividu(202, date_reference=JOUR, depuis=D(2026, 10, 8))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 1)

    def test_chevauchement_et_signalement_au_nom_de_la_structure(self):
        with Env() as e:
            completer(e)
            e.adhesion(200, D(2027, 1, 1), D(2028, 1, 1), observations="saisie manuelle")
            e.conso(201, D(2026, 10, 7), payeur=12)
            res = A.ReconcilierSansEchec([201], date_reference=JOUR, depuis=D(2026, 10, 7))
            self.assertEqual((res[201]["statut"], res[201]["motif"], res[201]["IDtitulaire"]),
                             (A.STATUT_A_VERIFIER, "chevauchement", 200))
            message = A.MessagesAVerifier(res)[0]
            self.assertIn(u"ASSOCIATION TEST (participation de SECTION FOOT)", message)
            self.assertEqual(e.compte("cotisations"), 1)

    def test_une_seule_adhesion_a_venir_pour_la_structure(self):
        with Env() as e:
            completer(e)
            e.adhesion(200, D(2026, 12, 1), D(2027, 12, 1), observations="saisie manuelle")
            e.conso(211, D(2027, 1, 5), payeur=14)       # autre association : non concernée
            e.conso(202, D(2028, 1, 10), payeur=12)      # section : au-delà de l'adhésion à venir
            res = A.ReconcilierIndividu(202, date_reference=JOUR, depuis=JOUR)
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_RIEN, "adhesion_a_venir_existante"))
            res = A.ReconcilierIndividu(211, date_reference=JOUR, depuis=JOUR)
            self.assertEqual(res["statut"], A.STATUT_CREE)
            self.assertEqual(e.lire("SELECT IDindividu FROM cotisations ORDER BY IDcotisation;"), [(200,), (210,)])

    def test_titulaire_ambigu_a_verifier(self):
        with Env() as e:
            completer(e)
            e.conso(611, D(2026, 10, 7), payeur=16)
            res = A.ReconcilierIndividu(611, date_reference=JOUR, depuis=D(2026, 10, 7))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "titulaire_ambigu"))
            self.assertEqual(e.compte("cotisations"), 0)


class ConcurrenceSectionsTests(_Concurrence, unittest.TestCase):

    def test_deux_sections_simultanees_une_seule_adhesion_de_la_structure(self):
        with Env() as e:
            completer(e)
            e.conso(201, D(2026, 10, 7), payeur=12)
            e.conso(202, D(2026, 10, 7), activite=2, payeur=12)
            b_bloque, resultats = self.lancer("sqlite", e.base.chemin, individus=(201, 202))
            self.assertTrue(b_bloque)
            self.assertEqual(sorted(r["statut"] for r in resultats.values()), [A.STATUT_CREE, A.STATUT_RIEN])
            self.assertEqual(e.lire("SELECT IDindividu FROM cotisations;"), [(200,)])
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)


if __name__ == "__main__":
    unittest.main()
