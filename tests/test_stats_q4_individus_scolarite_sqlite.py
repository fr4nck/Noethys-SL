# -*- coding: utf-8 -*-
"""Q4-B5 : quatre objets Ecoles/Niveaux avec vraies MAJ et SQL SQLite.

Les graphiques sont testes sur leurs donnees d'axes (figures capturees),
non sur le rendu Matplotlib, HTML, impression ou executable installe.
Les donnees sont exclusivement synthetiques.
"""
import ast
from collections import Counter
import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from tests.test_stats_q4_individus_genre_ages_sqlite import (
    FigureCapture, ObjetBase,
)

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"
MODELES_SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"
NOMS_ECOLES = {10: "Ecole A", 20: "Ecole B"}
NIVEAUX = {100: (1, "CP"), 200: (2, "CE1"), 300: (3, "CE2")}
CLASSES = (
    "Tableau_repartition_ecoles",
    "Graphe_repartition_ecoles",
    "Tableau_repartition_niveaux_scolaires",
    "Graphe_repartition_niveaux_scolaires",
)


class SQLiteScolarite:
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.requetes = []
        self.cursor.executescript("""
            CREATE TABLE individus(IDindividu INTEGER PRIMARY KEY);
            CREATE TABLE consommations(
                IDindividu INTEGER, date TEXT, etat TEXT, IDactivite INTEGER);
            CREATE TABLE scolarite(
                IDindividu INTEGER, IDecole INTEGER, IDniveau INTEGER,
                date_debut TEXT, date_fin TEXT);
            CREATE TABLE ecoles(IDecole INTEGER, nom TEXT);
            CREATE TABLE niveaux_scolaires(
                IDniveau INTEGER, ordre INTEGER, abrege TEXT);
        """)
        self.cursor.executemany(
            "INSERT INTO individus VALUES (?)", [(i,) for i in range(1, 9)])
        self.cursor.executemany(
            "INSERT INTO consommations VALUES (?,?,?,?)", [
                (1, "2026-04-01", "present", 1),
                (1, "2026-04-02", "present", 1),    # doublon meme enfant
                (2, "2026-04-01", "present", 1),
                (2, "2026-04-03", "present", 2),
                (3, "2026-04-01", "reservation", 2),
                (4, "2026-04-01", "present", 1),    # pas de scolarite
                (5, "2026-04-01", "present", 2),
                (6, "2026-04-01", "absent", 1),
                (7, "2025-04-01", "present", 1),    # hors periode
                (8, "2026-04-01", "present", 3),    # hors activite
            ])
        self.cursor.executemany(
            "INSERT INTO scolarite VALUES (?,?,?,?,?)", [
                (1, 10, 100, "2025-09-01", "2026-08-31"),
                (2, 10, 200, "2025-09-01", "2026-08-31"),
                (3, 20, 100, "2025-09-01", "2026-08-31"),
                (5, 20, 200, "2025-09-01", "2026-08-31"),
                (6, 20, 200, "2025-09-01", "2026-08-31"),
                (7, 20, 100, "2027-09-01", "2028-08-31"),
                (8, 10, 300, "2025-09-01", "2026-08-31"),
            ])
        self.cursor.executemany(
            "INSERT INTO ecoles VALUES (?,?)", sorted(NOMS_ECOLES.items()))
        self.cursor.executemany(
            "INSERT INTO niveaux_scolaires VALUES (?,?,?)", [
                (k, v[0], v[1]) for k, v in NIVEAUX.items()
            ])

    def ExecuterReq(self, sql):
        self.requetes.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.connexion.close()


