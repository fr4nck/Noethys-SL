#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-régression pour la garde ResultatReq() vide ajoutée dans
Dlg/DLG_Badgeage_interface.py : GetInfosActivite, Procedure_enregistrer,
Procedure_reserver.

Chaque fonction/méthode est extraite par AST (même technique que les lots
précédents) et exécutée isolément avec un faux GestionDB.DB() et un ``self``
minimal (MagicMock), sans wx réel ni interface de badgeage réelle. Ces tests
démontrent le contrat de retour de GetInfosActivite et l'abandon de l'action
de badgeage en cours (log + return False) — pas le rendu de l'interface, qui
reste du ressort d'une recette manuelle.
"""

import ast
import datetime
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "noethys" / "Dlg" / "DLG_Badgeage_interface.py"


class FakeDB:
    """Double minimal de GestionDB.DB() : renvoie une file de résultats
    préconfigurés, un par appel de ResultatReq(), et trace les appels."""

    def __init__(self, resultats):
        self._resultats = list(resultats)
        self.requetes = []
        self.close_appele = False

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return self._resultats.pop(0)

    def Close(self):
        self.close_appele = True


def _extract_node(name: str, extra_namespace: dict, class_name: str = None):
    """Extrait UNE fonction module-level (class_name=None) ou UNE méthode
    de classe par AST, compilée isolément (sans exécuter le reste du
    fichier, donc sans wx réel)."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE_PATH))
    if class_name is None:
        node = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
    else:
        class_node = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == class_name
        )
        node = next(
            n for n in class_node.body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(extra_namespace)
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace[name]


def _underscore(texte):
    return texte


class GetInfosActiviteContractTests(unittest.TestCase):
    def _load(self, resultats):
        fake_db = FakeDB(resultats)
        fake_gestiondb = types.SimpleNamespace(DB=lambda: fake_db)
        get_infos_activite = _extract_node(
            "GetInfosActivite", {"GestionDB": fake_gestiondb}
        )
        return get_infos_activite, fake_db

    def test_missing_activite_returns_none_without_indexerror_and_closes_db(self):
        get_infos_activite, fake_db = self._load(resultats=[[]])

        resultat = get_infos_activite(IDactivite=5, date=datetime.date(2024, 1, 1))

        self.assertIsNone(resultat)
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 1, "les requêtes unités/groupes/ouvertures sont inutiles")

    def test_existing_activite_returns_historical_structure_and_closes_db(self):
        get_infos_activite, fake_db = self._load(resultats=[
            [("Multisport", "MS", "2024-09-01", "2025-07-01")],  # activité
            [(10, 1, "Matin", "M", "accueil", "08:00", 0, "18:00", 0)],  # unités
            [(2, "GroupeA", "GA", 1)],  # groupes
            [(1, 10, 2)],  # ouvertures
        ])

        dictActivite, dictUnites, listeOuvertures, dictGroupes = get_infos_activite(
            IDactivite=5, date=datetime.date(2024, 1, 1)
        )

        self.assertEqual(dictActivite["nom"], "Multisport")
        self.assertEqual(dictUnites[10]["nom"], "Matin")
        self.assertEqual(dictGroupes[2]["nom"], "GroupeA")
        self.assertEqual(listeOuvertures, [(10, 2)])
        self.assertTrue(fake_db.close_appele)
        self.assertEqual(len(fake_db.requetes), 4)


