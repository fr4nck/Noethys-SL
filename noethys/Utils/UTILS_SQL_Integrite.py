# -*- coding: utf-8 -*-
"""Validation independante des dumps SQL Noethys : manifeste V1 et analyse
syntaxique (sans wx ni base)."""

import hashlib
import io
import os
import re
import tempfile
import uuid

_ENTETE = b"-- NOETHYS-SQL-MANIFEST-V1 "
_FIN = b"-- NOETHYS-SQL-MANIFEST-END-V1 "
_JETON_RE = re.compile(br"[0-9a-f]{32}\Z")
_FIN_RE = re.compile(br"-- NOETHYS-SQL-MANIFEST-END-V1 ([0-9a-f]{32}) ([0-9]+) ([0-9a-f]{64})\n?\Z")
_BLOC = 1024 * 1024


def AjouterManifesteIntegriteSQL(fichier):
    """Ajoute le manifeste V1 de master sans supprimer la source avant remplacement."""
    chemin = os.fspath(fichier)
    jeton = uuid.uuid4().hex.encode("ascii")
    repertoire = os.path.dirname(os.path.abspath(chemin))
    nom = os.path.basename(chemin)
    temporaire = None
    try:
        with open(chemin, "rb") as source:
            if source.read(len(_ENTETE)) == _ENTETE:
                raise ValueError("dump deja dote d'un manifeste SQL")
            source.seek(0)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=repertoire, prefix=nom + ".manifest-", delete=False
            ) as destination:
                temporaire = destination.name
                destination.write(_ENTETE + jeton + b"\n")
                empreinte = hashlib.sha256()
                taille = 0
                while True:
                    bloc = source.read(_BLOC)
                    if not bloc:
                        break
                    empreinte.update(bloc)
                    taille += len(bloc)
                    destination.write(bloc)
                if taille == 0:
                    raise ValueError("dump SQL vide : manifeste non ajoute")
                destination.write(b"\n" + _FIN + jeton + b" " + str(taille).encode("ascii")
                                  + b" " + empreinte.hexdigest().encode("ascii") + b"\n")
        os.replace(temporaire, chemin)
        temporaire = None
    finally:
        if temporaire is not None:
            try:
                os.unlink(temporaire)
            except OSError:
                pass


def VerifierIntegriteSQL(fichier):
    """Retourne (avec_manifeste, erreur). Ancien dump autorise, manifeste V1 strict.

    La taille et le SHA-256 sont controles en flux, sans charger le dump en RAM.
    """
    chemin = os.fspath(fichier)
    try:
        with open(chemin, "rb") as source:
            taille_fichier = os.fstat(source.fileno()).st_size
            if taille_fichier == 0:
                return False, "dump SQL vide"
            premiere = source.readline(128)
            if not premiere.startswith(_ENTETE):
                if premiere.startswith(b"-- NOETHYS-SQL-MANIFEST-V1"):
                    return False, "en-tete du manifeste SQL invalide"
                source.seek(max(0, taille_fichier - 1024))
                if _FIN in source.read():
                    return False, "manifeste terminal sans en-tete"
                return False, None
            if not premiere.endswith(b"\n"):
                return True, "en-tete du manifeste SQL tronque"
            jeton = premiere[len(_ENTETE):-1]
            if _JETON_RE.fullmatch(jeton) is None:
                return True, "identifiant du manifeste SQL invalide"
            depart_charge = source.tell()
            debut_queue = max(depart_charge, taille_fichier - 1024)
            source.seek(debut_queue)
            queue = source.read()
            marqueur = queue.rfind(b"\n" + _FIN)
            if marqueur < 0:
                return True, "manifeste terminal absent ou tronque"
            ligne_fin = queue[marqueur + 1:]
            correspondance = _FIN_RE.fullmatch(ligne_fin)
            if correspondance is None:
                return True, "manifeste terminal invalide"
            jeton_fin, taille_declaree, empreinte_declaree = correspondance.groups()
            if jeton_fin != jeton:
                return True, "identifiants du manifeste SQL differents"
            fin_charge = debut_queue + marqueur
            taille_reelle = fin_charge - depart_charge
            if taille_reelle == 0:
                return True, "charge SQL vide dans le manifeste"
            if taille_reelle != int(taille_declaree):
                return True, "taille du dump SQL differente du manifeste"
            source.seek(depart_charge)
            empreinte = hashlib.sha256()
            reste = taille_reelle
            while reste > 0:
                bloc = source.read(min(_BLOC, reste))
                if not bloc:
                    return True, "charge SQL tronquee"
                empreinte.update(bloc)
                reste -= len(bloc)
            if empreinte.hexdigest().encode("ascii") != empreinte_declaree:
                return True, "empreinte SHA-256 du dump SQL invalide"
            return True, None
    except OSError as erreur:
        return False, "lecture du dump SQL impossible : %s" % erreur


