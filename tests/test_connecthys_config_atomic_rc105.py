# -*- coding: utf-8 -*-
"""RC10.5 S1.4 : publication atomique SFTP de config.py (opt-in).

Serveur SFTP exclusivement simule en memoire : aucune connexion et aucun
contact avec le Connecthys historique ou la base de donnees PMSL.
"""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

try:
    from Utils import UTILS_Portail_securite as SEC
    from Utils import UTILS_Portail_synchro as U
    from Dlg import DLG_Portail_config as CFG
    IMPORT_OK = True
    IMPORT_ERROR = ""
except ImportError as erreur:
    IMPORT_OK = False
    IMPORT_ERROR = repr(erreur)


class _FichierEcriture:
    def __init__(self, serveur, chemin):
        self.serveur, self.chemin = serveur, chemin

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def write(self, octets):
        # On n'ecrit jamais une donnee secrete avant chmod 0600.
        if self.serveur.modes.get(self.chemin) != 0o600:
            raise AssertionError("Octet confidentiel ecrit avant chmod 0600")
        if self.serveur.couper_ecriture:
            self.serveur.fichiers[self.chemin] += octets[:3]
            raise OSError("transfert interrompu fictif")
        self.serveur.fichiers[self.chemin] += octets
        self.serveur.evenements.append(("write", self.chemin, len(octets)))


class FauxSFTP:
    """Subset Paramiko utilise par la fonction de transfert opt-in."""

    def __init__(self, ancienne=b"SECRET_CONFIG_ANCIEN", extension=True):
        self.fichiers = {"config.py": ancienne}
        self.modes = {"config.py": 0o644}
        self.evenements = []
        self.extension = extension
        self.couper_ecriture = False
        self.corrompre_lecture = False
        self.chemin = "/"

    def chdir(self, chemin):
        self.chemin = chemin
        self.evenements.append(("chdir", chemin))

    def open(self, chemin, mode="rb"):
        self.evenements.append(("open", chemin, mode))
        if mode == "wb":
            self.fichiers[chemin] = b""
            return _FichierEcriture(self, chemin)
        if mode == "rb":
            data = self.fichiers[chemin]
            if self.corrompre_lecture and chemin != "config.py":
                data = b"CORROMPU" + data
            return io.BytesIO(data)
        raise AssertionError("Mode de fichier inattendu : %s" % mode)

    def chmod(self, chemin, mode):
        if chemin not in self.fichiers:
            raise FileNotFoundError(chemin)
        self.modes[chemin] = mode
        self.evenements.append(("chmod", chemin, mode))

    def posix_rename(self, depart, arrivee):
        self.evenements.append(("posix_rename", depart, arrivee))
        if not self.extension:
            raise OSError("extension posix-rename absente")
        if depart not in self.fichiers:
            raise FileNotFoundError(depart)
        self.fichiers[arrivee] = self.fichiers.pop(depart)
        self.modes[arrivee] = self.modes.pop(depart)

    def remove(self, chemin):
        self.evenements.append(("remove", chemin))
        del self.fichiers[chemin]
        self.modes.pop(chemin, None)

    def put(self, local, remote):
        self.evenements.append(("put_legacy", remote))
        self.fichiers[remote] = Path(local).read_bytes()


class JournalFictif:
    def __init__(self):
        self.messages = []

    def EcritLog(self, message=""):
        self.messages.append(str(message))

    def SetGauge(self, value):
        return None


