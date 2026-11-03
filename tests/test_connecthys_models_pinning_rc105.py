# -*- coding: utf-8 -*-
"""S1 RC10.5 : ne jamais executer un models.py different du SHA256 configure.

Banc local et synthetique, aucune connexion, aucune vraie configuration.
Le mode sans empreinte est volontairement celui du Connecthys d'Ivan Lucas.
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

try:
    from Utils import UTILS_Portail_synchro as U
    from Utils import UTILS_Portail_securite as SEC
    from Dlg import DLG_Portail_config
    IMPORT_OK = True
except ImportError:
    IMPORT_OK = False


@unittest.skipUnless(IMPORT_OK, "Dependencies wx/Paramiko/SQLAlchemy requises")
class ModelesSSHCompatTests(unittest.TestCase):
    def setUp(self):
        self.rep = tempfile.TemporaryDirectory(prefix="connecthys-model-test-")
        self.addCleanup(self.rep.cleanup)
        self.chemin = Path(self.rep.name)
        self.fichier = self.chemin / "models.py"

    def _synchro(self, empreinte=""):
        class FauxJournal:
            def EcritLog(self, *args):
                pass

            def SetGauge(self, *args):
                pass

        return U.Synchro(dict_parametres={
            "models_sha256": empreinte, "accept_all_cert": False,
            "hebergement_type": 0,
        }, log=FauxJournal())

    def _modele(self, code):
        octets = code.encode("utf-8")
        self.fichier.write_bytes(octets)
        return hashlib.sha256(octets).hexdigest()

    def test_mode_historique_sans_empreinte_et_import_relatif(self):
        self._modele("from . import autre_modele\nVALEUR = autre_modele.VALEUR\n")
        (self.chemin / "autre_modele.py").write_text("VALEUR = 123\n", encoding="utf-8")
        modele = self._synchro().ChargeModuleModels(str(self.chemin), "models.py")
        self.assertEqual(modele.VALEUR, 123)
        self.assertFalse(any(k.startswith("noethys_connecthys_sync_") for k in sys.modules))

    def test_code_verifie_est_execute_sans_relecture(self):
        empreinte = self._modele("VALEUR = 'modele historique verifie'\n")
        original = U.importlib.machinery.SourceFileLoader.get_source
        with mock.patch.object(U.importlib.machinery.SourceFileLoader, "get_source",
                               side_effect=AssertionError("seconde lecture interdite")):
            modele = self._synchro(empreinte.upper()).ChargeModuleModels(
                str(self.chemin), "models.py")
        self.assertEqual(modele.VALEUR, "modele historique verifie")
        self.assertIsNotNone(original)

    def test_code_modifie_refuse_avant_execution(self):
        marqueur = self.chemin / "execution-interdite.txt"
        attendu = self._modele("VALEUR = 'attendue'\n")
        self._modele("from pathlib import Path\nPath(%r).write_text('execute')\n" % str(marqueur))
        with self.assertRaisesRegex(SEC.ModuleConnecthysNonFiable, "execution refusee"):
            self._synchro(attendu).ChargeModuleModels(str(self.chemin), "models.py")
        self.assertFalse(marqueur.exists())
        self.assertFalse(any(k.startswith("noethys_connecthys_sync_") for k in sys.modules))

    def test_sha256_invalide_refuse_avant_execution(self):
        marqueur = self.chemin / "execution-interdite.txt"
        self._modele("from pathlib import Path\nPath(%r).write_text('execute')\n" % str(marqueur))
        for invalide in ("interdit", "0" * 63, "X" * 64, None, False):
            with self.subTest(invalide=str(invalide)):
                with self.assertRaises(SEC.ModuleConnecthysNonFiable):
                    self._synchro(invalide).ChargeModuleModels(str(self.chemin), "models.py")
                self.assertFalse(marqueur.exists())

    def test_chargement_sans_pin_ne_change_pas_le_modele(self):
        self._modele("VALEUR = 'original'\n")
        self.assertEqual(self._synchro("").ChargeModuleModels(
            str(self.chemin), "models.py").VALEUR, "original")

    def test_modules_annexes_ne_sont_pas_couverts_par_le_pin(self):
        # Important : le SHA256 du seul models.py ne verrouille pas ses
        # imports relatifs. Cette limite devra etre mentionnee dans la RC.
        pin = self._modele("from . import annexe\nVALEUR = annexe.VALEUR\n")
        annexe = self.chemin / "annexe.py"
        annexe.write_text("VALEUR = 'v1'\n", encoding="utf-8")
        v1 = self._synchro(pin).ChargeModuleModels(str(self.chemin), "models.py")
        self.assertEqual(v1.VALEUR, "v1")
        annexe.write_text("VALEUR = 'v2'\n", encoding="utf-8")
        v2 = self._synchro(pin).ChargeModuleModels(str(self.chemin), "models.py")
        self.assertEqual(v2.VALEUR, "v2")

    def test_option_desactivee_par_defaut(self):
        self.assertEqual(DLG_Portail_config.VALEURS_DEFAUT.get("models_sha256"), "")


if __name__ == "__main__":
    unittest.main()