# ---------------------------------------------------------------------------
# Analyse syntaxique des dumps (Noe-032).
# Recopie a l'identique depuis master (origin/master b0be3c7e, UTILS_Sauvegarde.py) :
# constantes et fonctions _NettoyerSQLPourAnalyse, _NouvelInventaireObjetsSQL,
# _ClasserInstructionSQL, _DecouperInstructionsSQL, _NomObjetSQL. Seule l'entree
# AnalyserDumpSQL est propre a ce module : elle reutilise VerifierIntegriteSQL.
# ---------------------------------------------------------------------------

_TAILLE_PREFIXE_INSTRUCTION_SQL = 16 * 1024
_IDENTIFIANT_SQL = r'(?:`(?:``|[^`])+`|"(?:""|[^"])+"|[A-Za-z0-9_$]+)'
_NOM_QUALIFIE_SQL = r"(?:(?:%s)\s*\.\s*)?(?P<nom>%s)" % (_IDENTIFIANT_SQL, _IDENTIFIANT_SQL)
_MODIFICATEURS_CREATE_SQL = (
    r"(?P<modificateurs>(?:(?:OR\s+REPLACE|TEMPORARY|ALGORITHM\s*=\s*\S+|"
    r"DEFINER\s*=\s*\S+(?:\s*@\s*\S+)?|SQL\s+SECURITY\s+\w+)\s+)*)"
)
_CREATE_OBJET_SQL_RE = re.compile(
    r"\bCREATE\s+%s(?P<type>TABLE|VIEW|TRIGGER|PROCEDURE|FUNCTION|EVENT)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?%s" % (_MODIFICATEURS_CREATE_SQL, _NOM_QUALIFIE_SQL),
    re.IGNORECASE,
)
_ECRITURE_TABLE_SQL_RE = re.compile(
    r"\b(?:INSERT(?:\s+(?:LOW_PRIORITY|DELAYED|HIGH_PRIORITY|IGNORE))*|"
    r"REPLACE(?:\s+(?:LOW_PRIORITY|DELAYED))*)\s+INTO\s+%s" % _NOM_QUALIFIE_SQL,
    re.IGNORECASE,
)


