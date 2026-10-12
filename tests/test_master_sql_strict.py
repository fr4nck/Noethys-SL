# -*- coding: utf-8 -*-
"""Requetes compatibles SQL strict (MySQL ONLY_FULL_GROUP_BY).

Repris de origin/master :
- 0753bf71 : OL_Reglements (liste des reglements) ;
- f0256647 : DLG_Export_compta (exports Quadra et Cerig).

Sous MySQL avec ONLY_FULL_GROUP_BY, un SELECT qui projette des colonnes
non agregees absentes du GROUP BY est refuse. SQLite ne l'impose pas : la
requete reelle est donc capturee (base simulee), controlee par un
verificateur ONLY_FULL_GROUP_BY minimal, puis executee sur une base SQLite
temporaire pour verifier qu'elle ne duplique ni ne perd de lignes.
Aucune base reelle, aucun reseau, aucune fenetre.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import re  # noqa: E402
import sqlite3  # noqa: E402
import types  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.App(False) if not wx.GetApp() else wx.GetApp()

import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

_AGREGATS = re.compile(r"\b(SUM|MIN|MAX|COUNT|AVG|GROUP_CONCAT)\s*\(", re.IGNORECASE)


def _extraire_sous_requetes(req):
    """Remplace chaque sous-requete '(SELECT ...)' par un marqueur ; renvoie
    (requete_niveau_superieur, [sous_requetes])."""
    sous_requetes = []
    sortie = []
    i = 0
    while i < len(req):
        if req[i] == "(" and re.match(r"\(\s*SELECT\b", req[i:], re.IGNORECASE):
            profondeur = 0
            j = i
            while j < len(req):
                if req[j] == "(":
                    profondeur += 1
                elif req[j] == ")":
                    profondeur -= 1
                    if profondeur == 0:
                        break
                j += 1
            sous_requetes.append(req[i + 1:j])
            sortie.append("(__SOUS_REQUETE__)")
            i = j + 1
        else:
            sortie.append(req[i])
            i += 1
    return "".join(sortie), sous_requetes


def _decouper_virgules(texte):
    morceaux, courant, profondeur = [], [], 0
    for c in texte:
        if c == "(":
            profondeur += 1
        elif c == ")":
            profondeur -= 1
        if c == "," and profondeur == 0:
            morceaux.append("".join(courant))
            courant = []
        else:
            courant.append(c)
    morceaux.append("".join(courant))
    return [m.strip() for m in morceaux if m.strip()]


def _normaliser(expr):
    expr = re.sub(r"\s+AS\s+\w+\s*$", "", expr.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", "", expr).lower()


def violations_only_full_group_by(req):
    """Renvoie la liste des expressions projetees non agregees et absentes
    du GROUP BY, pour la requete et chacune de ses sous-requetes."""
    violations = []
    a_traiter = [req]
    while a_traiter:
        courante = a_traiter.pop()
        niveau, sous = _extraire_sous_requetes(courante)
        a_traiter.extend(sous)
        m_group = re.search(r"\bGROUP\s+BY\b(.*?)(\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|;|$)",
                            niveau, re.IGNORECASE | re.DOTALL)
        if not m_group:
            continue
        groupes = {_normaliser(g) for g in _decouper_virgules(m_group.group(1))}
        # Colonne groupee qualifiee (t.col) : accepter aussi col seule et inversement
        groupes |= {g.split(".")[-1] for g in groupes}
        m_select = re.search(r"\bSELECT\b(.*?)\bFROM\b", niveau, re.IGNORECASE | re.DOTALL)
        for expr in _decouper_virgules(m_select.group(1)):
            if _AGREGATS.search(expr):
                continue
            norm = _normaliser(expr)
            if norm in groupes or norm.split(".")[-1] in groupes and "." not in norm:
                continue
            violations.append(expr.strip())
    return violations


class _Capture(Exception):
    pass


class _DBCapture:
    """Remplace GestionDB.DB : memorise les requetes, ne touche aucune base."""

    requetes = []
    lever_apres = None

    def __init__(self, *args, **kwargs):
        pass

    def ExecuterReq(self, req, *args, **kwargs):
        _DBCapture.requetes.append(req)
        if _DBCapture.lever_apres and len(_DBCapture.requetes) >= _DBCapture.lever_apres:
            raise _Capture()
        return True

    def ResultatReq(self):
        return []

    def Close(self):
        pass

    def Commit(self):
        pass


def _base_sqlite(tables):
    """Base SQLite en memoire construite depuis le schema canonique."""
    con = sqlite3.connect(":memory:")
    for nom in tables:
        colonnes = ", ".join("%s %s" % (c[0], c[1]) for c in Tables.DB_DATA[nom])
        con.execute("CREATE TABLE %s (%s)" % (nom, colonnes))
    return con


TABLES_REGLEMENTS = ("reglements", "ventilation", "modes_reglements", "emetteurs",
                     "payeurs", "depots", "comptes_payeurs")


class ReglementsGroupByStrictTests(unittest.TestCase):
    """0753bf71 : la liste des reglements ne doit plus grouper toutes les
    colonnes sur reglements.IDreglement."""

    def _capturer_requete(self):
        from Ol import OL_Reglements
        faux = types.SimpleNamespace(mode="liste", listeFiltres=[], IDdepot=None,
                                     IDcompte_payeur=None, selectionID=None, selectionTrack=None)
        _DBCapture.requetes = []
        _DBCapture.lever_apres = None
        with mock.patch.object(GestionDB, "DB", _DBCapture):
            resultat = OL_Reglements.ListView.GetTracks(faux)
        self.assertEqual(resultat, [])
        self.assertEqual(len(_DBCapture.requetes), 1)
        return _DBCapture.requetes[0]

    def test_requete_conforme_only_full_group_by(self):
        req = self._capturer_requete()
        self.assertEqual(violations_only_full_group_by(req), [])

    def test_totaux_de_ventilation_sans_doublon(self):
        req = self._capturer_requete()
        con = _base_sqlite(TABLES_REGLEMENTS)
        con.execute("INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (1, 7)")
        con.execute("INSERT INTO reglements (IDreglement, IDcompte_payeur, date, montant) VALUES (1, 1, '2026-09-01', 30.0)")
        con.execute("INSERT INTO reglements (IDreglement, IDcompte_payeur, date, montant) VALUES (2, 1, '2026-09-02', 12.0)")
        con.execute("INSERT INTO ventilation (IDventilation, IDreglement, IDcompte_payeur, montant) VALUES (1, 1, 1, 10.0)")
        con.execute("INSERT INTO ventilation (IDventilation, IDreglement, IDcompte_payeur, montant) VALUES (2, 1, 1, 20.0)")
        lignes = con.execute(req).fetchall()
        con.close()
        self.assertEqual(sorted(l[0] for l in lignes), [1, 2])
        totaux = {l[0]: l[23] for l in lignes}
        self.assertEqual(totaux[1], 30.0)
        self.assertIsNone(totaux[2])
        self.assertEqual({l[25] for l in lignes}, {7})


if __name__ == "__main__":
    unittest.main()
