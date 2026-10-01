# -*- coding: utf-8 -*-
"""Règle métier PMSL : la présence au temps du midi (+1h, forfaitaire) ne
dépend JAMAIS de l'existence ou de la consommation d'une unité "Repas".

RÉÉCRITURE COMPLÈTE (lot "présence méridienne") -- l'ancienne version de ce
fichier reposait sur une unité fictive "Présence midi" (typeCalcul=0,
coeff=1) absente de toute configuration PMSL réelle, et sur un test par
formule (typeCalcul=3) qui n'est d'ailleurs utilisé nulle part en
production. Un audit en lecture seule de la base PMSL réelle a montré que
les coefficients réellement utilisés sont : Matin=4h, Après-midi=4h,
Journée=8h, Journée camp=10h (tous en typeCalcul=0, coefficient fixe) --
jamais de typeCalcul=3 (formule) pour exprimer une règle de présence.

Ces tests démontrent donc, au travers de UTILS_AFAS_Perimetre.GetDonneesPerimetre
(INCHANGÉ, zéro ligne modifiée dans ce lot) :
- que les coefficients fixes réels (4/4/8/10) sont bien portés tels quels ;
- que CalculerEtatGlobal lit nativement 3 nouvelles clés optionnelles de
  dict_options (forfait_presence_midi, heure_debut_presence_midi,
  heure_fin_presence_midi) pour ajouter un forfait UNE SEULE FOIS par
  (IDindividu, date), sans jamais inventer de ventilation par unité ni
  dépendre du nom/de la présence d'une unité "Repas" ;
- que l'activation est gouvernée PAR L'OPTION (0 = désactivé), jamais par
  une détection du type d'activité (extrascolaire/mini-camp compris) ;
- que GetDonneesPerimetre n'a besoin d'aucune adaptation : son addition
  générique sur tout dict_resultats (toutes clés de regroupement
  confondues) absorbe déjà le forfait automatiquement.

Ce lot qualifie explicitement ce comportement avec regroupement_principal="aucun"
(seul mode testé ici) -- aucune tentative de ventiler le forfait par unité.

Aucun ID PMSL réel n'est utilisé (IDactivite/IDgroupe génériques)."""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Utils import UTILS_AFAS_Perimetre  # noqa: E402


TABLES_SUPPLEMENTAIRES = ("vacances", "evenements", "etiquettes", "comptes_payeurs", "categories_tarifs", "ouvertures")


class BaseTempsDuMidiTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        for nom_table in TABLES_SUPPLEMENTAIRES:
            self.base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)

        self.base.inserer("regimes", ["IDregime", "nom"], [(1, "Régime Général")])
        self.base.inserer("caisses", ["IDcaisse", "nom", "IDregime"], [(1, "CAF Test", 1)])
        self.base.inserer("familles", ["IDfamille", "IDcaisse"], [(1, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
        date_naiss = str(datetime.date.today().replace(year=datetime.date.today().year - 10))
        self.base.inserer(
            "individus",
            ["IDindividu", "nom", "prenom", "IDcivilite", "date_naiss"],
            [(1, "DUPONT", "Enfant A", 1, date_naiss)],
        )
        # Activités génériques (aucun ID PMSL réel) : Extrascolaire, Mini-camp, Periscolaire.
        self.base.inserer(
            "activites",
            ["IDactivite", "nom"],
            [(30, "Extrascolaire"), (40, "Mini-camp"), (50, "Periscolaire")],
        )
        self.base.inserer(
            "vacances",
            ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
            [(1, "Toussaint", 2026, "2026-01-01", "2026-12-31")],
        )
        self.base.db.Commit()

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)
        self.addCleanup(self.base.fermer)

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

    def _unite(self, IDunite, IDactivite, nomUnite, typeCalcul=0, coeff=None, formule=None):
        return {
            "IDunite": IDunite, "IDactivite": IDactivite, "nomUnite": nomUnite, "nomActivite": "Activite",
            "typeCalcul": typeCalcul, "coeff": coeff, "arrondi": None,
            "duree_plafond": None, "duree_seuil": None,
            "heure_plafond": None, "heure_seuil": None, "formule": formule,
        }

    def _conso(self, IDconso, IDunite, date, heure_debut=None, heure_fin=None, IDactivite=30, IDgroupe=1,
               IDindividu=1, IDprestation=None):
        return (IDconso, IDindividu, IDunite, date, heure_debut, heure_fin, "present", None, IDactivite, IDprestation, 1, IDgroupe)

    def _inserer_consos(self, listeConso):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite", "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            listeConso,
        )
        self.base.db.Commit()

    def _calculer_heures(self, IDactivite, IDgroupe, dictUnites, dict_options=None, date_debut="2026-03-01", date_fin="2026-03-31"):
        resultat = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=IDactivite, IDgroupe=IDgroupe,
            date_debut=date_debut, date_fin=date_fin,
            dictUnites=dictUnites, dict_options=dict_options or self._options(),
        )
        return resultat["heures"]


