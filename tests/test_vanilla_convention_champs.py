# -*- coding: utf-8 -*-
"""Fournisseur de champs Convention : logique metier pure (sans wx, sans
base reelle necessaire pour la plupart des cas) + integration sur une
base SQLite temporaire synthetique et anonymisee.
"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
    creer_base_ecole_simple,
    creer_base_tarif_ambigu_simple,
)
from Utils import UTILS_Convention_champs as CC  # noqa: E402


class FauxInformations:
    """ Double du collaborateur UTILS_Infos_individus.Informations : la
    vraie classe se connecte toujours a la base par defaut de Noethys
    (GestionDB.DB() sans parametre injectable), donc pour tester la
    logique pure de selection du representant on fournit ici directement
    la forme de dict qu'elle produirait. """

    def __init__(self, dictValeurs):
        self._dictValeurs = dictValeurs

    def GetDictValeurs(self, mode, ID, formatChamp):
        return self._dictValeurs


def _conso(heure_debut, heure_fin, montant, date="2026-09-02", etat="reservation"):
    return {
        "heure_debut": heure_debut, "heure_fin": heure_fin, "etat": etat,
        "prestation": {"montant": montant, "label": "x", "paye": None},
    }


def _dict_donnees_simple(nom="STRUCTURE", prenom="Groupe", IDactivite=10, nom_activite="Encadrement enfants", seances=()):
    dates = {}
    for date, heure_debut, heure_fin, montant in seances:
        dates.setdefault(date, {"unites": {1: []}})
        dates[date]["unites"][1].append(_conso(heure_debut, heure_fin, montant, date=date))
    return {
        1: {
            "nom": nom, "prenom": prenom, "date_naiss": None, "sexe": None,
            "activites": {IDactivite: {"nom": nom_activite, "agrement": None, "dates": dates}},
        }
    }


class GetRepresentantTests(unittest.TestCase):
    def test_ignore_lentree_institutionnelle_sans_prenom(self):
        infos = FauxInformations({
            "{NBRE_REPRESENTANTS_RATTACHES}": 1,
            "{REPRESENTANT_RATTACHE_1_PRENOM}": "",
            "{REPRESENTANT_RATTACHE_1_NOM}": "STRUCTURE TEST",
            "{REPRESENTANT_RATTACHE_1_NOM_COMPLET}": "STRUCTURE TEST",
        })
        self.assertIsNone(CC.GetRepresentant(1, informations=infos))

    def test_retient_le_premier_representant_reellement_nomme(self):
        infos = FauxInformations({
            "{NBRE_REPRESENTANTS_RATTACHES}": 2,
            "{REPRESENTANT_RATTACHE_1_PRENOM}": "",
            "{REPRESENTANT_RATTACHE_1_NOM}": "STRUCTURE TEST",
            "{REPRESENTANT_RATTACHE_1_NOM_COMPLET}": "STRUCTURE TEST",
            "{REPRESENTANT_RATTACHE_2_PRENOM}": "Chantal",
            "{REPRESENTANT_RATTACHE_2_NOM}": "LE GALL",
            "{REPRESENTANT_RATTACHE_2_NOM_COMPLET}": "Mme LE GALL Chantal",
        })
        r = CC.GetRepresentant(1, informations=infos)
        self.assertEqual(r, {"nom": "LE GALL", "prenom": "Chantal", "nom_complet": "Mme LE GALL Chantal"})

    def test_aucun_representant_disponible(self):
        infos = FauxInformations({"{NBRE_REPRESENTANTS_RATTACHES}": 0})
        self.assertIsNone(CC.GetRepresentant(1, informations=infos))

    def test_caracteres_accentues_preserves(self):
        infos = FauxInformations({
            "{NBRE_REPRESENTANTS_RATTACHES}": 1,
            "{REPRESENTANT_RATTACHE_1_PRENOM}": "Éléonore",
            "{REPRESENTANT_RATTACHE_1_NOM}": "GARNIER",
            "{REPRESENTANT_RATTACHE_1_NOM_COMPLET}": "Mme GARNIER Éléonore",
        })
        r = CC.GetRepresentant(1, informations=infos)
        self.assertEqual(r["prenom"], "Éléonore")


