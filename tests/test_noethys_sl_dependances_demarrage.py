# -*- coding: utf-8 -*-
"""Démarrage du paquet Windows : python-dateutil 3.x interdit tant que
Chemins.py masque les modules standard.

Cause établie le 24/10/2026 par le diagnostic de démarrage du build RC9
(run 40059146221) : l'exécutable s'arrête à l'import, avant main(), sur
« module 'zoneinfo' has no attribute 'reset_tzpath' » levé par
dateutil/tz/_tzpath.py (python-dateutil 3.0.0, installé faute
d'épinglage ; le build RC8.1 utilisait 2.9.0.post0 et démarrait).
Chemins.py ajoute chaque sous-dossier du répertoire de l'exécutable en tête
de sys.path : le sous-paquet dateutil/zoneinfo y devient le module
« zoneinfo » et masque le module standard que dateutil 3 importe.

Le mécanisme est reproduit ici sur une disposition de fichiers synthétique
avec le vrai Chemins.py ; il ne remplace pas la recette du paquet réel.
"""
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def disposition_figee(dossier, dateutil3):
    """Répertoire d'exécutable fictif : Chemins.py et un paquet dateutil réduit."""
    app = Path(dossier) / "app"
    (app / "dateutil" / "zoneinfo").mkdir(parents=True)
    (app / "dateutil" / "tz").mkdir()
    (app / "Chemins.py").write_text((RACINE / "noethys" / "Chemins.py").read_text(encoding="utf-8"), encoding="utf-8")
    (app / "dateutil" / "__init__.py").write_text("", encoding="utf-8")
    (app / "dateutil" / "zoneinfo" / "__init__.py").write_text("def get_zonefile_instance():\n    return None\n",
                                                             encoding="utf-8")
    if dateutil3:
        # Comportement de python-dateutil 3.0 : dateutil.tz importe le zoneinfo standard.
        (app / "dateutil" / "tz" / "__init__.py").write_text("from . import _tzpath\n", encoding="utf-8")
        (app / "dateutil" / "tz" / "_tzpath.py").write_text("import zoneinfo\nzoneinfo.reset_tzpath\n", encoding="utf-8")
    else:
        (app / "dateutil" / "tz" / "__init__.py").write_text("", encoding="utf-8")
    return app


def importer_dans_disposition(app):
    code = textwrap.dedent("""
        import os, sys
        app = sys.argv[1]
        sys.path.insert(0, app)
        sys.frozen = True
        sys.executable = os.path.join(app, "Noethys.exe")
        import Chemins
        try:
            import dateutil.tz
        except AttributeError as erreur:
            import zoneinfo
            print("ECHEC", erreur, zoneinfo.__file__)
        else:
            print("OK")
    """)
    resultat = subprocess.run([sys.executable, "-I", "-c", code, str(app)], capture_output=True, text=True, timeout=60)
    return resultat.stdout.strip() + resultat.stderr


class DependancesDemarrageTests(unittest.TestCase):
    def test_python_dateutil_epingle_sur_la_version_du_build_rc81(self):
        lignes = [l.strip() for l in (RACINE / "requirements.txt").read_text(encoding="utf-8").splitlines()]
        dateutil = [l for l in lignes if re.match(r"^python-dateutil\b", l)]
        self.assertEqual(dateutil, ["python-dateutil==2.9.0.post0"])

    def test_mecanisme_masquage_de_zoneinfo_par_chemins(self):
        with tempfile.TemporaryDirectory() as dossier:
            sortie = importer_dans_disposition(disposition_figee(dossier, dateutil3=True))
        self.assertIn("ECHEC module 'zoneinfo' has no attribute 'reset_tzpath'", sortie)
        self.assertIn(os.path.join("dateutil", "zoneinfo", "__init__.py"), sortie)

    def test_disposition_dateutil_2_sans_import_de_zoneinfo(self):
        with tempfile.TemporaryDirectory() as dossier:
            self.assertEqual(importer_dans_disposition(disposition_figee(dossier, dateutil3=False)), "OK")


if __name__ == "__main__":
    unittest.main()
