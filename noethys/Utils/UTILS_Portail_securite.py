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
import secrets

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
    prouve rien. En mode epingle, les imports relatifs annexes sont refuses.
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


class PublicationConfigSFTPEchouee(IOError):
    """Le transfert fiable n'a pas ete confirme : etat distant a verifier."""


def PublierConfigAtomiqueSFTP(sftp, source, mode=0o644):
    """Publier le config.py du Connecthys original par extension posix-rename.

    Appelant : SFTP est deja dans `application/data`. Active UNIQUEMENT
    sur option volontaire. Aucun fallback vers un ecrasement non atomique :
    si l'hebergeur ne supporte pas l'extension OpenSSH `posix-rename`,
    le fichier existant reste intact et une erreur est remontee.

    La copie temporaire est mode 0600 AVANT le premier octet secret et
    son contenu est relu sur le serveur pour comparer le SHA256 aux octets
    source. L'extension posix-rename remplace ensuite config.py d'un seul
    coup. Tous les noms et le format definitif demeurent ceux de Connecthys d'origine.
    """
    if mode not in (0o600, 0o644):
        raise ValueError("Mode SFTP config.py interdit")
    if not callable(getattr(sftp, "posix_rename", None)):
        raise PublicationConfigSFTPEchouee("Renommage SFTP atomique indisponible")
    temporaire = ".config.py.noethys-sl-%s.tmp" % secrets.token_hex(16)
    remplace = False
    try:
        local_sha256 = hashlib.sha256()
        taille_locale = 0

        # Le chemin temporaire est aleatoire. Il ne doit jamais correspondre
        # au nom final ; la creation ne doit pas toucher l'ancien config.py.
        with open(source, "rb") as local:
            with sftp.open(temporaire, "wb") as destination:
                sftp.chmod(temporaire, 0o600)
                while True:
                    bloc = local.read(65536)
                    if not bloc:
                        break
                    destination.write(bloc)
                    local_sha256.update(bloc)
                    taille_locale += len(bloc)

        # Verifier le contenu recu AVANT toute promotion. Ne pas faire
        # confiance au code retour de put() ou a une simple taille.
        distant_sha256 = hashlib.sha256()
        taille_distante = 0
        with sftp.open(temporaire, "rb") as distant:
            while True:
                bloc = distant.read(65536)
                if not bloc:
                    break
                distant_sha256.update(bloc)
                taille_distante += len(bloc)
                if taille_distante > taille_locale:
                    raise PublicationConfigSFTPEchouee("Config SFTP plus volumineuse que l'originale")
        if (taille_distante != taille_locale or
                not hmac.compare_digest(distant_sha256.digest(),
                                        local_sha256.digest())):
            raise PublicationConfigSFTPEchouee("Configuration SFTP recue non identique")

        # 0644 par defaut pour le processus web historique ; 0600 seulement
        # si son utilisateur a ete valide et l'option specifique activee.
        sftp.chmod(temporaire, mode)
        sftp.posix_rename(temporaire, "config.py")
        remplace = True
        return True
    finally:
        if not remplace:
            try:
                sftp.remove(temporaire)
            except (OSError, IOError):
                # La purge peut echouer si le serveur vient de se couper.
                # Le nom reste aleatoire et le fichier etait cree en 0600 ;
                # l'appelant doit signaler l'echec, jamais un succes.
                pass


class RefuserModulesRelatifsNonVerifies:
    """Import hook limite au package ephemere de models.py (mode epingle).

    Un models.py verifie par SHA256 ne doit pas charger des annexes Python
    non signees au moyen d'imports relatifs. Les imports absolus stdlib/
    SQLAlchemy/Connecthys restent inchanges. C'est une restriction des
    imports, PAS un sandbox : une source principale deja malveillante peut
    appeler directement open(), exec(), etc. En mode legacy, aucun hook.
    """

    def __init__(self, nom_package, nom_module):
        self.prefixe = nom_package + "."
        self.module_principal = nom_module

    def find_spec(self, fullname, path=None, target=None):
        if (fullname.startswith(self.prefixe)
                and fullname != self.module_principal):
            raise ModuleConnecthysNonFiable(
                "Import relatif Python non verifie refuse en mode models_sha256")
        return None
