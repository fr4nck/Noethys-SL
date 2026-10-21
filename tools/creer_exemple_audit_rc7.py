#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crée uniquement une NOUVELLE base FICTIVE, au schéma canonique Noethys."""
import argparse
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Data.DATA_Tables import DB_DATA
from Utils.UTILS_Audit_cotisations import TABLES


def creer_exemple(dossier):
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=False)
    path = dossier / "FICTIF_recette_rc81_DATA.dat"
    db = sqlite3.connect(path)
    try:
        for table in TABLES:
            db.execute('CREATE TABLE "%s" (%s)' % (table, ", ".join(
                '"%s" %s' % (nom, type_sql) for nom, type_sql, *_ in DB_DATA[table])))
        for pid, facture, date in [(801, None, "2026-10-01"), (802, 99, "2026-10-01"),
                                    (803, None, "2026-10-01"), (804, 100, "2026-10-01"),
                                    (806, None, None), (808, None, "2026-10-01"), (810, None, "2026-10-01")]:
            db.execute("INSERT INTO prestations(IDprestation, IDindividu, IDcompte_payeur, categorie, date, montant, IDfacture) "
                       "VALUES (?,100,11,'cotisation',?,7.5,?)", (pid, date, facture))
        for cid, pid in [(701, 801), (702, 802), (703, 803), (704, 804), (705, 805),
                         (706, 806), (707, None), (708, 808), (709, 801), (710, 810)]:
            debut = "2026-10-01" if cid in (705, 708) else "0000-00-00" if cid == 710 else "2027-01-06"
            marqueur = "saisie manuelle" if cid == 707 else "[adhesion-auto]"
            db.execute("INSERT INTO cotisations(IDcotisation, IDindividu, IDtype_cotisation, IDunite_cotisation, "
                       "date_saisie,date_debut,date_fin,IDprestation,observations) VALUES (?,100,1,11,'2026-10-01',?,'2028-01-06',?,?)",
                       (cid, debut, pid, marqueur))
        db.executemany("INSERT INTO factures(IDfacture,numero,IDcompte_payeur,date_edition,etat) VALUES (?,?,11,'2026-10-02','edition')",
                       [(99, 260099), (100, 260100)])
        db.execute("INSERT INTO reglements(IDreglement, IDcompte_payeur, date, montant, encaissement_attente) VALUES (901,11,'2026-10-03',10,1)")
        db.executemany("INSERT INTO ventilation(IDventilation, IDcompte_payeur, IDprestation, IDreglement,montant) VALUES (?,11,?,?,?)",
                       [(1,803,901,5), (2,803,901,-5), (3,804,999,2.5)])
        db.commit()
    finally:
        db.close()
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dossier", help="nouveau dossier inexistant")
    print(creer_exemple(p.parse_args().dossier))