def charger_vraies_classes():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    noms_fonctions = ("GetListeEcoles", "GetListeNiveauxScolaires")
    defs = [
        x for x in arbre.body
        if (isinstance(x, ast.FunctionDef) and x.name in noms_fonctions)
        or (isinstance(x, ast.ClassDef) and x.name in CLASSES)
    ]
    if len(defs) != len(noms_fonctions) + len(CLASSES):
        raise AssertionError("Source Q4-B5 changee, requalification obligatoire")
    modele = ast.parse(MODELES_SOURCE.read_text(encoding="utf-8"))
    caches = [
        x for x in modele.body if isinstance(x, ast.FunctionDef)
        and x.name in ("LireCacheStats", "EcrireCacheStats")
    ]
    if len(caches) != 2:
        raise AssertionError("Fonctions cache absentes")
    espace_cache = {}
    module = ast.Module(body=caches, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(MODELES_SOURCE), "exec"), espace_cache)
    modeles = SimpleNamespace(
        Tableau=ObjetBase, Graphe=ObjetBase,
        GetDatesPeriode=lambda p: (
            p["periode"]["date_debut"], p["periode"]["date_fin"]),
        GetConditionActivites=lambda p: "(" + ",".join(
            str(a) for a in p["listeActivites"]) + ")",
        LireCacheStats=espace_cache["LireCacheStats"],
        EcrireCacheStats=espace_cache["EcrireCacheStats"],
    )
    mpl = SimpleNamespace(
        cm=SimpleNamespace(hsv=lambda x: ("couleur", x)),
        pyplot=SimpleNamespace(setp=lambda *args, **kwargs: None),
    )
    environnement = {
        "MODELES": modeles, "matplotlib": mpl, "_": lambda x: x,
        "DICT_ECOLES": {}, "DICT_NIVEAUX_SCOLAIRES": {},
    }
    module = ast.Module(body=defs, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), environnement)
    return environnement


def parametres(mode="presents", activites=(1, 2), debut=None, fin=None):
    return {
        "mode": mode,
        "listeActivites": list(activites),
        "periode": {
            "date_debut": debut or datetime.date(2026, 1, 1),
            "date_fin": fin or datetime.date(2026, 12, 31),
        },
    }


def reference_independante(db, p):
    """Ecoles sur premier jour de periode; comptes par enfant et rattachement."""
    if p["mode"] == "inscrits":
        return [], []
    marques = ",".join("?" for _ in p["listeActivites"])
    sql = (
        "SELECT DISTINCT i.IDindividu, s.IDecole, s.IDniveau "
        "FROM individus i JOIN consommations c "
        "ON c.IDindividu=i.IDindividu "
        "LEFT JOIN scolarite s ON s.IDindividu=i.IDindividu "
        "AND s.date_debut<=? AND s.date_fin>=? "
        "WHERE c.date BETWEEN ? AND ? "
        "AND c.etat IN ('present','reservation') "
        "AND c.IDactivite IN (" + marques + ")"
    )
    args = (str(p["periode"]["date_debut"]), str(p["periode"]["date_debut"]),
            str(p["periode"]["date_debut"]), str(p["periode"]["date_fin"]),
            *p["listeActivites"])
    lignes = db.connexion.execute(sql, args).fetchall()
    ecoles = Counter(ecole for _, ecole, _ in lignes)
    niveaux = Counter(niveau for _, _, niveau in lignes)
    resultat_ecoles = sorted(
        [(nombre, NOMS_ECOLES.get(cle, "Ecole inconnue"))
         for cle, nombre in ecoles.items()], reverse=True)
    resultat_niveaux = sorted(
        [(NIVEAUX.get(cle, (0, "Niveau inconnu"))[0],
          nombre,
          NIVEAUX.get(cle, (0, "Niveau inconnu"))[1])
         for cle, nombre in niveaux.items()])
    return resultat_ecoles, resultat_niveaux


