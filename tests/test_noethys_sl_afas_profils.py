# -*- coding: utf-8 -*-
"""AFAS -- profils anciens, incomplets, corrompus et groupes supprimés.

Non-régression des anomalies P1 de l'audit AFAS du 23/10/2026 : un ancien
profil sans unités provoquait une KeyError, et un profil référençant un
groupe supprimé permettait un calcul sur un périmètre réduit sans blocage.
ValiderConfiguration est testée sans wx ; le blocage du calcul dans le
dialogue s'appuie sur la liste des périmètres manquants qu'elle renvoie.
"""
import unittest

from Utils import UTILS_AFAS_Actualisation as AFAS


def _options():
    return {"regroupement_principal": "aucun", "regroupement_age": [], "periodes_detaillees": False,
            "jours_hors_vacances": [0, 1, 2, 3, 4], "jours_vacances": [0, 1, 2, 3, 4],
            "etat_consommations": ["present"], "plafond_journalier_individu": 0,
            "associer_regime_inconnu": "non", "tranches_qf_perso": []}


def _configuration(**modifs):
    configuration = dict(nom="Equipement", perimetres=[(10, 1), (10, 2)],
                         unites={51: {"IDunite": 51, "IDactivite": 10, "typeCalcul": 1}},
                         options=_options(), methode=0, valeurs_par_declaration={})
    configuration.update(modifs)
    return configuration


class ValiderConfigurationTests(unittest.TestCase):
    def test_profil_complet_accepte(self):
        configuration, manquants = AFAS.ValiderConfiguration(_configuration(), [(10, 1), (10, 2)])
        self.assertEqual((configuration["perimetres"], manquants), ([(10, 1), (10, 2)], []))

    def test_perimetres_listes_relus_par_eval(self):
        configuration, manquants = AFAS.ValiderConfiguration(_configuration(perimetres=[[10, 1]]), [(10, 1)])
        self.assertEqual(configuration["perimetres"], [(10, 1)])

    def test_groupe_supprime_signale(self):
        _, manquants = AFAS.ValiderConfiguration(_configuration(), [(10, 1)])
        self.assertEqual(manquants, [(10, 2)])

    def test_ancien_profil_sans_unites(self):
        configuration = _configuration()
        del configuration["unites"]
        with self.assertRaisesRegex(ValueError, "unités"):
            AFAS.ValiderConfiguration(configuration, [(10, 1)])

    def test_unites_vides_ou_incompletes(self):
        for unites in ({}, {51: {"IDunite": 51}}, {51: "texte"}, []):
            with self.subTest(unites=unites), self.assertRaises(ValueError):
                AFAS.ValiderConfiguration(_configuration(unites=unites), [(10, 1)])

    def test_options_absentes_ou_incompletes(self):
        options = _options()
        del options["etat_consommations"]
        for valeur in (None, {}, options):
            with self.subTest(options=valeur), self.assertRaises(ValueError):
                AFAS.ValiderConfiguration(_configuration(options=valeur), [(10, 1)])

    def test_valeurs_corrompues(self):
        for modifs in (dict(perimetres="10,1"), dict(perimetres=[(10, "1")]), dict(perimetres=[(10,)]),
                       dict(methode=7), dict(valeurs_par_declaration=[]), dict(nom=None)):
            with self.subTest(modifs=modifs), self.assertRaises(ValueError):
                AFAS.ValiderConfiguration(_configuration(**modifs), [(10, 1)])

    def test_configuration_non_dictionnaire(self):
        for valeur in (None, [], "profil"):
            with self.subTest(valeur=valeur), self.assertRaises(ValueError):
                AFAS.ValiderConfiguration(valeur, [(10, 1)])

    def test_cles_facultatives_par_defaut(self):
        configuration = _configuration()
        for cle in ("nom", "methode", "valeurs_par_declaration"):
            del configuration[cle]
        resultat, _ = AFAS.ValiderConfiguration(configuration, [(10, 1), (10, 2)])
        self.assertEqual((resultat["nom"], resultat["methode"], resultat["valeurs_par_declaration"]), ("", 0, {}))

    def test_configuration_source_non_modifiee(self):
        configuration = _configuration(perimetres=[[10, 1]])
        AFAS.ValiderConfiguration(configuration, [(10, 1)])
        self.assertEqual(configuration["perimetres"], [[10, 1]])


if __name__ == "__main__":
    unittest.main()
