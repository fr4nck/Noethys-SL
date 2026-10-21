#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit d'une COPIE explicite ; n'importe ni GestionDB, ni wx, ni Config.json.

SQLite : bibliothèque standard seulement. MySQL : pilote déjà installé requis.
Aucun téléchargement, aucune émission de facture ni régularisation.
"""
import argparse
import contextlib
import csv
import datetime
import getpass
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Utils.UTILS_Audit_cotisations import ConstruireInventaire, TABLES, date_iso


def _json(valeur):
    if isinstance(valeur, (datetime.date, datetime.datetime)):
        return valeur.isoformat()
    raise TypeError(type(valeur).__name__)


def _empreinte(path):
    h = hashlib.sha256()
    with path.open("rb") as flux:
        for bloc in iter(lambda: flux.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


@contextlib.contextmanager
def ouvrir_sqlite(path):
    path = Path(path).resolve(strict=True)
    # Copie figée : aucun WAL/journal actif à interpréter ou à créer.
    if any(Path(str(path) + suffixe).exists() for suffixe in ("-wal", "-journal")):
        raise ValueError("Copie SQLite non figée (WAL/journal) : refaire une copie cohérente à l'arrêt")
    avant = _empreinte(path)
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        autorises = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                     sqlite3.SQLITE_TRANSACTION}
        db.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in autorises else sqlite3.SQLITE_DENY)
        db.execute("BEGIN")
        identite = {"moteur": "SQLite", "fichier": path.name, "sha256_avant": avant,
                    "lecture_seule": True, "copie_confirmee_par_operateur": True}
        yield lambda req: db.execute(req).fetchall(), identite
        apres = _empreinte(path)
        if apres != avant:
            raise RuntimeError("La copie a changé pendant l'audit ; aucun rapport validé")
        identite["sha256_apres"] = apres
    finally:
        db.rollback()
        db.close()


@contextlib.contextmanager
def ouvrir_mysql(base, port, utilisateur, mot_de_passe):
    if not re.fullmatch(r"[A-Za-z0-9_]+_recette_rc81(?:_DATA)?", base):
        raise ValueError("La copie MySQL doit se terminer par _recette_rc81 ou _recette_rc81_DATA")
    connexion = None
    # Privilégie les pilotes utilisés par Noethys ; n'en installe aucun.
    try:
        import MySQLdb
    except ImportError:
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError("Aucun pilote MySQL disponible. Utiliser l'environnement Python Noethys existant ; aucune installation automatique.") from exc
        connexion = mysql.connector.connect(host="127.0.0.1", port=port, user=utilisateur,
                                           password=mot_de_passe, database=base, autocommit=False,
                                           connection_timeout=10)
    else:
        connexion = MySQLdb.connect(host="127.0.0.1", port=port, user=utilisateur,
                                   passwd=mot_de_passe, db=base, charset="utf8mb4", connect_timeout=10)
    try:
        cursor = connexion.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")
        cursor.execute("SELECT DATABASE(), VERSION(), CURRENT_USER()")
        nom, version, _compte = cursor.fetchone()
        if nom != base:
            raise ValueError("Base inattendue ; arrêt")
        cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                       "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN "
                       "('cotisations','prestations','factures','ventilation','reglements')")
        engines = dict(cursor.fetchall())
        if set(engines) != set(TABLES) or any(str(v).lower() != "innodb" for v in engines.values()):
            raise ValueError("Les cinq tables doivent être présentes et InnoDB pour un cliché transactionnel cohérent")
        def lire(req):
            cursor.execute(req)
            return cursor.fetchall()
        identite = {"moteur": "MySQL", "base": base, "hote": "127.0.0.1", "port": port,
                    "version_serveur": version, "lecture_seule": True,
                    "transaction": "READ ONLY / REPEATABLE READ / CONSISTENT SNAPSHOT",
                    "copie_confirmee_par_operateur": True}
        yield lire, identite
    finally:
        connexion.rollback()
        connexion.close()


def texte_html(rapport):
    esc = lambda x: html.escape(str(x if x is not None else "—"))
    entetes = ("Cotisation / titulaire", "Validité / saisie", "Prestation", "Facture", "Ventilations", "Motifs")
    lignes = []
    for r in rapport["lignes"]:
        details_v = "; ".join("V%s · R%s · %s € · règlement %s" % (
            v["IDventilation"], v["IDreglement"], v["montant"],
            "référencé" if v["reglement_existe"] else "introuvable") for v in r["ventilations"])
        cellules = [
            "C%s · individu %s · famille %s" % (r["IDcotisation"], r["IDindividu"], r["IDfamille"]),
            "%s → %s ; saisie %s" % (r["date_debut"], r["date_fin"], r["date_saisie"]),
            "P%s · %s · %s € · %s" % (r["IDprestation"], r["date_prestation"],
                                       r["montant_prestation"], "présente" if r["prestation_existe"] else "introuvable"),
            "ID %s · n° %s · référence %s · pièce %s" % (r["IDfacture"], r["numero_facture"],
                "présente" if r["facture_referencee"] else "absente", "présente" if r["facture_existe"] else "absente"),
            "%s ligne(s) · somme %s € ; %s" % (r["nb_ventilations"], r["montant_ventile"], details_v),
            r["etat_comptable"] + " ; " + ", ".join(r["motifs"]),
        ]
        lignes.append("<tr>" + "".join("<td>" + esc(c) + "</td>" for c in cellules) + "</tr>")
    return """<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inventaire RC7 — copie RC8.1</title>
