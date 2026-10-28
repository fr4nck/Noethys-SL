# -*- coding: utf-8 -*-
"""#436 : périodes AEEH vérifiées et confirmations parentales, SQLite fictif.

Les tests utilisent des connexions SQLite en mémoire, sans PMSL/Connecthys.
Le schéma des trois tables est extrait de DATA_Tables, source canonique.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_AEEH_Periodes as AEEH  # noqa: E402
from Utils import UTILS_Suivi_fiches as suivi  # noqa: E402


class BaseFictive:
    isNetwork = False
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        for nom in ("individus", "aeeh_periodes", "historique"):
            colonnes = []
            for champ, type_champ, _description in Tables.DB_DATA[nom]:
                colonnes.append("%s %s" % (champ, type_champ.replace("LONGBLOB", "BLOB")))
            self.cursor.execute("CREATE TABLE %s (%s)" % (nom, ", ".join(colonnes)))
        self.cursor.executemany(
            "INSERT INTO individus (IDindividu, IDcivilite, aeeh, nom) VALUES (?,?,?,?)",
            [(1, 4, None, "TEST-A"), (2, 5, 1, "TEST-B")])
        self.connexion.commit()

    def Commit(self):
        self.connexion.commit()

    def Close(self):
        self.connexion.close()

    def ExecuterReq(self, req):
        self.cursor.execute(req)
        return 1

    def ResultatReq(self):
        return self.cursor.fetchall()

    def lire(self, table):
        return self.connexion.execute("SELECT * FROM " + table).fetchall()


class EnregistrementAEEH(unittest.TestCase):
    def setUp(self):
        self.db = BaseFictive()

    def tearDown(self):
        self.db.Close()

    def ajouter(self, debut="2026-01-01", fin="2026-12-31"):
        return suivi.EnregistrerPeriodeVerifiee(
            1, 9, debut, fin, justificatif_verifie=True,
            source="pieces", DB=self.db)

    def test_periode_creee_et_historisee_sans_modifier_tri_etat(self):
        IDperiode = self.ajouter()
        self.assertEqual(IDperiode, 1)
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 1)
        self.assertEqual(self.db.lire("historique")[0][6], 40)
        self.assertEqual(self.db.lire("historique")[0][8], IDperiode)
        self.assertIsNone(
            self.db.connexion.execute("SELECT aeeh FROM individus WHERE IDindividu=1").fetchone()[0])

    def test_periodes_successives(self):
        self.ajouter()
        self.ajouter("2027-01-01", "2027-12-31")
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 2)

    def test_doublon_et_chevauchement_refuses(self):
        self.ajouter()
        for debut, fin in (("2026-01-01", "2026-12-31"),
                           ("2026-12-31", "2027-01-01"),
                           ("2026-02-01", "2026-05-01")):
            with self.subTest(debut=debut), self.assertRaises(AEEH.PeriodeAEEHInvalide):
                self.ajouter(debut, fin)
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 1)
        self.assertEqual(len(self.db.lire("historique")), 1)

    def test_autre_enfant_isole(self):
        self.ajouter()
        suivi.EnregistrerPeriodeVerifiee(
            2, 9, "2026-01-01", "2026-12-31",
            justificatif_verifie=True, source="papier", DB=self.db)
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 2)

    def test_justificatif_obligatoire_et_fin_non_inventee(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            suivi.EnregistrerPeriodeVerifiee(
                1, 9, "2026-01-01", "2026-12-31",
                justificatif_verifie=False, source="pieces", DB=self.db)
        with self.assertRaises(suivi.ControleFicheInvalide):
            suivi.EnregistrerPeriodeVerifiee(
                1, 9, "2026-01-01", None,
                justificatif_verifie=True, source="pieces", DB=self.db)
        self.assertEqual(self.db.lire("aeeh_periodes"), [])

    def test_absence_fin_uniquement_si_explicitement_confirmee(self):
        suivi.EnregistrerPeriodeVerifiee(
            1, 9, "2026-01-01", None, justificatif_verifie=True,
            source="papier", fin_non_precisee_confirmee=True, DB=self.db)
        self.assertIsNone(self.db.lire("aeeh_periodes")[0][3])

    def test_fin_ouverte_et_date_fin_contradictoires(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            suivi.EnregistrerPeriodeVerifiee(
                1, 9, "2026-01-01", "2026-12-31",
                justificatif_verifie=True, source="papier",
                fin_non_precisee_confirmee=True, DB=self.db)

    def test_dates_invalides_refusees(self):
        for debut, fin in (
                ("2026-02-30", "2026-12-31"),
                ("2026-12-31", "2026-01-01"),
                ("01/01/2026", "2026-12-31")):
            with self.subTest(debut=debut), self.assertRaises(suivi.ControleFicheInvalide):
                self.ajouter(debut, fin)

    def test_personne_absente_refusee(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            suivi.EnregistrerPeriodeVerifiee(
                99, 9, "2026-01-01", "2026-12-31",
                justificatif_verifie=True, source="pieces", DB=self.db)

    def test_identifiants_invalides_refuses(self):
        for id_utilisateur in (None, True, 0, "9"):
            with self.subTest(id=id_utilisateur), self.assertRaises(suivi.ControleFicheInvalide):
                suivi.EnregistrerPeriodeVerifiee(
                    1, id_utilisateur, "2026-01-01", "2026-12-31",
                    justificatif_verifie=True, source="pieces", DB=self.db)

    def test_erreur_historique_annule_insertion_periode(self):
        self.db.connexion.execute("DROP TABLE historique")
        self.db.Commit()
        with self.assertRaises(sqlite3.OperationalError):
            self.ajouter()
        self.assertEqual(self.db.lire("aeeh_periodes"), [])


class ConfirmationParentale(unittest.TestCase):
    def setUp(self):
        self.db = BaseFictive()

    def tearDown(self):
        self.db.Close()

    def confirmer(self, rubriques=("vaccinations", "allergies"), source="papier",
                  signee=True, relue=True, date_parent="2026-10-20"):
        return suivi.EnregistrerConfirmationParentale(
            1, 9, list(rubriques), source=source, fiche_signee=signee,
            document_relu=relue, date_parent=date_parent, DB=self.db)

    def test_confirmation_parentale_distincte_de_justificatif_medical(self):
        self.assertTrue(self.confirmer())
        action = self.db.lire("historique")[0][7]
        self.assertIn("vaccinations", action)
        self.assertIn("allergies", action)
        self.assertIn("justificatifs non validés", action)
        self.assertIn("2026-10-20", action)
        self.assertEqual(self.db.lire("historique")[0][6], 41)

    def test_derniere_reception_conserve_auteur_et_dates(self):
        self.confirmer()
        info = suivi.GetDerniereConfirmationParentale(1, DB=self.db)
        self.assertEqual(info["IDutilisateur"], 9)
        self.assertIn("2026-10-20", info["description"])
        self.assertIsNotNone(info["date_reception"])

    def test_aucune_reception(self):
        self.assertIsNone(suivi.GetDerniereConfirmationParentale(1, DB=self.db))

    def test_ecriture_refusee_si_signature_ou_relecture_absente(self):
        for signee, relue in ((False, True), (True, False), (False, False)):
            with self.subTest(signee=signee, relue=relue), self.assertRaises(suivi.ControleFicheInvalide):
                self.confirmer(signee=signee, relue=relue)
        self.assertEqual(self.db.lire("historique"), [])

    def test_rubrique_absente_inconnue_ou_dupliquee(self):
        for rubriques in ((), ("diagnostic",), ("pai", "pai"), ("pai", None)):
            with self.subTest(rubriques=rubriques), self.assertRaises(suivi.ControleFicheInvalide):
                self.confirmer(rubriques=rubriques)

    def test_signature_future_refusee(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            self.confirmer(date_parent="2099-01-01")

    def test_source_inconnue_refusee(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            self.confirmer(source="connecthys-admin")

    def test_deux_enfants_et_pieces_distincts(self):
        self.confirmer()
        suivi.EnregistrerConfirmationParentale(
            2, 8, ["pai"], source="pieces", fiche_signee=True,
            document_relu=True, IDpiece=22, DB=self.db)
        self.assertIsNone(suivi.GetDerniereConfirmationParentale(1, DB=self.db)["IDpiece"])
        self.assertEqual(suivi.GetDerniereConfirmationParentale(2, DB=self.db)["IDpiece"], 22)

    def test_derniere_confirmation_selon_identifiant_evenement(self):
        self.confirmer()
        self.confirmer(rubriques=("pai",), date_parent=None)
        self.assertIn("pai", suivi.GetDerniereConfirmationParentale(1, DB=self.db)["description"])

    def test_echec_ecriture_historique_ne_marque_pas_le_document(self):
        self.db.connexion.execute("DROP TABLE historique")
        self.db.Commit()
        with self.assertRaises(sqlite3.OperationalError):
            self.confirmer()

    def test_aucune_ecriture_medicale_ou_migration(self):
        source = (ROOT / "noethys/Utils/UTILS_Suivi_fiches.py").read_text(encoding="utf-8")
        self.assertNotIn("UPDATE individus", source)
        self.assertNotIn("INSERT INTO vaccins", source)
        self.assertNotIn("INSERT INTO problemes_sante", source)
        self.assertNotIn("ALTER TABLE", source)


if __name__ == "__main__":
    unittest.main()
