# -*- coding: utf-8 -*-
"""ALSH communal: tests sur donnees synthetiques, aucune DB ni reseau."""
import csv
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Frequentation_collectivites import (
    ErreurFrequentation, calculer, consolider_export_consommations,
    exporter_csv, exporter_pdf, exporter_xlsx, modele, _fr_jours,
)


def fixture():
    d = modele("Bais", 2026, "2026-10-29")
    d["controles"] = {"frequentation": True, "prevision": True,
                       "domiciliation": True, "acomptes": True}
    for c in d["conventions"]:
        c["tarif_confirme"] = True  # uniquement fixture, PAS le modele propose
    d["jours"] = [
        {"id": "ALSH-JAN-R", "convention": "ALSH-2025-2026", "mois": 1,
         "nature": "realise", "nombre": "10", "justificatif": "releve janvier fictif"},
        {"id": "ALSH-DEC-P", "convention": "ALSH-2025-2026", "mois": 12,
         "nature": "prevision", "nombre": "5", "justificatif": "reservations decembre fictives"},
        {"id": "ADOS-AOU-R", "convention": "ADOS-2024-2026-BAIS", "mois": 8,
         "nature": "realise", "nombre": "2", "justificatif": "releve ados aout fictif"},
        {"id": "ADOS-NOV-P", "convention": "ADOS-2024-2026-BAIS", "mois": 11,
         "nature": "prevision", "nombre": "1", "justificatif": "reservations ados novembre fictives"},
    ]
    d["acomptes"] = [
        {"id": "AC-1", "convention": "ALSH-2025-2026", "date": "2026-03-01",
         "exercice": 2026, "montant": "100.00", "justificatif": "virement commune fictif"},
    ]
    return d


