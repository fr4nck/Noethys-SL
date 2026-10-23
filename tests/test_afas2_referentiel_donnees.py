# -*- coding: utf-8 -*-
"""AFAS V2 -- référentiel des sites et chargement des données Noethys.

Base SQLite fictive (aucune donnée réelle), garde réseau active.
"""
import copy
import datetime
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402,F401
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_AFAS2_Referentiel as R  # noqa: E402
from Utils import UTILS_AFAS2_Donnees as Donnees  # noqa: E402

D = datetime.date
GROUPES = [(11, 1, "Bais +6 ans"), (12, 1, "Bais -6 ans"), (13, 1, "Moutiers"), (14, 1, "La Guerche"),
           (15, 1, "Minicamps 6/8"), (16, 1, "Minicamps 8/10"), (21, 2, "Club Ados"), (17, 1, "Bais")]


def referentiel():
    def lien(IDgroupe, nom, equipement):
        return {"IDactivite": 1, "IDgroupe": IDgroupe, "nom_groupe": nom, "equipement": equipement}
    return {"format": 2, "moutiers_rattachement_confirme": False, "sejours": [], "samedis_avec_ecole": {},
            "justificatifs": {R.MINICAMPS_6_8: "Déclaration fictive n° 0001"}, "regularisations": {}, "sites": {
        R.BAIS_PLUS_6: lien(11, "Bais +6 ans", "BAIS"), R.BAIS_MOINS_6: lien(12, "Bais -6 ans", "BAIS"),
        R.MOUTIERS: lien(13, "Moutiers", "LA_GUERCHE_MOUTIERS"), R.LA_GUERCHE: lien(14, "La Guerche", "LA_GUERCHE_MOUTIERS"),
        R.MINICAMPS_6_8: lien(15, "Minicamps 6/8", "BAIS"), R.MINICAMPS_8_10: lien(16, "Minicamps 8/10", None)}}


def groupes_dict():
    return {IDgroupe: (IDactivite, nom) for IDgroupe, IDactivite, nom in GROUPES}


