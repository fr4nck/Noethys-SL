# -*- coding: utf-8 -*-
"""Qualification du champ STANDARD INDIVIDU_AEEH dans l'Etat Nominatif.

Exécute le VRAI chemin de production (aucune donnée ni fonction
réimplémentée) contre une base SQLite réelle construite depuis le schéma
canonique (Data.DATA_Tables) :

    individus.aeeh
      -> Ol.OL_Etat_nomin_resultats.GetDictIndividus()
      -> Ol.OL_Etat_nomin_resultats.Track.INDIVIDU_AEEH
      -> rendu texte (UTILS_Aeeh.ValeurVersTexte, déjà appliqué dans Track)

pour les trois états NULL / 0 / 1, et vérifie que les autres champs
STANDARD (INDIVIDU_NOM, etc.) ne sont pas perturbés par l'ajout du champ.

Réutilise la fixture partagée tests/_fixtures_noethys_db.py (même principe
que test_vanilla_convention_scolaire.py), en ajoutant seulement les tables
"scolarite"/"ecoles"/"classes"/"niveaux_scolaires" nécessaires à l'appel
(pré-existant, non lié à l'AEEH) UTILS_Infos_individus.Informations(...,
scolarite=True) fait par GetDictIndividus -- ces tables ne sont pas dans
TABLES_REQUISES de la fixture partagée, donc ajoutées ici localement pour
ne pas modifier ce fichier partagé par d'autres suites.
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from Data import DATA_Tables as Tables  # noqa: E402
from Ol import OL_Etat_nomin_resultats as ENR  # noqa: E402
from Ol import OL_Etat_nomin_champs as ENC  # noqa: E402

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_ecole_simple,
)


def _completer_tables_scolarite(base):
    """ GetDictIndividus() appelle en interne
    UTILS_Infos_individus.Informations(..., scolarite=True), qui requiert
    ces 4 tables du schéma canonique -- absentes de TABLES_REQUISES car
    aucune autre suite existante n'en avait besoin. """
    for nom_table in ("niveaux_scolaires", "ecoles", "classes", "scolarite"):
        base.db.CreationTable(nom_table, dicoDB=Tables.DB_DATA)
    base.db.Commit()


