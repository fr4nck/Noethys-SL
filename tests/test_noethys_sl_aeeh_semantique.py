# -*- coding: utf-8 -*-
"""Garde-fous sémantiques sur le statut AEEH (Bénéficiaire AEEH).

AEEH = bénéficiaire de l'Allocation d'Education de l'Enfant Handicapé,
NULL/0/1 sur `individus.aeeh`. Ce test ne porte sur AUCUNE logique de
calcul ni migration : il verrouille uniquement la frontière métier de
présentation du champ AEEH lui-même (libellés, info-bulle, description de
colonne de l'Etat Nominatif), à savoir :

  - le champ reste explicitement identifié comme AEEH / allocation ;
  - aucun libellé du champ AEEH n'est simplement "Handicap" ou "Situation
    de handicap" ;
  - le tooltip précise que "Oui" ne concerne que le bénéfice de
    l'allocation, que "Non" ne signifie pas l'absence de handicap, et que
    "Non renseigné" signifie une information inconnue/non saisie ;
  - UTILS_Aeeh.py reste un simple mapping tri-état (aucune fonction ne
    dérive l'AEEH vers un indicateur générique de handicap ni ne
    déclenche quoi que ce soit côté accompagnement).

Ce fichier ne verrouille PAS l'emploi des mots "accompagnement",
"aménagement", "autonomie", "PPS", "AESH", "PCH", "CMI" ou "handicap"
ailleurs dans le logiciel : ces notions peuvent légitimement exister par
ailleurs, sans rapport avec AEEH. Le garde-fou anti-couplage AFAS existe
déjà dans tests/test_noethys_sl_aeeh.py
(Test_DossierIndividuelCablageAeeh.test_aucune_ecriture_dans_les_zones_hors_perimetre)
et n'est pas dupliqué ici.

La distinction mécanique NULL/0/1 -> ""/"Non"/"Oui" est déjà verrouillée
par tests/test_noethys_sl_aeeh_etat_nominatif.py ; ce fichier-ci ne
verrouille que la présentation, pas le calcul.
"""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Frontière métier : le champ AEEH ne doit jamais être réduit à un
# intitulé générique de handicap. Liste volontairement restreinte à ces
# deux intitulés précis -- pas une interdiction globale du mot "handicap".
LIBELLES_INTERDITS = (u"Handicap", u"Situation de handicap")


def _lire_source(chemin_relatif):
    return (ROOT / chemin_relatif).read_text(encoding="utf-8")


class ToolTipFicheIndividuTests(unittest.TestCase):
    """noethys/Dlg/DLG_Individu_identite.py : info-bulle du contrôle AEEH."""

    def setUp(self):
        self.source = _lire_source("noethys/Dlg/DLG_Individu_identite.py")
        m = re.search(r'self\.ctrl_aeeh\.SetToolTip\(wx\.ToolTip\(_\(u"(.*?)"\)\)\)', self.source)
        self.assertIsNotNone(m, "Info-bulle du contrôle AEEH introuvable")
        self.tooltip = m.group(1)

    def test_tooltip_precise_quil_sagit_uniquement_de_lallocation(self):
        self.assertIn(u"bénéficie de l'AEEH", self.tooltip)

    def test_tooltip_precise_que_non_ne_signifie_pas_absence_de_handicap(self):
        self.assertIn(u"ne signifie pas que l'individu n'est pas en situation de handicap", self.tooltip)

    def test_tooltip_precise_le_sens_de_non_renseigne(self):
        self.assertIn(u"Non renseigné", self.tooltip)
        self.assertIn(u"inconnue ou n'a pas été saisie", self.tooltip)

    def test_libelle_staticbox_nest_jamais_un_intitule_handicap_generique(self):
        m = re.search(r'self\.staticbox_aeeh = wx\.StaticBox\(self, -1, _\(u"(.*?)"\)\)', self.source)
        self.assertIsNotNone(m, "StaticBox AEEH introuvable")
        libelle = m.group(1).strip()
        self.assertNotIn(libelle, LIBELLES_INTERDITS)
        self.assertIn(u"AEEH", libelle)


class ChampEtatNominatifAeehTests(unittest.TestCase):
    """noethys/Ol/OL_Etat_nomin_champs.py : déclaration du champ STANDARD AEEH."""

    def setUp(self):
        self.source = _lire_source("noethys/Ol/OL_Etat_nomin_champs.py")
        m = re.search(
            r'\("INDIVIDU_AEEH", _\(u"(.*?)"\), _\(u"Individu"\), _\(u"(.*?)"\), (\d+)\)',
            self.source,
        )
        self.assertIsNotNone(m, "Champ STANDARD INDIVIDU_AEEH introuvable")
        self.description, self.titre_colonne, _largeur = m.groups()

    def test_titre_colonne_nest_jamais_un_intitule_handicap_generique(self):
        self.assertNotIn(self.titre_colonne.strip(), LIBELLES_INTERDITS)
        self.assertIn(u"AEEH", self.titre_colonne)

    def test_description_identifie_explicitement_lallocation(self):
        self.assertIn(u"AEEH", self.description)
        self.assertIn(u"pas une situation de handicap en général", self.description)

    def test_description_documente_le_rendu_des_trois_etats(self):
        # NULL (vide) doit rester documenté comme distinct de Non/Oui,
        # sans que la sémantique de rendu elle-même soit modifiée ici.
        self.assertIn(u"Oui/Non/vide si non renseigné", self.description)


class UtilsAeehResteUnMappingTriEtatTests(unittest.TestCase):
    """UTILS_Aeeh.py ne doit exposer que le mapping tri-état : aucune
    fonction ne doit dériver l'AEEH vers un indicateur générique de
    handicap, ni déclencher automatiquement un besoin d'accompagnement."""

    def test_utils_aeeh_nexpose_que_le_mapping_tri_etat(self):
        source = _lire_source("noethys/Utils/UTILS_Aeeh.py")
        fonctions_publiques = set(re.findall(r'^def (\w+)\(', source, re.MULTILINE))
        self.assertEqual(
            fonctions_publiques,
            {"GetLabels", "IndexVersValeur", "ValeurVersIndex", "ValeurVersTexte"},
        )


if __name__ == "__main__":
    unittest.main()