class ReferentielTests(unittest.TestCase):
    def test_referentiel_valide(self):
        self.assertEqual(R.ValiderReferentiel(referentiel(), groupes_dict())["sites"][R.MOUTIERS]["IDgroupe"], 13)

    def test_matrice_alsh(self):
        self.assertEqual(R.SitesAdmissibles("ALSH", "periscolaire"), (R.BAIS_PLUS_6, R.BAIS_MOINS_6, R.MOUTIERS, R.LA_GUERCHE))
        self.assertNotIn("Bais", R.SITES)
        self.assertFalse(any("Minicamps" in s for s in R.SitesAdmissibles("ALSH", "periscolaire")))
        with self.assertRaises(R.ReferentielInvalide):
            R.SitesAdmissibles("ALSH Ados", "periscolaire")

    def test_25_groupe_supprime(self):
        groupes = groupes_dict()
        del groupes[13]
        with self.assertRaisesRegex(R.ReferentielInvalide, "n'existe plus"):
            R.ValiderReferentiel(referentiel(), groupes)

    def test_25_groupe_renomme_ou_permute(self):
        groupes = groupes_dict()
        groupes[13], groupes[14] = (1, "La Guerche"), (1, "Moutiers")
        with self.assertRaisesRegex(R.ReferentielInvalide, "renommé ou permuté"):
            R.ValiderReferentiel(referentiel(), groupes)

    def test_casse_et_espaces_tolerees_pas_les_autres_noms(self):
        groupes = groupes_dict()
        groupes[11] = (1, "  bais +6  ANS ")
        R.ValiderReferentiel(referentiel(), groupes)
        groupes[11] = (1, "Bais")
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(referentiel(), groupes)

    def test_activite_proprietaire_verifiee(self):
        ref = referentiel()
        ref["sites"][R.BAIS_PLUS_6]["IDactivite"] = 2
        with self.assertRaisesRegex(R.ReferentielInvalide, "appartient à l'activité"):
            R.ValiderReferentiel(ref, groupes_dict())

    def test_meme_groupe_pour_deux_sites(self):
        ref = referentiel()
        ref["sites"][R.BAIS_MOINS_6] = dict(ref["sites"][R.BAIS_PLUS_6])
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(ref, groupes_dict())

    def test_site_hors_matrice_ou_identifiant_suppose(self):
        ref = referentiel()
        ref["sites"]["Bais"] = {"IDactivite": 1, "IDgroupe": 17, "nom_groupe": "Bais", "equipement": "BAIS"}
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(ref, groupes_dict())
        ref = referentiel()
        ref["sites"][R.BAIS_PLUS_6]["IDgroupe"] = "11"
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(ref, groupes_dict())

    def test_rattachement_contraire_a_la_convention(self):
        ref = referentiel()
        ref["sites"][R.MOUTIERS]["equipement"] = "BAIS"
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(ref, groupes_dict())

    def test_28_moutiers_non_validable_sans_confirmation(self):
        ref = R.ValiderReferentiel(referentiel(), groupes_dict())
        self.assertEqual(R.StatutSite(ref, R.MOUTIERS, "periscolaire")[0], False)
        ref["moutiers_rattachement_confirme"] = True
        # Confirmation seule : le formulaire d'implantation doit être référencé.
        self.assertFalse(R.StatutSite(ref, R.MOUTIERS, "periscolaire")[0])
        ref["justificatifs"][R.MOUTIERS] = "Formulaire d'implantation fictif"
        self.assertEqual(R.StatutSite(ref, R.MOUTIERS, "periscolaire"), (True, ""))

    def test_minicamp_sans_equipement_non_validable(self):
        ref = R.ValiderReferentiel(referentiel(), groupes_dict())
        self.assertFalse(R.StatutSite(ref, R.MINICAMPS_8_10, "extrascolaire")[0])
        self.assertTrue(R.StatutSite(ref, R.MINICAMPS_6_8, "extrascolaire")[0])

    def test_minicamp_sans_justificatif_non_validable(self):
        # Rattachement choisi mais non fondé sur la déclaration de l'équipement organisateur.
        ref = referentiel()
        del ref["justificatifs"][R.MINICAMPS_6_8]
        ref = R.ValiderReferentiel(ref, groupes_dict())
        validable, motif = R.StatutSite(ref, R.MINICAMPS_6_8, "extrascolaire")
        self.assertFalse(validable)
        self.assertIn("justificatif", motif)

    def test_justificatif_sans_objet_ou_vide_refuse(self):
        for justificatifs in ({R.LA_GUERCHE: "x"}, {R.MINICAMPS_6_8: "  "}, {R.MINICAMPS_6_8: 3},
                              {R.MINICAMPS_6_8: "x" * 301}):
            ref = referentiel()
            ref["justificatifs"] = justificatifs
            with self.subTest(justificatifs=justificatifs), self.assertRaises(R.ReferentielInvalide):
                R.ValiderReferentiel(ref, groupes_dict())

    def test_samedis_avec_ecole_dates(self):
        ref = referentiel()
        ref["samedis_avec_ecole"] = {"2026": ["2026-11-28"], "2025": []}
        self.assertEqual(R.ValiderReferentiel(ref, groupes_dict())["samedis_avec_ecole"]["2026"], ["2026-11-28"])
        for samedis in ({"2026": ["2026-11-27"]},              # vendredi
                        {"2025": ["2026-11-28"]},              # autre année scolaire
                        {"2026": ["2026-11-28", "2026-11-28"]},
                        {"26": []}, {"2026": "2026-11-28"}, []):
            ref["samedis_avec_ecole"] = samedis
            with self.subTest(samedis=samedis), self.assertRaises(R.ReferentielInvalide):
                R.ValiderReferentiel(ref, groupes_dict())

    def test_saisie_texte_des_samedis(self):
        calendrier = R.LireSamedisTexte("2026 : 2026-11-28, 2027-03-13\n\n2025 : aucun")
        self.assertEqual(calendrier, {"2026": ["2026-11-28", "2027-03-13"], "2025": []})
        self.assertEqual(R.LireSamedisTexte(R.TexteSamedis(calendrier)), calendrier)
        for texte in ("2026", "2026 :", "2026 : 2026-11-27", "2026 : aucun\n2026 : aucun"):
            with self.subTest(texte=texte), self.assertRaises(R.ReferentielInvalide):
                R.LireSamedisTexte(texte)

    def test_saisie_d_une_regularisation(self):
        self.assertEqual(R.LireRegularisation(" 9001 ", "12, 13", " Avoir "),
                         ("9001", {"consommations_annulees": [12, 13], "justification": "Avoir"}))
        self.assertEqual(R.LireRegularisation("9002", "", "Trop-perçu")[1]["consommations_annulees"], [])
        for saisie in (("x", "", "a"), ("9001", "a,b", "a"), ("9001", "1", "")):
            with self.subTest(saisie=saisie), self.assertRaises(R.ReferentielInvalide):
                R.LireRegularisation(*saisie)

    def test_migration_format_1(self):
        ancien = referentiel()
        ancien["format"] = 1
        del ancien["samedis_avec_ecole"], ancien["justificatifs"], ancien["regularisations"]
        migre = R.ValiderReferentiel(ancien, groupes_dict())
        self.assertEqual((migre["format"], migre["samedis_avec_ecole"], migre["justificatifs"], migre["regularisations"]),
                         (2, {}, {}, {}))
        # Plus strict après migration : les minicamps doivent être justifiés.
        self.assertFalse(R.StatutSite(migre, R.MINICAMPS_6_8, "extrascolaire")[0])

    def test_regularisations_qualifiees(self):
        ref = referentiel()
        ref["regularisations"] = {"9001": {"consommations_annulees": [12, 13], "justification": "Avoir maladie (fictif)"},
                                  "9002": {"consommations_annulees": [], "justification": "Remboursement de trop-perçu"}}
        self.assertEqual(len(R.ValiderReferentiel(ref, groupes_dict())["regularisations"]), 2)
        for regularisations in ({"x": {"consommations_annulees": [], "justification": "a"}},
                                {"09001": {"consommations_annulees": [], "justification": "a"}},
                                {"9001": {"consommations_annulees": [1, 1], "justification": "a"}},
                                {"9001": {"consommations_annulees": ["1"], "justification": "a"}},
                                {"9001": {"consommations_annulees": [], "justification": " "}},
                                {"9001": {"consommations_annulees": []}}, []):
            ref["regularisations"] = regularisations
            with self.subTest(regularisations=regularisations), self.assertRaises(R.ReferentielInvalide):
                R.ValiderReferentiel(ref, groupes_dict())

    def test_cle_inconnue_refusee(self):
        ref = referentiel()
        ref["annee"] = 2026
        with self.assertRaises(R.ReferentielInvalide):
            R.ValiderReferentiel(ref, groupes_dict())


