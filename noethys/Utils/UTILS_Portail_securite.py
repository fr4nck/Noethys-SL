# -*- coding: utf-8 -*-
"""Controles SSH purement cote client, compatibles avec Connecthys historique.

L'empreinte de la cle publique SSH est un parametre FACULTATIF configure par
l'administrateur apres verification independante aupres de l'hebergeur.
Aucun changement de protocole, de cle, de chiffrement ni de serveur.
"""
import base64
import hashlib
import hmac
import re

import paramiko


class EmpreinteSSHInvalide(ValueError):
    """Empreinte attendue absente, mal formee ou incorrecte."""


def EmpreinteCleSSH(cle_publique):
    """Format SHA256 OpenSSH, sans padding final."""
    digest = hashlib.sha256(cle_publique.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def VerifierFormatEmpreinte(empreinte):
    """N'accepter qu'une empreinte SHA256 complete et canonique."""
    if not isinstance(empreinte, str):
        raise EmpreinteSSHInvalide("Empreinte SSH attendue invalide")
    empreinte = empreinte.strip()
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", empreinte):
        raise EmpreinteSSHInvalide("Empreinte SSH attendue : format SHA256 invalide")
    try:
        valeurs = base64.b64decode(empreinte[7:] + "=", validate=True)
    except (ValueError, base64.binascii.Error):
        raise EmpreinteSSHInvalide("Empreinte SSH attendue : encodage invalide")
    if len(valeurs) != 32 or EmpreinteCleSSHBrute(valeurs) != empreinte:
        raise EmpreinteSSHInvalide("Empreinte SSH attendue : valeur non canonique")
    return empreinte


def EmpreinteCleSSHBrute(digest):
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class PolitiqueEmpreinteSSH(paramiko.MissingHostKeyPolicy):
    """Controle la cle hote AVANT l'authentification Paramiko.

    SSHClient tout neuf, sans appel a load_system_host_keys/load_host_keys :
    la politique est invoquee pour la cle presentee lors du handshake.
    Ne stocke jamais de cle et n'accepte jamais de substitution de cle.
    """

    def __init__(self, empreinte):
        self.attendue = VerifierFormatEmpreinte(empreinte)

    def missing_host_key(self, client, hostname, key):
        recue = EmpreinteCleSSH(key)
        if not hmac.compare_digest(recue, self.attendue):
            raise paramiko.SSHException(
                "Cle hote SSH differente de l'empreinte verifiee : connexion refusee")
        # Acceptation locale de la cle exacte, sans trust-on-first-use ni ecriture.


def ConfigurerPolitiqueSSH(client, parametres):
    """Connexion historique si aucun verrou n'a ete explicitement configure.

    Une empreinte invalide est refusee avant l'appel SSHClient.connect().
    Si presente, l'empreinte est verifiee pendant l'echange des cles hote.
    """
    attendue = parametres.get("ssh_host_key_sha256") or ""
    if not isinstance(attendue, str):
        raise EmpreinteSSHInvalide("Empreinte SSH attendue invalide")
    if not attendue.strip():
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return False
    client.set_missing_host_key_policy(PolitiqueEmpreinteSSH(attendue))
    return True


class ModuleConnecthysNonFiable(ValueError):
    """Le code du portail ne correspond pas au fichier confirme hors bande."""


def LireModeleVerifie(chemin, empreinte):
    """Retourne les octets EXACTS a executer si un SHA256 est configure.

    Sans empreinte, renvoie None et ne change pas le chargement historique.
    Le SHA256 doit etre releve depuis une source independante de l'echange :
    une somme fournie avec le fichier par le meme serveur non fiable ne
    prouve rien. Seul models.py est couvert, pas les imports relatifs.
    """
    if not isinstance(empreinte, str):
        raise ModuleConnecthysNonFiable("Empreinte du modele Connecthys invalide")
    attendue = empreinte.strip()
    if not attendue:
        return None
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", attendue):
        raise ModuleConnecthysNonFiable("SHA256 models.py attendu sur 64 caracteres hexadecimaux")
    with open(chemin, "rb") as contenu:
        octets = contenu.read()
    recue = hashlib.sha256(octets).hexdigest()
    if not hmac.compare_digest(recue, attendue.lower()):
        raise ModuleConnecthysNonFiable(
            "Le code models.py recu ne correspond pas a l'empreinte de confiance : execution refusee")
    return octets
