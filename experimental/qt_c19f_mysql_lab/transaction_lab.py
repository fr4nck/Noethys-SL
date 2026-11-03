"""C19f - laboratoire transactionnel MySQL 100 % jetable.

INTERDIT EN PRODUCTION. Ce module est sous experimental/, jamais importe
par noethys_qt ni par le moteur wx. Toutes les ecritures visent le schema
invente "qt_c19f_lab" du conteneur local GitHub Actions. Pas de
facturation Noethys, de numeros legaux, ni de droits authentifies PMSL.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from dataclasses import dataclass

SCHEMA = "qt_c19f_lab"
MARKER = "NOETHYS_C19F_FAKE_MYSQL_ONLY_20261103"
ACTION = "facturation_factures/creer"


class Refused(ValueError):
    """Operation fictive refusee avant toute emission de facture."""


class InjectedFailure(RuntimeError):
    """Panne experimentale volontaire : la transaction doit etre annulee."""


@dataclass(frozen=True)
class Intent:
    actor: int
    session_key: str
    family: int
    payer: int
    activities: tuple[int, ...]
    prestations: tuple[int, ...]
    idempotency_key: str


def _ident(value):
    return type(value) is int and value > 0


def _positive_ids(values):
    return (
        type(values) is tuple and bool(values) and len(values) <= 32
        and all(_ident(x) for x in values)
        and len(values) == len(set(values))
    )


def _validate_intent(intent):
    if not isinstance(intent, Intent):
        raise Refused("C19f : requete inconnue")
    if not all(_ident(x) for x in (intent.actor, intent.family, intent.payer)):
        raise Refused("C19f : identifiant invalide")
    if not _positive_ids(intent.activities) or not _positive_ids(intent.prestations):
        raise Refused("C19f : selection vide, invalide ou dupliquee")
    if (
        type(intent.session_key) is not str or not intent.session_key
        or len(intent.session_key) > 80
        or type(intent.idempotency_key) is not str
        or not intent.idempotency_key or len(intent.idempotency_key) > 80
    ):
        raise Refused("C19f : session ou cle d'idempotence invalide")
    # Ordre canonique pour une cle idempotente, sans arrondir de montant.
    data = (
        intent.actor, intent.session_key, intent.family, intent.payer,
        sorted(intent.activities), sorted(intent.prestations),
    )
    fingerprint = hashlib.sha256(
        json.dumps(data, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return fingerprint


def _connection_options():
    """Refuse meme de se connecter hors du runner ET du conteneur fictif."""
    expected = {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "fr4nck/Noethys-SL",
        "GITHUB_REF": "refs/heads/qt",
        "C19F_DISPOSABLE_MYSQL": "yes",
        "C19F_MYSQL_HOST": "127.0.0.1",
        "C19F_MYSQL_PORT": "33067",
        "C19F_MYSQL_DATABASE": SCHEMA,
        "C19F_MYSQL_USER": "qt_c19f",
    }
    for key, expected_value in expected.items():
        if os.environ.get(key) != expected_value:
            raise PermissionError("C19f : serveur et environnement de test non autorises")
    password = os.environ.get("C19F_MYSQL_PASSWORD")
    if not password:
        raise PermissionError("C19f : mot de passe synthetique absent")
    return dict(
        host="127.0.0.1", port=33067, user="qt_c19f",
        password=password, database=SCHEMA, charset="utf8mb4",
        autocommit=False, connect_timeout=5, read_timeout=8,
        write_timeout=8,
    )


def connect():
    """Connexion uniquement au conteneur MySQL CI ; aucun profil utilisateur."""
    opts = _connection_options()
    import pymysql  # dependency installed ONLY on disposable CI runners
    db = pymysql.connect(**opts)
    with db.cursor() as cur:
        cur.execute("SET SESSION innodb_lock_wait_timeout=6")
    return db


def _require_marker(cur):
    cur.execute("SELECT magic FROM c19f_marker WHERE id=1")
    if cur.fetchone() != (MARKER,):
        raise PermissionError("C19f : schema non marque comme jetable")


def _in_placeholders(values):
    # length is validated before calling this helper
    return ", ".join(["%s"] * len(values))


def simulate_transaction(intent: Intent, *, inject_failure=None) -> int:
    """Transaction MySQL experimentale, JAMAIS utilisable par Noethys.

    Aucune methode d'import/migration, jamais de facture commerciale.
    Toutes les lectures de session, droits, periode et prestations ainsi
    que les INSERT/UPDATE sont dans une transaction InnoDB.
    """
    signature = _validate_intent(intent)
    if inject_failure not in (None, "after_header", "after_first_line"):
        raise ValueError("Point de panne experimentale inconnu")
    db = connect()
    try:
        db.begin()
        try:
            with db.cursor() as cur:
                _require_marker(cur)
                # La session est une fixture inventee, pas un jeton PMSL.
                cur.execute(
                    "SELECT actor, revoked, expires FROM c19f_sessions "
                    "WHERE session_key=%s FOR UPDATE",
                    (intent.session_key,),
                )
                row = cur.fetchone()
                if row is None or row[0] != intent.actor or row[1] != 0:
                    raise Refused("C19f : session refusee")
                cur.execute("SELECT UTC_TIMESTAMP()")
                if row[2] is None or row[2] <= cur.fetchone()[0]:
                    raise Refused("C19f : session expiree")

                # Verrou par compte payeur : deux transactions sur la meme
                # famille/payer ne peuvent attribuer les memes prestations.
                cur.execute(
                    "SELECT family_id FROM c19f_payers WHERE id=%s FOR UPDATE",
                    (intent.payer,),
                )
                row = cur.fetchone()
                if row is None or row[0] != intent.family:
                    raise Refused("C19f : compte payeur hors famille")

                cur.execute(
                    "SELECT id, fingerprint FROM c19f_invoices "
                    "WHERE idempotency_key=%s FOR UPDATE",
                    (intent.idempotency_key,),
                )
                previous = cur.fetchone()
                if previous is not None:
                    if previous[1] != signature:
                        raise Refused("C19f : cle rejouee avec un autre perimetre")
                    db.commit()
                    return previous[0]

                # Verification exhaustive des droits, aucune permission
                # implicite pour l'absence d'activite ou de regle.
                for activity in sorted(intent.activities):
                    cur.execute(
                        "SELECT allowed FROM c19f_rights WHERE actor=%s "
                        "AND activity=%s AND permission_name=%s FOR UPDATE",
                        (intent.actor, activity, ACTION),
                    )
                    if cur.fetchone() != (1,):
                        raise Refused("C19f : droit non atteste sur toutes les activites")

                cur.execute(
                    "SELECT id, family_id, payer_id, activity_id, service_day, "
                    "raw_amount, invoice_id FROM c19f_prestations "
                    "WHERE id IN (" + _in_placeholders(intent.prestations) + ") "
                    "ORDER BY id FOR UPDATE",
                    tuple(intent.prestations),
                )
                lines = cur.fetchall()
                if len(lines) != len(intent.prestations):
                    raise Refused("C19f : prestation absente")
                if {line[3] for line in lines} != set(intent.activities):
                    raise Refused("C19f : activites des prestations non exhaustives")
                for line in lines:
                    if line[1] != intent.family or line[2] != intent.payer:
                        raise Refused("C19f : prestation hors compte payeur")
                    if line[6] is not None:
                        raise Refused("C19f : prestation deja attribuee")
                    # Le montant brut est preserve sous sa forme textuelle ;
                    # aucun calcul tarifaire ni arrondi de facture.
                    from decimal import Decimal, InvalidOperation
                    try:
                        if not Decimal(line[5]).is_finite():
                            raise InvalidOperation("non fini")
                    except (TypeError, InvalidOperation):
                        raise Refused("C19f : montant non qualifie")

                    cur.execute(
                        "SELECT id FROM c19f_periods "
                        "WHERE start_day<=%s AND end_day>=%s "
                        "AND (lock_prestations=1 OR lock_invoices=1) "
                        "LIMIT 1 FOR UPDATE",
                        (line[4], line[4]),
                    )
                    if cur.fetchone() is not None:
                        raise Refused("C19f : periode verrouillee")

                cur.execute(
                    "INSERT INTO c19f_invoices "
                    "(idempotency_key, fingerprint, actor, family_id, payer_id) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (intent.idempotency_key, signature, intent.actor,
                     intent.family, intent.payer),
                )
                invoice_id = cur.lastrowid
                if inject_failure == "after_header":
                    raise InjectedFailure("Panne apres en-tete fictif")

                for idx, prestation_id in enumerate(sorted(intent.prestations)):
                    cur.execute(
                        "UPDATE c19f_prestations SET invoice_id=%s "
                        "WHERE id=%s AND invoice_id IS NULL",
                        (invoice_id, prestation_id),
                    )
                    if cur.rowcount != 1:
                        raise Refused("C19f : prestation modifiee par une concurrence")
                    cur.execute(
                        "INSERT INTO c19f_invoice_lines(invoice_id, prestation_id) "
                        "VALUES(%s,%s)",
                        (invoice_id, prestation_id),
                    )
                    if inject_failure == "after_first_line" and idx == 0:
                        raise InjectedFailure("Panne apres premiere ligne fictive")
            db.commit()
            return invoice_id
        except BaseException:
            db.rollback()
            raise
    finally:
        db.close()


def assert_disposable_container_is_new():
    """Prevol de schema: refuse d'alterer une base deja peuplee.

    Fonction uniquement utilisee par la fixture CI, AVANT toute table.
    """
    db = connect()
    try:
        with db.cursor() as cur:
            cur.execute("SHOW FULL TABLES")
            if cur.fetchall():
                raise PermissionError("C19f : base non vide, creation refusee")
    finally:
        db.close()


SCHEMA_SQL = (
    """CREATE TABLE c19f_marker (
         id INT PRIMARY KEY, magic VARCHAR(100) NOT NULL
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_sessions (
         session_key VARCHAR(80) PRIMARY KEY, actor INT NOT NULL,
         revoked TINYINT NOT NULL, expires DATETIME NOT NULL
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_payers (
         id INT PRIMARY KEY, family_id INT NOT NULL
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_rights (
         actor INT NOT NULL, activity INT NOT NULL,
         permission_name VARCHAR(80) NOT NULL, allowed TINYINT NOT NULL,
         PRIMARY KEY(actor, activity, permission_name)
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_periods (
         id INT PRIMARY KEY AUTO_INCREMENT, start_day DATE NOT NULL,
         end_day DATE NOT NULL, lock_prestations TINYINT NOT NULL,
         lock_invoices TINYINT NOT NULL
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_invoices (
         id INT PRIMARY KEY AUTO_INCREMENT,
         idempotency_key VARCHAR(80) NOT NULL UNIQUE,
         fingerprint CHAR(64) NOT NULL,
         actor INT NOT NULL, family_id INT NOT NULL, payer_id INT NOT NULL
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_prestations (
         id INT PRIMARY KEY, family_id INT NOT NULL, payer_id INT NOT NULL,
         activity_id INT NOT NULL, service_day DATE NOT NULL,
         raw_amount VARCHAR(50) NOT NULL,
         invoice_id INT NULL,
         INDEX(invoice_id)
       ) ENGINE=InnoDB""",
    """CREATE TABLE c19f_invoice_lines (
         invoice_id INT NOT NULL, prestation_id INT NOT NULL UNIQUE,
         PRIMARY KEY(invoice_id, prestation_id)
       ) ENGINE=InnoDB""",
)


def create_disposable_schema_for_tests():
    """Initialisation uniquement de tables c19f_* dans une base CI VIDE."""
    assert_disposable_container_is_new()
    db = connect()
    try:
        with db.cursor() as cur:
            for statement in SCHEMA_SQL:
                cur.execute(statement)
            cur.execute(
                "INSERT INTO c19f_marker VALUES (1,%s)", (MARKER,),
            )
        db.commit()
    finally:
        db.close()


def reset_fictive_data_for_tests():
    """Uniquement sur une base deja marquee, jamais DROP/TRUNCATE."""
    db = connect()
    try:
        db.begin()
        try:
            with db.cursor() as cur:
                _require_marker(cur)
                for table in (
                    "c19f_invoice_lines", "c19f_invoices",
                    "c19f_periods", "c19f_prestations",
                    "c19f_rights", "c19f_payers", "c19f_sessions",
                ):
                    cur.execute("DELETE FROM " + table)
                cur.execute(
                    "INSERT INTO c19f_sessions VALUES "
                    "('fake-session-7',7,0,'2030-01-01 00:00:00'),"
                    "('fake-session-8',8,0,'2030-01-01 00:00:00')"
                )
                cur.execute("INSERT INTO c19f_payers VALUES (201,100),(202,101)")
                cur.execute(
                    "INSERT INTO c19f_rights VALUES "
                    "(7,1,%s,1),(7,2,%s,1),(8,1,%s,0)",
                    (ACTION, ACTION, ACTION),
                )
                cur.execute(
                    "INSERT INTO c19f_prestations VALUES "
                    "(301,100,201,1,'2026-10-05','12.005',NULL),"
                    "(302,100,201,2,'2026-10-06','-1.005',NULL),"
                    "(303,101,202,2,'2026-10-07','18.50',NULL),"
                    "(304,100,201,1,'2026-10-08','1000.0003',NULL)"
                )
            db.commit()
        except BaseException:
            db.rollback()
            raise
    finally:
        db.close()