class ExtrascolaireJourneeCompleteTests(BaseTempsDuMidiTests):
    """Extrascolaire : coefficient fixe réel "Journée" = 8h (typeCalcul=0),
    comme en configuration PMSL. Les horaires réels de la consommation
    n'influent jamais sur ce coefficient -- seulement, le cas échéant, sur
    la détection du chevauchement avec la tranche méridienne (tests
    dédiés ci-dessous)."""

    def test_journee_complete_egale_huit_heures_option_desactivee(self):
        self._inserer_consos([
            self._conso(1, 301, "2026-03-10", "08:00", "16:00", IDactivite=30, IDgroupe=1),
        ])
        dictUnites = {301: self._unite(301, IDactivite=30, nomUnite="Journée", typeCalcul=0, coeff=8)}
        heures = self._calculer_heures(30, 1, dictUnites, dict_options=self._options(forfait_presence_midi=0))
        self.assertEqual(heures, 8.0)

    def test_journee_complete_chevauchant_midi_huit_heures_plus_forfait_neuf_heures(self):
        # Mêmes 8h de coefficient, mais horaires réels 08h-17h (chevauche
        # bien la tranche méridienne 12:30-13:30) et option activée.
        self._inserer_consos([
            self._conso(1, 301, "2026-03-10", "08:00", "17:00", IDactivite=30, IDgroupe=1),
        ])
        dictUnites = {301: self._unite(301, IDactivite=30, nomUnite="Journée", typeCalcul=0, coeff=8)}
        heures = self._calculer_heures(30, 1, dictUnites, dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 9.0)


class MiniCampJourneeTests(BaseTempsDuMidiTests):
    """Mini-camp : coefficient fixe réel "Journée camp" = 10h -- même
    mécanisme générique que pour l'extrascolaire, aucun traitement
    spécifique au mini-camp. Ici l'option est désactivée (comme il convient
    à un contexte où la présence méridienne n'a pas de sens) : la
    désactivation se fait par l'option, jamais par une détection
    d'activité."""

    def test_journee_mini_camp_egale_dix_heures_option_desactivee(self):
        self._inserer_consos([
            self._conso(1, 401, "2026-07-10", "08:00", "18:00", IDactivite=40, IDgroupe=1),
        ])
        dictUnites = {401: self._unite(401, IDactivite=40, nomUnite="Journée camp", typeCalcul=0, coeff=10)}
        heures = self._calculer_heures(
            40, 1, dictUnites, dict_options=self._options(forfait_presence_midi=0),
            date_debut="2026-07-01", date_fin="2026-07-31",
        )
        self.assertEqual(heures, 10.0)