class ConventionTests(unittest.TestCase):
    def test_modeles_reels_tarifs_non_presumes_valides(self):
        bais = modele("Bais")
        self.assertEqual([(c["accueil"], c["tarif_jour"]) for c in bais["conventions"]],
                         [("ALSH classique", "11.54"), ("ALSH Ados", "19.55")])
        self.assertFalse(any(c["tarif_confirme"] for c in bais["conventions"]))
        self.assertEqual(len(modele("Moutiers")["conventions"]), 1)
        self.assertEqual(len(modele("Moussé")["conventions"]), 1)
        self.assertEqual(len(modele("Rannée")["conventions"]), 1)
        self.assertEqual(len(modele("LA GUERCHE DE BGNE")["conventions"]), 1)
        self.assertEqual(modele("Bais", 2027, "2027-01-15")["conventions"], [])

    def test_rejet_ancien_format_financier(self):
        with self.assertRaises(ErreurFrequentation):
            calculer({"version": 1, "lignes": [], "annee": 2026})

    def test_annee_civile_ni_saison_ni_exercice_scolaire(self):
        r = calculer(fixture())
        self.assertEqual((r["annee"], r["arrete"]), (2026, "2026-10-29"))
        self.assertEqual(r["mensuel"]["1"]["realise"], 10)
        self.assertEqual(r["mensuel"]["12"]["prevision"], 5)

    def test_convention_ados_bais_non_transposable(self):
        d = fixture()
        d["commune"] = "Moutiers"
        with self.assertRaises(ErreurFrequentation):
            calculer(d)

    def test_aucune_donnee_pas_un_zero_probatif(self):
        r = calculer(modele())
        self.assertIsNone(r["totaux"]["participation_estimee"])
        self.assertIsNone(r["totaux"]["solde_indicatif"])
        self.assertIsNone(r["totaux"]["solde_verifie"])
        self.assertEqual(r["statut"], "PROVISOIRE - A VERIFIER")

    def test_journees_montants_et_solde(self):
        r = calculer(fixture())
        t = r["totaux"]
        self.assertEqual(t["journees_reelles"], 12)
        self.assertEqual(t["journees_prevues"], 6)
        self.assertEqual(t["participation_reelle"], 10 * 1154 + 2 * 1955)
        self.assertEqual(t["participation_prevue"], 5 * 1154 + 1955)
        self.assertEqual(t["participation_estimee"], 23175)
        self.assertEqual(t["acomptes_recus"], 10000)
        self.assertEqual(t["solde_indicatif"], 13175)
        self.assertEqual(t["solde_verifie"], 13175)
        self.assertEqual(r["statut"], "ETAT VERIFIE - PREVISIONNEL")

    def test_une_verification_manquante_non_certifiable(self):
        d = fixture()
        d["controles"]["domiciliation"] = False
        r = calculer(d)
        self.assertEqual(r["totaux"]["solde_indicatif"], 13175)
        self.assertIsNone(r["totaux"]["solde_verifie"])

    def test_tarif_non_confirme_bloque_certification(self):
        d = fixture()
        d["conventions"][1]["tarif_confirme"] = False
        r = calculer(d)
        self.assertIsNone(r["totaux"]["solde_verifie"])
        self.assertTrue(any("signature" in x.lower() for x in r["alertes"]))

    def test_pas_de_sommation_factures_ou_reglements_familles(self):
        d = fixture()
        d["factures_familles"] = [{"montant": 100000000}]
        d["tva"] = "20%"
        self.assertEqual(calculer(d)["totaux"]["solde_indicatif"], 13175)

    def test_doublon_par_convention_mois_nature_refuse(self):
        d = fixture()
        copy = deepcopy(d["jours"][0])
        copy["id"] = "AUTRE-ID"
        d["jours"].append(copy)
        with self.assertRaises(ErreurFrequentation):
            calculer(d)

    def test_doublon_id_refuse(self):
        d = fixture()
        d["jours"][1]["id"] = d["jours"][0]["id"]
        with self.assertRaises(ErreurFrequentation):
            calculer(d)

    def test_prevision_passee_et_realise_futur_refuses(self):
        d = fixture()
        d["jours"][0]["nature"] = "prevision"
        with self.assertRaises(ErreurFrequentation):
            calculer(d)
        d = fixture()
        d["jours"][1]["nature"] = "realise"
        with self.assertRaises(ErreurFrequentation):
            calculer(d)

    def test_mois_arrete_autorise_realise_et_prevision_sous_controle(self):
        d = fixture()
        d["jours"].extend([
            {"id": "OCT-R", "convention": "ALSH-2025-2026", "mois": 10,
             "nature": "realise", "nombre": "1", "justificatif": "present jusqu'au 29"},
            {"id": "OCT-P", "convention": "ALSH-2025-2026", "mois": 10,
             "nature": "prevision", "nombre": "2", "justificatif": "reservations 30-31"},
        ])
        r = calculer(d)
        self.assertEqual((r["mensuel"]["10"]["realise"], r["mensuel"]["10"]["prevision"]), (1, 2))

    def test_les_demi_journees_ne_sont_pas_devinees(self):
        d = fixture()
        d["jours"][0]["nombre"] = "10.5"
        with self.assertRaises(ErreurFrequentation):
            calculer(d)
        d["conventions"][0]["demi_journee_autorisee"] = True
        r = calculer(d)
        self.assertEqual(r["totaux"]["participation_reelle"], 11 * 1154 + 2 * 1955 - 577)

    def test_arrondi_demi_journee_autorise(self):
        d = fixture()
        d["conventions"][1]["demi_journee_autorisee"] = True
        d["jours"][2]["nombre"] = "2.5"
        r = calculer(d)
        self.assertEqual(r["conventions"]["ADOS-2024-2026-BAIS"]["participation_reelle"], 4888)

    def test_montants_non_negatifs_et_precis_au_centime(self):
        for montant in ["-1", "1.2222", "nan", "inf"]:
            d = fixture()
            d["acomptes"][0]["montant"] = montant
            with self.subTest(montant=montant), self.assertRaises(ErreurFrequentation):
                calculer(d)

    def test_acompte_hors_exercice_refuse(self):
        d = fixture()
        d["acomptes"][0]["exercice"] = 2025
        with self.assertRaises(ErreurFrequentation):
            calculer(d)

    def test_acompte_futur_exclu_pas_encaisse(self):
        d = fixture()
        d["acomptes"][0]["date"] = "2026-12-31"
        r = calculer(d)
        self.assertEqual(r["totaux"]["acomptes_recus"], 0)
        self.assertEqual(r["totaux"]["solde_indicatif"], 23175)
        self.assertTrue(any("futurs" in s.lower() for s in r["alertes"]))

    def test_aucun_zero_d_acompte_sans_exhaustivite(self):
        d = fixture()
        d["acomptes"] = []
        d["controles"]["acomptes"] = False
        r = calculer(d)
        self.assertIsNone(r["totaux"]["acomptes_recus"])
        self.assertIsNone(r["totaux"]["solde_verifie"])

    def test_cases_mensuelles_inconnues_ne_sont_pas_zero(self):
        d = fixture()
        d["controles"]["frequentation"] = False
        d["controles"]["prevision"] = False
        r = calculer(d)
        self.assertIsNone(r["mensuel"]["2"]["realise"])
        self.assertIsNone(r["mensuel"]["11"]["participation"])
        self.assertIsNone(r["mensuel"]["1"]["realise"])  # ados janvier non confirme

    def test_arrondis_par_mois_egaux_aux_totaux_annuels(self):
        d = fixture()
        d["conventions"][1]["demi_journee_autorisee"] = True
        d["jours"][2]["nombre"] = "0.5"
        d["jours"][3]["nombre"] = "0.5"
        r = calculer(d)
        mois = r["mensuel"]
        self.assertEqual(sum(mois[str(m)]["participation"] for m in range(1, 13)),
                         r["totaux"]["participation_estimee"])

    def test_pas_de_certification_sans_justificatif(self):
        d = fixture()
        d["jours"][0]["justificatif"] = ""
        self.assertIsNone(calculer(d)["totaux"]["solde_verifie"])

    def test_format_10_jours_ne_devient_pas_1(self):
        self.assertEqual(_fr_jours(10), "10")
        self.assertEqual(_fr_jours(100), "100")
        self.assertEqual(_fr_jours(0), "0")