class SejoursTests(unittest.TestCase):
    def sejour(self, **kw):
        s = {"id": "s1", "libelle": "Camp", "site": R.MINICAMPS_6_8, "date_debut": "2026-07-06", "date_fin": "2026-07-09",
             "nuits": 3, "prevu_declaration_annuelle": False, "integre_projet_educatif": True, "declare_sejour_vacances": False}
        s.update(kw)
        return s

    def test_sejour_accessoire_admis(self):
        self.assertTrue(R.ValiderSejour(self.sejour(), referentiel()["sites"]))

    def test_sejours_non_admissibles(self):
        cas = [dict(nuits=6, date_fin="2026-07-12"), dict(nuits=0, date_fin="2026-07-06"), dict(date_fin="2026-07-10"),
               dict(integre_projet_educatif=False), dict(nuits=5, date_fin="2026-07-11"), dict(site="Bais"),
               dict(nuits="3"), dict(date_debut="06/07/2026")]
        for modif in cas:
            with self.subTest(modif=modif), self.assertRaises(R.ReferentielInvalide):
                R.ValiderSejour(self.sejour(**modif), referentiel()["sites"])

    def test_sejour_5_nuits_conditions_cumulatives(self):
        s = self.sejour(nuits=5, date_fin="2026-07-11", prevu_declaration_annuelle=True, declare_sejour_vacances=True)
        self.assertTrue(R.ValiderSejour(s, referentiel()["sites"]))