@unittest.skipUnless(IMPORT_OK, "wx/Paramiko indisponibles : %s" % IMPORT_ERROR)
class ConfigAtomiqueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sftp-atomic-")
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "config.py"
        self.contenu = b"SECRET_KEY=FAUX_ET_NE_DOIT_PAS_APPARAITRE_DANS_LES_LOGS"
        self.source.write_bytes(self.contenu)

    def _synchro(self, atomique=True, prive=False):
        p = CFG.VALEURS_DEFAUT.copy()
        p.update(hebergement_type=2, ssh_repertoire="www/connecthys",
                 ssh_config_atomique=atomique, ssh_config_prive=prive)
        return U.Synchro(dict_parametres=p, log=JournalFictif())

    def test_par_defaut_transfert_historique_inchange(self):
        self.assertFalse(CFG.VALEURS_DEFAUT["ssh_config_atomique"])
        sftp = FauxSFTP()
        s = self._synchro(atomique=False)
        self.assertTrue(s.UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source),
            repDest="application/data"))
        self.assertEqual(sftp.fichiers["config.py"], self.contenu)
        self.assertTrue(any(evt[0] == "put_legacy" for evt in sftp.evenements))
        self.assertFalse(any(evt[0] == "posix_rename" for evt in sftp.evenements))

    def test_mode_atomique_verifie_octets_et_renomme_une_seule_fois(self):
        sftp = FauxSFTP()
        s = self._synchro()
        self.assertTrue(s.UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source), repDest="application/data"))
        self.assertEqual(sftp.fichiers, {"config.py": self.contenu})
        self.assertEqual(sftp.modes["config.py"], 0o644)
        rename = [e for e in sftp.evenements if e[0] == "posix_rename"]
        self.assertEqual(len(rename), 1)
        self.assertEqual(rename[0][2], "config.py")
        self.assertFalse(any(e[0] == "put_legacy" for e in sftp.evenements))
        self.assertEqual(len([e for e in sftp.evenements if e[0] == "open" and e[2] == "rb"]), 1)

    def test_restriction_0600_est_conservee_lors_de_rename(self):
        sftp = FauxSFTP()
        self.assertTrue(self._synchro(prive=True).UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source), repDest="application/data"))
        self.assertEqual(sftp.modes["config.py"], 0o600)

    def test_serveur_sans_extension_refuse_avec_ancien_intact(self):
        sftp = FauxSFTP(extension=False)
        s = self._synchro()
        self.assertFalse(s.UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source), repDest="application/data"))
        self.assertEqual(sftp.fichiers, {"config.py": b"SECRET_CONFIG_ANCIEN"})
        self.assertEqual(sftp.modes["config.py"], 0o644)
        self.assertNotIn(self.contenu.decode(), " ".join(s.log.messages))

    def test_coupure_pendant_envoi_conserve_config_ancien(self):
        sftp = FauxSFTP()
        sftp.couper_ecriture = True
        self.assertFalse(self._synchro().UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source), repDest="application/data"))
        self.assertEqual(sftp.fichiers, {"config.py": b"SECRET_CONFIG_ANCIEN"})
        self.assertFalse(any(e[0] == "posix_rename" for e in sftp.evenements))

    def test_corruption_detectee_avant_remplacement(self):
        sftp = FauxSFTP()
        sftp.corrompre_lecture = True
        self.assertFalse(self._synchro().UploadFichier(
            ftp=sftp, nomFichierComplet=str(self.source), repDest="application/data"))
        self.assertEqual(sftp.fichiers, {"config.py": b"SECRET_CONFIG_ANCIEN"})
        self.assertFalse(any(e[0] == "posix_rename" for e in sftp.evenements))

    def test_option_ne_concerne_que_config_application_data(self):
        for fichier, repertoire in (("models.py", "application/data"),
                                    ("config.py", "application")):
            with self.subTest(fichier=fichier, rep=repertoire):
                sftp = FauxSFTP()
                f = Path(self.tmp.name) / fichier
                f.write_bytes(b"CONTENU_FACTICE")
                self.assertTrue(self._synchro().UploadFichier(
                    ftp=sftp, nomFichierComplet=str(f), repDest=repertoire))
                self.assertTrue(any(e[0] == "put_legacy" for e in sftp.evenements))
                self.assertFalse(any(e[0] == "posix_rename" for e in sftp.evenements))


if __name__ == "__main__":
    unittest.main()
