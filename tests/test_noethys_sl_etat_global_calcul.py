# -*- coding: utf-8 -*-
"""Caractérisation de CalculateurEtatGlobal.CalculerEtatGlobal (noethys/Dlg/DLG_Etat_global.py).

Contexte : ce calcul était auparavant imbriqué dans Dialog.Apercu(), couplé
à la génération du PDF. Il a été extrait dans une classe autonome
CalculateurEtatGlobal, indépendante de tout wx.Dialog (appelable sans
instancier Dialog -- ex. par un futur appelant AFAS), SANS changer sa
sémantique ni ses résultats -- ces tests verrouillent ce comportement
existant (caractérisation), pas une nouvelle règle métier.

CalculateurEtatGlobal reste volontairement un point d'ancrage de
self.dict_unites et appelle self.Calcule_formule() (même mécanisme
qu'avant, simplement déplacé hors de Dialog) : ces tests construisent donc
une instance de CalculateurEtatGlobal() (aucun widget wx créé, aucun
wx.App nécessaire) et appellent CalculerEtatGlobal() directement avec des
paramètres explicites -- exactement le contrat d'entrée visé par
l'extraction.

Généricité : aucun test ici ne code en dur une hypothèse "ALSH enfants"
uniquement -- un scénario dédié (MultiActiviteTests) exerce délibérément
deux IDactivite distincts (ALSH enfants + ALSH ados) pour vérifier que le
regroupement par activité et le plafond journalier "toutes activités
confondues" fonctionnent sans traitement spécifique à une activité.
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

import pytest

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Dlg import DLG_Etat_global  # noqa: E402


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs", "categories_tarifs")


class BaseCalculEtatGlobalTests(unittest.TestCase):
    """Socle commun : base de test minimale + construction d'un Dialog nu."""

    def setUp(self):
        self.base = BaseTest()
        for nom_table in TABLES_SUPPLEMENTAIRES:
            self.base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)

        # Régime / caisse / famille / compte payeur communs.
        self.base.inserer("regimes", ["IDregime", "nom"], [(1, "Régime Général")])
        self.base.inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "CAF Test", 1)])
        self.base.inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])

        # Deux individus, ~10 ans, pour être sûr d'une tranche d'âge stable.
        date_naiss = str(datetime.date.today().replace(year=datetime.date.today().year - 10))
        self.base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
            [(1, "DUPONT", "Enfant A", 1, date_naiss), (2, "MARTIN", "Enfant B", 1, date_naiss)],
        )

        # Deux activités distinctes : ALSH enfants (10) et ALSH ados (20).
        self.base.inserer("activites", ["IDactivite", "nom"], [(10, "ALSH enfants"), (20, "ALSH ados")])

        self.base.db.Commit()
        self.addCleanup(self.base.fermer)

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)

        self.calculateur = DLG_Etat_global.CalculateurEtatGlobal()

    # ---- Aides de construction ----

    def _options(self, **overrides):
        options = {
            "regroupement_principal": "aucun",
            "regroupement_age": [],
            "periodes_detaillees": False,
            "jours_hors_vacances": [0, 1, 2, 3, 4, 5, 6],
            "jours_vacances": [0, 1, 2, 3, 4, 5, 6],
            "etat_consommations": ["reservation", "present", "absentj", "absenti"],
            "plafond_journalier_individu": 0,
            "associer_regime_inconnu": "non",
            "tranches_qf_perso": [],
        }
        options.update(overrides)
        return options

    def _unite(self, IDunite, IDactivite=10, nomUnite="Unite", nomActivite="ALSH enfants",
               typeCalcul=1, coeff=None, arrondi=None, duree_seuil=None, duree_plafond=None,
               heure_seuil=None, heure_plafond=None, formule=None):
        return {
            "IDunite": IDunite, "IDactivite": IDactivite, "nomUnite": nomUnite, "nomActivite": nomActivite,
            "typeCalcul": typeCalcul, "coeff": coeff, "arrondi": arrondi,
            "duree_plafond": duree_plafond, "duree_seuil": duree_seuil,
            "heure_plafond": heure_plafond, "heure_seuil": heure_seuil, "formule": formule,
        }

    def _inserer_vacances_large(self):
        """ Une période de vacances couvrant toute l'année de test, pour que toutes les
        dates utilisées dans les scénarios 1-8 (hors tests dédiés période/anomalie)
        soient toujours valides (jamais 'Période inconnue'). """
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [(1, "Toussaint", 2026, "2026-01-01", "2026-12-31")],
        )
        self.base.db.Commit()

    def _conso(self, IDconso, IDindividu, IDunite, date, heure_debut=None, heure_fin=None,
               etat="present", quantite=None, IDactivite=10, IDprestation=None, IDcompte_payeur=1, IDgroupe=None):
        return (IDconso, IDindividu, IDunite, date, heure_debut, heure_fin, etat, quantite, IDactivite, IDprestation, IDcompte_payeur, IDgroupe)

    def _inserer_consos(self, listeConso):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            listeConso,
        )
        self.base.db.Commit()

    def _calculer(self, date_debut, date_fin, dictUnites, dict_options, listeActivites=(10, 20), dictInfosIndividus=None, dictInfosFamilles=None, listeGroupes=None):
        return self.calculateur.CalculerEtatGlobal(
            date_debut=date_debut,
            date_fin=date_fin,
            listeActivites=list(listeActivites),
            dictUnites=dictUnites,
            dict_options=dict_options,
            dictInfosIndividus=dictInfosIndividus or {},
            dictInfosFamilles=dictInfosFamilles or {},
            listeGroupes=listeGroupes,
        )


