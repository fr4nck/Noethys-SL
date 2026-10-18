# -*- coding: utf-8 -*-
"""Issue #429 : suggestions d'encadrement, sans DB ni reseau."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Encadrement import AgeAuJour, TauxEncadrement, CalculerEncadrement


class RatiosTests(unittest.TestCase):
    def test_regimes(self):
        for cadre, duree, pedt, taux in [
            ("periscolaire", 4, False, (10, 14)),
            ("periscolaire", 5, False, (10, 14)),
            ("periscolaire", 5.0001, False, (8, 12)),
            ("periscolaire", 8, False, (8, 12)),
            ("periscolaire", 5, True, (14, 18)),
            ("periscolaire", 6, True, (10, 14)),
            ("extrascolaire", None, False, (8, 12)),
        ]:
            with self.subTest(cadre=cadre, duree=duree, pedt=pedt):
                self.assertEqual(TauxEncadrement(cadre, duree, pedt), taux)

    def test_regime_inconnu_ou_pedt_non_qualifie_bloque(self):
        for args in [("inconnu", None, False), ("periscolaire", None, False),
                     ("periscolaire", -1, False), ("periscolaire", 4, "oui"),
                     ("extrascolaire", None, True)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                TauxEncadrement(*args)

    def test_anniversaires(self):
        self.assertEqual(AgeAuJour("2020-10-19", "2026-10-18"), 5)
        self.assertEqual(AgeAuJour("2020-10-19", "2026-10-19"), 6)
        self.assertEqual(AgeAuJour(date(2020, 2, 29), date(2026, 2, 28)), 5)
        self.assertEqual(AgeAuJour(None, date(2026, 2, 28)), None)
        self.assertEqual(AgeAuJour("2030-01-01", "2026-01-01"), None)


class CalculTests(unittest.TestCase):
    def setUp(self):
        self.date = "2026-10-19"
        self.matin = {"site": "A", "creneau": "matin", "cadre": "periscolaire", "duree_heures": 4}
        self.midi = {"site": "A", "creneau": "midi", "cadre": "periscolaire", "duree_heures": 2}
        self.soir = {"site": "A", "creneau": "apres-midi", "cadre": "periscolaire", "duree_heures": 4}
        self.config = {(1, 10): self.matin, (1, 11): self.midi, (1, 12): self.soir}
        self.enfants = {1: {"date_naiss": "2021-01-01"}, 2: {"date_naiss": "2015-01-01"},
                        3: {"date_naiss": "2000-01-01"}, 4: {"date_naiss": None}}

    def ligne(self, ident, unite=10, etat="present", groupe=1, jour=None):
        return {"IDindividu": ident, "IDgroupe": groupe, "IDunite": unite,
                "date": jour or self.date, "etat": etat}

    def test_une_plage_age_et_adultes(self):
        r = CalculerEncadrement([self.ligne(1), self.ligne(2), self.ligne(3)], self.enfants, self.config)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["moins_6"], r[0]["six_et_plus"], r[0]["adultes_ignores"]), (1, 1, 1))
        self.assertEqual(r[0]["animateurs_suggeres"], 2)
        self.assertTrue(r[0]["calcul_complet"])

    def test_reservation_vs_presence_et_absence(self):
        c = [self.ligne(1, etat="reservation"), self.ligne(2), self.ligne(4, etat="absent")]
        self.assertEqual(CalculerEncadrement(c, self.enfants, self.config, mode="previsionnel")[0]["enfants_connus"], 2)
        self.assertEqual(CalculerEncadrement(c, self.enfants, self.config, mode="reel")[0]["enfants_connus"], 1)

    def test_les_trois_temps_ne_sadditionnent_pas(self):
        c = [self.ligne(1, 10), self.ligne(1, 11), self.ligne(1, 12)]
        r = CalculerEncadrement(c, self.enfants, self.config)
        self.assertEqual(len(r), 3)
        self.assertEqual([a["animateurs_suggeres"] for a in r], [1, 1, 1])

    def test_double_reservation_meme_creneau_pas_doublee(self):
        self.config[(1, 14)] = self.matin
        c = [self.ligne(1, 10), self.ligne(1, 14), self.ligne(1, 10)]
        r = CalculerEncadrement(c, self.enfants, self.config)
        self.assertEqual(r[0]["moins_6"], 1)

    def test_age_inconnu_bloque_calcul_complet(self):
        r = CalculerEncadrement([self.ligne(4)], self.enfants, self.config)[0]
        self.assertEqual(r["age_inconnu"], 1)
        self.assertEqual(r["animateurs_suggeres"], 0)
        self.assertFalse(r["calcul_complet"])

    def test_conflit_de_sites_signale(self):
        self.config[(2, 20)] = dict(self.matin, site="B")
        c = [self.ligne(1), self.ligne(1, groupe=2, unite=20)]
        r = CalculerEncadrement(c, self.enfants, self.config)
        self.assertEqual(len(r), 2)
        self.assertEqual([x["conflits_sites"] for x in r], [1, 1])
        self.assertFalse(all(x["calcul_complet"] for x in r))

    def test_contradiction_regime_bloque(self):
        self.config[(2, 20)] = dict(self.matin, duree_heures=8)
        with self.assertRaises(ValueError):
            CalculerEncadrement([self.ligne(1), self.ligne(2, groupe=2, unite=20)], self.enfants, self.config)

    def test_groupe_non_configure_bloque(self):
        with self.assertRaises(ValueError):
            CalculerEncadrement([self.ligne(1, groupe=3, unite=30)], self.enfants, self.config)

    def test_arrondis_separes_pour_17_et_27(self):
        personnes = {i: {"date_naiss": "2021-01-01" if i <= 17 else "2015-01-01"} for i in range(1, 45)}
        c = [self.ligne(i) for i in range(1, 45)]
        r = CalculerEncadrement(c, personnes, self.config)[0]
        self.assertEqual((r["moins_6"], r["six_et_plus"], r["animateurs_suggeres"]), (17, 27, 4))
        config_long = {(1, 10): {"site": "A", "creneau": "matin", "cadre": "extrascolaire"}}
        self.assertEqual(CalculerEncadrement(c, personnes, config_long)[0]["animateurs_suggeres"], 6)

    def test_rejet_id_date_invalides(self):
        for value in [self.ligne(None), self.ligne(1, jour="pas-une-date")]:
            with self.assertRaises(ValueError):
                CalculerEncadrement([value], self.enfants, self.config)


if __name__ == "__main__":
    unittest.main()