def _NettoyerSQLPourAnalyse(texte):
    """ Retire commentaires et littéraux sans masquer les identifiants SQL quotés. """
    texte = re.sub(r"/\*!\d{5,6}\s*(.*?)\*/", r"\1", texte, flags=re.S)
    resultat = io.StringIO()
    index = 0
    longueur = len(texte)

    while index < longueur:
        caractere = texte[index]

        if caractere == u"'":
            quote = caractere
            resultat.write(u" __NOETHYS_SQL_STRING__ ")
            index += 1
            ferme = False
            while index < longueur:
                caractere = texte[index]
                if caractere == u"\\":
                    index += 2
                    continue
                if caractere == quote:
                    if index + 1 < longueur and texte[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    ferme = True
                    break
                index += 1
            if ferme == False:
                return resultat.getvalue(), False
            continue

        if caractere in (u"`", u'"'):
            quote = caractere
            debut = index
            index += 1
            ferme = False
            while index < longueur:
                if texte[index] == quote:
                    if index + 1 < longueur and texte[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    ferme = True
                    break
                if texte[index] == u"\\":
                    index += 2
                    continue
                index += 1
            resultat.write(texte[debut:index])
            if ferme == False:
                return resultat.getvalue(), False
            continue

        if caractere == u"/" and index + 1 < longueur and texte[index + 1] == u"*":
            finCommentaire = texte.find(u"*/", index + 2)
            if finCommentaire == -1:
                return resultat.getvalue(), False
            resultat.write(u" ")
            index = finCommentaire + 2
            continue

        if caractere == u"#":
            finLigne = texte.find(u"\n", index + 1)
            if finLigne == -1:
                break
            resultat.write(u"\n")
            index = finLigne + 1
            continue

        if caractere == u"-" and index + 1 < longueur and texte[index + 1] == u"-":
            suivant = texte[index + 2:index + 3]
            if suivant == u"" or suivant.isspace():
                finLigne = texte.find(u"\n", index + 2)
                if finLigne == -1:
                    break
                resultat.write(u"\n")
                index = finLigne + 1
                continue

        resultat.write(caractere)
        index += 1

    return resultat.getvalue(), True


def _NouvelInventaireObjetsSQL():
    return {
        "tables": set(),
        "vues": set(),
        "triggers": set(),
        "procedures": set(),
        "fonctions": set(),
        "evenements": set(),
    }


def _ClasserInstructionSQL(instruction, objets):
    correspondances = {
        "TABLE": "tables",
        "VIEW": "vues",
        "TRIGGER": "triggers",
        "PROCEDURE": "procedures",
        "FUNCTION": "fonctions",
        "EVENT": "evenements",
    }

    correspondance = _CREATE_OBJET_SQL_RE.match(instruction)
    if correspondance is not None:
        typeObjet = correspondance.group("type").upper()
        modificateurs = correspondance.group("modificateurs") or u""
        if typeObjet != "TABLE" or re.search(r"\bTEMPORARY\b", modificateurs, re.IGNORECASE) is None:
            objets[correspondances[typeObjet]].add(_NomObjetSQL(correspondance.group("nom")))
        return

    correspondance = _ECRITURE_TABLE_SQL_RE.match(instruction)
    if correspondance is not None:
        objets["tables"].add(_NomObjetSQL(correspondance.group("nom")))


def _DecouperInstructionsSQL(texte):
    """ Classe les instructions de premier niveau en respectant DELIMITER, avec mémoire bornée par instruction. """
    objets = _NouvelInventaireObjetsSQL()
    tampon = []
    tailleTampon = 0
    tamponSignificatif = False
    delimiteur = u";"
    index = 0
    debutLigne = True
    longueur = len(texte)

    while index < longueur:
        if debutLigne and tamponSignificatif == False:
            finLigne = texte.find(u"\n", index)
            if finLigne == -1:
                finLigne = longueur
            ligne = texte[index:finLigne]
            correspondance = re.match(r"^[ \t]*DELIMITER[ \t]+(\S+)[ \t\r]*$", ligne, re.IGNORECASE)
            if correspondance is not None:
                delimiteur = correspondance.group(1)
                tampon = []
                tailleTampon = 0
                index = finLigne + (1 if finLigne < longueur else 0)
                debutLigne = True
                continue

        caractere = texte[index]
        if caractere in (u"`", u'"'):
            quote = caractere
            debut = index
            index += 1
            while index < longueur:
                if texte[index] == quote:
                    if index + 1 < longueur and texte[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                if texte[index] == u"\\":
                    index += 2
                    continue
                index += 1
            fragment = texte[debut:index]
            if tailleTampon < _TAILLE_PREFIXE_INSTRUCTION_SQL:
                fragmentPrefixe = fragment[:_TAILLE_PREFIXE_INSTRUCTION_SQL - tailleTampon]
                tampon.append(fragmentPrefixe)
                tailleTampon += len(fragmentPrefixe)
            tamponSignificatif = True
            debutLigne = fragment.endswith(u"\n")
            continue

        if delimiteur and texte.startswith(delimiteur, index):
            instruction = u"".join(tampon).strip()
            if tamponSignificatif and instruction:
                _ClasserInstructionSQL(instruction, objets)
            tampon = []
            tailleTampon = 0
            tamponSignificatif = False
            index += len(delimiteur)
            debutLigne = False
            continue

        if tailleTampon < _TAILLE_PREFIXE_INSTRUCTION_SQL:
            tampon.append(caractere)
            tailleTampon += 1
        if not caractere.isspace():
            tamponSignificatif = True
        debutLigne = caractere == u"\n"
        index += 1

    # Un objet explicitement créé comme vue ne doit pas être accepté comme table ordinaire.
    objets["tables"].difference_update(objets["vues"])
    return objets, tamponSignificatif, delimiteur


def _NomObjetSQL(valeur):
    valeur = valeur.strip()
    if valeur.startswith(u"`") and valeur.endswith(u"`"):
        valeur = valeur[1:-1].replace(u"``", u"`")
    elif valeur.startswith(u'"') and valeur.endswith(u'"'):
        valeur = valeur[1:-1].replace(u'""', u'"')
    return valeur.lower()


def _LireChargeSQL(chemin, avec_manifeste):
    """Retourne la charge SQL brute, sans l'enveloppe V1 deja verifiee."""
    with open(chemin, "rb") as source:
        contenu = source.read()
    if not avec_manifeste:
        return contenu
    debut = contenu.find(b"\n") + 1
    fin = contenu.rfind(b"\n" + _FIN)
    return contenu[debut:fin]


# Ligne finale ecrite par mysqldump/mariadb-dump (MySQL 5.5, 5.7, 8.0, MariaDB
# 10.11 verifies) sauf avec --compact ou --skip-comments ; sans date si
# --skip-dump-date.
_FIN_MYSQLDUMP_RE = re.compile(br"-- Dump completed(?: on [^\r\n]*)?\Z")

ERREUR_FIN_MYSQLDUMP_ABSENTE = (
    "ancienne sauvegarde sans manifeste et sans ligne finale '-- Dump completed' : "
    "dump possiblement tronque, restauration normale refusee "
    "(procedure de recuperation isolee : docs/exploitation/RECUPERATION_DUMP_SQL.md)"
)


def FinMysqldumpPresente(charge):
    """Vrai si la derniere ligne non vide de la charge est la fin mysqldump."""
    fin = charge.rstrip()
    debut = fin.rfind(b"\n") + 1
    return _FIN_MYSQLDUMP_RE.match(fin[debut:]) is not None


def AnalyserDumpSQL(fichier, exiger_fin_mysqldump=True):
    """Retourne (analyse, erreur) ; analyse = {"avec_manifeste", "fin_mysqldump", "objets"}.

    Refuse avant toute commande mysql : manifeste invalide, dump vide, ancien
    dump sans manifeste ni ligne finale mysqldump (le manifeste SHA-256 prouve
    seul la completude d'un dump recent), chaine, identifiant ou commentaire non
    ferme, derniere instruction incomplete, delimiteur non retabli et dump sans
    objet persistant ni chargement de table.
    """
    chemin = os.fspath(fichier)
    avec_manifeste, erreur = VerifierIntegriteSQL(chemin)
    if erreur is not None:
        return None, erreur
    try:
        charge = _LireChargeSQL(chemin, avec_manifeste)
    except (IOError, OSError) as err:
        return None, "lecture du dump SQL impossible : %s" % err
    if not charge or not charge.strip():
        return None, "dump SQL vide"
    fin_mysqldump = FinMysqldumpPresente(charge)
    if exiger_fin_mysqldump and not avec_manifeste and not fin_mysqldump:
        return None, ERREUR_FIN_MYSQLDUMP_ABSENTE

    texte = charge.decode("utf-8", "ignore")
    texteNettoye, ferme = _NettoyerSQLPourAnalyse(texte)
    if ferme == False:
        return None, "dump SQL termine dans une chaine, un identifiant ou un commentaire non ferme"

    objets, reste, delimiteur = _DecouperInstructionsSQL(texteNettoye)
    if reste:
        return None, "derniere instruction SQL incomplete"
    if delimiteur != u";":
        return None, "delimiteur standard non retabli en fin de dump SQL"
    if not any(objets.values()):
        return None, "aucun objet persistant ni chargement de table dans le dump SQL"

    return {"avec_manifeste": avec_manifeste, "fin_mysqldump": fin_mysqldump, "objets": objets}, None


# ---------------------------------------------------------------------------
# Marqueur terminal et postconditions de restauration MySQL (Noe-032).
# Adaptes de master (b0be3c7e) : _AjouterMarqueurTerminalSQL,
# _VerifierPostconditionRestaurationMySQL, _SupprimerMarqueurRestaurationMySQL.
# La connexion est injectee (ExecuterReq / ResultatReq de GestionDB) : aucun
# acces base dans ce module. Ces controles prouvent que l'import est alle
# jusqu'au bout et que les objets inventories existent ; ils ne prouvent pas
# qu'un ancien dump etait complet (voir FinMysqldumpPresente).
# ---------------------------------------------------------------------------

def QuoteIdentifiantMySQL(valeur):
    return u"`%s`" % valeur.replace(u"`", u"``")


def EchapperLitteralMySQL(valeur):
    return valeur.replace(u"\\", u"\\\\").replace(u"'", u"\\'")


def AjouterMarqueurTerminalSQL(fichier, nomBase):
    """Ajoute a la copie extraite un objet ephemere qui n'existe que si la fin est executee."""
    jeton = uuid.uuid4().hex
    nomTable = u"__noethys_restore_%s" % jeton
    tableQualifiee = u"%s.%s" % (QuoteIdentifiantMySQL(nomBase), QuoteIdentifiantMySQL(nomTable))
    sql = (
        u"\n-- NOETHYS-RESTORE-END-V1 %s\n"
        u"CREATE TABLE %s (`jeton` CHAR(32) NOT NULL PRIMARY KEY);\n"
        u"INSERT INTO %s (`jeton`) VALUES ('%s');\n"
    ) % (jeton, tableQualifiee, tableQualifiee, jeton)
    with open(os.fspath(fichier), "ab") as flux:
        flux.write(sql.encode("utf-8"))
    return {"table": nomTable, "jeton": jeton}


def _ResultatRequete(DB, requete):
    if DB.ExecuterReq(requete) != 1:
        return None
    return DB.ResultatReq()


def _NormaliserValeurSQL(valeur):
    if isinstance(valeur, bytes):
        return valeur.decode("utf-8", "ignore").lower()
    return (u"%s" % valeur).lower()


def _DiagnosticObjetsManquants(categorie, manquants):
    return u"%s : %s" % (categorie, u", ".join(sorted(manquants)))


def VerifierPostconditionMySQL(DB, nomBase, marqueur, objetsAttendus):
    """Retourne (ok, diagnostic) : marqueur terminal execute puis objets attendus presents.

    Le marqueur n'est pas supprime ici (voir SupprimerMarqueurMySQL).
    """
    tableMarqueur = QuoteIdentifiantMySQL(marqueur["table"])
    jeton = EchapperLitteralMySQL(marqueur["jeton"])
    lignes = _ResultatRequete(
        DB, u"SELECT `jeton` FROM %s WHERE `jeton`='%s' LIMIT 1;" % (tableMarqueur, jeton))
    if lignes is None or len(lignes) != 1 or _NormaliserValeurSQL(lignes[0][0]) != marqueur["jeton"].lower():
        return False, u"le marqueur terminal n'a pas ete execute"

    lignes = _ResultatRequete(DB, u"SHOW FULL TABLES;")
    if lignes is None:
        return False, u"la liste des tables et vues restaurees est illisible"
    tables = set()
    vues = set()
    nomMarqueur = marqueur["table"].lower()
    for ligne in lignes:
        if not ligne:
            continue
        nomObjet = _NormaliserValeurSQL(ligne[0])
        if nomObjet == nomMarqueur:
            continue
        typeObjet = _NormaliserValeurSQL(ligne[1]) if len(ligne) > 1 else u"base table"
        if typeObjet == u"view":
            vues.add(nomObjet)
        else:
            tables.add(nomObjet)

    manquants = []
    if objetsAttendus["tables"] - tables:
        manquants.append(_DiagnosticObjetsManquants(u"tables", objetsAttendus["tables"] - tables))
    if objetsAttendus["vues"] - vues:
        manquants.append(_DiagnosticObjetsManquants(u"vues", objetsAttendus["vues"] - vues))

    schema = EchapperLitteralMySQL(nomBase)
    if not manquants and objetsAttendus["triggers"]:
        lignes = _ResultatRequete(
            DB, u"SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='%s';" % schema)
        if lignes is None:
            manquants.append(u"triggers : verification impossible")
        else:
            absents = objetsAttendus["triggers"] - set(_NormaliserValeurSQL(l[0]) for l in lignes)
            if absents:
                manquants.append(_DiagnosticObjetsManquants(u"triggers", absents))

    if not manquants and (objetsAttendus["procedures"] or objetsAttendus["fonctions"]):
        lignes = _ResultatRequete(
            DB, u"SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='%s';" % schema)
        if lignes is None:
            manquants.append(u"routines : verification impossible")
        else:
            procedures = set()
            fonctions = set()
            for ligne in lignes:
                if len(ligne) < 2:
                    continue
                if _NormaliserValeurSQL(ligne[1]) == u"procedure":
                    procedures.add(_NormaliserValeurSQL(ligne[0]))
                elif _NormaliserValeurSQL(ligne[1]) == u"function":
                    fonctions.add(_NormaliserValeurSQL(ligne[0]))
            if objetsAttendus["procedures"] - procedures:
                manquants.append(_DiagnosticObjetsManquants(u"procedures", objetsAttendus["procedures"] - procedures))
            if objetsAttendus["fonctions"] - fonctions:
                manquants.append(_DiagnosticObjetsManquants(u"fonctions", objetsAttendus["fonctions"] - fonctions))

    if not manquants and objetsAttendus["evenements"]:
        lignes = _ResultatRequete(
            DB, u"SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA='%s';" % schema)
        if lignes is None:
            manquants.append(u"evenements : verification impossible")
        else:
            absents = objetsAttendus["evenements"] - set(_NormaliserValeurSQL(l[0]) for l in lignes)
            if absents:
                manquants.append(_DiagnosticObjetsManquants(u"evenements", absents))

    if manquants:
        return False, u"des objets attendus sont absents ou de type incorrect : %s" % u" ; ".join(manquants)
    return True, u""


def SupprimerMarqueurMySQL(DB, marqueur):
    """Supprime la table marqueur ; retourne True si la requete a abouti."""
    try:
        return DB.ExecuterReq(u"DROP TABLE IF EXISTS %s;" % QuoteIdentifiantMySQL(marqueur["table"])) == 1
    except Exception:
        return False
