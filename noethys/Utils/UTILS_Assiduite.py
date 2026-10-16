# -*- coding: utf-8 -*-
"""Assiduité par journée enfant/activité. Activation du journal explicite seulement.

Les triggers s'exécutent dans la transaction de la consommation : aucun commit
ni changement de tarification/pointage dans les chemins de sauvegarde existants.
Le journal conserve des identifiants, jamais noms, messages ou montants.
"""
import datetime as dt
from collections import defaultdict

TABLE = 'noethys_sl_assiduite_v1'
TRIGGERS = {op: 'nsl_assiduite_v1_' + op for op in ('insert', 'update', 'delete')}
ACTIVE = frozenset(('reservation', 'present', 'absentj', 'absenti'))
POINTED = frozenset(('present', 'absentj', 'absenti'))


def query(db, sql):
    if not db.ExecuterReq(sql):
        raise RuntimeError("Impossible de lire les données d'assiduité.")
    return db.ResultatReq()


def trigger_names(db):
    if db.isNetwork:
        rows = query(db, "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()")
    else:
        rows = query(db, "SELECT name FROM sqlite_master WHERE type='trigger'")
    return {row[0] for row in rows}


def status(db):
    if TABLE not in {r[0] for r in query(db, "SHOW TABLES" if db.isNetwork else
                                       "SELECT name FROM sqlite_master WHERE type='table'")}:
        if set(TRIGGERS.values()) & trigger_names(db):
            raise RuntimeError("Le journal a disparu alors que ses déclencheurs sont présents.")
        return None
    if not set(TRIGGERS.values()).issubset(trigger_names(db)):
        raise RuntimeError("Journal incomplet : réactiver le suivi avant de calculer les annulations.")
    rows = query(db, "SELECT IDlog, horodatage FROM %s WHERE operation='ready' ORDER BY IDlog LIMIT 1" % TABLE)
    if not rows:
        raise RuntimeError("Activation du journal incomplète.")
    return rows[0]


