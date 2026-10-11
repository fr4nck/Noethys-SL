#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import types
import unittest
from pathlib import Path


SOURCE = Path("noethys/Ol/OL_Etiquettes.py")


def load_get_liste_familles(listeFamilles, titulaires):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonction = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "GetListeFamilles"
    )
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)

    class FakeDB:
        def ExecuterReq(self, req):
            return True

        def ResultatReq(self):
            return listeFamilles

        def Close(self):
            return None

    def fake_track_famille(listview, donnees, infosIndividus):
        return donnees

    namespace = {
        "GestionDB": types.SimpleNamespace(DB=FakeDB),
        "FonctionsPerso": types.SimpleNamespace(GetIDfichier=lambda: 1),
        "UTILS_Titulaires": types.SimpleNamespace(GetTitulaires=lambda: titulaires),
        "TrackFamille": fake_track_famille,
        "datetime": __import__("datetime"),
        "_": lambda texte: texte,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["GetListeFamilles"]


class EtiquettesListeFamillesContractTests(unittest.TestCase):
    def test_famille_avec_titulaire_utilise_son_secteur(self):
        fonction = load_get_liste_familles(
            listeFamilles=[(10, "Regime", "Caisse", "123", None, None)],
            titulaires={
                10: {
                    "titulairesSansCivilite": "Dupont",
                    "adresse": {"rue": "Rue A", "cp": "75000", "ville": "Paris", "nomSecteur": "Nord"},
                    "listeMails": [],
                }
            },
        )

        resultat = fonction()

        self.assertEqual(resultat[0]["secteur"], "Nord")

    def test_famille_sans_titulaire_ne_leve_pas_unboundlocalerror(self):
        # Famille présente dans la requête mais absente du dictionnaire des titulaires
        # (ex : famille sans rattachement de titulaire connu).
        fonction = load_get_liste_familles(
            listeFamilles=[(20, "Regime", "Caisse", "456", None, None)],
            titulaires={},
        )

        resultat = fonction()

        self.assertEqual(resultat[0]["secteur"], "")
        self.assertEqual(resultat[0]["titulaires"], "Aucun titulaire")


if __name__ == "__main__":
    unittest.main()
