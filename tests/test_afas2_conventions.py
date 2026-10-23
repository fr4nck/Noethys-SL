# -*- coding: utf-8 -*-
"""AFAS V2 -- règles contractuelles des conventions CAF ALSH 2025-2027.

Module pur : aucun import wx, aucune base. Chaque test cite la règle
conventionnelle qu'il vérifie (voir docs/afas/TRACABILITE_CONVENTIONS_2025_2027.md).
"""
import datetime
import sys
import unittest
from pathlib import Path

NOETHYS = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

from Utils import UTILS_AFAS2_Conventions as C  # noqa: E402

H = C.SECONDES_HEURE


def hm(texte):
    heures, minutes = texte.split(":")
    return int(heures) * H + int(minutes) * 60


class PeriscolaireTests(unittest.TestCase):
    """Conventions PERI Bais et La Guerche-Moutiers, art. 2-2."""

    def test_plage_1h15_retenue_entierement(self):
        self.assertEqual(C.PresencePeriscolaireJour([(hm("07:30"), hm("08:45"))]), hm("01:15"))

    def test_plusieurs_plages_additionnees(self):
        plages = [(hm("07:30"), hm("08:45")), (hm("11:45"), hm("13:45")), (hm("16:30"), hm("18:30"))]
        self.assertEqual(C.PresencePeriscolaireJour(plages), hm("05:15"))

    def test_plafond_9h_par_jour(self):
        plages = [(hm("07:00"), hm("12:00")), (hm("12:00"), hm("19:00"))]
        self.assertEqual(C.PresencePeriscolaireJour(plages), 9 * H)

    def test_recouvrement_compte_une_fois(self):
        # Repas méridien inclus dans une plage déjà retenue : pas de double comptage.
        plages = [(hm("11:45"), hm("13:45")), (hm("12:00"), hm("13:00"))]
        self.assertEqual(C.PresencePeriscolaireJour(plages), 2 * H)

    def test_plage_invalide_refusee(self):
        for plage in ((hm("09:00"), hm("08:00")), (hm("09:00"), hm("09:00")), (-1, 60), (0, 25 * H), (0.5, 60)):
            with self.subTest(plage=plage), self.assertRaises(ValueError):
                C.PresencePeriscolaireJour([plage])

    def test_meme_regle_bais_et_la_guerche(self):
        bais = C.CONVENTIONS["PERI_BAIS_2025_2027"]["regles"]
        guerche = C.CONVENTIONS["PERI_LA_GUERCHE_MOUTIERS_2025_2027"]["regles"]
        self.assertEqual(bais, guerche)
        self.assertEqual(bais["plafond_jour_secondes"], 9 * H)
        self.assertIsNone(bais["heures_facturees"])


class ExtrascolaireOption2Tests(unittest.TestCase):
    """Conventions EXTRA Bais et La Guerche-Moutiers, art. 2-2, option n°2 retenue."""

    def test_amplitude_9h(self):
        self.assertEqual(C.DureeJourneeOption2("journee", 9 * H), 8 * H)
        self.assertEqual(C.DureeJourneeOption2("demi_journee", 9 * H), 4 * H)

    def test_amplitude_8h_exactement(self):
        self.assertEqual(C.DureeJourneeOption2("journee", 8 * H), 8 * H)
        self.assertEqual(C.DureeJourneeOption2("demi_journee", 8 * H), 4 * H)

    def test_amplitude_6h(self):
        self.assertEqual(C.DureeJourneeOption2("journee", 6 * H), 6 * H)
        self.assertEqual(C.DureeJourneeOption2("demi_journee", 6 * H), 3 * H)

    def test_amplitude_7h45_moitie_exacte(self):
        self.assertEqual(C.DureeJourneeOption2("demi_journee", hm("07:45")), hm("03:52") + 30)

    def test_amplitude_absente_ou_invalide(self):
        for amplitude in (None, 0, -60, 3.5 * H, "8"):
            with self.subTest(amplitude=amplitude), self.assertRaises(ValueError):
                C.DureeJourneeOption2("journee", amplitude)

    def test_nature_inconnue(self):
        with self.assertRaises(ValueError):
            C.DureeJourneeOption2("repas", 9 * H)

    def test_option2_retenue_dans_les_deux_conventions(self):
        for code in ("EXTRA_BAIS_2025_2027", "EXTRA_LA_GUERCHE_MOUTIERS_2025_2027"):
            self.assertEqual(C.CONVENTIONS[code]["regles"]["option_facturation"], 2)

    def test_sejour_10h_par_journee(self):
        self.assertEqual(C.SEJOUR_JOURNEE, 10 * H)


class ValiditeTests(unittest.TestCase):
    def test_resolution_par_equipement_et_mode(self):
        jour = datetime.date(2026, 3, 4)
        self.assertEqual(C.ResoudreConvention(C.EQUIPEMENT_BAIS, C.PERISCOLAIRE, jour), "PERI_BAIS_2025_2027")
        self.assertEqual(C.ResoudreConvention(C.EQUIPEMENT_LA_GUERCHE_MOUTIERS, C.EXTRASCOLAIRE, jour),
                         "EXTRA_LA_GUERCHE_MOUTIERS_2025_2027")

    def test_annees_couvertes(self):
        for annee in (2025, 2026, 2027):
            with self.subTest(annee=annee):
                self.assertEqual(C.ResoudreConventionAnnee(C.EQUIPEMENT_BAIS, C.EXTRASCOLAIRE, annee), "EXTRA_BAIS_2025_2027")

    def test_hors_periode_jamais_etendue(self):
        for annee in (2024, 2028):
            with self.subTest(annee=annee), self.assertRaises(C.ConventionNonApplicable):
                C.ResoudreConventionAnnee(C.EQUIPEMENT_BAIS, C.PERISCOLAIRE, annee)
        with self.assertRaises(C.ConventionNonApplicable):
            C.ResoudreConvention(C.EQUIPEMENT_BAIS, C.PERISCOLAIRE, datetime.date(2024, 12, 31))

    def test_equipement_ou_mode_inconnu(self):
        with self.assertRaises(C.ConventionNonApplicable):
            C.ResoudreConvention("ADOS", C.PERISCOLAIRE, datetime.date(2026, 1, 1))
        with self.assertRaises(C.ConventionNonApplicable):
            C.ResoudreConvention(C.EQUIPEMENT_BAIS, "accueil_jeunes", datetime.date(2026, 1, 1))

    def test_chaque_regle_tracee(self):
        for cle in ("periscolaire_definition", "periscolaire_plage_9h", "periscolaire_repas", "complement_inclusif",
                    "extrascolaire_definition", "extrascolaire_actes", "extrascolaire_option2", "sejours",
                    "duree_conventions"):
            with self.subTest(cle=cle):
                self.assertTrue(C.SOURCES[cle])
                for source in C.SOURCES[cle]:
                    self.assertTrue(source["fichier"] and source["article"] and source["page_pdf"])


class OutilsTests(unittest.TestCase):
    def test_arrondi_heure_superieure(self):
        self.assertEqual(C.ArrondiHeureSuperieure(0), 0)
        self.assertEqual(C.ArrondiHeureSuperieure(1), H)
        self.assertEqual(C.ArrondiHeureSuperieure(H), H)
        self.assertEqual(C.ArrondiHeureSuperieure(H + 1), 2 * H)


if __name__ == "__main__":
    unittest.main()
