# -*- coding: utf-8 -*-
"""Tests de l'adhésion annuelle automatique (Utils.UTILS_Adhesions).

Base SQLite temporaire uniquement (RedirectionGestionDB) : aucune écriture
sur la vraie base. Le service est non-wx : aucune pile wx n'est chargée.
"""

import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Utils import UTILS_Adhesions as A  # noqa: E402

D = datetime.date

TABLES = (
    "individus", "familles", "rattachements", "comptes_payeurs", "activites", "inscriptions",
    "consommations", "prestations", "ventilation", "types_cotisations", "unites_cotisations",
    "cotisations", "cotisations_activites", "periodes_gestion", "historique",
)


def creer_base(montant=7.5, activites_liees=(1, 2)):
    base = BaseTest()
    for nom in TABLES:
        if not base.db.IsTableExists(nom):
            base.db.CreationTable(nom, dicoDB=Tables.DB_DATA)
    base.db.Commit()
    base.inserer("familles", ["IDfamille"], [(1,), (2,), (3,)])
    base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(11, 1), (12, 2), (13, 3)])
    base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], [
        (100, "DUPUIS", "Jean", 1), (200, "ASSOCIATION TEST", "", 6), (300, "MARTIN", "Alice", 1)])
    # 100 : famille 1 ; 200 (personne morale) : famille 2 ; 300 : deux familles (ambigu)
    base.inserer("rattachements", ["IDrattachement", "IDfamille", "IDindividu", "IDcategorie", "titulaire"], [
        (1, 1, 100, 2, 0), (2, 2, 200, 1, 1), (3, 1, 300, 2, 0), (4, 3, 300, 2, 0)])
    base.inserer("activites", ["IDactivite", "nom"], [(1, "Activite A"), (2, "Activite B"), (3, "Activite hors adhesion")])
    base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"], [
        (1, "Adhesion annuelle", "individu", 0, 1)])
    base.inserer("unites_cotisations",
                 ["IDunite_cotisation", "IDtype_cotisation", "date_debut", "date_fin", "nom", "montant", "label_prestation", "defaut", "duree"], [
        (11, 1, None, None, "Adhesion individuelle", montant, None, 1, "j0-m0-a1"),
        (12, 1, "2025-09-01", "2026-08-31", "Saison fixe", 20.0, None, 0, None)])
    base.inserer("cotisations_activites", ["IDactivite", "IDtype_cotisation"], [(a, 1) for a in activites_liees])
    return base


class Env:
    """Base + redirection ; helpers de lecture/écriture."""

    def __init__(self, **kw):
        self.base = creer_base(**kw)
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self._seq = 1000

    def __enter__(self):
        self.redirection.__enter__()
        return self

    def __exit__(self, *exc):
        self.redirection.__exit__(*exc)
        self.base.fermer()

    def conso(self, individu, date, activite=1, etat="reservation", payeur=11, inscription=None):
        self._seq += 1
        self.base.inserer("consommations",
                          ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "etat", "IDcompte_payeur", "IDinscription"],
                          [(self._seq, individu, activite, str(date), 1, etat, payeur, inscription)])
        return self._seq

    def supprimer_conso(self, IDconso):
        self.base.db.ExecuterReq("DELETE FROM consommations WHERE IDconso=%d;" % IDconso)
        self.base.db.Commit()

    def prestation(self, individu, date, activite=1, payeur=11, categorie="consommation", IDfacture=None):
        self._seq += 1
        self.base.inserer("prestations",
                          ["IDprestation", "IDcompte_payeur", "date", "categorie", "label", "montant", "IDindividu", "IDactivite", "IDfacture"],
                          [(self._seq, payeur, str(date), categorie, "p", 10.0, individu, activite, IDfacture)])
        return self._seq

    def adhesion(self, individu, debut, fin, unite=11, observations=None, IDprestation=None):
        self._seq += 1
        self.base.inserer("cotisations",
                          ["IDcotisation", "IDindividu", "IDtype_cotisation", "IDunite_cotisation", "date_debut", "date_fin", "observations", "IDprestation"],
                          [(self._seq, individu, 1, unite, str(debut), str(fin), observations, IDprestation)])
        return self._seq

    def lire(self, req):
        self.base.db.ExecuterReq(req)
        return self.base.db.ResultatReq()

    def compte(self, table, where="1=1"):
        return self.lire("SELECT COUNT(*) FROM %s WHERE %s;" % (table, where))[0][0]

    def reconcilier(self, individu, jour, depuis=None):
        return A.ReconcilierIndividu(individu, date_reference=jour, depuis=depuis or jour)


