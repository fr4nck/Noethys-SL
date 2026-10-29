# -*- coding: utf-8 -*-
"""#436 - Autorisations par enfant, sans modifier les donnees medicales.

Registre dedie, append-only, installe UNIQUEMENT par action explicite
d'un administrateur apres sauvegarde confirmee. Aucun appel ne modifie
les questionnaires, AEEH, fiches medicales ou documents originaux.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import re

TABLE = "accueil_autorisations"
TYPES = (
    "photos_site_imprimes", "maquillage", "piscine_baignade",
    "activites_physiques", "photos_prise", "photos_usage_interne",
    "photos_reseaux_sociaux",
)
LIBELLES = {
    "photos_site_imprimes": "Photos (site internet : pelemele.org)",
    "maquillage": "Maquillage",
    "piscine_baignade": "Baignade",
    "activites_physiques": "Activites physiques",
    "photos_prise": "Prise de photos / videos",
    "photos_usage_interne": "Photos : utilisation interne",
    "photos_reseaux_sociaux": "Photos : reseaux sociaux",
}
COLONNES = (
    "IDautorisation", "IDindividu", "type_autorisation", "perimetre",
    "valeur", "date_debut", "date_fin", "repondu_le", "date_signature",
    "IDsignataire", "autorite_verifiee", "texte_version", "source",
    "reference_preuve", "IDutilisateur", "empreinte",
)

SQLITE_DDL = """
CREATE TABLE accueil_autorisations (
 IDautorisation INTEGER PRIMARY KEY AUTOINCREMENT,
 IDindividu INTEGER NOT NULL,
 type_autorisation VARCHAR(50) NOT NULL,
 perimetre VARCHAR(120) NOT NULL,
 valeur INTEGER NOT NULL CHECK (valeur IN (0, 1)),
 date_debut DATE NOT NULL, date_fin DATE NOT NULL,
 repondu_le VARCHAR(40) NOT NULL,
 date_signature DATE NOT NULL,
 IDsignataire INTEGER NOT NULL, autorite_verifiee INTEGER NOT NULL,
 texte_version VARCHAR(100) NOT NULL, source VARCHAR(15) NOT NULL,
 reference_preuve VARCHAR(200) NOT NULL,
 IDutilisateur INTEGER NOT NULL,
 empreinte CHAR(64) NOT NULL UNIQUE
);
CREATE INDEX idx_accueil_autorisations_enfant
 ON accueil_autorisations (IDindividu, type_autorisation, perimetre, IDautorisation);
