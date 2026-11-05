# -*- coding: utf-8 -*-
"""RC10.5 S1 : SSH epingle optionnel, sans modification du Connecthys d'origine.

Aucune authentification, aucun serveur, aucun acces reseau : seul un client
Paramiko simule et des cles publiques entierement factices sont utilises.
"""
import base64
import hashlib
import hmac
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

import paramiko
from Utils import UTILS_Portail_securite as SEC


class ClePubliqueFictive:
    def __init__(self, donnees):
        self.donnees = donnees

    def asbytes(self):
        return self.donnees


def fingerprint(cle):
    return "SHA256:" + base64.b64encode(hashlib.sha256(cle.asbytes()).digest()).decode().rstrip("=")


class EmpreinteSSHTests(unittest.TestCase):
    def setUp(self):
        self.cle = ClePubliqueFictive(b"cle publique SSH de test - serveur historique")
        self.autre = ClePubliqueFictive(b"cle publique attaquant de test")
        self.attendue = fingerprint(self.cle)

    def test_format_canonique_sha256_open_ssh(self):
        self.assertEqual(SEC.EmpreinteCleSSH(self.cle), self.attendue)
        self.assertEqual(SEC.VerifierFormatEmpreinte(" " + self.attendue + " "), self.attendue)

    def test_format_invalide_refuse_sans_reseau(self):
        exemples = [None, 12, "", "abc", "MD5:123456", "SHA256:abc",
                    "SHA256:" + ("x" * 43) + "=", "SHA256:" + ("*" * 43),
                    "SHA256:" + ("A" * 44)]
        for brut in exemples:
            with self.subTest(valeur=str(brut)[:20]), self.assertRaises(SEC.EmpreinteSSHInvalide):
                SEC.VerifierFormatEmpreinte(brut)

    def test_empreinte_match_autorisee_sans_stockage(self):
        client = mock.Mock()
        politique = SEC.PolitiqueEmpreinteSSH(self.attendue)
        self.assertIsNone(politique.missing_host_key(client, "srv.invalid", self.cle))
        self.assertFalse(client.save_host_keys.called)
        self.assertFalse(client.get_host_keys.called)

    def test_cle_hote_substituee_refusee(self):
        politique = SEC.PolitiqueEmpreinteSSH(self.attendue)
        with self.assertRaisesRegex(paramiko.SSHException, "connexion refusee"):
            politique.missing_host_key(mock.Mock(), "srv.invalid", self.autre)

    def test_aucune_empreinte_conserve_la_politique_originale(self):
        for valeurs in ({}, {"ssh_host_key_sha256": ""}, {"ssh_host_key_sha256": "  "}):
            client = mock.Mock()
            self.assertFalse(SEC.ConfigurerPolitiqueSSH(client, valeurs))
            pol = client.set_missing_host_key_policy.call_args.args[0]
            self.assertIsInstance(pol, paramiko.AutoAddPolicy)

    def test_empreinte_configuree_active_verification_pre_auth(self):
        client = mock.Mock()
        self.assertTrue(SEC.ConfigurerPolitiqueSSH(
            client, {"ssh_host_key_sha256": self.attendue}))
        pol = client.set_missing_host_key_policy.call_args.args[0]
        self.assertIsInstance(pol, SEC.PolitiqueEmpreinteSSH)
        pol.missing_host_key(client, "srv.invalid", self.cle)
        with self.assertRaises(paramiko.SSHException):
            pol.missing_host_key(client, "srv.invalid", self.autre)
        client.load_host_keys.assert_not_called()
        client.load_system_host_keys.assert_not_called()


class IntegrationClientsSSHTests(unittest.TestCase):
    def setUp(self):
        self.cle = ClePubliqueFictive(b"cle serveur connu et verifie par un autre canal")
        self.autre = ClePubliqueFictive(b"cle serveur non autorisee")
        self.attendue = fingerprint(self.cle)
        self.parametres = {
            "hebergement_type": 2, "ssh_serveur": "srv.invalid",
            "ssh_port": "7655", "ssh_utilisateur": "compte-fictif",
            "ssh_mdp": "MOTDEPASSE_TEST_NE_PAS_JOURNALISER",
            "ssh_key_file": "", "ssh_repertoire": "www",
            "ssh_host_key_sha256": self.attendue,
        }

    def _connecter_simule(self, client, cle):
        def connect(*args, **kwargs):
            politique = client.set_missing_host_key_policy.call_args.args[0]
            # Equivaut au callback de Paramiko pendant l'echange des cles,
            # avant que connect() ait termine son authentification.
            politique.missing_host_key(client, "srv.invalid", cle)
        client.connect.side_effect = connect

    def test_client_synchronisation_epingle_et_deconnecte(self):
        from Utils import UTILS_Portail_synchro as U
        client = mock.MagicMock()
        self._connecter_simule(client, self.cle)
        log = SimpleNamespace(EcritLog=lambda *a: None, SetGauge=lambda *a: None)
        synchro = U.Synchro(dict_parametres=dict(self.parametres), log=log)
        with mock.patch.object(U.paramiko, "SSHClient", return_value=client):
            ftp, ssh = synchro.Connexion()
            self.assertIs(ssh, client)
            synchro.Deconnexion(ftp, ssh)
        client.open_sftp.assert_called_once()
        client.close.assert_called_once()

    def test_cle_etrangere_ne_peut_ouvrir_sftp_et_ferme_ssh(self):
        from Utils import UTILS_Portail_synchro as U
        client = mock.MagicMock()
        self._connecter_simule(client, self.autre)
        log = SimpleNamespace(EcritLog=lambda *a: None, SetGauge=lambda *a: None)
        synchro = U.Synchro(dict_parametres=dict(self.parametres), log=log)
        with mock.patch.object(U.paramiko, "SSHClient", return_value=client), \
             mock.patch.object(U, "print", create=True):
            self.assertFalse(synchro.Connexion())
        client.open_sftp.assert_not_called()
        client.close.assert_called_once()

    def test_outils_serveur_emploient_meme_epingle_et_fermeture(self):
        from Utils import UTILS_Portail_controle as U
        client = mock.MagicMock()
        self._connecter_simule(client, self.autre)
        controle = U.ServeurConnecthys.__new__(U.ServeurConnecthys)
        controle.dict_parametres = dict(self.parametres)
        erreurs = []
        controle.parent = SimpleNamespace(EcritLog=erreurs.append)
        with mock.patch.object(U.paramiko, "SSHClient", return_value=client), \
             mock.patch.object(U, "print", create=True):
            self.assertIsNone(controle.OpenSSHConnec())
        client.close.assert_called_once()
        self.assertNotIn("MOTDEPASSE_TEST_NE_PAS_JOURNALISER", str(erreurs))

    def test_interface_nouvelle_option_vide_par_defaut(self):
        from Dlg import DLG_Portail_config
        self.assertEqual(DLG_Portail_config.VALEURS_DEFAUT["ssh_host_key_sha256"], "")

    def test_journaux_ne_contiennent_plus_urls_jetons(self):
        src = (ROOT / "noethys" / "Utils" / "UTILS_Portail_synchro.py").read_text(encoding="utf-8")
        for libelle in ("syncup", "syncdown", "update", "upgrade", "repair"):
            self.assertNotIn('print("URL ' + libelle + ' =", url)', src)
            self.assertIn('print("URL ' + libelle + ' = [jeton masque]")', src)


if __name__ == "__main__":
    unittest.main()