<style>body{font:16px system-ui;line-height:1.5;margin:2rem;color:#172c3c;background:#f8fafb}
h1{font-size:1.8rem}article{max-width:95rem;margin:auto}.alerte{padding:1rem;border-left:5px solid #ba6700;background:#fff1d6}
table{border-collapse:collapse;background:white;width:100%%;font-size:.9rem}th,td{padding:.7rem;border:1px solid #ccd5dc;vertical-align:top;text-align:left}
th{background:#e6eef4}.table{overflow:auto}code{overflow-wrap:anywhere}@media print{body{margin:.5cm;font-size:10pt}table{font-size:8pt}}</style>
<article><h1>Inventaire des cotisations automatiques — RC7 / recette RC8.1</h1>
<p class="alerte"><b>INVENTAIRE SEULEMENT — aucune régularisation automatique.</b> Les lignes signalées sont à examiner. Aucune présence réelle ni encaissement n'est attesté.</p>
<p>Date de référence : <b>%(date)s</b> · génération : %(gen)s · audit %(version)s.</p>
<p>%(population)s cotisations automatiques examinées ; <b>%(signalees)s signalées</b> ; %(prestations)s prestations distinctes signalées.
Somme des montants connus : %(montant)s € ; montants inconnus : %(inconnus)s. Ces montants ne sont pas un remboursement proposé.</p>
<p>Source contrôlée : <code>%(source)s</code></p>
<div class="table"><table><thead><tr>%(entetes)s</tr></thead><tbody>%(lignes)s</tbody></table></div>
<h2>Limites et suite à donner</h2><ul>%(limites)s</ul>
<p>Conserver le JSON pour les dates brutes et les détails des liens. Reporter toute décision dans la fiche de validation séparée ; aucune ligne n'autorise une suppression.</p>
</article></html>""" % {
        "date": esc(rapport["date_reference"]), "gen": esc(rapport["genere_le"]),
        "version": esc(rapport["version_audit"]), "population": rapport["cotisations_automatiques_examinees"],
        "signalees": rapport["cotisations_signalees"], "prestations": rapport["prestations_distinctes_signalees"],
        "montant": esc(rapport["total_montants_prestations_connus"]), "inconnus": rapport["prestations_montant_inconnu"],
        "source": esc(json.dumps(rapport["source"], ensure_ascii=False)),
        "entetes": "".join("<th>" + esc(h) + "</th>" for h in entetes),
        "lignes": "".join(lignes) or '<tr><td colspan="6">Aucun signal dans le périmètre du marqueur. Consulter les limites.</td></tr>',
        "limites": "".join("<li>" + esc(l) + "</li>" for l in rapport["limites"]),
    }


def exporter(rapport, destination):
    contenu_json = json.dumps(rapport, ensure_ascii=False, indent=2, default=_json)
    contenu_html = texte_html(rapport)
    dossier = Path(destination)
    dossier.mkdir(parents=True, exist_ok=False)
    (dossier / "inventaire.json").write_text(contenu_json, encoding="utf-8")
    (dossier / "inventaire.html").write_text(contenu_html, encoding="utf-8")
    champs = ["IDcotisation", "IDindividu", "IDfamille", "IDprestation", "date_saisie", "date_debut", "date_fin",
              "date_prestation", "montant_prestation", "IDfacture", "facture_existe", "nb_ventilations",
              "montant_ventile", "etat_comptable", "motifs", "action_automatique"]
    with (dossier / "inventaire.csv").open("w", newline="", encoding="utf-8-sig") as flux:
        writer = csv.DictWriter(flux, fieldnames=champs, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for r in rapport["lignes"]:
            writer.writerow({**r, "motifs": " | ".join(r["motifs"])})
    with (dossier / "validation_comptable.csv").open("w", newline="", encoding="utf-8-sig") as flux:
        writer = csv.writer(flux, delimiter=";")
        writer.writerow(["IDcotisation", "IDprestation", "participation_effective_verifiee", "facture_verifiee",
                         "ventilations_verifiees", "decision_comptable", "reference_avoir_ou_regularisation",
                         "valide_par", "date_validation"])
        for r in rapport["lignes"]:
            writer.writerow([r["IDcotisation"], r["IDprestation"], "", "", "", "", "", "", ""])
    noms = ("inventaire.json", "inventaire.html", "inventaire.csv", "validation_comptable.csv")
    (dossier / "SHA256SUMS.txt").write_text("".join(_empreinte(dossier / n) + "  " + n + "\n" for n in noms), encoding="ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--sqlite", metavar="COPIE_DATA.dat")
    groupe.add_argument("--mysql-base", metavar="pmsl_recette_rc81_DATA")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-utilisateur", default="audit_rc81")
    parser.add_argument("--copie-confirmee", action="store_true", required=True,
                        help="attester que la cible est une copie isolée, jamais la production")
    parser.add_argument("--date-reference", type=date_iso, required=True)
    parser.add_argument("--sortie", required=True, help="nouveau dossier de rapport, ne doit pas exister")
    args = parser.parse_args(argv)
    if Path(args.sortie).exists():
        parser.error("Le dossier de sortie existe déjà ; choisir un nouveau dossier")
    contexte = (ouvrir_sqlite(args.sqlite) if args.sqlite else
                ouvrir_mysql(args.mysql_base, args.mysql_port, args.mysql_utilisateur,
                             getpass.getpass("Mot de passe du compte SELECT de la copie : ")))
    try:
        with contexte as (lire, source):
            rapport = ConstruireInventaire(lire, args.date_reference)
        rapport["source"] = source
        rapport["code_audit"] = {
            "cli_sha256": _empreinte(Path(__file__).resolve()),
            "module_sha256": _empreinte(Path(__file__).resolve().parents[1] / "noethys/Utils/UTILS_Audit_cotisations.py"),
            "statut": "audit renforcé externe ; absent du binaire RC8.1 publié le 19/10/2026",
        }
        rapport["genere_le"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        exporter(rapport, args.sortie)
    except Exception as exc:
        # Erreur explicite, aucun rapport « zéro anomalie » après une erreur SQL.
        print("AUDIT INTERROMPU : " + str(exc), file=sys.stderr)
        return 2
    print("Inventaire terminé : %s cotisations signalées. Aucune régularisation." % rapport["cotisations_signalees"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
