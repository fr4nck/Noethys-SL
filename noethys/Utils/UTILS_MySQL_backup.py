# -*- coding: utf-8 -*-
"""Contrat d'export complet, sans wx, profil utilisateur ni connexion SQL."""
import re
import shlex
import base64
import os
import subprocess
import tempfile
import time
import json
import zipfile


def OptionsDump(options=""):
    """Les options personnelles ne peuvent ni filtrer les données ni changer de cible.

    Conserver les options de compatibilité et de transport usuelles. Refuser les
    autres AVANT le lancement, au lieu de produire une sauvegarde incomplète.
    """
    autorisees = {
        "--default-character-set", "--set-gtid-purged", "--no-tablespaces",
        "--column-statistics", "--tz-utc", "--skip-tz-utc", "--compress",
        "--routines", "--events", "--skip-extended-insert",
        "--ssl-mode", "--ssl-ca", "--ssl-capath", "--ssl-cert", "--ssl-key",
        "--ssl-cipher", "--tls-version",
    }
    resultat = shlex.split(options or "")
    for option in resultat:
        if option.split("=", 1)[0] not in autorisees:
            # Ne jamais recopier une option arbitraire : elle peut être un secret.
            nom = option.split("=", 1)[0]
            nom = nom if re.fullmatch(r"--[A-Za-z-]+", nom) else "(argument)"
            raise ValueError("Option de sauvegarde non autorisée %s ; utiliser uniquement "
                             "les options de compatibilité/transport documentées "
                             "avec leur valeur sous la forme --option=valeur." % nom)
    # Options finales : aucun --opt/--skip-opt personnalisé ne peut les annuler.
    return resultat + [
        "--single-transaction", "--skip-lock-tables", "--quick",
        "--hex-blob", "--max-allowed-packet=1G", "--comments", "--dump-date", "--verbose", "--triggers",
    ]


def NettoyerDiagnostic(texte, secrets=()):
    """Diagnostic exploitable sans identifiants, mot de passe ni contenu SQL."""
    valeurs = [str(s) for s in secrets if s]
    for valeur in tuple(valeurs):
        if valeur.startswith("#64#"):
            try:
                valeurs.append(base64.b64decode(valeur[4:]).decode("utf-8"))
            except (ValueError, UnicodeError):
                pass
    for secret in sorted((s for s in valeurs if s), key=len, reverse=True):
        texte = texte.replace(secret, "[masqué]")
    texte = re.sub(r"(?is)(?:INSERT\s+INTO|REPLACE\s+INTO).*", "[SQL masqué]", texte)
    return texte[:4096]


def ExporterSQL(programme, login, fichier, base, options="", progression=None,
                secrets=(), inactivite=600, duree_max=7200):
    """Export en lecture seule ; processus enfant toujours attendu avant retour.

    Le résultat ne contient ni SQL, ni ligne de commande, ni identifiants. Les
    options sont validées avant de créer le fichier SQL. Aucune relance aveugle.
    """
    debut = time.monotonic()
    maintenant = debut
    derniere_progression = debut
    taille = 0
    erreur = None
    code = None
    diagnostic = ""
    try:
        args = [os.fspath(programme), "--defaults-file=%s" % login, "--opt"]
        args += OptionsDump(options) + ["--databases", base]
        with open(fichier, "wb") as sortie, tempfile.TemporaryFile() as erreurs:
            proc = subprocess.Popen(args, shell=False, stdout=sortie, stderr=erreurs,
                                    stdin=subprocess.DEVNULL)
            try:
                while True:
                    try:
                        proc.wait(timeout=2)
                        break
                    except subprocess.TimeoutExpired:
                        maintenant = time.monotonic()
                        nouvelle_taille = os.path.getsize(fichier)
                        if nouvelle_taille > taille:
                            derniere_progression = maintenant
                        taille = nouvelle_taille
                        if maintenant - derniere_progression >= inactivite:
                            erreur = "Export MySQL sans progression depuis 10 minutes (%s)." % base
                            break
                        if maintenant - debut >= duree_max:
                            erreur = "Export MySQL au-dela de 2 heures (%s)." % base
                            break
                        if progression:
                            progression(taille)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
            code = proc.returncode
            # Dernier état de mysqldump, y compris après un timeout : sa première
            # ligne seule ne permet pas d'identifier la table ou l'erreur finale.
            erreurs.seek(0, os.SEEK_END)
            erreurs.seek(max(0, erreurs.tell() - 4096))
            diagnostic = NettoyerDiagnostic(erreurs.read().decode("utf-8", "replace"), secrets)
            if erreur is None and code != 0:
                erreur = "mysqldump a echoue (code %s)." % code
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        erreur = "Impossible de terminer l'export SQL : %s" % exc
    taille = os.path.getsize(fichier) if os.path.isfile(fichier) else 0
    return {"etape": "export_mysql", "base": base, "octets": taille,
            "secondes": round(time.monotonic() - debut, 1), "code_retour": code,
            "erreur": NettoyerDiagnostic(erreur, secrets) if erreur else None,
            "diagnostic": diagnostic}


def CreerArchive(programme, login, fichiers, destination, integrite, progression=None, secrets=()):
    """Même export que l'interface, utilisable sans ouvrir un profil Noethys.

    Aucune restauration. Publier seulement après fin mysqldump, analyse SQL,
    manifeste et contrôle CRC de tous les membres. L'archive existante est refusée.
    """
    destination = os.path.abspath(destination)
    if os.path.exists(destination):
        raise FileExistsError("La sauvegarde cible existe déjà")
    if not fichiers or len(set(fichiers)) != len(fichiers):
        raise ValueError("Liste de bases vide ou dupliquée")
    if any(not re.fullmatch(r"[A-Za-z0-9_$]+", f) for f in fichiers):
        raise ValueError("Nom de base non pris en charge")
    bilan = {"succes": False, "exports": []}
    try:
        with tempfile.TemporaryDirectory(prefix=".noethys-save-", dir=os.path.dirname(destination)) as rep:
            archive = os.path.join(rep, "sauvegarde.nod")
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
                for base in fichiers:
                    fichier = os.path.join(rep, base + ".sql")
                    callback = (lambda taille: progression(base, "export", taille)) if progression else None
                    resultat = ExporterSQL(programme, login, fichier, base, progression=callback, secrets=secrets)
                    bilan["exports"].append(resultat)
                    if resultat["erreur"]:
                        raise RuntimeError(resultat["erreur"])
                    if progression:
                        progression(base, "verification_sql", resultat["octets"])
                    analyse, erreur = integrite.AnalyserDumpSQL(fichier, exiger_fin_mysqldump=True)
                    if erreur:
                        raise RuntimeError("Dump %s refusé : %s" % (base, erreur))
                    resultat["fin_mysqldump"] = analyse["fin_mysqldump"]
                    integrite.AjouterManifesteIntegriteSQL(fichier)
                    if progression:
                        progression(base, "compression", resultat["octets"])
                    z.write(fichier, base + ".sql")
                    os.remove(fichier)
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None or z.namelist() != [base + ".sql" for base in fichiers]:
                    raise RuntimeError("Contrôle de l'archive échoué")
            # Ce CLI refuse tout remplacement, y compris une création concurrente.
            os.link(archive, destination)
            bilan["succes"] = True
    except Exception as exc:
        bilan["erreur"] = NettoyerDiagnostic(str(exc), secrets)
    with open(destination + ".diagnostic.json", "w", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=False, indent=2)
    return bilan