class DetecterTarifsTests(unittest.TestCase):
    def test_taux_unique_quand_toutes_les_activites_concordent(self):
        dictDonnees = _dict_donnees_simple(seances=[
            ("2026-09-02", "09:00", "11:00", 40.00),
            ("2026-09-09", "10:00", "11:00", 20.00),
        ])
        resultat = CC.DetecterTarifs(dictDonnees)
        self.assertEqual(resultat["mode"], "unique")
        self.assertEqual(resultat["taux"], Decimal("20.00"))

    def test_taux_multiples_coherents_par_activite(self):
        dictDonnees = _dict_donnees_simple(IDactivite=10, nom_activite="Encadrement enfants", seances=[
            ("2026-09-02", "17:30", "19:00", 36.00),
            ("2026-09-09", "17:30", "19:00", 36.00),
        ])
        dictDonnees[2] = _dict_donnees_simple(IDactivite=11, nom_activite="Encadrement adultes", seances=[
            ("2026-09-07", "19:30", "20:30", 36.50),
        ])[1]
        resultat = CC.DetecterTarifs(dictDonnees)
        self.assertEqual(resultat["mode"], "detail")
        self.assertEqual(resultat["taux_par_activite"][10], Decimal("24.00"))
        self.assertEqual(resultat["taux_par_activite"][11], Decimal("36.50"))

    def test_taux_ambigu_bascule_en_manuel(self):
        dictDonnees = _dict_donnees_simple(seances=[
            ("2026-09-02", "09:00", "10:00", 20.00),
            ("2026-09-09", "09:00", "10:00", 25.00),
        ])
        resultat = CC.DetecterTarifs(dictDonnees)
        self.assertEqual(resultat["mode"], "manuel")

    def test_aucune_prestation_donne_mode_manuel(self):
        dictDonnees = _dict_donnees_simple(seances=[])
        resultat = CC.DetecterTarifs(dictDonnees)
        self.assertEqual(resultat["mode"], "manuel")

    def test_ne_modifie_jamais_le_dict_donnees_fourni(self):
        dictDonnees = _dict_donnees_simple(seances=[("2026-09-02", "09:00", "10:00", 20.00)])
        import copy
        avant = copy.deepcopy(dictDonnees)
        CC.DetecterTarifs(dictDonnees)
        self.assertEqual(dictDonnees, avant)


class GetResumePlanningTests(unittest.TestCase):
    def test_resume_creneau_hebdomadaire_recurrent(self):
        dictDonnees = _dict_donnees_simple(
            nom="ATOUT SPORTS", prenom="Badminton enfants", nom_activite="Encadrement enfants",
            seances=[
                ("2026-09-02", "17:30", "19:00", 36.00),
                ("2026-09-09", "17:30", "19:00", 36.00),
                ("2026-09-16", "17:30", "19:00", 36.00),
            ],
        )
        resume = CC.GetResumePlanning(dictDonnees)
        self.assertIn("Mercredi de 17h30 à 19h00", resume["detail"])
        self.assertEqual(resume["nbre_seances"], 3)
        self.assertEqual(resume["total_heures_minutes"], 3 * 90)
        self.assertEqual(resume["total_montant"], Decimal("108.00"))

    def test_ne_fabrique_pas_de_libelle_absent_des_donnees(self):
        """ Le libellé de l'activité affiché est exactement celui présent
        dans Noethys : aucune discipline ("Fitness", "Badminton", ...)
        n'est inventée si elle n'est pas dans le nom d'activité fourni. """
        dictDonnees = _dict_donnees_simple(
            nom_activite="Encadrement sportif enfants",
            seances=[("2026-09-02", "17:30", "19:00", 36.00)],
        )
        resume = CC.GetResumePlanning(dictDonnees)
        self.assertIn("Encadrement sportif enfants", resume["detail"])
        self.assertNotIn("Fitness", resume["detail"])
        self.assertNotIn("Badminton", resume["detail"])

    def test_symbole_euro_non_altere_dans_les_totaux(self):
        # Le résumé produit des Decimal, pas de texte formaté avec le
        # symbole monnaie : on vérifie juste qu'une chaîne contenant un
        # symbole € dans un nom d'activité traverse sans erreur.
        dictDonnees = _dict_donnees_simple(
            nom_activite="Encadrement (tarif révisé à 20€/h)",
            seances=[("2026-09-02", "09:00", "10:00", 20.00)],
        )
        resume = CC.GetResumePlanning(dictDonnees)
        self.assertIn("€", resume["detail"])

    def test_planning_vide(self):
        resume = CC.GetResumePlanning({})
        self.assertEqual(resume["detail"], "")
        self.assertEqual(resume["nbre_seances"], 0)
        self.assertEqual(resume["total_heures_minutes"], 0)
        self.assertEqual(resume["total_montant"], Decimal("0"))

    def test_regroupement_par_individu_pour_plusieurs_cycles(self):
        """ Cas scolaire : chaque cycle est un individu distinct, le résumé
        doit les séparer sans les fusionner. """
        dictDonnees = _dict_donnees_simple(
            nom="ECOLE TEST", prenom="CYCLE 3",
            seances=[("2026-09-02", "09:00", "11:00", 40.00)],
        )
        dictDonnees[2] = _dict_donnees_simple(
            nom="ECOLE TEST", prenom="CYCLE 1",
            seances=[("2026-09-03", "10:00", "11:00", 20.00)],
        )[1]
        resume = CC.GetResumePlanning(dictDonnees)
        self.assertIn("CYCLE 3", resume["detail"])
        self.assertIn("CYCLE 1", resume["detail"])
        self.assertEqual(resume["nbre_seances"], 2)


