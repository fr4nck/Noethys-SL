"""Contrat du mode GetHTML sans importer wxPython."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


def charger_gethtml():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    methode = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "GetHTML"
    )
    module = ast.Module(body=[methode], type_ignores=[])
    ast.fix_missing_locations(module)
    espace = {}
    exec(compile(module, str(SOURCE), "exec"), espace)
    return espace["GetHTML"]


class StatistiquesGetHTMLModeTests(unittest.TestCase):
    def setUp(self):
        self.gethtml = charger_gethtml()
        self.modele = type("ModeleTest", (), {
            "dictParametres": {"listeActivites": []},
            "liste_objets": [],
        })()

    def test_mode_invalide_rejete_meme_sans_activite(self):
        with self.assertRaises(ValueError):
            self.gethtml(self.modele, mode="inconnu")

    def test_modes_valides_conservent_le_repli_sans_activite(self):
        for mode in ("affichage", "impression"):
            with self.subTest(mode=mode):
                self.assertEqual(self.gethtml(self.modele, mode=mode), "")


if __name__ == "__main__":
    unittest.main()