class TypeCalculTests(BaseCalculEtatGlobalTests):
    """Points 1 à 5 : les 4 modes de calcul, isolément."""

    def test_1_typecalcul_0_coefficient(self):
        self._inserer_vacances_large()
        self._inserer_consos([self._conso(1, 1, 50, "2026-03-10", None, None, "present", 1)])
        dictUnites = {50: self._unite(50, typeCalcul=0, coeff=2.5)}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=2.5))

    def test_2_typecalcul_1_temps_reel_simple(self):
        self._inserer_vacances_large()
        self._inserer_consos([self._conso(1, 1, 51, "2026-03-10", "08:00", "12:00")])
        dictUnites = {51: self._unite(51, typeCalcul=1)}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=4))

    def test_3_typecalcul_1_avec_arrondi_seuil_plafond(self):
        self._inserer_vacances_large()
        # Arrivée avant le seuil (08h) et départ après le plafond (17h) : seuil/plafond
        # ramènent la plage utile à 08h-17h = 9h, puis l'arrondi "durée 15 min sup."
        # ne change rien (9h est déjà un multiple de 15 min).
        self._inserer_consos([self._conso(1, 1, 52, "2026-03-10", "07:15", "17:45")])
        dictUnites = {52: self._unite(
            52, typeCalcul=1,
            heure_seuil="08:00", heure_plafond="17:00",
            arrondi=("duree", 15),
        )}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=9))

    def test_4_typecalcul_2_temps_facture_dedoublonne_par_prestation(self):
        self._inserer_vacances_large()
        self.base.inserer("prestations", ["IDprestation", "temps_facture"], [(500, "02:00")])
        self.base.db.Commit()
        # Deux consommations différentes partagent la même prestation : le temps
        # facturé ne doit être compté qu'une seule fois (2h), jamais deux fois (4h).
        self._inserer_consos([
            self._conso(1, 1, 53, "2026-03-10", None, None, "present", None, 10, 500),
            self._conso(2, 1, 53, "2026-03-11", None, None, "present", None, 10, 500),
        ])
        dictUnites = {53: self._unite(53, typeCalcul=2)}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=2))

    def test_5_typecalcul_3_formule_simple_sans_uniteN(self):
        self._inserer_vacances_large()
        self._inserer_consos([self._conso(1, 1, 54, "2026-03-10", "08:00", "11:00")])
        dictUnites = {54: self._unite(
            54, typeCalcul=3,
            formule=u'SI(duree > HEURE("02:00"), HEURE("03:00"), HEURE("01:00"))',
        )}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=3))


