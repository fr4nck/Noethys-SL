# -*- coding: utf-8 -*-
"""Contrat #436 : donnees fictives, aucune base PMSL et aucun portail."""
import sqlite3
import unittest
from datetime import date
from Utils import UTILS_Fiche_accueil_enfant as F

JOUR = "2026-10-28"
DROITS = dict.fromkeys(F.RUBRIQUES, True)


def preuve(**changements):
    entree = {"IDindividu": 11, "type": "piscine_baignade", "perimetre": "general",
              "valeur": 1, "date_debut": "2026-09-01", "date_fin": "2027-08-31",
              "repondu_le": "2026-09-01T09:00:00+02:00", "signataire": 21,
              "autorite_verifiee": True, "texte_version": "v1", "preuve": "piece-fictive"}
    entree.update(changements)
    return entree


class EtablissementDesDroits(unittest.TestCase):
    def test_par_defaut_tout_est_masque_et_portail_eteint(self):
        fiche = F.ConstruireFiche(11, JOUR, aeeh=1, pai={"statut": "valide"},
                                 type_repas="standard", autorisations=[preuve()])
        self.assertEqual(fiche["aeeh"], {"etat": "restreint"})
        self.assertEqual(fiche["pai"], {"etat": "restreint"})
        self.assertEqual(fiche["repas"], {"etat": "restreint"})
        self.assertEqual(set(x["etat"] for x in fiche["autorisations"].values()), {"restreint"})
        self.assertFalse(any(fiche["portail"].values()))

    def test_droits_partiels_isolent_les_rubriques(self):
        fiche = F.ConstruireFiche(11, JOUR, {"repas": True}, type_repas="vegetarien",
                                 aeeh=999, pai={"statut": "invalide"}, autorisations="illisible")
        self.assertEqual(fiche["repas"]["etat"], "vegetarien")
        self.assertEqual(fiche["aeeh"]["etat"], "restreint")
        self.assertEqual(fiche["pai"]["etat"], "restreint")

    def test_droit_non_booleen_refuse(self):
        for valeur in (1, "oui", [], None):
            with self.subTest(valeur=valeur):
                fiche = F.ConstruireFiche(11, JOUR, {"aeeh": valeur}, aeeh=1)
                self.assertEqual(fiche["aeeh"]["etat"], "restreint")

    def test_champ_non_habilite_ne_propage_pas_erreur_de_donnees(self):
        self.assertEqual(F.ConstruireFiche(11, JOUR, {}, autorisations=object())["pai"],
                         {"etat": "restreint"})

    def test_identifiant_et_date_rejetes(self):
        for identifiant in (None, 0, -1, True, "1", 3.4):
            with self.subTest(identifiant=identifiant), self.assertRaises(F.FicheAccueilInvalide):
                F.ConstruireFiche(identifiant, JOUR)
        for jour in (None, "28/10/2026", "2026-02-30", "2026-1-2"):
            with self.subTest(jour=jour), self.assertRaises(F.FicheAccueilInvalide):
                F.ConstruireFiche(11, jour)

    def test_aucune_chaine_de_donnees_medicales_en_sortie(self):
        fiche = F.ConstruireFiche(11, JOUR, DROITS, aeeh=1,
            pai={"statut": "valide", "document_verifie": True, "valide_par": 9,
                 "date_debut": "2026-09-01", "date_fin": "2027-08-31",
                 "diagnostic": "NE JAMAIS EXPOSER", "document_ref": "FICHIER_SECRET"},
            autorisations=[preuve(note_medicale="NE JAMAIS EXPOSER")])
        self.assertNotIn("NE JAMAIS EXPOSER", str(fiche))
        self.assertNotIn("FICHIER_SECRET", str(fiche))


class ContratAEEH(unittest.TestCase):
    def test_trois_etats_de_la_colonne_existante(self):
        for valeur, libelle in [(None, "non_renseigne"), (0, "non"), (1, "oui")]:
            with self.subTest(valeur=valeur):
                self.assertEqual(F.EtatAEEH(valeur, [], JOUR),
                                 {"etat": libelle, "periode_active": None, "periodes": []})

    def test_statut_et_periodicite_sont_independants(self):
        droit = [{"date_debut": "2026-09-01", "date_fin": "2026-12-31"}]
        self.assertEqual(F.EtatAEEH(0, droit, JOUR),
                         {"etat": "non", "periode_active": True, "periodes": droit})
        self.assertEqual(F.EtatAEEH(1, droit, "2027-01-01"),
                         {"etat": "oui", "periode_active": False, "periodes": droit})

    def test_bornes_comprises_ouvertes(self):
        droits = [{"date_debut": "2026-09-01", "date_fin": "2026-10-28"}]
        self.assertTrue(F.EtatAEEH(None, droits, JOUR)["periode_active"])
        self.assertFalse(F.EtatAEEH(None, droits, "2026-10-29")["periode_active"])
        droits[0]["date_fin"] = None
        self.assertTrue(F.EtatAEEH(None, droits, "2040-01-01")["periode_active"])

    def test_valeurs_et_periodes_incorrectes(self):
        for valeur in (True, False, 2, "1", "non"):
            with self.subTest(valeur=valeur), self.assertRaises(F.FicheAccueilInvalide):
                F.EtatAEEH(valeur, [], JOUR)
        for droits in ([{"date_debut": "2026-12-01", "date_fin": "2026-01-01"}], [{}]):
            with self.subTest(droits=droits), self.assertRaises(F.FicheAccueilInvalide):
                F.EtatAEEH(1, droits, JOUR)


