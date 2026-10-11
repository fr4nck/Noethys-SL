import ast
import os
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / (
    "noethys/Dlg/DLG_Synchronisation.py"
)

class QuarantineTests(unittest.TestCase):
    def test_previous_failure_is_preserved(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        node = next(
            x for x in tree.body
            if isinstance(x, ast.FunctionDef)
            and x.name == "MettreEnQuarantaine"
        )
        namespace = {
            "os": os,
            "EXTENSION_QUARANTAINE": ".echec",
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     str(SOURCE), "exec"), namespace)
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "actions_test.nsc"
            precedent = Path(str(original) + ".echec")
            precedent.write_bytes(b"premier")
            original.write_bytes(b"second")
            resultat = namespace["MettreEnQuarantaine"](str(original))
            self.assertEqual(precedent.read_bytes(), b"premier")
            self.assertEqual(Path(resultat).read_bytes(), b"second")
            self.assertNotEqual(resultat, str(precedent))
            self.assertFalse(original.exists())

if __name__ == "__main__":
    unittest.main()