class PeriscolairePresenceMeridienneTests(BaseTempsDuMidiTests):
    """Périscolaire : Matin (4h) et Après-midi (4h), coefficients fixes
    réels -- la présence méridienne est lue nativement par
    CalculerEtatGlobal via dict_options (forfait_presence_midi /
    heure_debut_presence_midi / heure_fin_presence_midi), jamais ventilée
    sur une unité "Présence midi" ni dépendante d'une unité "Repas"."""

    def _unites_matin_apres_midi(self):
        return {
            501: self._unite(501, IDactivite=50, nomUnite="Matin", typeCalcul=0, coeff=4),
            502: self._unite(502, IDactivite=50, nomUnite="Après-midi", typeCalcul=0, coeff=4),
        }

    def test_journee_complete_matin_et_apres_midi_chevauchant_midi(self):
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "12:00", IDactivite=50, IDgroupe=1),  # Matin, ne chevauche pas
            self._conso(2, 502, "2026-03-10", "13:00", "17:00", IDactivite=50, IDgroupe=1),  # Après-midi, chevauche (13:00 < 13:30)
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4 + 4 + 1)

    def test_matinee_seule_chevauchant_midi_cinq_heures(self):
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "13:00", IDactivite=50, IDgroupe=1),  # Matin, déborde sur midi
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4 + 1)

    def test_matinee_seule_sans_chevauchement_quatre_heures(self):
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "12:00", IDactivite=50, IDgroupe=1),  # Matin, départ avant midi
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4.0)

    def test_borne_depart_exactement_12h30_aucun_forfait(self):
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "12:30", IDactivite=50, IDgroupe=1),
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4.0)

    def test_borne_arrivee_exactement_13h30_aucun_forfait(self):
        self._inserer_consos([
            self._conso(1, 502, "2026-03-10", "13:30", "17:30", IDactivite=50, IDgroupe=1),
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4.0)

    def test_aucune_dependance_a_une_unite_repas(self):
        """ Une unité "Repas" (Unitaire, sans horaire, coeff propre) est
        consommée le même jour : elle s'additionne normalement, mais
        n'influence ni ne conditionne en rien le forfait méridien, qui ne
        regarde que les horaires des plages Horaire/coefficient. """
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "13:00", IDactivite=50, IDgroupe=1),           # Matin, chevauche midi
            self._conso(2, 503, "2026-03-10", None, None, IDactivite=50, IDgroupe=1),  # Repas, coeff=1, sans horaire
        ])
        dictUnites = dict(self._unites_matin_apres_midi())
        dictUnites[503] = self._unite(503, IDactivite=50, nomUnite="Repas", typeCalcul=0, coeff=1)
        heures = self._calculer_heures(50, 1, dictUnites, dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4 + 1 + 1)  # Matin + Repas + forfait méridien

    def test_enfant_apportant_son_propre_repas_aucune_conso_repas(self):
        """ L'unité Repas EXISTE dans le paramétrage (facturation possible
        pour d'autres enfants), mais cet enfant n'a AUCUNE consommation
        Repas (il apporte son propre repas) -- le forfait méridien reste
        compté normalement via la seule plage Matin. """
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "13:00", IDactivite=50, IDgroupe=1),
            # Aucune ligne IDunite=503 (Repas) pour cet enfant.
        ])
        dictUnites = dict(self._unites_matin_apres_midi())
        dictUnites[503] = self._unite(503, IDactivite=50, nomUnite="Repas", typeCalcul=0, coeff=1)
        heures = self._calculer_heures(50, 1, dictUnites, dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4 + 1)  # Matin + forfait méridien, aucun Repas

    def test_pique_nique_non_facture_ne_necessite_aucun_repas(self):
        """ Prestation en temps facturé (typeCalcul=2) sans temps_facture
        renseigné (pique-nique non facturé, valeur nulle pour cette conso) :
        le forfait méridien se déclenche normalement via la plage Matin,
        sans qu'aucune unité "Repas" n'ait jamais été nécessaire. """
        self.base.inserer("prestations", ["IDprestation", "temps_facture"], [(900, None)])
        self.base.db.Commit()
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "13:00", IDactivite=50, IDgroupe=1),
            self._conso(2, 504, "2026-03-10", None, None, IDactivite=50, IDgroupe=1, IDprestation=900),
        ])
        dictUnites = dict(self._unites_matin_apres_midi())
        dictUnites[504] = self._unite(504, IDactivite=50, nomUnite="Pique-nique", typeCalcul=2)
        heures = self._calculer_heures(50, 1, dictUnites, dict_options=self._options(forfait_presence_midi=60))
        self.assertEqual(heures, 4 + 1)  # Matin + forfait méridien, pique-nique non facturé = 0h

    def test_dict_options_sans_nouvelles_cles_comportement_inchange(self):
        """ Un profil déjà existant avant ce lot (dict_options sans les 3
        nouvelles clés) ne doit produire AUCUN forfait, même en cas de
        chevauchement réel -- comportement historique strictement
        préservé. """
        self._inserer_consos([
            self._conso(1, 501, "2026-03-10", "08:00", "13:00", IDactivite=50, IDgroupe=1),
        ])
        heures = self._calculer_heures(50, 1, self._unites_matin_apres_midi(), dict_options=self._options())
        self.assertEqual(heures, 4.0)


if __name__ == "__main__":
    unittest.main()