class ContratPAI(unittest.TestCase):
    def test_aucune_donnee_ne_devient_un_pai_non(self):
        self.assertEqual(F.EtatPAI(None, JOUR), {"etat": "non_renseigne"})
        self.assertEqual(F.EtatPAI({"statut": "non"}, JOUR), {"etat": "non"})

    def test_etapes_documentaires(self):
        for statut in ("signale", "document_a_verifier"):
            self.assertEqual(F.EtatPAI({"statut": statut}, JOUR)["etat"], statut)

    def test_valide_seulement_si_preuve_verifiee(self):
        p = {"statut": "valide", "date_debut": "2026-09-01", "date_fin": "2027-08-31",
             "document_verifie": True, "valide_par": 9}
        self.assertEqual(F.EtatPAI(p, JOUR)["etat"], "valide")
        self.assertEqual(F.EtatPAI(p, JOUR)["date_fin"], "2027-08-31")
        for changement in ({"document_verifie": False}, {"valide_par": None},
                           {"valide_par": True}):
            with self.subTest(changement=changement):
                self.assertEqual(F.EtatPAI(dict(p, **changement), JOUR)["etat"],
                                 "document_a_verifier")

    def test_validite_borne_et_expiration(self):
        p = {"statut": "valide", "date_debut": "2026-09-01", "date_fin": JOUR,
             "document_verifie": True, "valide_par": 9}
        self.assertEqual(F.EtatPAI(p, JOUR)["etat"], "valide")
        self.assertEqual(F.EtatPAI(p, "2026-10-29")["etat"], "expire")
        self.assertEqual(F.EtatPAI(p, "2026-08-31")["etat"], "non_renseigne")

    def test_metadonnees_malformees_refusees(self):
        for meta in ("oui", {"statut": "oui"}, {"statut": 1}):
            with self.subTest(meta=meta), self.assertRaises(F.FicheAccueilInvalide):
                F.EtatPAI(meta, JOUR)