class JourneeMultiUnitesTests(BaseCalculEtatGlobalTests):
    """Point 6 : garderie matin + ALSH + repas + garderie soir, même jour, même enfant."""

    def test_6_journee_multi_unites_additionne_chaque_unite(self):
        self._inserer_vacances_large()
        self._inserer_consos([
            self._conso(1, 1, 61, "2026-03-10", "07:30", "09:00"),   # garderie matin : 1h30
            self._conso(2, 1, 62, "2026-03-10", "09:00", "12:00"),   # ALSH matin : 3h
            self._conso(3, 1, 63, "2026-03-10", None, None, "present", 1),  # repas : compté (coeff)
            self._conso(4, 1, 64, "2026-03-10", "13:30", "17:00"),   # ALSH après-midi : 3h30
            self._conso(5, 1, 65, "2026-03-10", "17:00", "18:30"),   # garderie soir : 1h30
        ])
        dictUnites = {
            61: self._unite(61, typeCalcul=1),
            62: self._unite(62, typeCalcul=1),
            63: self._unite(63, typeCalcul=0, coeff=0.5),
            64: self._unite(64, typeCalcul=1),
            65: self._unite(65, typeCalcul=1),
        }
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        # 1h30 + 3h + 0h30 + 3h30 + 1h30 = 10h
        self.assertEqual(total, datetime.timedelta(hours=10))


class PlafondJournalierTests(BaseCalculEtatGlobalTests):
    """Point 7 : plafond journalier par individu, toutes activités confondues."""

    def test_7_plafond_journalier_cappe_le_cumul(self):
        self._inserer_vacances_large()
        self._inserer_consos([
            self._conso(1, 1, 71, "2026-03-10", "08:00", "12:00"),  # 4h
            self._conso(2, 1, 72, "2026-03-10", "13:00", "18:00"),  # 5h -> cumul brut 9h
        ])
        dictUnites = {
            71: self._unite(71, typeCalcul=1),
            72: self._unite(72, typeCalcul=1),
        }
        # Plafond = 6h (360 minutes) toutes activités confondues pour cet individu.
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(plafond_journalier_individu=360))
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=6))


class FiltrageEtatTests(BaseCalculEtatGlobalTests):
    """Point 8 : filtrage par état (option) + exclusion SQL dure (attente/refus)."""

    def test_8_filtrage_par_etat(self):
        self._inserer_vacances_large()
        self._inserer_consos([
            self._conso(1, 1, 81, "2026-03-10", "08:00", "10:00", etat="present"),     # inclus
            self._conso(2, 1, 81, "2026-03-11", "08:00", "10:00", etat="absentj"),     # exclu par l'option
            self._conso(3, 1, 81, "2026-03-12", "08:00", "10:00", etat="attente"),     # exclu par le SQL (jamais remonté)
        ])
        dictUnites = {81: self._unite(81, typeCalcul=1)}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(etat_consommations=["present"]))
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=2))


class PeriodeVacancesTests(BaseCalculEtatGlobalTests):
    """Point 9 : distinction période de vacances / hors vacances."""

    def test_9_periode_vacances_et_hors_vacances(self):
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [(1, "Toussaint", 2026, "2026-10-19", "2026-11-02")],
        )
        self.base.db.Commit()
        self._inserer_consos([
            self._conso(1, 1, 91, "2026-10-25", "08:00", "10:00"),  # dans les vacances
            self._conso(2, 1, 91, "2026-11-10", "08:00", "10:00"),  # hors vacances
        ])
        dictUnites = {91: self._unite(91, typeCalcul=1)}
        resultat = self._calculer("2026-10-01", "2026-11-30", dictUnites, self._options())
        dict_periodes = resultat["dict_resultats"][None][0]
        self.assertEqual(dict_periodes["petitesVacs"][1], datetime.timedelta(hours=2))
        self.assertEqual(dict_periodes["horsVacs"][1], datetime.timedelta(hours=2))