class Q4ScolariteSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteScolarite()
        self.source = charger_vraies_classes()

    def tearDown(self):
        self.db.Close()

    def verifier(self, p, graphes=True):
        ecoles_ref, niveaux_ref = reference_independante(self.db, p)
        for nom, ref in (
            ("Tableau_repartition_ecoles", ecoles_ref),
            ("Tableau_repartition_niveaux_scolaires", niveaux_ref),
        ):
            with self.subTest(mode=p["mode"], activites=p["listeActivites"],
                              objet=nom):
                tableau = self.source[nom]()
                tableau.MAJ(DB=self.db, dictParametres=p)
                attendu = (
                    [(label, nombre) for nombre, label in ref]
                    if nom.endswith("_ecoles")
                    else [(label, nombre) for _, nombre, label in ref]
                )
                self.assertEqual(tableau.lignes, attendu)
        if graphes:
            for nom, ref in (
                ("Graphe_repartition_ecoles", ecoles_ref),
                ("Graphe_repartition_niveaux_scolaires", niveaux_ref),
            ):
                with self.subTest(mode=p["mode"], objet=nom):
                    f = FigureCapture()
                    g = self.source[nom]()
                    self.assertIs(g.MAJ(
                        figure=f, DB=self.db, dictParametres=p), f)
                    self.assertEqual(len(f.axes), 1)
                    axe = f.axes[0]
                    self.assertEqual(
                        list(zip(axe.valeurs, axe.labels)),
                        ref if nom.endswith("_ecoles")
                        else [(n, label) for _, n, label in ref])
                    self.assertEqual(axe.options.get("autopct"), "%1.1f%%")
                    self.assertEqual(len(axe.couleurs), len(axe.valeurs))
                    self.assertEqual(axe.aspect, 1)

    def test_scolarite_present_et_doublons_reels(self):
        self.verifier(parametres())

    def test_filtre_une_activite(self):
        self.verifier(parametres(activites=(1,)))

    def test_inscrits_aucun_calcul_scolaire_historique(self):
        # Contrat actuel : la fonctionnalite scolaire n'existe qu'en presents.
        # Ce test n'avalise pas un choix metier de cacher l'ecole en inscrits.
        self.verifier(parametres("inscrits"), graphes=False)
        self.assertFalse(self.db.requetes)

    def test_sans_donnees_et_periode_non_couverte(self):
        self.verifier(parametres(activites=(99,)), graphes=False)
        self.verifier(parametres(
            debut=datetime.date(2027, 1, 1),
            fin=datetime.date(2027, 12, 31)), graphes=False)

    def test_cache_par_connexion_et_filtre(self):
        params = parametres()
        initial_ecoles = self.source["GetListeEcoles"](self.db, params)
        initial_niveaux = self.source["GetListeNiveauxScolaires"](
            self.db, params)
        apres = len(self.db.requetes)
        self.assertIs(self.source["GetListeEcoles"](
            self.db, params), initial_ecoles)
        self.assertIs(self.source["GetListeNiveauxScolaires"](
            self.db, params), initial_niveaux)
        self.assertEqual(apres, len(self.db.requetes))
        params["listeActivites"][:] = [1]
        modifiees = self.source["GetListeEcoles"](self.db, params)
        self.assertEqual(modifiees, reference_independante(self.db, params)[0])
        self.assertNotEqual(modifiees, initial_ecoles)
        self.assertGreater(len(self.db.requetes), apres)

    def test_scolarite_mise_a_jour_nouvelle_connexion(self):
        params = parametres()
        ancienne = self.source["GetListeEcoles"](self.db, params)
        autre = SQLiteScolarite()
        try:
            autre.cursor.execute("INSERT INTO individus VALUES (9)")
            autre.cursor.execute(
                "INSERT INTO consommations VALUES (?,?,?,?)",
                (9, "2026-04-01", "present", 1))
            autre.cursor.execute(
                "INSERT INTO scolarite VALUES (?,?,?,?,?)",
                (9, 20, 200, "2025-09-01", "2026-08-31"))
            nouvelle = self.source["GetListeEcoles"](autre, params)
            self.assertEqual(nouvelle, reference_independante(autre, params)[0])
            self.assertNotEqual(nouvelle, ancienne)
        finally:
            autre.Close()


if __name__ == "__main__":
    unittest.main()