class GetChampsConventionIntegrationTests(unittest.TestCase):
    def test_generation_bout_en_bout_sur_base_synthetique(self):
        with creer_base_association_simple() as base:
            champs, dictDonnees = CC.GetChampsConvention(
                IDfamille=1, date_debut="2026-09-01", date_fin="2026-09-30",
                saison="2026-2027", listeIDindividus=[2, 3], DB=base.db,
                informations=FauxInformations({"{NBRE_REPRESENTANTS_RATTACHES}": 0}),
            )
        self.assertEqual(champs["{CONVENTION_SAISON}"], "2026-2027")
        self.assertEqual(champs["{CONVENTION_PLANNING_NBRE_SEANCES}"], 6)
        self.assertAlmostEqual(champs["{CONVENTION_PLANNING_TOTAL_MONTANT}"], 217.5)
        self.assertEqual(champs["{CONVENTION_TARIF_ADULTE}"], 36.5)
        self.assertEqual(champs["{CONVENTION_TARIF_ENFANT}"], 24.0)
        self.assertIn("consommation #", champs["{CONVENTION_TARIF_ADULTE_PROVENANCE}"])
        self.assertIn("prestation #", champs["{CONVENTION_TARIF_ADULTE_PROVENANCE}"])
        self.assertIn("36,50 €/h", champs["{CONVENTION_TARIF_ADULTE_PROVENANCE}"])
        self.assertIn("consommation #", champs["{CONVENTION_TARIF_ENFANT_PROVENANCE}"])
        self.assertIn("24,00 €/h", champs["{CONVENTION_TARIF_ENFANT_PROVENANCE}"])
        # La clé reste presente (vide) plutot qu'absente : c'est ce qui
        # permet au moteur [[SI {CHAMP}=->...]] de detecter "vide" dans
        # le modele .ndc (une cle absente ne declenche aucune des deux
        # branches d'un bloc [[SI ...]]).
        self.assertEqual(champs["{CONVENTION_REPRESENTANT_NOM}"], u"")

    def test_representant_present_est_reporte_dans_les_champs(self):
        infos = FauxInformations({
            "{NBRE_REPRESENTANTS_RATTACHES}": 1,
            "{REPRESENTANT_RATTACHE_1_PRENOM}": "Chantal",
            "{REPRESENTANT_RATTACHE_1_NOM}": "LE GALL",
            "{REPRESENTANT_RATTACHE_1_NOM_COMPLET}": "Mme LE GALL Chantal",
        })
        with creer_base_association_simple() as base:
            champs, _ = CC.GetChampsConvention(
                IDfamille=1, date_debut="2026-09-01", date_fin="2026-09-30",
                listeIDindividus=[2, 3], DB=base.db, informations=infos,
            )
        self.assertEqual(champs["{CONVENTION_REPRESENTANT_NOM_COMPLET}"], "Mme LE GALL Chantal")


