# -*- coding: utf-8 -*-
"""Chemins portables et protection de la migration de configuration.

Repris de fix/windows-installable-config (31e6d85c) : le correctif est dans main
depuis #160, sans test dedie. Aucun profil reel : chemins et appdirs simules.
"""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


def _load_utils_files(root, config_root=None):
    root = Path(root)
    config_root = Path(config_root) if config_root is not None else root / "outside-user-config"
    (root / "outside-site-data").mkdir(parents=True, exist_ok=True)
    (root / "outside-user-data").mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)

    # Faux modules limites au chargement : sys.modules est restaure ensuite pour
    # ne pas casser les tests suivants du meme processus (vrais six/Utils).
    with mock.patch.dict(sys.modules):
        chemins = types.ModuleType("Chemins")
        chemins.GetMainPath = lambda fichier="": str(root / fichier)
        chemins.GetStaticPath = lambda fichier="": str(root / "Static" / fichier)
        sys.modules["Chemins"] = chemins

        utils_pkg = types.ModuleType("Utils")
        utils_pkg.__path__ = []
        sys.modules["Utils"] = utils_pkg

        customize = types.ModuleType("Utils.UTILS_Customize")
        customize.GetValeur = lambda *args, **kwargs: ""
        sys.modules["Utils.UTILS_Customize"] = customize
        utils_pkg.UTILS_Customize = customize

        appdirs = types.ModuleType("appdirs")
        appdirs.site_data_dir = lambda **kwargs: str(root / "outside-site-data")
        appdirs.user_data_dir = lambda **kwargs: str(root / "outside-user-data")
        appdirs.user_config_dir = lambda **kwargs: str(config_root)
        sys.modules["appdirs"] = appdirs

        six = types.ModuleType("six")
        six.PY2 = False
        six.PY3 = True
        sys.modules["six"] = six

        path = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Fichiers.py"
        spec = importlib.util.spec_from_file_location("noe041_utils_fichiers", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class PortablePathsTests(unittest.TestCase):
    def test_portable_marker_isolates_config_and_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            portable = root / "Portable"
            portable.mkdir()
            module = _load_utils_files(root)

            self.assertEqual(Path(module.GetRepUtilisateur("Config.json")), portable / "Config.json")
            self.assertEqual(Path(module.GetRepData("demo_DATA.dat")), portable / "Data" / "demo_DATA.dat")
            self.assertTrue((portable / "Data").is_dir())

    def test_portable_runtime_subdirectories_are_created_on_demand(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            portable = root / "Portable"
            portable.mkdir()
            module = _load_utils_files(root)

            expected = {
                "Temp": module.GetRepTemp("journal.tmp"),
                "Updates": module.GetRepUpdates("update.bin"),
                "Lang": module.GetRepLang("fr.xlang"),
                "Sync": module.GetRepSync("sync.json"),
                "Extensions": module.GetRepExtensions("plugin.py"),
            }
            for dirname, path in expected.items():
                parent = Path(path).parent
                if dirname == "Temp":
                    # main isole les temporaires par processus (#175) : Temp/<pid>.
                    self.assertEqual(parent, portable / "Temp" / str(os.getpid()))
                    self.assertTrue(parent.is_dir())
                else:
                    # main cree Updates/Lang/Sync/Extensions au demarrage (Noethys.main()),
                    # pas a la demande : seul l'emplacement est verifie ici.
                    self.assertEqual(parent, portable / dirname)

    def test_portable_mode_does_not_use_appdirs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Portable").mkdir()
            module = _load_utils_files(root)

            config = Path(module.GetRepUtilisateur("Config.json"))
            data = Path(module.GetRepData("demo.dat"))
            self.assertNotIn("outside-", str(config))
            self.assertNotIn("outside-", str(data))


    def test_real_config_is_written_and_reloaded_inside_portable(self):
        """Exercise the production JSON writer, not an artificial smoke file."""
        from Utils import UTILS_Config
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            portable = root / "Portable"
            portable.mkdir()
            user_profile = root / "outside-user-config"
            module = _load_utils_files(root, config_root=user_profile)

            with mock.patch.object(UTILS_Config.UTILS_Fichiers, "GetRepUtilisateur",
                                   side_effect=module.GetRepUtilisateur):
                writer = UTILS_Config.FichierConfig()
                writer.SetItemConfig("test_preference_portable", 42)
                config_path = portable / "Config.json"
                self.assertEqual(Path(writer.nomFichier), config_path)
                self.assertTrue(config_path.is_file())
                self.assertEqual(UTILS_Config.FichierConfig().GetItemConfig(
                    "test_preference_portable"), 42)

                # A new FichierConfig instance acts like a second launch.
                restarted = UTILS_Config.FichierConfig()
                self.assertEqual(restarted.GetItemConfig("test_preference_portable"), 42)

            self.assertFalse((user_profile / "noethys").exists())



class InstallableConfigPathsTests(unittest.TestCase):
    def test_config_path_is_independent_from_process_working_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile-roaming"
            module = _load_utils_files(root, config_root=profile)
            cwd_a = root / "cwd-a"
            cwd_b = root / "cwd-b"
            cwd_a.mkdir()
            cwd_b.mkdir()

            previous = Path.cwd()
            try:
                os.chdir(str(cwd_a))
                path_a = Path(module.GetRepUtilisateur("Config.json"))
                os.chdir(str(cwd_b))
                path_b = Path(module.GetRepUtilisateur("Config.json"))
            finally:
                os.chdir(str(previous))

            expected = profile / "noethys" / "Config.json"
            self.assertEqual(path_a, expected)
            self.assertEqual(path_b, expected)

    def test_migration_does_not_read_config_from_current_working_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile-roaming"
            module = _load_utils_files(root, config_root=profile)
            cwd = root / "foreign-working-directory"
            cwd.mkdir()
            foreign_config = cwd / "Config.json"
            foreign_config.write_text('{"source":"foreign"}', encoding="utf-8")
            home = root / "home"
            home.mkdir()

            previous = Path.cwd()
            try:
                os.chdir(str(cwd))
                with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                    module.DeplaceFichiers()
            finally:
                os.chdir(str(previous))

            self.assertEqual(foreign_config.read_text(encoding="utf-8"), '{"source":"foreign"}')
            self.assertFalse((profile / "noethys" / "Config.json").exists())

    def test_migration_never_overwrites_existing_user_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile-roaming"
            module = _load_utils_files(root, config_root=profile)
            legacy_config = root / "Config.json"
            legacy_config.write_text('{"source":"legacy"}', encoding="utf-8")
            active_config = Path(module.GetRepUtilisateur("Config.json"))
            active_config.write_text('{"source":"active"}', encoding="utf-8")
            home = root / "home"
            home.mkdir()

            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                module.DeplaceFichiers()

            self.assertEqual(active_config.read_text(encoding="utf-8"), '{"source":"active"}')
            self.assertEqual(legacy_config.read_text(encoding="utf-8"), '{"source":"legacy"}')

    def test_migration_moves_application_config_and_backup_when_destination_is_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile-roaming"
            module = _load_utils_files(root, config_root=profile)
            legacy_config = root / "Config.json"
            legacy_backup = root / "Config.json.bak"
            legacy_config.write_text('{"source":"legacy"}', encoding="utf-8")
            legacy_backup.write_text('{"source":"backup"}', encoding="utf-8")
            home = root / "home"
            home.mkdir()

            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                module.DeplaceFichiers()

            active_config = profile / "noethys" / "Config.json"
            active_backup = profile / "noethys" / "Config.json.bak"
            self.assertEqual(active_config.read_text(encoding="utf-8"), '{"source":"legacy"}')
            self.assertEqual(active_backup.read_text(encoding="utf-8"), '{"source":"backup"}')
            self.assertFalse(legacy_config.exists())
            self.assertFalse(legacy_backup.exists())


if __name__ == "__main__":
    unittest.main()
