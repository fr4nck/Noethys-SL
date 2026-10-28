# -*- coding: utf-8 -*-
"""Garde de l'interface de sauvegarde existante (référence : tag RC10)."""
import ast
import json
from pathlib import Path
import unittest

RACINE = Path(__file__).resolve().parents[1]


class InterfaceHistoriqueTests(unittest.TestCase):
    def test_libelles_traduits_identiques_a_rc10(self):
        reference = json.loads((RACINE / "tests/fixtures/backup_ui_rc10.json").read_text(encoding="utf-8"))
        for fichier, attendu in reference.items():
            arbre = ast.parse((RACINE / "noethys/Utils" / fichier).read_text(encoding="utf-8"))
            actuel = {n.args[0].value for n in ast.walk(arbre)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id == "_" and n.args and isinstance(n.args[0], ast.Constant)
                      and isinstance(n.args[0].value, str)}
            self.assertEqual(actuel, set(attendu), fichier)

    def test_pas_de_nouveau_parcours_de_dossier(self):
        texte = (RACINE / "noethys/Utils/UTILS_Sauvegarde_auto.py").read_text(encoding="utf-8")
        for ajout in ("ChoisirRepertoirePoste", "MemoriserRepertoirePoste", "sauvegarde_repertoires_poste"):
            self.assertNotIn(ajout, texte)

    def test_presentation_du_dialogue_de_progression_conservee(self):
        arbre = ast.parse((RACINE / "noethys/Utils/UTILS_Sauvegarde.py").read_text(encoding="utf-8"))
        fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "Sauvegarde")
        appel = next(n for n in ast.walk(fonction) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "ProgressDialog")
        style = next(k.value for k in appel.keywords if k.arg == "style")
        self.assertEqual({n.attr for n in ast.walk(style) if isinstance(n, ast.Attribute)},
                         {"PD_SMOOTH", "PD_AUTO_HIDE", "PD_APP_MODAL"})


if __name__ == "__main__":
    unittest.main()
