# -*- coding: utf-8 -*-
"""Regressions restes : mesures locales et suggestions non appliquées."""
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"noethys"))
from Utils import UTILS_Repas_oceane_restes as R
from Utils import UTILS_Repas_oceane_annexe as A
from Utils.UTILS_Repas_totaux import TotauxRepas


def ligne(jour="2026-11-04", site="Bais", plat="Semoule HVE", portion=20,
          servies=15, restes=140, grammes=90):
    return {"date": jour, "site": site, "composante": "garniture",
            "plat": plat, "tranche": "P", "commandes":portion,
            "livrees":portion, "servies":servies,
            "restes_assiettes_g": restes,"grammes_par_portion":grammes}


class RestesTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fichier=Path(self.temp.name)/"restes.csv"

    def test_mesure_du_surplus_et_borne_15_pourcent(self):
        examples=[ligne(jour=x,restes=100,servies=18) for x in (
            "2026-11-04","2026-11-11","2026-11-18")]
        self.assertIsNone(R.SuggereQuantite(
            examples[:2],"Bais","garniture","Semoule HVE","P",30))
        result=R.SuggereQuantite(
            examples,"Bais","garniture","Semoule HVE","P",30)
        self.assertEqual(result["nombre_observations"],3)
        self.assertEqual(result["taux_reduction_plafonne"],0.15)
        self.assertEqual(result["quantite_proposee"],26)
        self.assertTrue(result["validation_humaine_obligatoire"])
        self.assertEqual(examples[0]["commandes"],20)

    def test_restes_conformes_aux_portions_servies(self):
        with self.assertRaises(ValueError):
            R.ValiderObservation(ligne(servies=21))
        with self.assertRaises(ValueError):
            R.ValiderObservation(ligne(restes=2000,grammes=90))
        with self.assertRaises(ValueError):
            R.ValiderObservation(ligne(restes=50,grammes=0))
        with self.assertRaises(ValueError):
            R.ValiderObservation(ligne(portion=-2))
        with self.assertRaises(ValueError):
            R.ValiderObservation(ligne(plat=""))

    def test_separe_plats_sites_et_tranches(self):
        history=[ligne(jour=x) for x in (
            "2026-11-04","2026-11-11","2026-11-18")]
        for site,plat,tranche in (
            ("Moutiers","Semoule HVE","P"),
            ("Bais","Riz","P"),
            ("Bais","Semoule HVE","M")):
            self.assertIsNone(R.SuggereQuantite(
                history,site,"garniture",plat,tranche,30))
        self.assertIsNotNone(R.SuggereQuantite(
            history,"Bais","garniture","Semoule HVE","P",30))

    def test_csv_append_uniquement_et_refus_doublons(self):
        premier=ligne()
        self.assertEqual(R.EnregistrerObservations(self.fichier,[premier]),1)
        self.assertEqual(len(R.LireHistorique(self.fichier)),1)
        avant=self.fichier.read_bytes()
        with self.assertRaises(ValueError):
            R.EnregistrerObservations(self.fichier,[premier])
        self.assertEqual(self.fichier.read_bytes(),avant)
        suivant=ligne(jour="2026-11-11")
        R.EnregistrerObservations(self.fichier,[suivant])
        self.assertEqual(len(R.LireHistorique(self.fichier)),2)

    def test_annexe_et_relecture(self):
        fiche={
            "date":date(2026,11,4),"site":"Bais","service":"midi",
            "totaux":TotauxRepas(8,25,animateurs_repas=4),
            "composantes":{k:{"M":8,"P":29} for k in (
                "entree","plat","garniture","laitage","dessert")},
            "intitules":{"plat":"Sauté de porc","garniture":"Semoule"},
            "grammages":{"plat":{"M":80,"P":100}},
        }
        fichier=Path(self.temp.name)/"annexe.csv"
        self.assertEqual(A.EnregistrerAnnexe(fichier,[fiche]),10)
        result=A.LireAnnexe(fichier)
        self.assertEqual(len(result),10)
        plat_P=[x for x in result if x["composante"]=="plat"
                and x["tranche"]=="P"][0]
        self.assertEqual((plat_P["commandes"],plat_P["grammes_par_portion"]),
                         (29,100))
        self.assertEqual(plat_P["plat"],"Sauté de porc")


if __name__ == "__main__":
    unittest.main()
