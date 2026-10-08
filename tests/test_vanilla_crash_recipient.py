# -*- coding: utf-8 -*-
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Rapport_bugs.py"


def _load_get_destinataire():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "GetDestinataireRapports"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"DESTINATAIRE_DEFAUT": "noethys@gmail.com"}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class CrashRecipientMigrationTests(unittest.TestCase):
    def test_explicit_empty_shared_value_restores_historical_default(self):
        namespace = _load_get_destinataire()
        namespace["_LireDestinataireBase"] = lambda: ("", True, True)
        namespace["_GetDestinataireLocal"] = lambda: self.fail("Le réglage local ne doit plus être relu")
        namespace["SetDestinataireRapports"] = lambda *args, **kwargs: self.fail("Aucune migration ne doit être tentée")

        self.assertEqual(namespace["GetDestinataireRapports"](), "noethys@gmail.com")

    def test_existing_shared_value_is_authoritative(self):
        namespace = _load_get_destinataire()
        namespace["_LireDestinataireBase"] = lambda: ("maintenance@example.org", True, True)
        namespace["_GetDestinataireLocal"] = lambda: self.fail("Le réglage local ne doit pas être relu")
        namespace["SetDestinataireRapports"] = lambda *args, **kwargs: self.fail("Aucune migration ne doit être tentée")

        self.assertEqual(namespace["GetDestinataireRapports"](), "maintenance@example.org")

    def test_legacy_local_value_seeds_database_only_when_row_is_absent(self):
        namespace = _load_get_destinataire()
        calls = []
        namespace["_LireDestinataireBase"] = lambda: ("", False, True)
        namespace["_GetDestinataireLocal"] = lambda: "legacy@example.org"
        namespace["SetDestinataireRapports"] = lambda adresse, silencieux=False: calls.append((adresse, silencieux)) or True

        self.assertEqual(namespace["GetDestinataireRapports"](), "legacy@example.org")
        self.assertEqual(calls, [("legacy@example.org", True)])

    def test_unavailable_database_keeps_legacy_local_value_without_writing(self):
        namespace = _load_get_destinataire()
        calls = []
        namespace["_LireDestinataireBase"] = lambda: ("", False, False)
        namespace["_GetDestinataireLocal"] = lambda: "legacy@example.org"
        namespace["SetDestinataireRapports"] = lambda *args, **kwargs: calls.append((args, kwargs)) or True

        self.assertEqual(namespace["GetDestinataireRapports"](), "legacy@example.org")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