def activate(db):
    """Migration volontaire sur connexion dédiée. Idempotente, sans reprise fictive.

    MySQL : InnoDB exigé pour conserver l'atomicité avec les consommations.
    Aucun DROP et aucun changement des tables métier. Échec visible, réparable.
    """
    locked = False
    try:
        if db.isNetwork:
            lock = query(db, "SELECT GET_LOCK(CONCAT('nsl_assiduite:', SHA1(DATABASE())), 10)")
            if not lock or lock[0][0] != 1:
                raise RuntimeError("Une activation est déjà en cours.")
            locked = True
            engine = query(db, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='consommations'")
            if not engine or engine[0][0].upper() != 'INNODB':
                raise RuntimeError("Le suivi nécessite des consommations InnoDB ; aucune conversion automatique.")
        else:
            db.cursor.execute('BEGIN IMMEDIATE')
        pk = 'BIGINT PRIMARY KEY AUTO_INCREMENT' if db.isNetwork else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        suffix = ' ENGINE=InnoDB' if db.isNetwork else ''
        db.cursor.execute("""CREATE TABLE IF NOT EXISTS %s (
            IDlog %s, horodatage DATETIME NOT NULL,
            operation VARCHAR(16) NOT NULL, IDconso INTEGER, IDfamille INTEGER,
            IDindividu INTEGER, IDactivite INTEGER, date DATE, etat VARCHAR(20))%s""" % (TABLE, pk, suffix))
        if db.isNetwork:
            engine = query(db, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'" % TABLE)
            if not engine or engine[0][0].upper() != 'INNODB':
                raise RuntimeError("Le journal existant n'est pas InnoDB ; aucune conversion automatique.")
        indexes = {r[0] for r in query(db,
            "SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='%s'" % TABLE
            if db.isNetwork else "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='%s'" % TABLE)}
        for name, fields in (('nsl_assiduite_date', 'date, IDactivite, IDlog'),
                             ('nsl_assiduite_conso', 'IDconso, IDlog')):
            if name not in indexes:
                db.cursor.execute('CREATE INDEX %s ON %s (%s)' % (name, TABLE, fields))
        names = trigger_names(db)
        clock = 'UTC_TIMESTAMP()' if db.isNetwork else 'CURRENT_TIMESTAMP'
        for op, name in TRIGGERS.items():
            if name in names:
                continue
            ref = 'OLD' if op == 'delete' else 'NEW'
            body = """INSERT INTO %s
                (horodatage, operation, IDconso, IDfamille, IDindividu, IDactivite, date, etat)
                VALUES (%s, '%s', %s.IDconso,
                (SELECT IDfamille FROM inscriptions WHERE IDinscription=%s.IDinscription),
                %s.IDindividu, %s.IDactivite, %s.date, %s.etat)""" % (TABLE, clock, op, ref, ref, ref, ref, ref, ref)
            fields = ('etat', 'IDindividu', 'IDactivite', 'IDinscription', 'date')
            if db.isNetwork:
                if op == 'update':
                    condition = ' AND '.join('OLD.%s <=> NEW.%s' % (f, f) for f in fields)
                    body = 'BEGIN IF NOT (%s) THEN %s; END IF; END' % (condition, body)
                sql = 'CREATE TRIGGER %s AFTER %s ON consommations FOR EACH ROW %s' % (name, op.upper(), body)
            else:
                condition = ' WHEN ' + ' OR '.join('OLD.%s IS NOT NEW.%s' % (f, f) for f in fields) if op == 'update' else ''
                sql = 'CREATE TRIGGER %s AFTER %s ON consommations%s BEGIN %s; END' % (name, op.upper(), condition, body)
            db.cursor.execute(sql)
        if not query(db, "SELECT IDlog FROM %s WHERE operation='ready'" % TABLE):
            db.cursor.execute("INSERT INTO %s (horodatage, operation) VALUES (%s, 'ready')" % (TABLE, clock))
        result = status(db)
        db.Commit()  # terminer aussi le snapshot de validation MySQL
        return result
    except Exception:
        db.connexion.rollback()
        raise
    finally:
        if locked:
            db.cursor.execute("SELECT RELEASE_LOCK(CONCAT('nsl_assiduite:', SHA1(DATABASE())))")
            db.cursor.fetchall()


def period(start, end, activities):
    start = dt.date.fromisoformat(str(start))
    end = dt.date.fromisoformat(str(end))
    if start > end:
        raise ValueError('La date de fin précède le début.')
    ids = sorted({int(i) for i in activities})
    if not ids or min(ids) <= 0:
        raise ValueError('Sélectionnez au moins une activité.')
    return "date BETWEEN '%s' AND '%s' AND IDactivite IN (%s)" % (start, end, ','.join(map(str, ids)))


def read(db, start, end, activities):
    """Deux taux indépendants ; pas d'écriture lors de la consultation."""
    # SQLite : garder le même snapshot pour le journal ET les consommations,
    # sans terminer une transaction appartenant à l'appelant. MySQL utilise
    # son snapshot REPEATABLE READ sur la connexion dédiée du dialogue.
    own_snapshot = not db.isNetwork and not db.connexion.in_transaction
    if own_snapshot:
        db.cursor.execute('BEGIN')
    try:
        return _read(db, start, end, activities)
    finally:
        if own_snapshot:
            db.connexion.rollback()


def _read(db, start, end, activities):
    where = period(start, end, activities)
    enabled = status(db)
    current = query(db, """SELECT i.IDfamille, c.IDindividu, c.IDactivite, c.date, c.etat
        FROM consommations c LEFT JOIN inscriptions i ON i.IDinscription=c.IDinscription
        WHERE %s""" % where.replace('date BETWEEN', 'c.date BETWEEN').replace('AND IDactivite', 'AND c.IDactivite'))
    events = []
    if enabled:
        events = query(db, """SELECT IDlog, operation, IDconso, IDfamille, IDindividu, IDactivite, date, etat
            FROM %s WHERE IDlog>%d AND %s ORDER BY IDlog""" % (TABLE, enabled[0], where))
    # Une insertion peut précéder la période retenue (changement de date).
    # Les seuls ID créés dans le suivi sont recherchés sans filtrage de date.
    created = set()
    if enabled:
        scoped = where.replace('date BETWEEN', 'e.date BETWEEN').replace('AND IDactivite', 'AND e.IDactivite')
        created = {r[0] for r in query(db, """SELECT DISTINCT c.IDconso FROM %s c
            INNER JOIN %s e ON e.IDconso=c.IDconso WHERE c.IDlog>%d AND c.operation='insert'
            AND e.IDlog>%d AND %s""" % (TABLE, TABLE, enabled[0], enabled[0], scoped))}
    return summarize(current, events, created, enabled)


def day_key(family, child, activity, day):
    return family, child, activity, str(day)[:10]


def summarize(current, events=(), created=(), enabled=None, today=None):
    today = str(today or dt.date.today())
    days = defaultdict(set)
    for family, child, activity, day, state in current:
        if state in ACTIVE:
            days[day_key(family, child, activity, day)].add(state)
    cohort = set()
    pointed_history = set()
    for _, operation, ident, family, child, activity, day, state in events:
        key = day_key(family, child, activity, day)
        if ident in created and operation != 'delete' and state == 'reservation':
            cohort.add(key)
        if state in POINTED:
            pointed_history.add(key)
    children = {}
    for key in sorted(set(days) | cohort, key=lambda x: tuple(str(v) for v in x)):
        family, child, activity, day = key
        row = children.setdefault((family, child), dict(family=family, child=child,
            reserved=0, cancelled=0, pointed=0, absent=0, justified=0,
            unjustified=0, partial=0, pending=0, details=[]))
        states = days.get(key, set())
        cancelled = key in cohort and not states and key not in pointed_history
        row['reserved'] += int(key in cohort)
        row['cancelled'] += int(cancelled)
        category = 'À venir'
        if cancelled:
            category = 'Annulée (réservations supprimées)'
        elif day <= today and states:
            if 'reservation' in states:
                row['pending'] += 1
                category = 'Pointage incomplet'
            else:
                row['pointed'] += 1
                if 'present' not in states:
                    row['absent'] += 1
                    reason = 'unjustified' if 'absenti' in states else 'justified'
                    row[reason] += 1
                    category = 'Absence injustifiée' if reason == 'unjustified' else 'Absence justifiée'
                elif states != {'present'}:
                    row['partial'] += 1
                    category = 'Absence partielle'
                else:
                    category = 'Présence'
        elif not states and key in pointed_history:
            category = 'Pointage supprimé : exclu des absences'
        row['details'].append(dict(date=day, activity=activity, category=category,
                                   tracked=key in cohort, states=sorted(states)))
    families = {}
    counts = ('reserved', 'cancelled', 'pointed', 'absent', 'justified', 'unjustified', 'partial', 'pending')
    for row in children.values():
        # Ne pas fusionner les enfants de familles non renseignées.
        key = row['family'] if row['family'] is not None else ('unknown', row['child'])
        target = families.setdefault(key, dict(family=row['family'], child=None,
                                             details=[], **{k: 0 for k in counts}))
        for k in counts:
            target[k] += row[k]
        target['details'].extend(dict(detail, child=row['child']) for detail in row['details'])
    for row in list(children.values()) + list(families.values()):
        row['cancellation_rate'] = 100 * row['cancelled'] / row['reserved'] if enabled and row['reserved'] else None
        row['absence_rate'] = 100 * row['absent'] / row['pointed'] if row['pointed'] else None
    return dict(children=list(children.values()), families=list(families.values()), enabled=enabled)