class CheminCompletEtatNominatifTests(unittest.TestCase):
    """ Les 3 cycles fictifs (20/21/22) de creer_base_ecole_simple() portent
    chacun un état AEEH différent : NULL (valeur par défaut, jamais
    touchée), 0 (Non) et 1 (Oui). """

    def test_null_0_1_traversent_la_chaine_reelle_et_rendent_le_bon_texte(self):
        with creer_base_ecole_simple() as base:
            _completer_tables_scolarite(base)
            # 20 = NULL (non renseigné, valeur par défaut, non touchée)
            base.db.ExecuterReq("UPDATE individus SET aeeh=0 WHERE IDindividu=21;")
            base.db.ExecuterReq("UPDATE individus SET aeeh=1 WHERE IDindividu=22;")
            base.db.Commit()

            with RedirectionGestionDB(base.chemin):
                dict_individus = ENR.GetDictIndividus(
                    parametres={"date_debut": datetime.date(2026, 9, 1), "date_fin": datetime.date(2027, 8, 31)}
                )

        # ---- Chemin individus.aeeh -> GetDictIndividus (valeurs brutes) ----
        self.assertIsNone(dict_individus[20]["aeeh"])
        self.assertEqual(dict_individus[21]["aeeh"], 0)
        self.assertEqual(dict_individus[22]["aeeh"], 1)

        # Aucune conversion implicite NULL -> 0 à cet étage
        self.assertIsNot(dict_individus[20]["aeeh"], 0)

        # ---- Chemin GetDictIndividus -> Track.INDIVIDU_AEEH (rendu texte) ----
        # Peuple les globals minimalistes attendus par Track, exactement comme le
        # fait réellement ListView.GetTracks() juste avant de créer les Track
        # (DICT_TITULAIRES/DICT_FAMILLES/DICT_QUESTIONNAIRES), sans ré-exercer le
        # calcul des titulaires/familles (couvert par ailleurs, hors périmètre AEEH).
        ENR.DICT_INDIVIDUS = dict_individus
        ENR.DICT_TITULAIRES = {
            2: {"titulairesSansCivilite": "MARTIN Alice",
                "adresse": {"rue": "", "cp": "", "ville": "", "secteur": ""}},
        }
        ENR.DICT_FAMILLES = {2: {"nomCaisse": None, "num_allocataire": None, "nomAllocataire": None, "qf": None}}
        ENR.DICT_QUESTIONNAIRES = {}

        track_non_renseigne = ENR.Track(IDindividu=20, IDfamille=2, listeConso=[], listeChamps=[])
        track_non = ENR.Track(IDindividu=21, IDfamille=2, listeConso=[], listeChamps=[])
        track_oui = ENR.Track(IDindividu=22, IDfamille=2, listeConso=[], listeChamps=[])

        # ---- Rendu attendu : NULL -> vide, 0 -> "Non", 1 -> "Oui" ----
        self.assertEqual(track_non_renseigne.INDIVIDU_AEEH, u"")
        self.assertEqual(track_non.INDIVIDU_AEEH, u"Non")
        self.assertEqual(track_oui.INDIVIDU_AEEH, u"Oui")

        # Garde-fou explicite : NULL ne doit jamais rendre le même texte que 0
        self.assertNotEqual(track_non_renseigne.INDIVIDU_AEEH, track_non.INDIVIDU_AEEH)

        # ---- Non-perturbation des autres champs STANDARD (nom/prénom) ----
        self.assertEqual(track_non_renseigne.INDIVIDU_NOM, "CE2-CM1-CM2")
        self.assertEqual(track_non_renseigne.INDIVIDU_PRENOM, "CYCLE FICTIF 3")
        self.assertEqual(track_non.INDIVIDU_NOM, "CP-CE1-CE2")
        self.assertEqual(track_non.INDIVIDU_PRENOM, "CYCLE FICTIF 2")
        self.assertEqual(track_oui.INDIVIDU_NOM, "PS-MS-GS")
        self.assertEqual(track_oui.INDIVIDU_PRENOM, "CYCLE FICTIF 1")

    def test_champ_aeeh_selectionnable_parmi_les_champs_standards(self):
        """ Vérification mécanique (pas juste textuelle) : INDIVIDU_AEEH est bien
        un champ STANDARD proposé par Ol.OL_Etat_nomin_champs.Champs.GetTracks(). """
        codes = [code for code, label, categorie, titre, largeur in ENC.LISTE_CHAMPS_STANDARDS]
        self.assertIn("INDIVIDU_AEEH", codes)

        index_aeeh = codes.index("INDIVIDU_AEEH")
        # Champ juste avant/après restent inchangés : l'ajout n'a rien décalé/altéré
        self.assertEqual(codes[index_aeeh - 1], "SCOLARITE_ABREGE_NIVEAU")
        self.assertEqual(ENC.LISTE_CHAMPS_STANDARDS[index_aeeh][2], u"Individu")

    def test_ordre_isinstance_formatagevaleur_protege_0_de_la_branche_numerique(self):
        """ Garde-fou anti-régression : le rendu final de la grille
        (OL_Etat_nomin_resultats.ListView.InitObjectListView -> FormatageValeur)
        distingue str/int/float par isinstance(). Comme INDIVIDU_AEEH est déjà
        du texte (jamais un entier brut) grâce à UTILS_Aeeh.ValeurVersTexte(),
        il tombe dans la branche "texte" et n'est JAMAIS traité par la branche
        "Nombre" -- qui, elle, transforme un entier 0 en chaîne vide (ce qui
        rendrait "Non" indistinguable de "Non renseigné"). Verrouille l'ordre
        des branches dans le code source pour empêcher une régression silencieuse. """
        source = (NOETHYS_DIR / "Ol" / "OL_Etat_nomin_resultats.py").read_text(encoding="utf-8")
        pos_texte = source.index('if isinstance(valeur, str)')
        pos_nombre = source.index("# Nombre")
        self.assertLess(pos_texte, pos_nombre,
                         "La branche texte de FormatageValeur doit rester avant la branche Nombre")


if __name__ == "__main__":
    unittest.main()