class AnomalieTests(BaseCalculEtatGlobalTests):
    """Point 10 : remontée d'anomalie (période inconnue), sans exception ni dialogue."""

    def test_10_anomalie_periode_inconnue_remontee_sans_exception(self):
        # Une seule période de vacances déclarée, avec périodes détaillées activées :
        # aucune période "hors vacances" n'est générée (il en faut au moins deux pour
        # calculer un intervalle entre elles) -- une date hors de cette unique période
        # ne peut donc être classée : anomalie attendue, sans lever d'exception.
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [(1, "Toussaint", 2026, "2026-10-19", "2026-11-02")],
        )
        self.base.db.Commit()
        self._inserer_consos([self._conso(1, 1, 101, "2026-03-10", "08:00", "10:00")])
        dictUnites = {101: self._unite(101, typeCalcul=1)}
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(periodes_detaillees=True))
        self.assertEqual(len(resultat["listeAnomalies"]), 1)
        self.assertIn(u"Période inconnue", resultat["listeAnomalies"][0])
        # Et la consommation non classée ne contribue à aucun total.
        self.assertEqual(resultat["dict_resultats"], {})


class MultiActiviteTests(BaseCalculEtatGlobalTests):
    """Précision métier : ALSH enfants (10) et ALSH ados (20) traités par le même
    moteur générique, sans hypothèse codée en dur sur l'une ou l'autre activité."""

    def test_deux_activites_regroupement_par_activite_et_plafond_toutes_activites(self):
        self._inserer_vacances_large()
        # Même individu, même jour, une conso dans chaque activité.
        self._inserer_consos([
            self._conso(1, 1, 111, "2026-03-10", "08:00", "12:00", IDactivite=10),  # ALSH enfants : 4h
            self._conso(2, 1, 112, "2026-03-10", "13:00", "18:00", IDactivite=20),  # ALSH ados : 5h -> cumul brut 9h
        ])
        dictUnites = {
            111: self._unite(111, IDactivite=10, nomActivite="ALSH enfants", typeCalcul=1),
            112: self._unite(112, IDactivite=20, nomActivite="ALSH ados", typeCalcul=1),
        }

        # 1) Sans regroupement : le plafond journalier toutes activités confondues
        #    s'applique bien au cumul des DEUX activités (comportement inchangé).
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(plafond_journalier_individu=360))
        total = resultat["dict_resultats"][None][0]["petitesVacs"][1]
        self.assertEqual(total, datetime.timedelta(hours=6))

        # 2) Regroupement par activité (sans plafond) : chaque activité conserve son
        #    propre total, aucune fusion, aucun traitement spécifique à l'une d'elles.
        resultat2 = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(regroupement_principal="activite"))
        self.assertEqual(resultat2["dict_resultats"]["ALSH enfants"][0]["petitesVacs"][1], datetime.timedelta(hours=4))
        self.assertEqual(resultat2["dict_resultats"]["ALSH ados"][0]["petitesVacs"][1], datetime.timedelta(hours=5))