class AutorisationsTracables(unittest.TestCase):
    def test_catalogue_inclut_les_autorisations_validees(self):
        self.assertEqual(len(F.AUTORISATIONS), 7)
        for categorie in ("piscine_baignade", "photos_prise", "photos_reseaux_sociaux",
                          "maquillage", "activites_physiques"):
            self.assertIn(categorie, F.AUTORISATIONS)

    def test_aucune_preuve_ne_signifie_pas_non(self):
        self.assertEqual(F.EtatAutorisation([], 11, "piscine_baignade", JOUR),
                         {"etat": "non_renseigne"})

    def test_oui_et_non_sont_distincts_et_dates(self):
        self.assertEqual(F.EtatAutorisation([preuve()], 11, "piscine_baignade", JOUR)["etat"], "oui")
        self.assertEqual(F.EtatAutorisation([preuve(valeur=0)], 11, "piscine_baignade", JOUR)["etat"], "non")
        self.assertEqual(F.EtatAutorisation([preuve(valeur=None)], 11, "piscine_baignade", JOUR)["etat"], "non_renseigne")

    def test_reponse_refus_posterieure_prime_sans_ecraser_l_histoire(self):
        ancienne = preuve()
        nouvelle = preuve(valeur=0, repondu_le="2026-10-20T17:20:00+02:00")
        source = [ancienne, nouvelle]
        self.assertEqual(F.EtatAutorisation(source, 11, "piscine_baignade", JOUR)["etat"], "non")
        self.assertEqual(source[0]["valeur"], 1)
        self.assertEqual(len(source), 2)

    def test_date_limite_incluse_puis_expiration(self):
        p = preuve(date_fin=JOUR)
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", JOUR)["etat"], "oui")
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", "2026-10-29")["etat"], "expire")

    def test_preuve_future_non_active(self):
        p = preuve(date_debut="2026-11-01", date_fin="2027-01-01")
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", JOUR)["etat"],
                         "non_renseigne")
        p = preuve(repondu_le="2026-11-01T10:00:00+01:00")
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", JOUR)["etat"],
                         "non_renseigne")

    def test_une_autorisation_ne_vaut_pas_pour_un_autre_enfant(self):
        self.assertEqual(F.EtatAutorisation([preuve(IDindividu=12)], 11,
                        "piscine_baignade", JOUR)["etat"], "non_renseigne")
        self.assertEqual(F.EtatAutorisation([preuve(IDindividu=True)], 11,
                        "piscine_baignade", JOUR)["etat"], "non_renseigne")

    def test_autorisations_independantes_des_supports_photo(self):
        photos = preuve(type="photos_prise")
        self.assertEqual(F.EtatAutorisation([photos], 11, "photos_prise", JOUR)["etat"], "oui")
        self.assertEqual(F.EtatAutorisation([photos], 11,
                         "photos_reseaux_sociaux", JOUR)["etat"], "non_renseigne")

    def test_perimetre_strict(self):
        p = preuve(perimetre="sejour_ete")
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", JOUR)["etat"],
                         "non_renseigne")
        self.assertEqual(F.EtatAutorisation([p], 11, "piscine_baignade", JOUR,
                         "sejour_ete")["etat"], "oui")

    def test_preuve_incomplete_ne_donne_pas_oui(self):
        for delta in ({"signataire": None}, {"texte_version": ""}, {"preuve": ""},
                      {"autorite_verifiee": False}):
            with self.subTest(delta=delta):
                self.assertEqual(F.EtatAutorisation([preuve(**delta)], 11,
                                 "piscine_baignade", JOUR)["etat"], "a_verifier")

    def test_preuves_concurrentes_contradictoires_bloquent(self):
        self.assertEqual(F.EtatAutorisation([preuve(), preuve(valeur=0)], 11,
                         "piscine_baignade", JOUR)["etat"], "a_verifier")

    def test_bloque_dates_et_horodatage_invalides(self):
        for p in (preuve(date_fin="2026-01-01"),
                  preuve(repondu_le="2026-09-01T10:00:00"),
                  preuve(repondu_le="bonjour")):
            with self.subTest(p=p), self.assertRaises(F.FicheAccueilInvalide):
                F.EtatAutorisation([p], 11, "piscine_baignade", JOUR)

    def test_perimetre_et_historique_malformes(self):
        with self.assertRaises(F.FicheAccueilInvalide):
            F.EtatAutorisation(None, 11, "piscine_baignade", JOUR)
        with self.assertRaises(F.FicheAccueilInvalide):
            F.EtatAutorisation([], 11, "piscine_baignade", JOUR, perimetre="")

    def test_non_declare_ailleurs_sans_approbation(self):
        f = F.ConstruireFiche(11, JOUR, DROITS, autorisations=[preuve()])
        self.assertEqual(f["autorisations"]["piscine_baignade"]["etat"], "oui")
        self.assertEqual(f["autorisations"]["piscine_baignade"]["date_fin"], "2027-08-31")
        self.assertEqual(f["autorisations"]["maquillage"]["etat"], "non_renseigne")
        self.assertFalse(any(f["portail"].values()))


class QuestionnaireEtBaseFictive(unittest.TestCase):
    def test_quatre_repas_et_absence_de_defaut_global(self):
        for repas in F.TYPES_REPAS:
            self.assertEqual(F.ConstruireFiche(11, JOUR, DROITS, type_repas=repas)["repas"],
                             {"etat": repas})
        self.assertEqual(F.ConstruireFiche(11, JOUR, DROITS)["repas"],
                         {"etat": "non_renseigne"})
        with self.assertRaises(F.FicheAccueilInvalide):
            F.ConstruireFiche(11, JOUR, DROITS, type_repas="allergie")

    def test_source_aeeh_existante_sqlite_lecture_seule(self):
        """Lit les deux tables historiques d'une base strictement fictive."""
        c = sqlite3.connect(":memory:")
        try:
            c.executescript("""CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, aeeh INTEGER);
                CREATE TABLE aeeh_periodes (IDperiode INTEGER, IDindividu INTEGER,
                   date_debut DATE, date_fin DATE);
                INSERT INTO individus VALUES (11, 1);
                INSERT INTO aeeh_periodes VALUES (1, 11, '2026-09-01', '2026-12-31');""")
            c.set_authorizer(lambda action, a1, a2, db, src: sqlite3.SQLITE_OK
                             if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                                           sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY)
            aeeh = c.execute("SELECT aeeh FROM individus WHERE IDindividu=?", (11,)).fetchone()[0]
            periodes = [dict(date_debut=d, date_fin=f) for d, f in
                        c.execute("SELECT date_debut, date_fin FROM aeeh_periodes WHERE IDindividu=?", (11,))]
            res = F.ConstruireFiche(11, JOUR, {"aeeh": True}, aeeh=aeeh,
                                    periodes_aeeh=periodes)
            self.assertEqual(res["aeeh"], {"etat": "oui", "periode_active": True,
                                            "periodes": periodes})
            self.assertEqual(res["pai"], {"etat": "restreint"})
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