"""
MYSQL_DDL = """
CREATE TABLE accueil_autorisations (
 IDautorisation INTEGER PRIMARY KEY AUTO_INCREMENT,
 IDindividu INTEGER NOT NULL,
 type_autorisation VARCHAR(50) NOT NULL,
 perimetre VARCHAR(120) NOT NULL,
 valeur INTEGER NOT NULL,
 date_debut DATE NOT NULL, date_fin DATE NOT NULL,
 repondu_le VARCHAR(40) NOT NULL, date_signature DATE NOT NULL,
 IDsignataire INTEGER NOT NULL, autorite_verifiee INTEGER NOT NULL,
 texte_version VARCHAR(100) NOT NULL, source VARCHAR(15) NOT NULL,
 reference_preuve VARCHAR(200) NOT NULL,
 IDutilisateur INTEGER NOT NULL,
 empreinte CHAR(64) NOT NULL,
 UNIQUE KEY uk_accueil_empreinte (empreinte),
 INDEX idx_accueil_autorisations_enfant (IDindividu, type_autorisation, perimetre, IDautorisation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class RegistreAbsent(RuntimeError):
    pass


class AutorisationRefusee(PermissionError):
    pass


class PreuveInvalide(ValueError):
    pass


class ConflitConcurrent(RuntimeError):
    pass


def AccesUtilisateur(utilisateur, action="consulter"):
    """Refus par defaut, independant des anciens droits permissifs."""
    if not isinstance(utilisateur, dict) or action not in ("consulter", "modifier"):
        return False
    ID = utilisateur.get("IDutilisateur")
    if type(ID) is not int or ID <= 0 or utilisateur.get("actif") not in (1, True):
        return False
    profil = utilisateur.get("profil")
    if isinstance(profil, str) and profil.startswith("administrateur"):
        return True
    droits = utilisateur.get("droits")
    if not isinstance(droits, dict):
        return False
    regle = droits.get(("fiche_accueil_autorisations", action))
    return isinstance(regle, str) and regle.startswith("autorisation")


def _ouvrir(DB):
    if DB is not None:
        return DB, False
    import GestionDB
    base = GestionDB.DB()
    if getattr(base, "echec", 0):
        raise RegistreAbsent("Base Noethys indisponible")
    return base, True


def _exec(base, sql, params=()):
    if base.isNetwork:
        sql = sql.replace("?", "%s")
    base.cursor.execute(sql, tuple(params))


def _colonnes(base):
    if base.isNetwork:
        _exec(base, """SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?""", (TABLE,))
        return set(ligne[0] for ligne in base.cursor.fetchall())
    _exec(base, "PRAGMA table_info(accueil_autorisations)")
    return set(ligne[1] for ligne in base.cursor.fetchall())


def _schema(base):
    colonnes = _colonnes(base)
    if not colonnes:
        raise RegistreAbsent("Registre des autorisations non initialise")
    if not set(COLONNES).issubset(colonnes):
        raise RegistreAbsent("Registre existant mais schema incompatible")
    return True


def VerifierRegistre(DB=None, autorise=False):
    if autorise is not True:
        raise AutorisationRefusee("Acces au registre non autorise")
    base, propre = _ouvrir(DB)
    try:
        return _schema(base)
    finally:
        if propre:
            base.Close()


def InitialiserRegistre(DB=None, administrateur=False, sauvegarde_confirmee=False):
    """Ajoute uniquement la nouvelle table, apres confirmation et sauvegarde.

    Aucune migration au demarrage ni en ouvrant la fiche. Ne modifie aucune
    table existante. MySQL et SQLite serialisent deux tentatives simultanees.
    """
    if administrateur is not True or sauvegarde_confirmee is not True:
        raise AutorisationRefusee("Administrateur et sauvegarde confirmee requis")
    base, propre = _ouvrir(DB)
    verrou = False
    started = False
    try:
        if base.isNetwork:
            _exec(base, "SELECT GET_LOCK(CONCAT('nsl_acc_', LEFT(MD5(DATABASE()), 16)), 0)")
            verrou = base.cursor.fetchone()[0] == 1
            if not verrou:
                raise ConflitConcurrent("Une autre preparation du registre est en cours")
        else:
            _exec(base, "BEGIN IMMEDIATE")
            started = True
        existing = _colonnes(base)
        if existing:
            if not set(COLONNES).issubset(existing):
                raise RegistreAbsent("Une table incompatible porte deja ce nom")
            base.connexion.commit()
            started = False
            return False
        if base.isNetwork:
            _exec(base, MYSQL_DDL)
        else:
            for commande in SQLITE_DDL.strip().split(";"):
                if commande.strip():
                    _exec(base, commande)
        _schema(base)
        base.connexion.commit()
        started = False
        return True
    except Exception:
        if started or not base.isNetwork:
            base.connexion.rollback()
        raise
    finally:
        if verrou:
            try:
                _exec(base, "SELECT RELEASE_LOCK(CONCAT('nsl_acc_', LEFT(MD5(DATABASE()), 16)))")
                base.cursor.fetchone()
            except Exception:
                pass
        if propre:
            base.Close()


def _jour(valeur):
    if type(valeur) is date:
        return valeur.isoformat()
    if type(valeur) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        try:
            return date.fromisoformat(valeur).isoformat()
        except ValueError:
            pass
    raise PreuveInvalide("Date de la fiche invalide (AAAA-MM-JJ)")


def _positive(valeur, etiquette):
    if type(valeur) is not int or valeur <= 0:
        raise PreuveInvalide("%s manquant" % etiquette)
    return valeur


def _texte(valeur, etiquette, maximum):
    if not isinstance(valeur, str) or not valeur.strip() or len(valeur.strip()) > maximum:
        raise PreuveInvalide("%s manquant ou trop long" % etiquette)
    return valeur.strip()


def _normaliser(enfant, donnees, operateur):
    if not isinstance(donnees, dict):
        raise PreuveInvalide("Decision invalide")
    typ = donnees.get("type")
    if typ not in TYPES:
        raise PreuveInvalide("Autorisation inconnue")
    if type(donnees.get("valeur")) is not int or donnees["valeur"] not in (0, 1):
        raise PreuveInvalide("Choix explicite Oui ou Non obligatoire")
    if donnees.get("autorite_verifiee") is not True:
        raise PreuveInvalide("Autorite du signataire non verifiee")
    debut = _jour(donnees.get("date_debut"))
    fin = _jour(donnees.get("date_fin"))
    if fin < debut:
        raise PreuveInvalide("Periode inversée")
    signature = _jour(donnees.get("date_signature"))
    if signature > date.today().isoformat():
        raise PreuveInvalide("Signature future interdite")
    source = donnees.get("source")
    if source not in ("papier", "pieces"):
        raise PreuveInvalide("Source papier ou Pieces obligatoire")
    payload = {
        "IDindividu": enfant, "type_autorisation": typ,
        "perimetre": _texte(donnees.get("perimetre"), "Perimetre", 120),
        "valeur": donnees["valeur"], "date_debut": debut, "date_fin": fin,
        "date_signature": signature,
        "IDsignataire": _positive(donnees.get("IDsignataire"), "Responsable signataire"),
        "autorite_verifiee": 1,
        "texte_version": _texte(donnees.get("texte_version"), "Version du texte", 100),
        "source": source,
        "reference_preuve": _texte(donnees.get("reference_preuve"), "Reference de la fiche signee", 200),
        "IDutilisateur": operateur,
    }
    # L'empreinte n'inclut pas la date de saisie pour rendre le rejeu idempotent.
    chaine = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload["empreinte"] = hashlib.sha256(chaine.encode("utf-8")).hexdigest()
    return payload


def _dernier(base, IDindividu, typ, perimetre):
    _exec(base, """SELECT IDautorisation, empreinte FROM accueil_autorisations
        WHERE IDindividu=? AND type_autorisation=? AND perimetre=?
        ORDER BY IDautorisation DESC LIMIT 1""", (IDindividu, typ, perimetre))
    ligne = base.cursor.fetchone()
    return tuple(ligne) if ligne else (None, None)


def DerniersIdentifiants(IDindividu, DB=None, autorise=False, perimetre="general"):
    if autorise is not True:
        raise AutorisationRefusee("Lecture non autorisee")
    enfant = _positive(IDindividu, "Enfant")
    perimetre = _texte(perimetre, "Perimetre", 120)
    base, propre = _ouvrir(DB)
    try:
        _schema(base)
        return {typ: _dernier(base, enfant, typ, perimetre)[0] for typ in TYPES}
    finally:
        if propre:
            base.Close()


def LireHistorique(IDindividu, DB=None, autorise=False):
    if autorise is not True:
        raise AutorisationRefusee("Lecture non autorisee")
    enfant = _positive(IDindividu, "Enfant")
    base, propre = _ouvrir(DB)
    try:
        _schema(base)
        _exec(base, """SELECT IDautorisation, IDindividu, type_autorisation, perimetre,
          valeur, date_debut, date_fin, repondu_le, date_signature,
          IDsignataire, autorite_verifiee, texte_version, source, reference_preuve
          FROM accueil_autorisations WHERE IDindividu=?
          ORDER BY IDautorisation""", (enfant,))
        lignes = list(base.cursor.fetchall())
        resultat = []
        for ligne in lignes:
            (ident, indiv, typ, perimetre, valeur, debut, fin, instant,
             signature, signataire, verification, version, source, preuve) = ligne
            resultat.append({
                "IDautorisation": int(ident), "IDindividu": int(indiv),
                "type": typ, "perimetre": perimetre, "valeur": int(valeur),
                "date_debut": str(debut), "date_fin": str(fin),
                "repondu_le": instant, "date_signature": str(signature),
                "signataire": int(signataire),
                "autorite_verifiee": verification == 1, "texte_version": version,
                "preuve": "%s:%s" % (source, preuve),
            })
        return resultat
    finally:
        if propre:
            base.Close()


def EnregistrerLot(IDindividu, IDutilisateur, decisions, attendus, DB=None,
                   autorise=False):
    """Batch atomique avec comparaison des revisions, 0 Yes implicite.

    Idempotence : meme preuve signee et meme decision = ID deja conserve.
    Nouvelle decision = insertion dans historique, jamais UPDATE/DELETE.
    Les appels concurrents sur le meme enfant sont serialises.
    """
    if autorise is not True:
        raise AutorisationRefusee("Ecriture non autorisee")
    enfant = _positive(IDindividu, "Enfant")
    operateur = _positive(IDutilisateur, "Operateur")
    if not isinstance(decisions, (list, tuple)) or not decisions:
        raise PreuveInvalide("Aucune decision a enregistrer")
    if not isinstance(attendus, dict):
        raise PreuveInvalide("Revisions attendues manquantes")
    payloads = [_normaliser(enfant, ligne, operateur) for ligne in decisions]
    cles = [(x["type_autorisation"], x["perimetre"]) for x in payloads]
    if len(set(cles)) != len(cles):
        raise PreuveInvalide("Une seule decision par autorisation et perimetre")
    for typ, perimetre in cles:
        if (typ, perimetre) not in attendus:
            raise PreuveInvalide("Version de consultation manquante")
        ident = attendus[(typ, perimetre)]
        if ident is not None and (type(ident) is not int or ident <= 0):
            raise PreuveInvalide("Identifiant de revision invalide")
    base, propre = _ouvrir(DB)
    started = False
    try:
        _schema(base)
        _exec(base, "START TRANSACTION" if base.isNetwork else "BEGIN IMMEDIATE")
        started = True
        _exec(base, "SELECT IDindividu FROM individus WHERE IDindividu=?" +
              (" FOR UPDATE" if base.isNetwork else ""), (enfant,))
        if base.cursor.fetchone() is None:
            raise PreuveInvalide("Enfant introuvable")
        resultat = {}
        for data in payloads:
            typ, perimetre = data["type_autorisation"], data["perimetre"]
            dernier_id, derniere_empreinte = _dernier(base, enfant, typ, perimetre)
            cle = (typ, perimetre)
            if derniere_empreinte == data["empreinte"]:
                resultat[cle] = dernier_id
                continue
            if dernier_id != attendus[cle]:
                raise ConflitConcurrent("L'autorisation a change sur un autre poste ; actualisez la fiche")
            _exec(base, "SELECT IDautorisation FROM accueil_autorisations WHERE empreinte=?",
                  (data["empreinte"],))
            if base.cursor.fetchone() is not None:
                raise PreuveInvalide("Une ancienne preuve a deja ete remplacee")
            data["repondu_le"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            champs = (
                "IDindividu", "type_autorisation", "perimetre", "valeur",
                "date_debut", "date_fin", "repondu_le", "date_signature",
                "IDsignataire", "autorite_verifiee", "texte_version", "source",
                "reference_preuve", "IDutilisateur", "empreinte")
            _exec(base, "INSERT INTO accueil_autorisations (%s) VALUES (%s)" % (
                ",".join(champs), ",".join("?" for _ in champs)),
                [data[champ] for champ in champs])
            if base.isNetwork:
                _exec(base, "SELECT LAST_INSERT_ID()")
                ident = int(base.cursor.fetchone()[0])
            else:
                ident = int(base.cursor.lastrowid)
            resultat[cle] = ident
        base.connexion.commit()
        started = False
        return resultat
    except Exception:
        if started:
            base.connexion.rollback()
        raise
    finally:
        if propre:
            base.Close()