class _BaseDB(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        for table in ("ouvertures", "factures", "aeeh_periodes", "vacances", "profils", "profils_parametres"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        self.base.inserer("activites", ["IDactivite", "nom"], [(1, "ALSH"), (2, "ALSH Ados")])
        self.base.inserer("groupes", ["IDgroupe", "IDactivite", "nom"], GROUPES)
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], [(1, "FICTIF", "Lea", 1), (2, "FICTIF", "Tom", 1)])
        self.base.inserer("unites", ["IDunite", "IDactivite", "nom", "type", "heure_debut", "heure_fin"],
                          [(101, 1, "Matin", "Unitaire", "07:30", "08:45"), (201, 1, "Journée", "Unitaire", "08:30", "17:30"),
                           (301, 2, "Ados", "Unitaire", "14:00", "18:00")])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def conso(self, IDconso, individu, date, IDunite, IDactivite, IDgroupe, etat="present", IDprestation=None):
        self.base.inserer("consommations", ["IDconso", "IDindividu", "date", "IDunite", "IDactivite", "IDgroupe",
                                            "heure_debut", "heure_fin", "etat", "IDprestation"],
                          [(IDconso, individu, date, IDunite, IDactivite, IDgroupe, "08:30", "17:30", etat, IDprestation)])


class DonneesTests(_BaseDB):
    def test_consommations_restreintes_aux_couples_exacts(self):
        self.conso(1, 1, "2026-10-19", 201, 1, 11)
        self.conso(2, 1, "2026-10-19", 201, 1, 12)   # Bais -6 non demandé
        self.conso(3, 1, "2026-10-19", 301, 2, 11)   # activité 2 avec groupe 11 : couple croisé
        lignes = Donnees.ChargerConsommations([(1, 11), (2, 21)], D(2026, 1, 1), D(2026, 12, 31))
        self.assertEqual([l["IDconso"] for l in lignes], [1])
        self.assertEqual(lignes[0]["individu"], "FICTIF Lea")
        self.assertEqual(lignes[0]["date"], D(2026, 10, 19))

    def test_tous_les_statuts_charges_y_compris_inconnus(self):
        for i, etat in enumerate(("present", "reservation", "refus", None, "xyz"), 1):
            self.conso(i, 1, "2026-10-%02d" % (18 + i), 201, 1, 11, etat=etat)
        etats = [l["etat"] for l in Donnees.ChargerConsommations([(1, 11)], D(2026, 1, 1), D(2026, 12, 31))]
        self.assertEqual(etats, ["present", "reservation", "refus", None, "xyz"])

    def test_facture_annulee_et_prestation_non_facturee(self):
        self.base.inserer("factures", ["IDfacture", "numero", "etat"], [(1, 1, None), (2, 2, "annulation")])
        self.base.inserer("prestations", ["IDprestation", "IDfacture"], [(10, 1), (11, 2), (12, None)])
        for i, prestation in enumerate((10, 11, 12), 1):
            self.conso(i, i, "2026-10-19", 201, 1, 11, IDprestation=prestation)
        lignes = Donnees.ChargerConsommations([(1, 11)], D(2026, 1, 1), D(2026, 12, 31))
        self.assertEqual([(l["IDfacture"], l["facture_etat"]) for l in lignes], [(1, None), (2, "annulation"), (None, None)])

    def test_detail_de_la_prestation_charge(self):
        self.base.inserer("factures", ["IDfacture", "numero", "etat"], [(1, 1, None)])
        self.base.inserer("prestations", ["IDprestation", "IDfacture", "montant", "forfait", "forfait_date_debut",
                                          "IDindividu", "IDfamille"],
                          [(10, 1, 12.5, None, None, 1, 501), (11, 1, 30.0, 2, "2026-10-19", 2, 502)])
        self.conso(1, 1, "2026-10-19", 201, 1, 11, IDprestation=10)
        self.conso(2, 2, "2026-10-19", 201, 1, 11, IDprestation=11)
        lignes = Donnees.ChargerConsommations([(1, 11)], D(2026, 1, 1), D(2026, 12, 31))
        self.assertEqual([(l["prestation_montant"], l["prestation_forfait"], l["prestation_forfait_debut"],
                           l["prestation_IDindividu"], l["IDfamille"]) for l in lignes],
                         [(12.5, None, None, 1, 501), (30.0, 2, "2026-10-19", 2, 502)])
        self.assertIn("quantite", lignes[0])

    def test_regularisations_non_rattachees(self):
        self.base.inserer("factures", ["IDfacture", "numero", "etat"], [(5, 5, None)])
        self.base.inserer("prestations", ["IDprestation", "IDfacture", "montant", "date", "IDactivite", "IDindividu",
                                          "IDfamille", "label", "categorie"], [
            (20, 5, -15.0, "2026-11-05", 1, 1, 501, "Avoir absence", "consommation"),     # retenue
            (21, None, -8.0, "2026-11-06", None, None, 501, "Avoir famille", "autre"),     # retenue (famille)
            (22, None, -8.0, "2026-11-06", 2, 9, 900, "Avoir ados", "consommation"),        # hors périmètre
            (23, None, 12.0, "2026-11-06", 1, 1, 501, "Positive", "consommation"),          # positive
            (24, None, -5.0, "2027-06-01", 1, 1, 501, "Hors fenêtre", "consommation"),      # hors fenêtre
            (25, None, -5.0, "2026-11-07", 1, 1, 501, "Rattachée", "consommation")])        # rattachée à une conso
        self.conso(1, 1, "2026-10-19", 201, 1, 11, IDprestation=25)
        lignes = Donnees.ChargerRegularisations([1], [1], [501], D(2026, 1, 1), D(2027, 3, 31))
        self.assertEqual([(l["IDprestation"], l["IDindividu"], l["IDfacture"]) for l in lignes], [(20, 1, 5), (21, None, None)])
        self.assertEqual(Donnees.ChargerRegularisations([], [], [], D(2026, 1, 1), D(2027, 3, 31)), [])

    def test_ouvertures_unites_aeeh(self):
        self.base.inserer("ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"],
                          [(1, 201, 11, "2026-10-19"), (1, 201, 12, "2026-10-19"), (2, 301, 11, "2026-10-19")])
        self.assertEqual(Donnees.ChargerOuvertures([(1, 11)], D(2026, 1, 1), D(2026, 12, 31)), {(1, 201, 11, D(2026, 10, 19))})
        self.assertEqual(set(Donnees.ChargerUnites([1])), {101, 201})
        self.base.inserer("aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"], [(1, 1, "2026-06-01", None)])
        self.assertEqual(Donnees.ChargerAEEH([1, 2]), {1: [(D(2026, 6, 1), None)]})

    def test_couples_invalides(self):
        for couples in ([], [(1, "11")], [("1", 11)]):
            with self.subTest(couples=couples), self.assertRaises(ValueError):
                Donnees.ChargerConsommations(couples, D(2026, 1, 1), D(2026, 12, 31))


