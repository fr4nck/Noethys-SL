"""C19g: projection MySQL strictement fictive des champs DATA_Tables.

Tables de reference (prestations, factures, comptes_payeurs, inscriptions,
consommations, ventilation, periodes_gestion), mais UNIQUEMENT dans la
base jetable qt_c19g_lab sur un runner GitHub Actions.
Pas d'execution wx, pas d'ecriture metier, pas de calcul de tarif.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from .schema_contract import REQUIRED, projection_ddl, limitations

MARKER = "NOETHYS_C19G_PROJECTION_FICTIVE_20261103"
DBNAME = "qt_c19g_lab"


def _connection_options():
    required = {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "fr4nck/Noethys-SL",
        "GITHUB_REF": "refs/heads/qt",
        "C19G_DISPOSABLE_MYSQL": "yes",
        "C19G_MYSQL_HOST": "127.0.0.1",
        "C19G_MYSQL_PORT": "33068",
        "C19G_MYSQL_DATABASE": DBNAME,
        "C19G_MYSQL_USER": "qt_c19g",
    }
    for key, val in required.items():
        if os.environ.get(key) != val:
            raise PermissionError("C19g : contexte jetable non atteste : " + key)
    password = os.environ.get("C19G_MYSQL_PASSWORD")
    if not password:
        raise PermissionError("C19g : mot de passe synthetique absent")
    return {
        "host": "127.0.0.1", "port": 33068, "user": "qt_c19g",
        "password": password, "database": DBNAME, "charset": "utf8mb4",
        "autocommit": False, "connect_timeout": 5, "read_timeout": 8,
        "write_timeout": 8,
    }


def _connect():
    import pymysql
    return pymysql.connect(**_connection_options())


def _marker(cursor):
    cursor.execute("SELECT magic FROM c19g_marker WHERE id=1")
    if cursor.fetchone() != (MARKER,):
        raise PermissionError("C19g : marqueur de fixture absent ou modifie")


def create_empty_projection():
    """Exige une base initialement VIDE, jamais de DROP ou TRUNCATE."""
    db = _connect()
    try:
        with db.cursor() as cur:
            cur.execute("SHOW TABLES")
            if cur.fetchall():
                raise PermissionError("C19g : database non vide")
            # DDL contient UNIQUEMENT les projections du schema officiel.
            for ddl in projection_ddl():
                cur.execute(ddl)
            cur.execute(
                "CREATE TABLE c19g_marker("
                "id INT NOT NULL PRIMARY KEY, magic VARCHAR(100) NOT NULL"
                ") ENGINE=InnoDB"
            )
            cur.execute("INSERT INTO c19g_marker VALUES (1,%s)", (MARKER,))
        db.commit()
    finally:
        db.close()


def reset_synthetic_rows():
    """Seed fictif, exclusivement si la base est exactement la projection."""
    db = _connect()
    try:
        db.begin()
        try:
            with db.cursor() as cur:
                _marker(cur)
                cur.execute("SHOW TABLES")
                names = {row[0] for row in cur.fetchall()}
                if names != set(REQUIRED) | {"c19g_marker"}:
                    raise PermissionError("C19g : tables de projection inattendues")
                for table in (
                    "ventilation", "consommations", "inscriptions",
                    "prestations", "factures", "periodes_gestion",
                    "comptes_payeurs",
                ):
                    cur.execute("DELETE FROM " + table)
                cur.execute(
                    "INSERT INTO comptes_payeurs "
                    "(IDcompte_payeur,IDfamille) "
                    "VALUES(201,100),(202,101)"
                )
                cur.execute(
                    "INSERT INTO inscriptions "
                    "(IDinscription,IDindividu,IDfamille,IDactivite,IDcompte_payeur) "
                    "VALUES(501,10,100,1,201),(503,10,100,2,201),"
                    "(502,20,101,2,202)"
                )
                cur.execute(
                    "INSERT INTO factures "
                    "(IDfacture,numero,IDcompte_payeur,date_edition,"
                    "date_debut,date_fin,total,regle,solde) "
                    "VALUES(901,78001,202,'2026-10-07',"
                    "'2026-10-01','2026-10-31',18.50,0,18.50)"
                )
                cur.execute(
                    "INSERT INTO prestations "
                    "(IDprestation,IDcompte_payeur,date,montant,IDactivite,"
                    "IDfacture,IDfamille,IDindividu,forfait) VALUES "
                    "(301,201,'2026-10-05',12.005,1,NULL,100,10,0),"
                    "(302,201,'2026-10-06',-1.005,2,NULL,100,10,0),"
                    "(303,202,'2026-10-07',18.50,2,901,101,20,0),"
                    "(304,201,'2026-10-08',0.00,1,NULL,100,10,0)"
                )
                cur.execute(
                    "INSERT INTO consommations "
                    "(IDconso,IDindividu,IDinscription,IDactivite,date,"
                    "etat,IDcompte_payeur,IDprestation,verrouillage) VALUES "
                    "(1,10,501,1,'2026-10-05','present',201,301,0),"
                    "(2,10,501,1,'2026-10-05','present',201,301,0),"
                    "(3,10,503,2,'2026-10-06','present',201,302,0),"
                    "(4,20,502,2,'2026-10-07','present',202,303,0)"
                )
                cur.execute(
                    "INSERT INTO ventilation "
                    "(IDventilation,IDcompte_payeur,IDreglement,"
                    "IDprestation,montant) VALUES (1,201,77,301,3.50)"
                )
                cur.execute(
                    "INSERT INTO periodes_gestion "
                    "(IDperiode,date_debut,date_fin,verrou_consommations,"
                    "verrou_prestations,verrou_factures) "
                    "VALUES(1,'2026-10-06','2026-10-06',0,1,0)"
                )
            db.commit()
        except BaseException:
            db.rollback()
            raise
    finally:
        db.close()


def _ids(values):
    if (
        type(values) is not tuple or not values or len(values) > 32
        or any(type(x) is not int or x <= 0 for x in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("C19g : identifiants exacts, positifs, sans doublon requis")
    return values


def _id(value):
    if type(value) is not int or value <= 0:
        raise ValueError("C19g : identifiant positif entier requis")
    return value


@dataclass(frozen=True)
class SourceLine:
    id: int
    activity_id: int
    family_id: int
    payer_id: int
    amount_float: float | None
    invoice_id: int | None
    consumption_count: int
    ventilation_count: int
    alerts: tuple[str, ...]


@dataclass(frozen=True)
class SourceAudit:
    lines: tuple[SourceLine, ...]
    alerts: tuple[str, ...]
    executable: bool = False

    def __post_init__(self):
        if self.executable:
            raise ValueError("C19g ne peut emettre de facture.")


def inspect_synthetic_prestations(
    *, prestation_ids, family_id, payer_id,
):
    """Transaction explicite READ ONLY, aucun writer, aucun total.

    Chaque lien de consommation et inscription est relu via ses IDs,
    sans jointure croisee qui multiplierait les ventilations.
    """
    requested = _ids(prestation_ids)
    _id(family_id)
    _id(payer_id)
    db = _connect()
    try:
        with db.cursor() as cur:
            cur.execute("START TRANSACTION READ ONLY")
            _marker(cur)
            query = (
                "SELECT p.IDprestation,p.IDactivite,p.IDfamille,"
                "p.IDcompte_payeur,p.montant,p.IDfacture,"
                "cp.IDfamille,f.IDcompte_payeur,p.date,p.IDindividu "
                "FROM prestations p "
                "LEFT JOIN comptes_payeurs cp "
                "ON cp.IDcompte_payeur=p.IDcompte_payeur "
                "LEFT JOIN factures f ON f.IDfacture=p.IDfacture "
                "WHERE p.IDprestation IN ("
                + ",".join("%s" for _ in requested)
                + ") ORDER BY p.IDprestation"
            )
            cur.execute(query, requested)
            fetched = {row[0]: row for row in cur.fetchall()}
            results = []
            all_alerts = set(limitations())
            for prest_id in requested:
                row = fetched.get(prest_id)
                if row is None:
                    results.append(SourceLine(
                        prest_id, 0, 0, 0, None, None, 0, 0,
                        ("PRESTATION_ABSENTE",),
                    ))
                    all_alerts.add("PRESTATION_ABSENTE")
                    continue
                (_, activity, family, payer, amount, invoice,
                 payer_family, invoice_payer, service_day, prest_individual) = row
                alerts = []
                if not activity or activity <= 0:
                    alerts.append("ACTIVITE_NON_QUALIFIEE")
                if family != family_id or payer != payer_id:
                    alerts.append("FAMILLE_OU_PAYEUR_DIVERGENT")
                if payer_family != family:
                    alerts.append("RELATION_COMPTE_PAYEUR_INCOHERENTE")
                if invoice is not None:
                    alerts.append("DEJA_FACTUREE")
                    if invoice_payer is None or invoice_payer != payer:
                        alerts.append("FACTURE_ABSENTE_OU_COMPTE_DIVERGENT")
                # Verifier chaque consommation distinctement, y compris
                # le rattachement a l'inscription. Aucun calcul tarifaire.
                cur.execute(
                    "SELECT c.IDactivite,c.IDindividu,c.IDcompte_payeur,"
                    "c.verrouillage,i.IDactivite,i.IDindividu,"
                    "i.IDfamille,i.IDcompte_payeur "
                    "FROM consommations c "
                    "LEFT JOIN inscriptions i "
                    "ON i.IDinscription=c.IDinscription "
                    "WHERE c.IDprestation=%s",
                    (prest_id,),
                )
                cons = cur.fetchall()
                for c in cons:
                    if (
                        c[0] != activity or c[1] != prest_individual or c[2] != payer
                        or c[4] != c[0] or c[5] != c[1]
                        or c[6] != family or c[7] != payer
                    ):
                        alerts.append("CONSOMMATION_INSCRIPTION_DIVERGENTE")
                    if c[3] not in (0, None):
                        alerts.append("CONSOMMATION_VERROUILLEE")
                if len(cons) > 1:
                    alerts.append("PRESTATION_PARTAGEE_NON_MULTIPLIABLE")
                cur.execute(
                    "SELECT COUNT(*) FROM ventilation "
                    "WHERE IDprestation=%s", (prest_id,)
                )
                vent = cur.fetchone()[0]
                if vent:
                    alerts.append("VENTILATION_PRESENTE")
                cur.execute(
                    "SELECT COUNT(*) FROM periodes_gestion "
                    "WHERE date_debut<=%s AND date_fin>=%s "
                    "AND (verrou_prestations=1 OR verrou_factures=1)",
                    (service_day, service_day),
                )
                if cur.fetchone()[0]:
                    alerts.append("PERIODE_VERROUILLEE")
                alerts = tuple(dict.fromkeys(alerts))
                all_alerts.update(alerts)
                results.append(SourceLine(
                    prest_id, activity, family, payer, amount, invoice,
                    len(cons), vent, alerts,
                ))
        db.rollback()
        return SourceAudit(tuple(results), tuple(sorted(all_alerts)))
    finally:
        db.close()