class FiltrageGroupeTests(BaseCalculEtatGlobalTests):
    """Filtre optionnel listeGroupes : aucun ID PMSL réel, IDgroupe génériques.

    Trois groupes sous l'activité 10 (101, 102, 103) + un groupe sous
    l'activité 20 (201), même jour, même unité (typeCalcul=1, temps réel),
    pour isoler strictement l'effet du filtre par groupe."""

    def _fixture_trois_groupes(self):
        """ Insère en base 3 groupes de l'activité 10 + 1 groupe d'une AUTRE
        activité (20) réellement présent en base -- mais dictUnites ne
        contient que l'unité de l'activité 10 : c'est ce périmètre
        (dictUnites/listeActivites), pas listeGroupes seul, qui empêche déjà
        toute fuite inter-activité (cf. test 5). """
        self._inserer_vacances_large()
        # Individus 3 et 4, en plus des 1/2 du socle commun -- même tranche
        # d'âge pour que toutes les contributions tombent dans le même
        # panier (index_tranche_age=0) ; sans date_naiss, une conso serait
        # rangée sous une tranche d'âge "None" distincte.
        date_naiss = str(datetime.date.today().replace(year=datetime.date.today().year - 10))
        self.base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
            [(3, "DURAND", "Enfant C", 1, date_naiss), (4, "PETIT", "Enfant D", 1, date_naiss)],
        )
        self.base.db.Commit()
        self._inserer_consos([
            self._conso(1, 1, 151, "2026-03-10", "08:00", "10:00", IDactivite=10, IDgroupe=101),  # 2h
            self._conso(2, 2, 151, "2026-03-10", "08:00", "11:00", IDactivite=10, IDgroupe=102),  # 3h
            self._conso(3, 3, 151, "2026-03-10", "08:00", "09:00", IDactivite=10, IDgroupe=103),  # 1h
            self._conso(4, 4, 251, "2026-03-10", "08:00", "12:00", IDactivite=20, IDgroupe=201),  # 4h, autre activité, hors dictUnites
        ])
        dictUnites = {
            151: self._unite(151, IDactivite=10, nomActivite="ALSH enfants", typeCalcul=1),
        }
        return dictUnites

    def _total(self, resultat):
        try:
            return resultat["dict_resultats"][None][0]["petitesVacs"][1]
        except KeyError:
            return datetime.timedelta(0)

    def test_1_sans_filtre_groupe_comportement_historique_inchange(self):
        dictUnites = self._fixture_trois_groupes()
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(), listeActivites=[10])
        # Les 3 groupes de l'activité 10 sont sommés, comme avant l'existence de listeGroupes.
        self.assertEqual(self._total(resultat), datetime.timedelta(hours=2 + 3 + 1))

    def test_2_listeGroupes_un_seul_groupe_A(self):
        dictUnites = self._fixture_trois_groupes()
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(), listeActivites=[10], listeGroupes=[101])
        self.assertEqual(self._total(resultat), datetime.timedelta(hours=2))

    def test_3_listeGroupes_un_seul_groupe_B(self):
        dictUnites = self._fixture_trois_groupes()
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(), listeActivites=[10], listeGroupes=[102])
        self.assertEqual(self._total(resultat), datetime.timedelta(hours=3))

    def test_4_plusieurs_groupes_union_correcte(self):
        dictUnites = self._fixture_trois_groupes()
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(), listeActivites=[10], listeGroupes=[101, 102])
        # Union de A et B, exclut explicitement le 3e groupe (103) de la même activité.
        self.assertEqual(self._total(resultat), datetime.timedelta(hours=2 + 3))

    def test_5_groupe_dune_autre_activite_que_listeActivites_ne_donne_aucun_resultat(self):
        dictUnites = self._fixture_trois_groupes()
        # Le groupe 201 existe réellement en base, mais sur l'activité 20 --
        # hors du périmètre (dictUnites/listeActivites=[10]) de cet appel.
        # Même en lui passant explicitement listeGroupes=[201], aucune fuite :
        # aucune consommation de l'activité 10 n'a ce groupe.
        resultat = self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options(), listeActivites=[10], listeGroupes=[201])
        self.assertEqual(resultat["dict_resultats"], {})


