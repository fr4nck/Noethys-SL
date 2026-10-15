"""Benchmark #427, sans profil ni connexion reseau.

python scripts/benchmark_grille_synthetic.py [--source fichier_CTRL_Grille.py]
Les durees sont CPU/client synthetiques, jamais un gain terrain/MySQL.
"""
import argparse
import ast
import json
import itertools
from pathlib import Path
import statistics
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from _synthetic_grille import Database, conso, grille, saver


def driver_counts(source):
    """Execute les methodes Python originales du pilote, transport remplace.

    Source mysqlclient officielle fournie explicitement, aucun import MySQL,
    connexion ou interpretation du module complet. Ne mesure pas le serveur.
    """
    tree = ast.parse(source.read_text(encoding='utf-8'))
    pattern = next(n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'RE_INSERT_VALUES' for t in n.targets))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BaseCursor')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
               and n.name in ('executemany', '_do_execute_many')]
    namespace = {'re': re}
    exec(compile(ast.Module(body=[pattern] + methods, type_ignores=[]), str(source), 'exec'), namespace)

    class Cursor:
        max_stmt_length = 65536
        executemany = namespace['executemany']
        _do_execute_many = namespace['_do_execute_many']

        def __init__(self):
            self.queries = 0

        def execute(self, query, args=None):
            self.queries += 1
            return 1

        def _get_db(self):
            return type('Encoding', (), {'encoding': 'utf8'})()

        def _mogrify(self, query, args):
            if isinstance(query, str):
                query = query.encode('utf8')
            return query % tuple(str(arg).encode('ascii') for arg in args)

    for size in (1, 10, 50):
        for operation, query in [('UPDATE', 'UPDATE consommations SET etat=%s WHERE IDconso=%s'),
                                 ('INSERT', 'INSERT INTO consommations (etat, IDconso) VALUES (%s, %s)')]:
            cursor = Cursor()
            cursor.executemany(query, [(1, i) for i in range(size)])
            print(json.dumps(dict(driver_operation=operation, rows=size, transport_calls=cursor.queries)))


def compare(source):
    count = 0
    for status, state, identifier in itertools.product(
            (None, 'ajout', 'modification', 'suppression', 'inconnu'),
            (None, 'attente', 'reservation'), (None, -1, 1)):
        results = []
        for path in (source, None):
            db = Database()
            error = None
            try:
                saver(db, source=path)(grille([conso(identifier, status, state), conso(2)]))
            except Exception as exc:
                error = (type(exc).__name__, str(exc))
            results.append((db.calls, db.history, error))
        assert results[0] == results[1], (status, state, identifier)
        count += 1
    print(json.dumps(dict(equivalent_scenarios=count,
                          compared=['SQL', 'values', 'history', 'commit', 'errors'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--driver-source', type=Path,
                        help='Optionnel : fichier officiel MySQLdb/cursors.py, transport simule')
    parser.add_argument('--compare-source', type=Path,
                        help='Compare SQL/historique/erreurs sur 45 cas avec un ancien fichier')
    args = parser.parse_args()
    if args.compare_source:
        compare(args.compare_source)
        return
    if args.driver_source:
        driver_counts(args.driver_source)
    for loaded in (50, 10000):
        for changed in (1, 10, 50):
            for status in ('modification', 'ajout'):
                g = grille([conso(i + 1, status if i < changed else None,
                                  'reservation' if i < changed else 'attente') for i in range(loaded)])
                durations = []
                for _ in range(9):
                    db = Database()
                    save = saver(db, source=args.source)
                    start = time.perf_counter()
                    save(g)
                    durations.append(1000 * (time.perf_counter() - start))
                print(json.dumps(dict(loaded=loaded, changed=changed, status=status,
                                      median_ms=round(statistics.median(durations), 3),
                                      sql_batches=sum(c[0] == 'many' for c in db.calls),
                                      commits=sum(c[0] == 'commit' for c in db.calls))))


if __name__ == '__main__':
    main()