class ExportConsommationsTests(unittest.TestCase):
    def setUp(self):
        self.rules = {
            "1:10": {"convention": "ALSH-2025-2026", "poids": "1"},
            "1:11": {"convention": "ALSH-2025-2026", "poids": "0"},
            "1:20": {"convention": "ALSH-2025-2026", "poids": "0.5", "demi_journee_confirmee": True},
            "1:21": {"convention": "ALSH-2025-2026", "poids": "0.5", "demi_journee_confirmee": True},
        }

    def rec(self, ident, enfant, jour, unite, etat="present", commune="Bais"):
        return {"IDconso": ident, "IDindividu": enfant, "date": jour,
                "IDactivite": 1, "IDunite": unite, "etat": etat,
                "commune_residence": commune}

    def test_matin_plus_aprem_une_journee_et_repas_zero(self):
        recs = [self.rec(1, 1, "2026-01-10", 20),
                self.rec(2, 1, "2026-01-10", 21),
                self.rec(3, 1, "2026-01-10", 11),
                self.rec(4, 2, "2026-01-10", 10)]
        r = consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")
        self.assertEqual(r["jours"][0]["nombre"], "2.0")
        self.assertEqual(r["nb_enfants_jour"], 2)

    def test_deux_activites_meme_jour_pas_de_double(self):
        recs = [self.rec(1, 1, "2026-01-10", 10), self.rec(2, 1, "2026-01-10", 20)]
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")

    def test_reservation_futur_uniquement_et_absences_exclues(self):
        recs = [self.rec(1, 1, "2026-10-01", 10, "reservation"),
                self.rec(2, 1, "2026-11-05", 10, "reservation"),
                self.rec(3, 2, "2026-01-05", 10, "absent")]
        r = consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")
        self.assertEqual(r["jours"][0]["nature"], "prevision")
        self.assertEqual(r["exclusions"]["reservations_passees"], 1)
        self.assertEqual(r["exclusions"]["absences"], 1)

    def test_autre_commune_n_est_pas_site_accueil(self):
        recs = [self.rec(1, 1, "2026-01-10", 10, commune="Moutiers")]
        r = consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")
        self.assertEqual(r["jours"], [])
        self.assertEqual(r["exclusions"]["autres_communes"], 1)

    def test_pas_de_double_compte_entre_alsh_et_ados(self):
        rules = deepcopy(self.rules)
        rules["2:22"] = {"convention": "ADOS-2024-2026-BAIS", "poids": "1"}
        r1 = self.rec(1, 1, "2026-01-10", 10)
        r2 = self.rec(2, 1, "2026-01-10", 22)
        r2["IDactivite"] = 2
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations([r1, r2], rules, "Bais", 2026, "2026-10-29")

    def test_domicile_absent_bloque(self):
        recs = [self.rec(1, 1, "2026-01-10", 10, commune="")]
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")

    def test_unite_inconnue_bloque_et_demi_non_justifie(self):
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations([self.rec(1, 1, "2026-01-10", 99)], self.rules, "Bais", 2026, "2026-10-29")
        rules = deepcopy(self.rules)
        rules["1:20"]["demi_journee_confirmee"] = False
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations([self.rec(1, 1, "2026-01-10", 20)], rules, "Bais", 2026, "2026-10-29")

    def test_presence_future_et_etat_inconnu_bloquent(self):
        for rec in [self.rec(1, 1, "2026-11-02", 10), self.rec(1, 1, "2026-01-10", 10, etat="attente")]:
            with self.subTest(rec=rec), self.assertRaises(ErreurFrequentation):
                consolider_export_consommations([rec], self.rules, "Bais", 2026, "2026-10-29")

    def test_pas_de_identifiants_personnels_en_sortie(self):
        recs = [self.rec(1, 74749, "2026-01-10", 10)]
        r = consolider_export_consommations(recs, self.rules, "Bais", 2026, "2026-10-29")
        self.assertNotIn("74749", str(r))