class GetChampsConventionOverridesTests(unittest.TestCase):
    """ Les overrides (saisis dans DLG_Generation_convention) sont
    appliques APRES le calcul automatique, uniquement sur les cles
    fournies, et ne modifient jamais aucune donnee Noethys : voir
    UTILS_Convention_champs.GetChampsConvention(overrides=...). """

    def test_override_representant_ecrase_la_valeur_automatique(self):
        infos = FauxInformations({
            "{NBRE_REPRESENTANTS_RATTACHES}": 1,
            "{REPRESENTANT_RATTACHE_1_PRENOM}": "Chantal",
            "{REPRESENTANT_RATTACHE_1_NOM}": "LE GALL",
            "{REPRESENTANT_RATTACHE_1_NOM_COMPLET}": "Mme LE GALL Chantal",
        })
        with creer_base_association_simple() as base:
            champs, _ = CC.GetChampsConvention(
                IDfamille=1, listeIDindividus=[2, 3], DB=base.db, informations=infos,
                overrides={"{CONVENTION_REPRESENTANT_NOM_COMPLET}": "M. CORRIGE Manuellement"},
            )
        self.assertEqual(champs["{CONVENTION_REPRESENTANT_NOM_COMPLET}"], "M. CORRIGE Manuellement")

    def test_override_fonction_du_representant(self):
        """ La fonction n'est jamais determinee automatiquement (aucune
        donnee Noethys ne la porte) : c'est un override pur. """
        with creer_base_association_simple() as base:
            champs, _ = CC.GetChampsConvention(
                IDfamille=1, listeIDindividus=[2, 3], DB=base.db,
                informations=FauxInformations({"{NBRE_REPRESENTANTS_RATTACHES}": 0}),
                overrides={"{CONVENTION_REPRESENTANT_FONCTION}": "Présidente"},
            )
        self.assertEqual(champs["{CONVENTION_REPRESENTANT_FONCTION}"], "Présidente")

    def test_override_date_et_lieu_de_signature(self):
        with creer_base_association_simple() as base:
            champs, _ = CC.GetChampsConvention(
                IDfamille=1, listeIDindividus=[2, 3], DB=base.db,
                informations=FauxInformations({"{NBRE_REPRESENTANTS_RATTACHES}": 0}),
                overrides={
                    "{CONVENTION_DATE_SIGNATURE}": "21/09/2026",
                    "{CONVENTION_LIEU_SIGNATURE}": "TESTVILLE",
                },
            )
        self.assertEqual(champs["{CONVENTION_DATE_SIGNATURE}"], "21/09/2026")
        self.assertEqual(champs["{CONVENTION_LIEU_SIGNATURE}"], "TESTVILLE")

    def test_override_none_ne_remplace_pas_la_valeur_automatique(self):
        """ Un dialogue qui ne renseigne pas une cle (valeur None) ne doit
        jamais effacer une valeur deja determinee automatiquement. """
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                champs, _ = CC.GetChampsConvention(
                    IDfamille=2, listeIDindividus=[20, 21, 22], DB=base.db,
                    overrides={"{CONVENTION_TARIF_HORAIRE}": None},
                )
        self.assertEqual(champs["{CONVENTION_TARIF_HORAIRE}"], 20.0)

    def test_tarif_automatique_utilise_si_aucun_override(self):
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                champs, _ = CC.GetChampsConvention(
                    IDfamille=2, listeIDindividus=[20, 21, 22], DB=base.db,
                )
        self.assertEqual(champs["{CONVENTION_TARIF_HORAIRE}"], 20.0)

    def test_tarif_override_ecrase_le_tarif_automatique(self):
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                champs, _ = CC.GetChampsConvention(
                    IDfamille=2, listeIDindividus=[20, 21, 22], DB=base.db,
                    overrides={"{CONVENTION_TARIF_HORAIRE}": 22.5},
                )
        self.assertEqual(champs["{CONVENTION_TARIF_HORAIRE}"], 22.5)

    def test_tarif_ambigu_reste_vide_sans_override(self):
        with creer_base_tarif_ambigu_simple() as base:
            with RedirectionGestionDB(base.chemin):
                champs, dictDonnees = CC.GetChampsConvention(
                    IDfamille=1, listeIDindividus=[2], DB=base.db,
                )
        self.assertEqual(CC.DetecterTarifs(dictDonnees)["mode"], "manuel")
        self.assertEqual(champs["{CONVENTION_TARIF_HORAIRE}"], u"")

    def test_tarif_ambigu_est_utilisable_avec_un_override_manuel(self):
        with creer_base_tarif_ambigu_simple() as base:
            with RedirectionGestionDB(base.chemin):
                champs, _ = CC.GetChampsConvention(
                    IDfamille=1, listeIDindividus=[2], DB=base.db,
                    overrides={"{CONVENTION_TARIF_HORAIRE}": 40.0},
                )
        self.assertEqual(champs["{CONVENTION_TARIF_HORAIRE}"], 40.0)

    def test_override_ne_modifie_jamais_les_prestations_en_base(self):
        """ Les overrides ne sont que des valeurs de generation : la table
        prestations doit etre strictement identique avant/apres, meme
        quand un tarif different est fourni en override. """
        with creer_base_ecole_simple() as base:
            base.db.ExecuterReq("SELECT IDprestation, label, montant FROM prestations ORDER BY IDprestation;")
            avant = base.db.ResultatReq()

            with RedirectionGestionDB(base.chemin):
                CC.GetChampsConvention(
                    IDfamille=2, listeIDindividus=[20, 21, 22], DB=base.db,
                    overrides={"{CONVENTION_TARIF_HORAIRE}": 999.99},
                )

            base.db.ExecuterReq("SELECT IDprestation, label, montant FROM prestations ORDER BY IDprestation;")
            apres = base.db.ResultatReq()
        self.assertEqual(avant, apres)


