# -*- coding: utf-8 -*-
"""SQLite réel au schéma canonique, aucune dépendance wx/GestionDB/réseau."""
import ast
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Data.DATA_Tables import DB_DATA
from Utils.UTILS_Audit_cotisations import ConstruireInventaire, REQUETE, TABLES

spec = importlib.util.spec_from_file_location("audit_cli", ROOT / "tools/auditer_cotisations_rc7.py")
CLI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CLI)
JOUR = dt.date(2026, 10, 21)


def creer_schema(db):
    for table in TABLES:
        champs = ", ".join('"%s" %s' % (nom, sqltype) for nom, sqltype, *_ in DB_DATA[table])
        db.execute('CREATE TABLE "%s" (%s)' % (table, champs))


def inserer(db, table, **valeurs):
    db.execute("INSERT INTO %s (%s) VALUES (%s)" % (
        table, ",".join(valeurs), ",".join("?" for _ in valeurs)), tuple(valeurs.values()))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        creer_schema(self.db)

    def tearDown(self):
        self.db.close()

    def c(self, cid=1, **kw):
        valeurs = dict(IDcotisation=cid, IDindividu=100, IDtype_cotisation=1, IDunite_cotisation=11,
                       date_saisie="2026-10-01", date_debut="2027-01-06", date_fin="2028-01-06",
                       IDprestation=801, observations="[adhesion-auto]")
        valeurs.update(kw)
        inserer(self.db, "cotisations", **valeurs)

    def p(self, **kw):
        valeurs = dict(IDprestation=801, IDindividu=100, IDcompte_payeur=11, categorie="cotisation",
                       date="2026-10-01", montant=7.5)
        valeurs.update(kw)
        inserer(self.db, "prestations", **valeurs)

    def v(self, vid=1, **kw):
        valeurs = dict(IDventilation=vid, IDprestation=801, IDcompte_payeur=11, IDreglement=901, montant=2.5)
        valeurs.update(kw)
        inserer(self.db, "ventilation", **valeurs)

    def rapport(self):
        return ConstruireInventaire(lambda q: self.db.execute(q).fetchall(), JOUR)

    def ligne(self):
        return self.rapport()["lignes"][0]

    def test_anticipation_trois_indices_separes(self):
        self.c(); self.p()
        r = self.ligne()
        self.assertEqual(set(r["motifs"]), {"validite_anticipee", "validite_future", "prestation_anticipee"})
        self.assertTrue(r["anticipation_detectee"])
        self.assertFalse(r["participation_reelle_verifiee"])

    def test_historique_toujours_visible_apres_date_de_validite(self):
        self.c(date_debut="2026-10-05", date_fin="2027-10-05"); self.p()
        self.assertIn("validite_anticipee", self.ligne()["motifs"])
        self.assertNotIn("validite_future", self.ligne()["motifs"])

    def test_facture_et_ventilation_quatre_combinaisons(self):
        for facture, ventile, attendu in [(False, False, "sans_facture_ni_ventilation_identifiee"),
                                        (True, False, "facturee"), (False, True, "ventilee"),
                                        (True, True, "facturee_et_ventilee")]:
            with self.subTest(facture=facture, ventile=ventile):
                for table in TABLES:
                    self.db.execute("DELETE FROM " + table)
                self.c(); self.p(IDfacture=99 if facture else None)
                if facture:
                    inserer(self.db, "factures", IDfacture=99, numero=260099, IDcompte_payeur=11)
                if ventile:
                    self.v()
                    inserer(self.db, "reglements", IDreglement=901, IDcompte_payeur=11, montant=10)
                self.assertEqual(self.ligne()["etat_comptable"], attendu)

    def test_facture_reference_cassee_reste_protegee(self):
        self.c(); self.p(IDfacture=99)
        r = self.ligne()
        self.assertTrue(r["facture_referencee"])
        self.assertFalse(r["facture_existe"])
        self.assertIn("facture_introuvable", r["motifs"])
        self.assertEqual(r["statut"], "reglement_ou_facture_a_regolariser")

    def test_plusieurs_ventilations_et_montants_signes_sans_doubler_prestation(self):
        self.c(); self.p(); self.v(montant=5); self.v(2, montant=-2.5); self.v(3, montant=0)
        inserer(self.db, "reglements", IDreglement=901, montant=10, encaissement_attente=1)
        r = self.ligne()
        self.assertEqual(r["nb_ventilations"], 3)
        self.assertEqual(r["montant_ventile"], "2.5")
        self.assertEqual(self.rapport()["total_montants_prestations_connus"], "7.5")
        self.assertEqual(r["ventilations"][0]["encaissement_attente"], 1)

    def test_ventilations_a_somme_nulle_restent_signalees(self):
        self.c(); self.p(); self.v(montant=5); self.v(2, montant=-5)
        self.assertEqual(self.ligne()["etat_comptable"], "ventilee")
        self.assertEqual(self.ligne()["montant_ventile"], "0.0")

    def test_reglement_introuvable_reste_ventilation(self):
        self.c(); self.p(); self.v()
        self.assertIn("reglement_introuvable", self.ligne()["motifs"])
        self.assertEqual(self.ligne()["nb_ventilations"], 1)

    def test_prestation_absente_hors_filtre_de_dates_est_retenue(self):
        self.c(date_debut="2026-10-01", date_fin="2027-10-01")
        self.assertIn("prestation_introuvable", self.ligne()["motifs"])
        self.assertFalse(self.ligne()["anticipation_detectee"])

    def test_prestation_sans_date_presente_et_non_introuvable(self):
        self.c(); self.p(date=None)
        r = self.ligne()
        self.assertTrue(r["prestation_existe"])
        self.assertIn("date_prestation_absente", r["motifs"])
        self.assertNotIn("prestation_introuvable", r["motifs"])

    def test_prestation_absente_avec_ventilation_orpheline(self):
        self.c(); self.v()
        self.assertEqual(self.ligne()["etat_comptable"], "ventilee")
        self.assertIn("prestation_introuvable", self.ligne()["motifs"])

    def test_aucun_id_prestation(self):
        self.c(IDprestation=None)
        self.assertIn("prestation_introuvable", self.ligne()["motifs"])

    def test_dates_absentes_invalides_et_validite_inversee_ne_masquent_pas_la_ligne(self):
        for champ, valeur, motif in [("date_debut", None, "date_debut_absente"),
                                    ("date_debut", "0000-00-00", "date_debut_invalide"),
                                    ("date_debut", "2026-99-99", "date_debut_invalide"),
                                    ("date_saisie", None, "date_saisie_absente"),
                                    ("date_fin", "2026-01-01", "validite_inversee")]:
            with self.subTest(champ=champ, valeur=valeur):
                self.db.execute("DELETE FROM cotisations")
                self.c(**{champ: valeur})
                self.assertIn(motif, self.ligne()["motifs"])

    def test_categorie_et_identites_incoherentes(self):
        self.c(IDfamille=1); self.p(categorie="consommation", IDindividu=200, IDfamille=2, IDfacture=99)
        inserer(self.db, "factures", IDfacture=99, IDcompte_payeur=12)
        self.v(IDcompte_payeur=12)
        self.assertTrue({"categorie_prestation_inattendue", "individu_prestation_incoherent",
                         "famille_prestation_incoherente", "payeur_facture_incoherent",
                         "payeur_ventilation_ou_reglement_incoherent"}.issubset(self.ligne()["motifs"]))

    def test_prestation_partagee_comptee_une_fois(self):
        self.c(); self.c(2); self.p(); self.v()
        r = self.rapport()
        self.assertEqual(r["cotisations_signalees"], 2)
        self.assertEqual(r["prestations_distinctes_signalees"], 1)
        self.assertEqual(r["total_montants_prestations_connus"], "7.5")
        self.assertIn("prestation_partagee", r["lignes"][0]["motifs"])

    def test_manuelles_exclues_et_population_connue(self):
        self.c(observations="manuelle"); self.c(2, observations=None)
        self.assertEqual(self.rapport()["cotisations_automatiques_examinees"], 0)

    def test_automatique_saine_examinee_mais_non_signalee(self):
        self.c(date_debut="2026-10-01", date_fin="2027-10-01"); self.p()
        self.assertEqual(self.rapport()["cotisations_automatiques_examinees"], 1)
        self.assertEqual(self.rapport()["lignes"], [])

    def test_montant_inconnu_pas_converti_en_zero(self):
        self.c(); self.p(montant=None); self.v(montant=None)
        r = self.rapport()
        self.assertEqual(r["prestations_montant_inconnu"], 1)
        self.assertIsNone(r["lignes"][0]["montant_ventile"])

    def test_montant_decimal_exact(self):
        self.c(); self.p(montant=.3); self.v(montant=.1); self.v(2, montant=.2)
        self.assertEqual(self.ligne()["montant_ventile"], "0.3")

    def test_date_valeur_anticipee_separee(self):
        self.c(date_debut="2026-10-01", date_fin="2027-10-01"); self.p(date_valeur="2026-09-30")
        self.assertIn("date_valeur_anticipee", self.ligne()["motifs"])

    def test_audit_exactement_un_select_et_aucune_modification(self):
        self.c(); self.p(); self.v()
        avant = "\n".join(self.db.iterdump())
        requetes = []
        self.db.set_trace_callback(requetes.append)
        self.rapport()
        self.db.set_trace_callback(None)
        self.assertEqual(requetes, [REQUETE])
        self.assertEqual("\n".join(self.db.iterdump()), avant)

    def test_erreur_sql_pas_un_inventaire_vide(self):
        self.db.execute("DROP TABLE ventilation")
        with self.assertRaises(sqlite3.OperationalError):
            self.rapport()

    def test_date_reference_invalide_refusee(self):
        with self.assertRaises(ValueError):
            ConstruireInventaire(lambda q: [], "2026-10-21' OR 1=1")

    def test_export_echappe_html_et_ne_propose_aucune_action(self):
        self.c(); self.p(IDfacture=99)
        inserer(self.db, "factures", IDfacture=99, numero="<script>alert(1)</script>")
        r = self.rapport(); r.update(source={"moteur": "fictif"}, genere_le="2026-10-21")
        page = CLI.texte_html(r)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertFalse(r["regularisation_automatique"])
        self.assertEqual(r["lignes"][0]["action_automatique"], "aucune")

    def test_api_historique_erreur_sql_et_fermeture(self):
        # Exerce le vrai corps de la fonction publique sans importer l'UI.
        source = (ROOT / "noethys/Utils/UTILS_Adhesions_echeances.py").read_text(encoding="utf-8")
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "AuditerCotisationsAnticipees")
        for echec, retour in [(1, 1), (0, 0), (0, 1)]:
            with self.subTest(echec=echec, retour=retour):
                db = types.SimpleNamespace(echec=echec, ferme=False)
                db.ExecuterReq = lambda q: retour
                db.ResultatReq = lambda: []
                db.Close = lambda: setattr(db, "ferme", True)
                espace = {"A": types.SimpleNamespace(GestionDB=types.SimpleNamespace(DB=lambda: db)), "datetime": dt}
                exec(compile(ast.Module(body=[node], type_ignores=[]), "api", "exec"), espace)
                if echec or retour == 0:
                    with self.assertRaises(RuntimeError):
                        espace["AuditerCotisationsAnticipees"](JOUR)
                else:
                    self.assertEqual(espace["AuditerCotisationsAnticipees"](JOUR), [])
                self.assertTrue(db.ferme)


class CopieEtCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "copie_DATA.dat"
        db = sqlite3.connect(self.path); creer_schema(db)
        inserer(db, "cotisations", IDcotisation=1, date_saisie="2026-10-01", date_debut="2027-01-06",
                date_fin="2028-01-06", observations="[adhesion-auto]")
        db.commit(); db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_mode_ro_refuse_update_insert_delete_et_schema(self):
        avant = self.path.read_bytes()
        with CLI.ouvrir_sqlite(self.path) as (lire, source):
            for sql in ("UPDATE cotisations SET IDindividu=3", "DELETE FROM cotisations",
                        "INSERT INTO cotisations(IDcotisation) VALUES(2)", "CREATE TABLE x(a)",
                        "ATTACH DATABASE ':memory:' AS autre", "PRAGMA query_only=OFF"):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    lire(sql)
            ConstruireInventaire(lire, JOUR)
        self.assertEqual(avant, self.path.read_bytes())
        self.assertEqual(source["sha256_avant"], source["sha256_apres"])

    def test_fichier_absent_non_cree(self):
        path = Path(self.tmp.name) / "absent.dat"
        with self.assertRaises(FileNotFoundError), CLI.ouvrir_sqlite(path):
            pass
        self.assertFalse(path.exists())

    def test_wal_refuse(self):
        Path(str(self.path) + "-wal").touch()
        with self.assertRaises(ValueError), CLI.ouvrir_sqlite(self.path):
            pass

    def test_cli_exports_et_empreintes(self):
        dossier = Path(self.tmp.name) / "rapport"
        resultat = CLI.main(["--sqlite", str(self.path), "--copie-confirmee", "--date-reference", str(JOUR), "--sortie", str(dossier)])
        self.assertEqual(resultat, 0)
        rapport = json.loads((dossier / "inventaire.json").read_text(encoding="utf-8"))
        self.assertEqual(rapport["cotisations_signalees"], 1)
        for ligne in (dossier / "SHA256SUMS.txt").read_text().splitlines():
            h, fichier = ligne.split("  ")
            self.assertEqual(h, hashlib.sha256((dossier / fichier).read_bytes()).hexdigest())
        self.assertIn("decision_comptable", (dossier / "validation_comptable.csv").read_text(encoding="utf-8-sig"))

    def test_cli_erreur_sql_aucun_rapport(self):
        db = sqlite3.connect(self.path); db.execute("DROP TABLE factures"); db.commit(); db.close()
        dossier = Path(self.tmp.name) / "rapport"
        self.assertEqual(CLI.main(["--sqlite", str(self.path), "--copie-confirmee", "--date-reference", str(JOUR), "--sortie", str(dossier)]), 2)
        self.assertFalse(dossier.exists())

    def test_copie_confirmation_explicite_requise(self):
        with self.assertRaises(SystemExit):
            CLI.main(["--sqlite", str(self.path), "--date-reference", str(JOUR), "--sortie", str(Path(self.tmp.name) / "rapport")])

    def test_mysql_nom_production_refuse_avant_pilote(self):
        with self.assertRaises(ValueError), CLI.ouvrir_mysql("pmsl_DATA", 3306, "audit", "secret-fictif"):
            pass


if __name__ == "__main__":
    unittest.main()