class EditionTests(unittest.TestCase):
    @staticmethod
    def cellule_xlsx(archive, feuille, cellule):
        nom = "xl/worksheets/sheet%d.xml" % feuille
        racine = ET.fromstring(archive.read(nom))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        element = racine.find(".//m:c[@r='%s']" % cellule, ns)
        assert element is not None, "Cellule absente : " + cellule
        formule = element.find("m:f", ns)
        cache = element.find("m:v", ns)
        return (formule.text if formule is not None else None,
                cache.text if cache is not None else None, element.attrib)

    def test_excel_export_avec_formules_et_resultats_en_cache(self):
        d = fixture()
        r = calculer(d)
        with tempfile.TemporaryDirectory() as repertoire:
            p = exporter_xlsx(r, Path(repertoire) / "situation.xlsx", d)
            self.assertTrue(p.read_bytes().startswith(b"PK"))
            with ZipFile(p) as archive:
                noms = archive.namelist()
                self.assertIn("xl/worksheets/sheet4.xml", noms)
                self.assertEqual(self.cellule_xlsx(archive, 1, "J11")[1], "131.75")
                self.assertEqual(self.cellule_xlsx(archive, 1, "F9")[0], "ROUND(C9*D9,2)")
                self.assertEqual(self.cellule_xlsx(archive, 1, "F9")[1], "115.4")
                self.assertEqual(float(self.cellule_xlsx(archive, 1, "I9")[1]), 100.0)
                self.assertEqual(self.cellule_xlsx(archive, 2, "D16")[1], "231.75")
                self.assertEqual(float(self.cellule_xlsx(archive, 3, "F4")[1]), 100.0)

    def test_excel_retrait_des_acomptes_futurs(self):
        d = fixture()
        d["acomptes"].append({"id": "A-FUTUR", "convention": "ALSH-2025-2026",
                              "date": "2026-11-30", "exercice": 2026,
                              "montant": "50.00", "justificatif": "test fictif"})
        r = calculer(d)
        with tempfile.TemporaryDirectory() as repertoire:
            p = exporter_xlsx(r, Path(repertoire) / "futur.xlsx", d)
            with ZipFile(p) as archive:
                self.assertEqual(float(self.cellule_xlsx(archive, 3, "F4")[1]), 100.0)
                self.assertEqual(float(self.cellule_xlsx(archive, 3, "F5")[1]), 0.0)
                self.assertEqual(float(self.cellule_xlsx(archive, 3, "F6")[1]), 100.0)
                self.assertEqual(self.cellule_xlsx(archive, 1, "J11")[1], "131.75")

    def test_excel_aucune_presence_inconnue_n_est_zero(self):
        r = calculer(modele())
        with tempfile.TemporaryDirectory() as repertoire:
            p = exporter_xlsx(r, Path(repertoire) / "incomplet.xlsx")
            with ZipFile(p) as archive:
                f, v, attributes = self.cellule_xlsx(archive, 1, "J11")
                self.assertIsNone(f)
                self.assertEqual(attributes.get("t"), "s")
                self.assertIn("NON CALCULABLE", archive.read("xl/sharedStrings.xml").decode("utf-8"))

    def test_excel_protection_formules_depuis_saisies(self):
        d = fixture()
        d["conventions"][0]["accueil"] = '=HYPERLINK("https://exemple.invalid", "test")'
        d["acomptes"][0]["justificatif"] = "=1+1"
        with tempfile.TemporaryDirectory() as repertoire:
            p = exporter_xlsx(calculer(d), Path(repertoire) / "texte.xlsx", d)
            with ZipFile(p) as archive:
                ss = archive.read("xl/sharedStrings.xml").decode("utf-8")
                sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
                self.assertIn("HYPERLINK", ss)
                self.assertIn("=1+1", ss)
                self.assertNotIn("HYPERLINK", sheet)

    def test_excel_refus_ecrasement_et_dossier_melange(self):
        d = fixture()
        r = calculer(d)
        with tempfile.TemporaryDirectory() as repertoire:
            cible = Path(repertoire) / "situation.xlsx"
            exporter_xlsx(r, cible, d)
            contenu = cible.read_bytes()
            with self.assertRaises(FileExistsError):
                exporter_xlsx(r, cible, d)
            self.assertEqual(cible.read_bytes(), contenu)
            autre = deepcopy(d)
            autre["jours"][0]["nombre"] = "11"
            with self.assertRaises(ErreurFrequentation):
                exporter_xlsx(r, Path(repertoire) / "autre.xlsx", autre)
            self.assertFalse((Path(repertoire) / "autre.xlsx").exists())

    def test_excel_exemple_explicitement_fictif_et_ui_wx(self):
        d = fixture()
        with tempfile.TemporaryDirectory() as repertoire:
            p = exporter_xlsx(calculer(d), Path(repertoire) / "exemple.xlsx", d,
                              fictif=True)
            with ZipFile(p) as archive:
                self.assertIn("NE PAS TRANSMETTRE", archive.read("xl/sharedStrings.xml").decode("utf-8"))
        source = (ROOT / "noethys" / "Dlg" / "DLG_Frequentation_collectivites.py").read_text(encoding="utf-8")
        self.assertIn('("Exporter Excel", self.OnExcel)', source)
        self.assertIn('self._exporter("xlsx",', source)

    def test_exports_csv_et_pdf(self):
        r = calculer(fixture())
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            p = exporter_csv(r, target / "report.csv")
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f, delimiter=";"))
            self.assertIn(["solde_indicatif", "131.75"], rows)
            csv_text = p.read_text(encoding="utf-8-sig").lower()
            self.assertIn("journees", csv_text)
            self.assertNotIn("facture", csv_text)
            self.assertNotIn("tva", csv_text)
            pdf_path = exporter_pdf(r, target / "report.pdf", fictif=True)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            self.assertGreater(pdf_path.stat().st_size, 2500)

    def test_ne_pas_ecraser_un_rapport_existant(self):
        r = calculer(fixture())
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tableau.csv"
            exporter_csv(r, path)
            with self.assertRaises(FileExistsError):
                exporter_csv(r, path)


if __name__ == "__main__":
    unittest.main()