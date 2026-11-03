# -*- coding: utf-8 -*-
"""RC10.5 S1.3 : proteger config.py sans changer le protocole Connecthys.

Fichiers temporaires et clients SFTP factices. Aucun acces au portail ni a
la base PMSL. L'option 0600 distante reste OFF par defaut.
"""
import contextlib
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

try:
    from Utils import UTILS_Portail_synchro as U
    from Dlg import DLG_Portail_config as CFG
    IMPORT_OK = True
    IMPORT_ERROR = ""
except ImportError as err:
    IMPORT_OK = False
    IMPORT_ERROR = repr(err)


class Journal:
    def __init__(self):
        self.messages = []

    def EcritLog(self, message=""):
        self.messages.append(str(message))

    def SetGauge(self, value):
        pass


@unittest.skipUnless(IMPORT_OK, "wx/Paramiko non disponibles : %s" % IMPORT_ERROR)
class SftpDroitsTests(unittest.TestCase):
    def _synchro(self, prive=False):
        p = copy.deepcopy(CFG.VALEURS_DEFAUT)
        p.update(hebergement_type=2, ssh_repertoire="www/connecthys",
                 ssh_config_prive=prive)
        log = Journal()
        return U.Synchro(dict_parametres=p, log=log), log

    def _upload(self, filename, prive=False, chmod_error=False):
        s, log = self._synchro(prive)
        sftp = mock.MagicMock()
        if chmod_error:
            sftp.chmod.side_effect = OSError("permission refusee fictive")
        with tempfile.TemporaryDirectory(prefix="sftp-fictif-") as d:
            f = os.path.join(d, filename)
            with open(f, "wb") as fichier:
                fichier.write(b"contenu purement fictif")
            with contextlib.redirect_stdout(io.StringIO()):
                ok = s.UploadFichier(
                    ftp=sftp, nomFichierComplet=f, repDest="application/data")
        return ok, sftp, log

    def test_mode_historique_config_reste_0644(self):
        self.assertFalse(CFG.VALEURS_DEFAUT["ssh_config_prive"])
        ok, ftp, _ = self._upload("config.py", prive=False)
        self.assertTrue(ok)
        ftp.chmod.assert_called_once_with(
            "/www/connecthys/application/data/config.py", mode=0o644)

    def test_config_privee_seule_recoit_0600(self):
        ok, ftp, _ = self._upload("config.py", prive=True)
        self.assertTrue(ok)
        ftp.chmod.assert_called_once_with(
            "/www/connecthys/application/data/config.py", mode=0o600)
        ok, ftp, _ = self._upload("models.py", prive=True)
        self.assertTrue(ok)
        ftp.chmod.assert_called_once_with(
            "/www/connecthys/application/data/models.py", mode=0o644)

    def test_echec_chmod_prive_refuse_faux_succes(self):
        ok, ftp, log = self._upload("config.py", prive=True, chmod_error=True)
        self.assertFalse(ok)
        ftp.put.assert_called_once()
        self.assertTrue(any("Droits prives" in t for t in log.messages))

    def test_echec_chmod_mode_historique_comportement_conserve(self):
        ok, ftp, _ = self._upload("config.py", prive=False, chmod_error=True)
        self.assertTrue(ok)
        ftp.chmod.assert_called_once()

    def test_absence_du_transport_refuse_au_lieu_de_reussir(self):
        s, log = self._synchro(prive=False)
        self.assertFalse(s.UploadFichier(
            ftp=None, nomFichierComplet="fichier-fictif", repDest="application/data"))
        self.assertTrue(any("Aucun transport" in t for t in log.messages))