class BugPorteeUniteNTests(BaseCalculEtatGlobalTests):
    """Exprime le comportement CORRECT attendu (pas le bug) pour la portée des
    références uniteN dans les formules : deux individus différents, même
    date, même unité, doivent chacun retrouver LEUR PROPRE uniteN -- jamais
    celle d'un autre individu.

    Tant que self.dict_unites reste indexé uniquement par date (sans la
    scoper par individu, cf. docstring de CalculateurEtatGlobal), ce test
    doit échouer (XFAIL) : c'est la correction du bug, pas ce test, qui doit
    un jour le faire passer (XPASS). Rien ici ne fige le bug comme contrat --
    c'est l'inverse : ce test fige l'exigence métier correcte."""

    @pytest.mark.xfail(
        reason=(
            "Anomalie connue, non corrigée : self.dict_unites est indexé "
            "uniquement par date, pas par individu (cf. docstring de "
            "CalculateurEtatGlobal). Ce test exprime le comportement "
            "correct attendu (chaque individu retrouve SA PROPRE uniteN) ; "
            "il échoue tant que le bug subsiste. strict=False : XFAIL "
            "aujourd'hui (bug présent), XPASS le jour où il sera corrigé -- "
            "jamais un échec bloquant dans les deux cas."
        ),
        strict=False,
    )
    def test_formule_uniteN_retrouve_lunite_du_bon_individu_pas_celle_dun_autre(self):
        self._inserer_vacances_large()
        # Unité 77 (Horaire) : durées réellement différentes entre les deux enfants.
        # Unité 88 (Formule) : ne contribue rien par elle-même (heures neutres),
        # seule sa formule (qui référence unite77) nous intéresse ici.
        self._inserer_consos([
            self._conso(1, 1, 77, "2026-03-10", "08:00", "10:00"),  # Enfant A : unite77 = 2h
            self._conso(2, 2, 77, "2026-03-10", "08:00", "14:00"),  # Enfant B : unite77 = 6h
            self._conso(3, 1, 88, "2026-03-10", "09:00", "09:00"),
            self._conso(4, 2, 88, "2026-03-10", "09:00", "09:00"),
        ])
        formule = u'SI(unite77.duree > HEURE("03:00"), HEURE("05:00"), HEURE("01:00"))'
        dictUnites = {
            77: self._unite(77, typeCalcul=0, coeff=0),  # neutre : ne compte jamais dans dict_resultats
            88: self._unite(88, typeCalcul=3, formule=formule),
        }
        dictInfosIndividus = {
            1: {"INDIVIDU_NOM_COMPLET": "Enfant A"},
            2: {"INDIVIDU_NOM_COMPLET": "Enfant B"},
        }
        resultat = self._calculer(
            "2026-03-01", "2026-03-31", dictUnites,
            self._options(regroupement_principal="individu"),
            dictInfosIndividus=dictInfosIndividus,
        )
        valeur_A = resultat["dict_resultats"]["Enfant A"][0]["petitesVacs"][1]
        valeur_B = resultat["dict_resultats"]["Enfant B"][0]["petitesVacs"][1]

        # Comportement CORRECT attendu : chaque enfant retrouve SA PROPRE
        # unite77 (2h pour A -> 1h ; 6h pour B -> 5h), jamais celle de l'autre.
        self.assertEqual(valeur_A, datetime.timedelta(hours=1))
        self.assertEqual(valeur_B, datetime.timedelta(hours=5))
        self.assertNotEqual(valeur_A, valeur_B)


class ErreursSansDialogueWxTests(BaseCalculEtatGlobalTests):
    """IMPORTANT -- ERREURS UI : le calcul extrait ne doit afficher aucune boîte
    de dialogue wx. Les deux cas bloquants remontent via ErreurCalculEtatGlobal,
    à charge de Apercu() de les afficher (non testé ici, hors périmètre wx)."""

    def test_horaires_incoherents_leve_erreur_sans_dialogue(self):
        self._inserer_vacances_large()
        # Heure de fin antérieure à l'heure de début : horaires incohérents.
        self._inserer_consos([self._conso(1, 1, 121, "2026-03-10", "14:00", "08:00")])
        dictUnites = {121: self._unite(121, typeCalcul=1)}
        with self.assertRaises(DLG_Etat_global.ErreurCalculEtatGlobal) as ctx:
            self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        self.assertEqual(ctx.exception.titre, u"Erreur")

    def test_formule_invalide_leve_erreur_sans_dialogue(self):
        self._inserer_vacances_large()
        self._inserer_consos([self._conso(1, 1, 122, "2026-03-10", "08:00", "09:00")])
        dictUnites = {122: self._unite(122, typeCalcul=3, formule=u"1/0")}
        with self.assertRaises(DLG_Etat_global.ErreurCalculEtatGlobal) as ctx:
            self._calculer("2026-03-01", "2026-03-31", dictUnites, self._options())
        self.assertEqual(ctx.exception.titre, u"Erreur de formule")


if __name__ == "__main__":
    unittest.main()