class PersistanceReferentielTests(_BaseDB):
    def test_enregistrement_et_relecture(self):
        self.assertEqual(R.ChargerReferentiel(), R.ReferentielVide())
        R.EnregistrerReferentiel(referentiel())
        relu = R.ChargerReferentiel()
        self.assertEqual(relu["sites"][R.LA_GUERCHE]["IDgroupe"], 14)

    def test_relecture_refuse_un_groupe_devenu_invalide(self):
        R.EnregistrerReferentiel(referentiel())
        self.base.db.ExecuterReq("UPDATE groupes SET nom='Autre' WHERE IDgroupe=11;")
        self.base.db.Commit()
        with self.assertRaises(R.ReferentielInvalide):
            R.ChargerReferentiel()

    def test_aucun_residu_d_anciennes_cles(self):
        R.EnregistrerReferentiel(referentiel())
        IDprofil = R.ProfilsCategorie(R.CATEGORIE_PROFIL)[0][0]
        self.base.inserer("profils_parametres", ["nom", "parametre", "type_donnee", "IDprofil"], [("annee", "2026", "autre", IDprofil)])
        with self.assertRaises(ValueError):
            R.ChargerReferentiel()
        R.EnregistrerReferentiel(referentiel())
        self.assertEqual(R.ChargerReferentiel()["format"], 2)

    def test_enregistrement_refuse_un_referentiel_invalide(self):
        ref = referentiel()
        ref["sites"][R.BAIS_PLUS_6]["IDgroupe"] = 99
        with self.assertRaises(R.ReferentielInvalide):
            R.EnregistrerReferentiel(ref)
        self.assertEqual(R.ProfilsCategorie(R.CATEGORIE_PROFIL), [])


if __name__ == "__main__":
    unittest.main()