@unittest.skipUnless(IMPORT_OK, "wx/Paramiko non disponibles : %s" % IMPORT_ERROR)
class ConfigTemporaireTests(unittest.TestCase):
    def _contexte(self, prive=False, serveur_type=0):
        p = copy.deepcopy(CFG.VALEURS_DEFAUT)
        p.update(hebergement_type=2, ssh_repertoire="www/connecthys",
                 ssh_config_prive=prive, serveur_type=serveur_type,
                 email_type_adresse=0)
        return U.Synchro(dict_parametres=p, log=Journal())

    def test_config_generee_est_privee_et_supprimee_apres_succes(self):
        s = self._contexte()
        with tempfile.TemporaryDirectory(prefix="config-fictif-") as tmp:
            trace = []
            def memoriser(ftp=None, nomFichierComplet="", repDest=""):
                self.assertEqual(repDest, "application/data")
                contenu = Path(nomFichierComplet).read_text(encoding="utf8")
                self.assertIn("SECRET_KEY", contenu)
                mode = os.stat(nomFichierComplet).st_mode & 0o777
                trace.append(mode)
                return True
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier", return_value=False), \
                 mock.patch.object(s, "UploadFichier", side_effect=memoriser):
                self.assertTrue(s.Upload_config(ftp=mock.MagicMock()))
            self.assertEqual(len(trace), 1)
            if os.name != "nt":
                self.assertEqual(trace[0], 0o600)
            self.assertFalse(Path(tmp, "config.py").exists())
            self.assertEqual(os.listdir(tmp), [])

    def test_echec_transfert_retourne_false_et_efface_config(self):
        s = self._contexte()
        with tempfile.TemporaryDirectory(prefix="config-fictif-") as tmp:
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier", return_value=False), \
                 mock.patch.object(s, "UploadFichier", return_value=False), \
                 mock.patch.object(s, "AutoReloadWSGI") as reload:
                self.assertFalse(s.Upload_config(ftp=mock.MagicMock()))
            reload.assert_not_called()
            self.assertEqual(os.listdir(tmp), [])

    def test_wgsi_reload_refuse_retourne_false_et_efface_config(self):
        s = self._contexte(serveur_type=2)
        with tempfile.TemporaryDirectory(prefix="config-fictif-") as tmp:
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier", return_value=False), \
                 mock.patch.object(s, "UploadFichier", return_value=True), \
                 mock.patch.object(s, "AutoReloadWSGI", return_value=False) as reload:
                self.assertFalse(s.Upload_config(ftp=mock.MagicMock()))
            reload.assert_called_once()
            self.assertEqual(os.listdir(tmp), [])

    def test_auto_reload_wsgi_propage_echec_de_l_envoi(self):
        s = self._contexte(serveur_type=2)
        with tempfile.TemporaryDirectory(prefix="wsgi-fictif-") as tmp:
            Path(tmp, "wsgi-original").write_text(
                "# Connecthys WSGI fictif\n# lastupdate = ancienne valeur\n",
                encoding="utf8")
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier",
                                   return_value=(tmp, "wsgi-original")), \
                 mock.patch.object(s, "UploadFichier", return_value=False) as upload:
                self.assertFalse(s.AutoReloadWSGI(ftp=mock.MagicMock()))
            upload.assert_called_once()
            self.assertTrue(any("Rechargement WSGI non envoye" in t
                                for t in s.log.messages))

    def test_auto_reload_wsgi_confirme_le_transfert(self):
        s = self._contexte(serveur_type=2)
        with tempfile.TemporaryDirectory(prefix="wsgi-fictif-") as tmp:
            Path(tmp, "wsgi-original").write_text(
                "# Connecthys WSGI fictif\n# lastupdate = ancienne valeur\n",
                encoding="utf8")
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier",
                                   return_value=(tmp, "wsgi-original")), \
                 mock.patch.object(s, "UploadFichier", return_value=True) as upload:
                self.assertTrue(s.AutoReloadWSGI(ftp=mock.MagicMock()))
            upload.assert_called_once()

    def test_config_inchangee_mode_prive_applique_droits_et_supprime_les_copies(self):
        s = self._contexte(prive=True)
        ftp = mock.MagicMock()
        with tempfile.TemporaryDirectory(prefix="config-fictif-") as tmp:
            contenu = []
            def capturer(ftp=None, nomFichierComplet="", repDest=""):
                contenu.append(Path(nomFichierComplet).read_text(encoding="utf8"))
                return True
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier", return_value=False), \
                 mock.patch.object(s, "UploadFichier", side_effect=capturer):
                self.assertTrue(s.Upload_config(ftp=ftp))
            self.assertEqual(len(contenu), 1)
            distant = Path(tmp, "copie-distante.py")
            distant.write_text(contenu[0], encoding="utf8")
            with mock.patch.object(U.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(tmp, fichier)), \
                 mock.patch.object(s, "TelechargeFichier",
                                   return_value=(tmp, "copie-distante.py")), \
                 mock.patch.object(s, "UploadFichier") as upload:
                self.assertTrue(s.Upload_config(ftp=ftp))
            upload.assert_not_called()
            ftp.chmod.assert_called_once_with(
                "/www/connecthys/application/data/config.py", mode=0o600)
            self.assertFalse(distant.exists())
            self.assertFalse(Path(tmp, "config.py").exists())


if __name__ == "__main__":
    unittest.main()
