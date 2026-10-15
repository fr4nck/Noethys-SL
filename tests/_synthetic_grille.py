"""Harnais #427 : methode reelle, aucune importation applicative/profil/reseau.

Seules Sauvegarde et Executermany sont compilees depuis leurs sources AST.
Les connexions sont exclusivement SQLite explicites ou des doubles en memoire.
"""
import ast
import copy
import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('IDindividu', 'IDinscription', 'IDactivite', 'date', 'IDunite',
          'IDgroupe', 'heure_debut', 'heure_fin', 'etat', 'verrouillage',
          'date_saisie', 'IDutilisateur', 'IDcategorie_tarif', 'IDcompte_payeur',
          'IDprestation', 'quantite', 'etiquettes', 'IDevenement',
          'badgeage_debut', 'badgeage_fin')


def method(path, classname, name, namespace):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class Database:
    def __init__(self, connection=None, fail=False):
        self.connexion = connection
        self.fail = fail
        self.calls = []
        self.history = []
        self.closed = False
        self.isNetwork = False
        self.cursor = connection.cursor() if connection else None

    def Executermany(self, req, values, commit=True):
        self.calls.append(('many', req, copy.deepcopy(values), commit))
        if self.fail:
            raise RuntimeError('synthetic write failure')
        if self.cursor:
            self.cursor.executemany(req, values)
        if commit:
            self.Commit()

    def ExecuterReq(self, req):
        self.calls.append(('execute', req))
        if self.cursor:
            self.cursor.execute(req)

    def Commit(self):
        self.calls.append(('commit',))
        if self.connexion:
            self.connexion.commit()

    def Close(self):
        self.calls.append(('close',))
        self.closed = True
        if self.cursor:
            self.cursor.close()
        # La connexion appartient au test et reste ouverte pour les assertions.


def history(actions, DB):
    DB.history.extend(copy.deepcopy(actions))
    DB.Commit()  # Meme frontiere que UTILS_Historique.InsertActions(DB=DB).


def saver(db, source=None, convert=None):
    namespace = dict(GestionDB=SimpleNamespace(DB=lambda: db), copy=copy,
                     datetime=datetime, ConvertListeToStr=convert or (lambda x: ';'.join(map(str, x))),
                     UTILS_Historique=SimpleNamespace(InsertActions=history),
                     UTILS_Adhesions=SimpleNamespace(AUTO_CREATION_SUSPENDUE=True))
    return method(source or ROOT / 'noethys/Ctrl/CTRL_Grille.py', 'CTRL', 'Sauvegarde', namespace)


def conso(id=1, statut=None, etat='attente'):
    values = dict.fromkeys(FIELDS)
    values.update(IDconso=id, statut=statut, etat=etat, IDinscription=1,
                  IDactivite=1, IDgroupe=1, IDfamille=1, IDutilisateur=1,
                  IDcompte_payeur=1, quantite=1, etiquettes=[],
                  date_saisie=datetime.date(2026, 1, 1))
    return SimpleNamespace(**values)


def grille(consos):
    return SimpleNamespace(dictPrestations={}, listePrestationsModifiees=[],
                           listePrestationsSupprimees=[], dictConsoIndividus={
                               1: {datetime.date(2026, 1, 2): {1: consos}}},
                           dictUnites={1: {'abrege': 'SYN'}},
                           listeConsoSupprimees=[], dictMemos={})


def schema(connection):
    connection.execute('CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, %s)' %
                       ', '.join(FIELDS))
