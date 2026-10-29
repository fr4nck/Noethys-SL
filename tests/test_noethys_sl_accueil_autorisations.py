# -*- coding: utf-8 -*-
"""#436 : autorisations signees fictives, SQLite, aucun profil reel."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from Utils import UTILS_Accueil_autorisations as A
from Utils import UTILS_Fiche_accueil_enfant as F


class FausseBase:
    isNetwork = False
    def __init__(self, path=":memory:"):
        self.connexion = sqlite3.connect(str(path), timeout=0.04)
        self.cursor = self.connexion.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS individus (IDindividu INTEGER PRIMARY KEY, nom TEXT)")
        self.cursor.executemany(
            "INSERT OR IGNORE INTO individus VALUES (?,?)",
            [(10, "FICTIF-A"), (11, "FICTIF-B")])
        self.connexion.commit()
    def Close(self):
        self.connexion.close()


def decision(type_="photos_site_imprimes", valeur=1, **kwargs):
    donnees = {
        "type": type_, "valeur": valeur, "date_debut": "2026-09-01",
        "date_fin": "2027-08-31", "date_signature": "2026-10-10",
        "IDsignataire": 99, "autorite_verifiee": True,
        "perimetre": "alsh-2026", "texte_version": "fiche-enfant-2026-06",
        "source": "pieces", "reference_preuve": "piece-fictive-001",
    }
    donnees.update(kwargs)
    return donnees


def attendu(**par_type):
    return {(code, "alsh-2026"): valeur for code, valeur in par_type.items()}


class AutorisationsSQLite(unittest.TestCase):
    def setUp(self):
        self.base = FausseBase()
        self.addCleanup(self.base.Close)
    def installer(self):
        return A.InitialiserRegistre(DB=self.base, administrateur=True,
                                    sauvegarde_confirmee=True)
    def enregistrer(self, lignes, revisions, operateur=3, enfant=10):
        return A.EnregistrerLot(enfant, operateur, lignes, revisions,
                               DB=self.base, autorise=True)
    def lignes(self):
        return self.base.connexion.execute(
            "SELECT IDindividu,type_autorisation,valeur,empreinte "
            "FROM accueil_autorisations ORDER BY IDautorisation").fetchall()

    def test_aucune_table_creee_a_la_lecture(self):
        with self.assertRaises(A.RegistreAbsent):
            A.LireHistorique(10, DB=self.base, autorise=True)
        self.assertFalse(self.base.connexion.execute(
            "SELECT 1 FROM sqlite_master WHERE name='accueil_autorisations'").fetchone())

    def test_admin_et_sauvegarde_explicites(self):
        for admin, backup in ((False, True), (True, False), (1, True),
                              (True, 1), (None, None)):
            with self.subTest(admin=admin, backup=backup):
                with self.assertRaises(A.AutorisationRefusee):
                    A.InitialiserRegistre(DB=self.base,
                                         administrateur=admin,
                                         sauvegarde_confirmee=backup)
        self.assertTrue(self.installer())

    def test_migration_unique_idempotente(self):
        self.assertTrue(self.installer())
        self.assertFalse(self.installer())
        self.assertEqual(A.LireHistorique(10, DB=self.base, autorise=True), [])
        self.assertEqual(self.base.connexion.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='accueil_autorisations'"
        ).fetchone()[0], 1)

    def test_table_preexistante_incompatible_refuse(self):
        self.base.connexion.execute(
            "CREATE TABLE accueil_autorisations (IDautorisation INTEGER)")
        self.base.connexion.commit()
        with self.assertRaises(A.RegistreAbsent):
            self.installer()
        cols = self.base.connexion.execute(
            "PRAGMA table_info(accueil_autorisations)").fetchall()
        self.assertEqual(len(cols), 1)

    def test_permissions_refus_par_defaut_et_admin_explicit(self):
        self.assertFalse(A.AccesUtilisateur(None))
        self.assertFalse(A.AccesUtilisateur({"profil": "administrateur"}))
        self.assertFalse(A.AccesUtilisateur({
            "IDutilisateur": 3, "actif": True, "profil": "perso:3"}))
        self.assertTrue(A.AccesUtilisateur({
            "IDutilisateur": 3, "actif": True, "profil": "administrateur"}))
        self.assertTrue(A.AccesUtilisateur({
            "IDutilisateur": 4, "actif": 1, "profil": "perso:4",
            "droits": {("fiche_accueil_autorisations", "consulter"): "autorisation"}}))
        self.assertFalse(A.AccesUtilisateur({
            "IDutilisateur": 4, "actif": 1, "profil": "perso:4",
            "droits": {("fiche_accueil_autorisations", "consulter"): "interdiction"}},
            "consulter"))

    def test_lecture_et_ecriture_interdites_sans_droit(self):
        self.installer()
        with self.assertRaises(A.AutorisationRefusee):
            A.LireHistorique(10, DB=self.base)
        with self.assertRaises(A.AutorisationRefusee):
            A.DerniersIdentifiants(10, DB=self.base)
        with self.assertRaises(A.AutorisationRefusee):
            A.EnregistrerLot(10, 3, [decision()], attendu(photos_site_imprimes=None),
                            DB=self.base)

    def test_quatre_autorisations_formulaire_papier(self):
        self.installer()
        codes = ["photos_site_imprimes", "maquillage",
                 "piscine_baignade", "activites_physiques"]
        lignes = [decision(code, int(code != "maquillage")) for code in codes]
        ids = self.enregistrer(lignes, attendu(**{c: None for c in codes}))
        self.assertEqual(len(ids), 4)
        self.assertEqual(len(self.lignes()), 4)
        historique = A.LireHistorique(10, DB=self.base, autorise=True)
        self.assertEqual({x["type"] for x in historique}, set(codes))
        fiche = F.ConstruireFiche(10, "2026-10-29",
                     {"autorisations": True}, autorisations=historique,
                     perimetre="alsh-2026")
        self.assertEqual(fiche["autorisations"]["maquillage"]["etat"], "non")
        self.assertEqual(fiche["autorisations"]["piscine_baignade"]["etat"], "oui")
        self.assertFalse(any(fiche["portail"].values()))

    def test_aucun_oui_ou_non_implicit(self):
        self.installer()
        for valeur in (None, True, False, "", 2, -1):
            with self.subTest(valeur=valeur):
                with self.assertRaises(A.PreuveInvalide):
                    self.enregistrer([decision(valeur=valeur)],
                                    attendu(photos_site_imprimes=None))
        self.assertEqual(self.lignes(), [])

    def test_signataire_version_et_piece_obligatoires(self):
        self.installer()
        for changement in (
            {"IDsignataire": 0}, {"autorite_verifiee": False},
            {"texte_version": ""}, {"reference_preuve": ""},
            {"date_signature": None}, {"source": "web"},
        ):
            with self.subTest(change=changement):
                with self.assertRaises(A.PreuveInvalide):
                    self.enregistrer([decision(**changement)],
                                    attendu(photos_site_imprimes=None))
        self.assertEqual(self.lignes(), [])

    def test_dates_et_perimetre_rejetes(self):
        self.installer()
        for changement in (
            {"date_debut": "2026-02-30"}, {"date_fin": "2025-01-01"},
            {"date_debut": "01/09/2026"}, {"date_signature": "2039-01-01"},
            {"perimetre": ""}, {"type": "inconnu"},
        ):
            with self.subTest(change=changement):
                with self.assertRaises(A.PreuveInvalide):
                    self.enregistrer([decision(**changement)],
                                    attendu(photos_site_imprimes=None))

    def test_meme_piece_meme_evenement_aucun_doublon(self):
        self.installer()
        first = self.enregistrer([decision()], attendu(photos_site_imprimes=None),
                                 operateur=3)
        second = self.enregistrer([decision()], attendu(photos_site_imprimes=None),
                                  operateur=8)
        self.assertEqual(first, second)
        self.assertEqual(len(self.lignes()), 1)

    def test_modification_refus_historisee_et_non_ecrasee(self):
        self.installer()
        initial = self.enregistrer([decision()], attendu(photos_site_imprimes=None))
        ref = initial[("photos_site_imprimes", "alsh-2026")]
        change = decision(valeur=0, reference_preuve="piece-fictive-002")
        self.enregistrer([change], attendu(photos_site_imprimes=ref))
        self.assertEqual([x[2] for x in self.lignes()], [1, 0])
        histo = A.LireHistorique(10, DB=self.base, autorise=True)
        self.assertEqual(F.EtatAutorisation(histo, 10, "photos_site_imprimes",
                                          "2026-10-29", "alsh-2026")["etat"], "non")

    def test_revision_changee_sur_autre_poste_stop(self):
        self.installer()
        ref = self.enregistrer([decision()], attendu(photos_site_imprimes=None))
        with self.assertRaises(A.ConflitConcurrent):
            self.enregistrer([decision(valeur=0,
                          reference_preuve="piece-fictive-002")],
                            attendu(photos_site_imprimes=None))
        self.assertEqual(len(self.lignes()), 1)

    def test_ancienne_preuve_interdite_apres_revocation(self):
        self.installer()
        oui = self.enregistrer([decision()], attendu(photos_site_imprimes=None))
        ref = oui[("photos_site_imprimes", "alsh-2026")]
        self.enregistrer([decision(valeur=0,reference_preuve="piece-fictive-002")],
                        attendu(photos_site_imprimes=ref))
        with self.assertRaises(A.PreuveInvalide):
            self.enregistrer([decision()],
               attendu(photos_site_imprimes=2))
        self.assertEqual(len(self.lignes()), 2)

    def test_rollback_tout_lot_si_second_insert_refuse(self):
        self.installer()
        self.base.connexion.execute("""CREATE TRIGGER interdit_maquillage
            BEFORE INSERT ON accueil_autorisations
            WHEN NEW.type_autorisation='maquillage'
            BEGIN SELECT RAISE(ABORT,'test'); END""")
        self.base.connexion.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.enregistrer([decision(),decision("maquillage")],
               attendu(photos_site_imprimes=None,maquillage=None))
        self.assertEqual(self.lignes(), [])

    def test_autre_enfant_isole_et_identite_preservee(self):
        self.installer()
        self.enregistrer([decision()], attendu(photos_site_imprimes=None))
        self.enregistrer([decision()], attendu(photos_site_imprimes=None),
                         enfant=11)
        self.assertEqual(len(A.LireHistorique(10, DB=self.base, autorise=True)), 1)
        self.assertEqual(len(A.LireHistorique(11, DB=self.base, autorise=True)), 1)
        self.assertEqual(self.base.connexion.execute(
            "SELECT nom FROM individus WHERE IDindividu=10").fetchone()[0], "FICTIF-A")

    def test_revisions_absentes_stop_sans_ecriture(self):
        self.installer()
        with self.assertRaises(A.PreuveInvalide):
            self.enregistrer([decision()], {})
        self.assertEqual(self.lignes(), [])

    def test_aucun_champ_donnees_medicales_dans_registre(self):
        self.installer()
        cols = set(x[1] for x in self.base.connexion.execute(
            "PRAGMA table_info(accueil_autorisations)").fetchall())
        for interdit in ("pai", "diagnostic", "allergies", "aeeh", "traitement"):
            self.assertNotIn(interdit, cols)


class ConcurrenceSQLite(unittest.TestCase):
    def test_deux_postes_memes_revisions_aucun_ecrasement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accueil-fictif.db"
            a = FausseBase(path)
            b = FausseBase(path)
            try:
                A.InitialiserRegistre(a, administrateur=True, sauvegarde_confirmee=True)
                A.EnregistrerLot(10, 3, [decision()],
                    attendu(photos_site_imprimes=None), DB=a, autorise=True)
                with self.assertRaises(A.ConflitConcurrent):
                    A.EnregistrerLot(10, 4,
                         [decision(valeur=0, reference_preuve="piece-fictive-002")],
                         attendu(photos_site_imprimes=None), DB=b, autorise=True)
                self.assertEqual(len(A.LireHistorique(10, DB=b, autorise=True)), 1)
            finally:
                a.Close()
                b.Close()


if __name__ == "__main__":
    unittest.main()
