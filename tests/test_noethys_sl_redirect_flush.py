# -*- coding: utf-8 -*-
"""Non-regression du journal de l'executable Windows avec print(flush=True).

Extraire uniquement la classe Redirect : ne pas lancer l'interface,
ouvrir un profil reel ou connecter un serveur.
"""
import ast
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Noethys.py"


def charger_redirect():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    classes = [n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "Redirect"]
    if len(classes) != 1:
        raise AssertionError("Une seule classe Redirect attendue")
    fragment = ast.fix_missing_locations(ast.Module(body=classes, type_ignores=[]))
    contexte = {}
    exec(compile(fragment, str(SOURCE), "exec"), contexte)
    return contexte["Redirect"]


class JournalExécutableWindowsTests(unittest.TestCase):
    def test_print_flush_vrai_sur_deux_jalons_connecthys(self):
        Redirect = charger_redirect()
        with tempfile.TemporaryDirectory(prefix="noethys-redirect-") as dossier:
            journal = Path(dossier) / "journal-fictif.log"
            sortie = Redirect(str(journal))
            try:
                print("RECETTE_CONNECTHYS_COMMENCER nb=2", file=sortie, flush=True)
                print("RECETTE_CONNECTHYS_CONSTRUCT_DEBUT", file=sortie, flush=True)
                self.assertEqual(
                    journal.read_text(encoding="utf-8").splitlines(),
                    ["RECETTE_CONNECTHYS_COMMENCER nb=2",
                     "RECETTE_CONNECTHYS_CONSTRUCT_DEBUT"],
                )
            finally:
                sortie.filename.close()

    def test_flush_apres_fermeture_est_sans_effet(self):
        Redirect = charger_redirect()
        with tempfile.TemporaryDirectory(prefix="noethys-redirect-") as dossier:
            sortie = Redirect(str(Path(dossier) / "journal-fictif.log"))
            sortie.filename.close()
            sortie.flush()


if __name__ == "__main__":
    unittest.main()