class PeriodeAdresseTarifRecetteTests(unittest.TestCase):
    def test_periode_par_defaut_vient_des_seances_et_pas_du_jour_courant(self):
        import datetime
        with creer_base_association_simple() as base:
            debut, fin = CC.GetPeriodeParDefaut(
                1, date_reference=datetime.date(2026, 9, 10), DB=base.db,
            )
        self.assertEqual(str(debut), "2026-09-02")
        self.assertEqual(str(fin), "2026-09-21")

    def test_adresse_ne_duplique_pas_cp_ville_deja_inclus_dans_la_rue(self):
        adresse = CC.ComposerAdresseConvention(
            "1, Place Saint Martin - 35130 MOUTIERS", "35130", "MOUTIERS"
        )
        self.assertEqual(adresse, "1, Place Saint Martin\n35130 MOUTIERS")
        self.assertEqual(adresse.count("35130 MOUTIERS"), 1)

    def test_creneaux_compacts_ne_repetent_pas_les_dates_de_seances(self):
        donnees = _dict_donnees_simple(
            nom="ATOUT SPORTS", prenom="Badminton enfants",
            nom_activite="Encadrement enfants",
            seances=[
                ("2026-09-02", "17:30", "19:00", 36.0),
                ("2026-09-09", "17:30", "19:00", 36.0),
            ],
        )
        resume = CC.GetResumePlanning(donnees)
        self.assertIn("Mercredi de 17h30 à 19h00", resume["creneaux"])
        self.assertNotIn("02/09/2026", resume["creneaux"])

    def test_provenance_tarifs_adulte_enfant_est_explicite(self):
        with creer_base_association_simple() as base:
            champs, _ = CC.GetChampsConvention(
                IDfamille=1, date_debut="2026-09-01", date_fin="2026-09-30",
                listeIDindividus=[2, 3], DB=base.db,
                informations=FauxInformations({"{NBRE_REPRESENTANTS_RATTACHES}": 0}),
            )
        self.assertEqual(champs["{CONVENTION_TARIF_ADULTE}"], 36.5)
        self.assertEqual(champs["{CONVENTION_TARIF_ENFANT}"], 24.0)
        self.assertIn("36,50 € / 1h00 = 36,50 €/h", champs["{CONVENTION_TARIF_ADULTE_PROVENANCE}"])
        self.assertIn("36,00 € / 1h30 = 24,00 €/h", champs["{CONVENTION_TARIF_ENFANT_PROVENANCE}"])
        self.assertEqual(champs["{CONVENTION_TARIF_ADULTE_AFFICHE}"], "36,50 €")
        self.assertEqual(champs["{CONVENTION_TARIF_ENFANT_AFFICHE}"], "24,00 €")


if __name__ == "__main__":
    unittest.main()