class AdhesionsTests(unittest.TestCase):

    # 1
    def test_premiere_reservation_cree_adhesion_cotisation_prestation_historique(self):
        with Env() as e:
            e.conso(100, D(2026, 6, 15))
            res = e.reconcilier(100, D(2026, 6, 15))
            self.assertEqual(res["statut"], A.STATUT_CREE)
            self.assertEqual(len(res["cotisations_creees"]), 1)
            ligne = e.lire("SELECT IDindividu, IDfamille, IDtype_cotisation, IDunite_cotisation, date_debut, date_fin, IDprestation, date_saisie FROM cotisations;")
            self.assertEqual(len(ligne), 1)
            IDindividu, IDfamille, IDtype, IDunite, debut, fin, IDprestation, date_saisie = ligne[0]
            self.assertEqual((IDindividu, IDfamille, IDtype, IDunite), (100, None, 1, 11))
            self.assertEqual((debut, fin, date_saisie), ("2026-06-15", "2027-06-15", "2026-06-15"))
            pres = e.lire("SELECT IDcompte_payeur, categorie, montant, montant_initial, IDfamille, IDindividu, date, date_valeur, label FROM prestations WHERE IDprestation=%d;" % IDprestation)
            self.assertEqual(pres[0][:6], (11, "cotisation", 7.5, 7.5, 1, 100))
            self.assertEqual(pres[0][6:8], ("2026-06-15", "2026-06-15"))
            self.assertEqual(pres[0][8], "Adhesion annuelle - Adhesion individuelle")
            histo = e.lire("SELECT IDindividu, IDcategorie, action FROM historique;")
            self.assertEqual(len(histo), 1)
            self.assertEqual(histo[0][:2], (100, 21))
            self.assertIn("du 15/06/2026 au 15/06/2027", histo[0][2])

    # 2
    def test_adhesion_valide_ne_cree_rien(self):
        with Env() as e:
            e.adhesion(100, D(2026, 1, 10), D(2027, 1, 10))
            e.conso(100, D(2026, 6, 15))
            res = e.reconcilier(100, D(2026, 6, 15))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 0)

    # 3
    def test_date_fin_plus_un_an_sans_retirer_un_jour(self):
        self.assertEqual(A.CalculerDateFin(D(2026, 6, 15), "j0-m0-a1"), D(2027, 6, 15))
        self.assertEqual(A.CalculerDateFin("2026-06-15", "j0-m0-a1"), D(2027, 6, 15))
        self.assertEqual(A.CalculerDateFin(D(2026, 6, 15), "j0-m6-a0"), D(2026, 12, 15))
        with self.assertRaises(A.ConfigurationAdhesionInvalide):
            A.CalculerDateFin(D(2026, 6, 15), "n'importe quoi")

    # 4
    def test_fin_incluse_et_nouvelle_adhesion_le_lendemain(self):
        with Env() as e:
            e.adhesion(100, D(2026, 6, 15), D(2027, 6, 15))
            self.assertIsNotNone(A.GetAdhesionValide(100, D(2026, 6, 15), 1))
            self.assertIsNotNone(A.GetAdhesionValide(100, D(2027, 6, 15), 1))
            self.assertIsNone(A.GetAdhesionValide(100, D(2027, 6, 16), 1))
            self.assertIsNone(A.GetAdhesionValide(100, D(2026, 6, 14), 1))
            e.conso(100, D(2027, 6, 15))
            self.assertEqual(e.reconcilier(100, D(2027, 6, 15))["statut"], A.STATUT_RIEN)
            e.conso(100, D(2027, 6, 16))
            res = e.reconcilier(100, D(2027, 6, 16))
            self.assertEqual(res["statut"], A.STATUT_CREE)
            debut, fin = e.lire("SELECT date_debut, date_fin FROM cotisations ORDER BY date_debut DESC;")[0]
            self.assertEqual((debut, fin), ("2027-06-16", "2028-06-16"))

    # 5
    def test_pas_de_renouvellement_sans_participation(self):
        with Env() as e:
            e.adhesion(100, D(2026, 6, 15), D(2027, 6, 15))
            res = e.reconcilier(100, D(2028, 1, 1))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertIsNone(A.GetProchaineDateDeclenchante(100, A.ResoudreConfiguration(), date_reference=D(2028, 1, 1)))
            self.assertEqual(A.GetDerniereAdhesion(100, 1)["date_fin"], D(2027, 6, 15))

    # 6
    def test_plusieurs_activites_une_seule_adhesion(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1), activite=1)
            e.conso(100, D(2026, 9, 1), activite=2)
            e.conso(100, D(2026, 9, 2), activite=2)
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(len(res["cotisations_creees"]), 1)
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)

    # 7
    def test_plusieurs_participations_dans_l_annee_une_seule_adhesion(self):
        with Env() as e:
            for mois in (9, 10, 11, 12):
                e.conso(100, D(2026, mois, 3))
            e.conso(100, D(2027, 2, 3))
            res = e.reconcilier(100, D(2026, 9, 3))
            self.assertEqual(len(res["cotisations_creees"]), 1)
            self.assertEqual(e.compte("cotisations"), 1)

    # 8
    def test_personne_morale_meme_regle(self):
        with Env() as e:
            e.conso(200, D(2026, 9, 1), payeur=12)
            e.conso(200, D(2026, 9, 8), payeur=12, activite=2)
            res = e.reconcilier(200, D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_CREE)
            self.assertEqual(e.compte("cotisations", "IDindividu=200"), 1)
            self.assertEqual(e.lire("SELECT IDcompte_payeur FROM prestations WHERE categorie='cotisation';")[0][0], 12)

    # 9
    def test_idempotence_deux_executions(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1))
            r1 = e.reconcilier(100, D(2026, 9, 1))
            r2 = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(r1["statut"], A.STATUT_CREE)
            self.assertEqual(r2["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)
            self.assertEqual(e.compte("historique"), 1)

    def test_recheck_dans_creer_adhesion_empeche_le_doublon(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1))
            config = A.ResoudreConfiguration()
            participation = A.GetProchaineDateDeclenchante(100, config, date_reference=D(2026, 9, 1))
            e.adhesion(100, D(2026, 8, 1), D(2027, 8, 1))  # apparue entre-temps
            res = A.CreerAdhesion(100, participation, config, date_reference=D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 1)

    # 10
    def test_etats_non_participants_et_simple_inscription_ne_declenchent_pas(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1), etat="absentj")
            e.conso(100, D(2026, 9, 2), etat="attente")
            e.conso(100, D(2026, 9, 3), etat="refus")
            e.base.inserer("inscriptions", ["IDinscription", "IDindividu", "IDfamille", "IDactivite", "IDgroupe", "IDcategorie_tarif", "IDcompte_payeur", "date_inscription"],
                           [(1, 100, 1, 1, 1, 1, 11, "2026-09-01")])
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 0)

    def test_present_declenche(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1), etat="present")
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_CREE)

    # 11
    def test_activite_non_liee_ne_declenche_pas(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1), activite=3)
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 0)

    # 12
    def test_prestation_sans_consommation_declenche_sinon_pas_de_double(self):
        with Env() as e:
            e.prestation(100, D(2026, 9, 1))
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_CREE)
        with Env() as e:
            e.conso(100, D(2026, 9, 1))
            e.prestation(100, D(2026, 9, 1))
            parts = A.GetParticipations(100, [1], D(2026, 9, 1))
            self.assertEqual([p["source"] for p in parts], ["consommation"])
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(len(res["cotisations_creees"]), 1)
        with Env() as e:  # une prestation 'cotisation' n'est pas une participation
            e.prestation(100, D(2026, 9, 1), categorie="cotisation")
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_RIEN)

    # 13
    def test_montant_lu_en_configuration(self):
        with Env(montant=9.25) as e:
            e.conso(100, D(2026, 9, 1))
            e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(e.lire("SELECT montant, montant_initial FROM prestations WHERE categorie='cotisation';")[0], (9.25, 9.25))
        source = (NOETHYS / "Utils" / "UTILS_Adhesions.py").read_text(encoding="utf-8")
        self.assertNotIn("7.5", source)
        self.assertNotIn("IDtype_cotisation=1", source)
        self.assertNotIn("wx", [l.split()[1] for l in source.splitlines() if l.startswith("import ")])

    # 14
    def test_periode_de_gestion_verrouillee(self):
        with Env() as e:
            e.base.inserer("periodes_gestion", ["IDperiode", "date_debut", "date_fin", "verrou_prestations", "verrou_cotisations"],
                           [(1, "2026-01-01", "2026-12-31", 0, 1)])
            e.conso(100, D(2026, 9, 1))
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "periode_verrouillee"))
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 0)

    # 15
    def test_payeur_conso_sinon_inscription_sinon_famille_unique_sinon_a_verifier(self):
        with Env() as e:  # payeur NULL sur la conso, famille unique
            e.conso(100, D(2026, 9, 1), payeur=None)
            e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(e.lire("SELECT IDcompte_payeur, IDfamille FROM prestations WHERE categorie='cotisation';")[0], (11, 1))
        with Env() as e:  # payeur de l'inscription
            e.base.inserer("inscriptions", ["IDinscription", "IDindividu", "IDfamille", "IDactivite", "IDgroupe", "IDcategorie_tarif", "IDcompte_payeur", "date_inscription"],
                           [(5, 300, 3, 1, 1, 1, 13, "2026-09-01")])
            e.conso(300, D(2026, 9, 1), payeur=None, inscription=5)
            e.reconcilier(300, D(2026, 9, 1))
            self.assertEqual(e.lire("SELECT IDcompte_payeur, IDfamille FROM prestations WHERE categorie='cotisation';")[0], (13, 3))
        with Env() as e:  # deux familles, aucun payeur : jamais de choix arbitraire
            e.conso(300, D(2026, 9, 1), payeur=None)
            res = e.reconcilier(300, D(2026, 9, 1))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "payeur_indeterminable"))
            self.assertEqual(e.compte("cotisations"), 0)

    def test_adhesion_a_dates_fixes_existante_couvre(self):
        with Env() as e:
            e.adhesion(100, D(2025, 9, 1), D(2026, 8, 31), unite=12)
            e.conso(100, D(2026, 3, 1))
            self.assertEqual(e.reconcilier(100, D(2026, 3, 1))["statut"], A.STATUT_RIEN)
            e.conso(100, D(2026, 9, 1))
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_CREE)

    def test_pas_de_retro_creation_avant_depuis(self):
        with Env() as e:
            e.conso(100, D(2025, 1, 10))
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 0)

    def test_participation_apres_expiration_cree_a_la_date_de_participation(self):
        with Env() as e:
            e.adhesion(100, D(2025, 9, 1), D(2026, 9, 1))
            e.conso(100, D(2026, 9, 1))   # couverte (fin incluse)
            e.conso(100, D(2026, 10, 5))  # première non couverte
            e.conso(100, D(2026, 11, 5))
            res = A.ReconcilierIndividu(100, date_reference=D(2026, 11, 20), depuis=D(2026, 9, 1))
            self.assertEqual(len(res["cotisations_creees"]), 1)
            self.assertEqual(e.lire("SELECT date_debut FROM cotisations ORDER BY date_debut DESC;")[0][0], "2026-10-05")

    def test_configuration_invalide_ne_cree_rien(self):
        with Env() as e:
            e.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"], [(2, "Autre", "individu", 0, 1)])
            e.conso(100, D(2026, 9, 1))
            res = e.reconcilier(100, D(2026, 9, 1))
            self.assertEqual(res["statut"], A.STATUT_CONFIG_INVALIDE)
            self.assertEqual(e.compte("cotisations"), 0)
        with Env() as e:  # unité sans durée : refusée
            e.base.db.ExecuterReq("UPDATE unites_cotisations SET duree=NULL WHERE IDunite_cotisation=11;")
            e.base.db.Commit()
            e.conso(100, D(2026, 9, 1))
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_CONFIG_INVALIDE)
            self.assertEqual(e.compte("cotisations"), 0)
        with Env() as e:  # type famille : refusé
            e.base.db.ExecuterReq("UPDATE types_cotisations SET type='famille';")
            e.base.db.Commit()
            self.assertEqual(e.reconcilier(100, D(2026, 9, 1))["statut"], A.STATUT_CONFIG_INVALIDE)

    def test_liste_d_individus_dedoublonnee(self):
        with Env() as e:
            e.conso(100, D(2026, 9, 1))
            e.conso(200, D(2026, 9, 1), payeur=12)
            res = A.ReconcilierIndividus([100, 200, 100, 200], date_reference=D(2026, 9, 1), depuis={100: D(2026, 9, 1), 200: D(2026, 9, 1)})
            self.assertEqual(sorted(res), [100, 200])
            self.assertEqual(e.compte("cotisations"), 2)
            self.assertEqual(A.ReconcilierSansEchec([100, 200], date_reference=D(2026, 9, 1), depuis=D(2026, 9, 1))[100]["statut"], A.STATUT_RIEN)
            self.assertEqual(e.compte("cotisations"), 2)

    # --- Annulation prudente -------------------------------------------------

    def _adhesion_auto(self, e):
        c = e.conso(100, D(2026, 9, 1))
        e.reconcilier(100, D(2026, 9, 1))
        return c

    def test_une_reservation_disparait_une_autre_reste_adhesion_conservee(self):
        with Env() as e:
            c1 = self._adhesion_auto(e)
            e.conso(100, D(2026, 10, 1), activite=2)
            e.supprimer_conso(c1)
            res = e.reconcilier(100, D(2026, 10, 2))
            self.assertEqual(res["a_verifier"], [])
            self.assertEqual(e.compte("cotisations"), 1)

    def test_toutes_participations_disparues_non_facturee_a_verifier_sans_delete(self):
        with Env() as e:
            c1 = self._adhesion_auto(e)
            avant = (e.compte("cotisations"), e.compte("prestations"), e.compte("historique"))
            e.supprimer_conso(c1)
            res = e.reconcilier(100, D(2026, 9, 2))
            self.assertEqual([(x["statut"], x["motif"]) for x in res["a_verifier"]], [(A.STATUT_A_VERIFIER, "non_demontrable")])
            self.assertEqual((e.compte("cotisations"), e.compte("prestations"), e.compte("historique")), avant)

    def test_toutes_participations_disparues_facturee_ou_reglee_aucune_suppression(self):
        with Env() as e:
            c1 = self._adhesion_auto(e)
            IDprestation = e.lire("SELECT IDprestation FROM cotisations;")[0][0]
            e.base.db.ExecuterReq("UPDATE prestations SET IDfacture=5 WHERE IDprestation=%d;" % IDprestation)
            e.base.db.Commit()
            e.supprimer_conso(c1)
            res = e.reconcilier(100, D(2026, 9, 2))
            self.assertEqual(res["a_verifier"][0]["motif"], "facturee_ou_reglee")
            self.assertEqual(e.compte("cotisations"), 1)
        with Env() as e:
            c1 = self._adhesion_auto(e)
            IDprestation = e.lire("SELECT IDprestation FROM cotisations;")[0][0]
            e.base.inserer("ventilation", ["IDcompte_payeur", "IDreglement", "IDprestation", "montant"], [(11, 1, IDprestation, 7.5)])
            e.supprimer_conso(c1)
            self.assertEqual(e.reconcilier(100, D(2026, 9, 2))["a_verifier"][0]["motif"], "facturee_ou_reglee")
            self.assertEqual(e.compte("cotisations"), 1)

    def test_adhesion_manuelle_non_evaluee(self):
        with Env() as e:
            e.adhesion(100, D(2026, 1, 1), D(2027, 1, 1), observations="saisie manuelle")
            self.assertEqual(A.EvaluerAdhesionsAutomatiques(100), [])

    def test_service_sans_delete(self):
        source = (NOETHYS / "Utils" / "UTILS_Adhesions.py").read_text(encoding="utf-8")
        self.assertNotIn("DELETE", source.upper().replace("EVALUERADHESIONSAUTOMATIQUES", ""))
        self.assertNotIn("ReqDEL", source)

    # --- Point d'appel -------------------------------------------------------

    def test_point_d_appel_unique_dans_la_sauvegarde_de_la_grille(self):
        source = (NOETHYS / "Ctrl" / "CTRL_Grille.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("UTILS_Adhesions.ReconcilierSansEchec"), 1)
        sauvegarde = source.split("    def Sauvegarde(self):")[1].split("    def SauvegardeTransports")[0]
        self.assertIn("UTILS_Adhesions.ReconcilierSansEchec", sauvegarde)
        self.assertGreater(sauvegarde.index("UTILS_Adhesions.ReconcilierSansEchec"), sauvegarde.rindex("DB.Close()") - 1)

    def test_import_sans_wx(self):
        self.assertNotIn("wx", sys.modules.get("Utils.UTILS_Adhesions").__dict__)

    # --- Chevauchements et anticipation (deux adhésions 7,50 € du 01/10/2026) ---

    def _periodes(self, e):
        return e.lire("SELECT date_debut, date_fin FROM cotisations ORDER BY date_debut;")

    def test_reservation_anterieure_a_l_adhesion_creee_ne_cree_pas_de_chevauchement(self):
        jour = D(2026, 10, 1)
        with Env() as e:
            e.conso(100, D(2026, 10, 14))
            self.assertEqual(A.ReconcilierIndividu(100, date_reference=jour, depuis=D(2026, 10, 14))["statut"], A.STATUT_CREE)
            e.conso(100, D(2026, 10, 7))  # seconde sauvegarde le même jour
            res = A.ReconcilierIndividu(100, date_reference=jour, depuis=D(2026, 10, 7))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "chevauchement"))
            self.assertEqual(self._periodes(e), [("2026-10-14", "2027-10-14")])
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)

    def test_adhesion_future_manuelle_n_est_pas_chevauchee(self):
        with Env() as e:
            e.adhesion(100, D(2027, 1, 1), D(2028, 1, 1), observations="saisie manuelle")
            e.conso(100, D(2026, 10, 7))
            res = A.ReconcilierIndividu(100, date_reference=D(2026, 10, 1), depuis=D(2026, 10, 7))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "chevauchement"))
            self.assertEqual(e.compte("cotisations"), 1)

    def test_adhesion_2027_creee_puis_reservation_2026_reste_a_verifier(self):
        jour = D(2026, 10, 1)
        with Env() as e:
            e.conso(100, D(2027, 2, 15))
            self.assertEqual(A.ReconcilierIndividu(100, date_reference=jour, depuis=D(2027, 2, 15))["statut"], A.STATUT_CREE)
            e.conso(100, D(2026, 10, 7))
            res = A.ReconcilierIndividu(100, date_reference=jour, depuis=D(2026, 10, 7))
            self.assertEqual(res["statut"], A.STATUT_A_VERIFIER)
            self.assertEqual(self._periodes(e), [("2027-02-15", "2028-02-15")])

    def test_au_plus_une_adhesion_a_venir(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            e.conso(100, D(2027, 10, 20))
            res = A.ReconcilierIndividu(100, date_reference=D(2026, 10, 1), depuis=D(2026, 10, 7))
            self.assertEqual(len(res["cotisations_creees"]), 1)
            self.assertEqual(res["motif"], "adhesion_a_venir_existante")
            self.assertEqual(self._periodes(e), [("2026-10-07", "2027-10-07")])
            # Une réconciliation ultérieure, l'adhésion commencée, traite la participation suivante.
            res = A.ReconcilierIndividu(100, date_reference=D(2027, 10, 15), depuis=D(2027, 10, 15))
            self.assertEqual(len(res["cotisations_creees"]), 1)
            self.assertEqual(self._periodes(e), [("2026-10-07", "2027-10-07"), ("2027-10-20", "2028-10-20")])

    def test_adhesion_a_venir_permise_apres_une_adhesion_en_cours(self):
        with Env() as e:
            e.adhesion(100, D(2025, 11, 15), D(2026, 11, 15), observations="saisie manuelle")
            e.conso(100, D(2026, 11, 20))
            res = A.ReconcilierIndividu(100, date_reference=D(2026, 10, 1), depuis=D(2026, 10, 1))
            self.assertEqual(res["statut"], A.STATUT_CREE)
            self.assertEqual(self._periodes(e)[-1], ("2026-11-20", "2027-11-20"))

    def test_meme_demande_repetee_une_seule_adhesion(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            for _ in range(3):
                A.ReconcilierIndividu(100, date_reference=D(2026, 10, 1), depuis=D(2026, 10, 7))
            self.assertEqual(e.compte("cotisations"), 1)
            self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)


if __name__ == "__main__":
    unittest.main()