class ProcedureEnregistrerEntityLookupGuardTests(unittest.TestCase):
    def _load(self, get_infos_activite):
        return _extract_node(
            "Procedure_enregistrer",
            {"GetInfosActivite": get_infos_activite, "_": _underscore, "datetime": datetime},
            class_name="CTRL_Interface",
        )

    def _dict_action(self):
        return {
            "action_activite": "5", "action_unite": "10", "action_etat": "present",
            "action_demande": "0", "action_heure_debut": "defaut", "action_heure_fin": "defaut",
            "action_message": None, "action_vocal": "0", "action_ticket": None,
        }

    def _fake_self(self):
        fake_self = mock.MagicMock()
        fake_self.infosIndividus.RechercheIndividu.return_value = {"nom": "DUPOND", "prenom": "Jean"}
        return fake_self

    def test_missing_activite_aborts_this_badging_action_only(self):
        procedure = self._load(mock.MagicMock(return_value=None))
        fake_self = self._fake_self()

        resultat = procedure(fake_self, self._dict_action(), IDindividu=1, date=datetime.date(2024, 1, 1), heure="08:00")

        self.assertIs(resultat, False)
        fake_self.log.AjouterAction.assert_called_once_with(
            individu="DUPOND Jean", IDindividu=1,
            action="Enregistrement d'une consommation", resultat="Activité introuvable",
        )
        fake_self.RechercheInscription.assert_not_called()
        fake_self.ctrl_grille.SaisieConso.assert_not_called()

    def test_existing_activite_still_reaches_inscription_lookup_with_correct_data(self):
        infos_activite = (
            {"nom": "Multisport"},
            {10: {"nom": "Matin"}},
            [(10, 2)],
            {2: {"nom": "GroupeA"}},
        )
        procedure = self._load(mock.MagicMock(return_value=infos_activite))
        fake_self = self._fake_self()
        fake_self.RechercheInscription.return_value = (False, False)

        resultat = procedure(fake_self, self._dict_action(), IDindividu=1, date=datetime.date(2024, 1, 1), heure="08:00")

        self.assertIs(resultat, False)
        fake_self.RechercheInscription.assert_called_once_with(
            1, "DUPOND Jean", 5, {"nom": "Multisport"}, "Enregistrement d'une consommation 'Matin'"
        )
        for call in fake_self.log.AjouterAction.call_args_list:
            self.assertNotEqual(call.kwargs.get("resultat"), "Activité introuvable")


class ProcedureReserverEntityLookupGuardTests(unittest.TestCase):
    def _load(self, get_infos_activite):
        return _extract_node(
            "Procedure_reserver",
            {
                "GetInfosActivite": get_infos_activite,
                "_": _underscore,
                "ConvertStrToListe": lambda texte=None: (texte.split(";") if texte else []),
            },
            class_name="CTRL_Interface",
        )

    def _dict_action(self):
        return {
            "action_activite": "5", "action_unite": "10;11", "action_etat": "present",
            "action_attente": "0", "action_date": "date_actuelle", "action_question": None,
            "action_message": None, "action_vocal": "0",
        }

    def _fake_self(self):
        fake_self = mock.MagicMock()
        fake_self.infosIndividus.RechercheIndividu.return_value = {"nom": "DUPOND", "prenom": "Jean"}
        return fake_self

    def test_missing_activite_aborts_this_badging_action_only(self):
        procedure = self._load(mock.MagicMock(return_value=None))
        fake_self = self._fake_self()

        resultat = procedure(fake_self, self._dict_action(), IDindividu=1, date=datetime.date(2024, 1, 1), heure="08:00")

        self.assertIs(resultat, False)
        fake_self.log.AjouterAction.assert_called_once_with(
            individu="DUPOND Jean", IDindividu=1,
            action="Réservation de consommations", resultat="Activité introuvable",
        )
        fake_self.RechercheInscription.assert_not_called()
        fake_self.ctrl_grille.InitGrille.assert_not_called()

    def test_existing_activite_still_reaches_inscription_lookup_with_correct_data(self):
        infos_activite = (
            {"nom": "Multisport"},
            {10: {"nom": "Matin"}, 11: {"nom": "Soir"}},
            [(10, 2)],
            {2: {"nom": "GroupeA"}},
        )
        procedure = self._load(mock.MagicMock(return_value=infos_activite))
        fake_self = self._fake_self()
        fake_self.RechercheInscription.return_value = (False, False)

        resultat = procedure(fake_self, self._dict_action(), IDindividu=1, date=datetime.date(2024, 1, 1), heure="08:00")

        self.assertIs(resultat, False)
        fake_self.RechercheInscription.assert_called_once_with(
            1, "DUPOND Jean", 5, {"nom": "Multisport"}, "Réservation de consommations 'Multisport'"
        )
        for call in fake_self.log.AjouterAction.call_args_list:
            self.assertNotEqual(call.kwargs.get("resultat"), "Activité introuvable")


if __name__ == "__main__":
    unittest.main()
