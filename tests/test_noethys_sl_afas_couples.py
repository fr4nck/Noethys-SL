# -*- coding: utf-8 -*-
"""AFAS -- filtrage par couples exacts (IDactivite, IDgroupe).

Non-régression de l'anomalie P0-1 de l'audit AFAS du 23/10/2026 : le moteur
filtrait par deux listes indépendantes (unités/groupes), si bien qu'une
consommation hors des couples demandés pouvait être comptée. Bases SQLite
fictives uniquement, aucune connexion réseau.
"""
import datetime
import unittest

import _garde_reseau  # noqa: F401  aucune connexion à une base réseau

from test_noethys_sl_afas_donnees import _BaseAFASDonneesTests
from Dlg import DLG_Etat_global
from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Donnees
from Utils import UTILS_AFAS_Perimetre


class _BaseCouples(_BaseAFASDonneesTests):
    def setUp(self):
        super().setUp()
        self.base.inserer("activites", ["IDactivite", "nom"], [(20, "Activite B"), (30, "Activite C")])
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"],
                          [(1, 10, "Groupe A1"), (2, 20, "Groupe B2"), (3, 10, "Groupe A3")])
        self._commit()

    def _conso(self, IDconso, IDactivite, IDgroupe, IDunite=51, IDprestation=None):
        self.base.inserer(
            "consommations",
            ["IDconso", "IDindividu", "IDunite", "date", "heure_debut", "heure_fin", "etat", "quantite",
             "IDactivite", "IDprestation", "IDcompte_payeur", "IDgroupe"],
            [(IDconso, 1, IDunite, "2026-03-04", "08:00", "10:00", "present", None, IDactivite,
              IDprestation, 1, IDgroupe)],
        )

    def _unites(self):
        return {51: self._unite_reel(51, 10), 61: self._unite_reel(61, 20)}

    def _periode(self, perimetres):
        self._commit()
        unites = self._unites()
        facture = {cle: self._unite_facture(cle, u["IDactivite"]) for cle, u in unites.items()}
        return UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
            perimetres, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), datetime.date(2026, 12, 31),
            unites, facture, self._options())


class CouplesExactsTests(_BaseCouples):
    def test_couple_croise_exclu(self):
        # (10, 2) n'est pas demandé, alors que l'activité 10 et le groupe 2 le sont séparément.
        self._conso(1, 10, 2)
        resultat = self._periode([(10, 1), (20, 2)])
        self.assertEqual(resultat["heures_reelles"], 0)

    def test_activite_non_selectionnee_exclue(self):
        # Activité 30 absente du périmètre, malgré une unité et un groupe sélectionnés.
        self._conso(1, 30, 1)
        self.assertEqual(self._periode([(10, 1)])["heures_reelles"], 0)

    def test_couples_demandes_retenus(self):
        self._conso(1, 10, 1)
        self._conso(2, 20, 2, IDunite=61)
        self.assertEqual(self._periode([(10, 1), (20, 2)])["heures_reelles"], 4)

    def test_facture_restreint_aux_couples(self):
        self._inserer_prestation(501, "02:00")
        self._inserer_prestation(502, "02:00")
        self._conso(1, 10, 1, IDprestation=501)
        self._conso(2, 10, 2, IDprestation=502)
        self.assertEqual(self._periode([(10, 1), (20, 2)])["heures_facturees"], 2)

    def test_get_donnees_afas_couple_unique(self):
        self._conso(1, 30, 1)
        self._conso(2, 10, 1)
        self._commit()
        resultat = UTILS_AFAS_Donnees.GetDonneesAFAS(
            10, 1, 2026, UTILS_AFAS.PHASE_REEL, {51: self._unite_reel(51, 10)},
            {51: self._unite_facture(51, 10)}, self._options())
        self.assertEqual(resultat["heures_reelles"], 2)

    def test_perimetre_historique_couple_unique(self):
        self._conso(1, 30, 1)
        self._conso(2, 10, 1)
        self._commit()
        resultat = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            10, 1, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31),
            {51: self._unite_reel(51, 10)}, self._options())
        self.assertEqual(resultat["heures"], 2)


class ConditionSQLCouplesTests(unittest.TestCase):
    def test_aucun_couple_fourni_comportement_historique(self):
        self.assertEqual(DLG_Etat_global.ConditionSQLCouples(None), "")

    def test_condition_par_couple(self):
        self.assertEqual(
            DLG_Etat_global.ConditionSQLCouples([(10, 1), (20, 2), (10, 1)]),
            "AND ((consommations.IDactivite = 10 AND consommations.IDgroupe = 1) OR "
            "(consommations.IDactivite = 20 AND consommations.IDgroupe = 2))")

    def test_liste_vide_refusee(self):
        with self.assertRaises(DLG_Etat_global.ErreurCalculEtatGlobal):
            DLG_Etat_global.ConditionSQLCouples([])

    def test_identifiants_non_entiers_refuses(self):
        for couple in ((10, "1"), ("10", 1), (True, 1), (10, None), (10,), "10,1"):
            with self.subTest(couple=couple), self.assertRaises(DLG_Etat_global.ErreurCalculEtatGlobal):
                DLG_Etat_global.ConditionSQLCouples([couple])


class EtatGlobalSansCouplesTests(_BaseCouples):
    def test_etat_global_sans_couples_inchange(self):
        # Appel historique (sans listeCouples) : la consommation (30, 1) reste comptée comme avant.
        self._conso(1, 30, 1)
        self._commit()
        resultat = DLG_Etat_global.CalculateurEtatGlobal().CalculerEtatGlobal(
            date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 12, 31), listeActivites=[10],
            dictUnites={51: self._unite_reel(51, 10)}, dict_options=self._options(),
            dictInfosIndividus={}, dictInfosFamilles={})
        total = sum((v for t in resultat["dict_resultats"].values() for p in t.values()
                     for r in p.values() for v in r.values()), datetime.timedelta(0))
        self.assertEqual(total, datetime.timedelta(hours=2))


if __name__ == "__main__":
    unittest.main()
