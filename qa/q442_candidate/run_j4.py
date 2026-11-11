#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""J4 Q442 standalone qualification. Never opens any association database.

All SQLite is synthetic and in memory. Output directory explicitly required.
"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import unittest

import matplotlib
matplotlib.use('Agg',force=True)
from matplotlib import pyplot as plt

import test_q442_jalon4
from source_j3 import test_q442_jalon3
from q442_j4_objets import export_csv_aggreges
from q442_j4_lecteur import LecteurMultisite


def collect_suite():
    loader=unittest.defaultTestLoader
    suite=unittest.TestSuite()
    for mod in (test_q442_jalon4,test_q442_jalon3):
        suite.addTests(loader.loadTestsFromModule(mod))
    return suite


def write_results(output):
    db=test_q442_jalon4.facture_schema_realiste()
    try:
        reader=LecteurMultisite(test_q442_jalon4.DB(db),test_q442_jalon4.configuration())
        result=reader.lire(*test_q442_jalon4.PERIOD)
    finally:
        db.close()
    (output/'resultats_agreges_fictifs.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    combined=output/'q442_statistiques_agregees_tous_sites.csv'
    export_csv_aggreges(result,combined)
    with combined.open(encoding='utf-8',newline='') as fh:
        rows=list(csv.DictReader(fh,delimiter=';'))
        fields=rows[0].keys()
    # The multisite export is split into a global CSV and one CSV per site,
    # without names, IDs or monetary amounts.
    destinations={'Synthese generale':'q442_synthese_globale.csv',
                  'Bais':'q442_site_bais.csv',
                  'La Guerche':'q442_site_la_guerche.csv',
                  'Moutiers':'q442_site_moutiers.csv'}
    for name,filename in destinations.items():
        with (output/filename).open('w',encoding='utf-8',newline='') as dest:
            w=csv.DictWriter(dest,fieldnames=fields,delimiter=';')
            w.writeheader()
            w.writerows([x for x in rows if x['site']==name])
    db=test_q442_jalon4.facture_schema_realiste()
    try:
        bridge=test_q442_jalon4.DB(db)
        opts=test_q442_jalon4.params()
        for shape,klass,filename in [
            ('barres',test_q442_jalon4.BARS,'q442_preuve_barres_qf_familles.png'),
            ('secteurs',test_q442_jalon4.PIE,'q442_preuve_secteurs_qf_familles.png'),
        ]:
            fig=plt.figure(figsize=(10,5),dpi=110)
            try:
                klass('familles','qf').MAJ(figure=fig,DB=bridge,dictParametres=opts)
                fig.savefig(output/filename,format='png',bbox_inches='tight')
            finally:plt.close(fig)
    finally:db.close()
    return result


def manifest(root):
    hashes=[]
    for f in sorted(root.rglob('*')):
        if (not f.is_file() or f.name=='MANIFESTE_SHA256_J4.json' or
                '__pycache__' in f.parts):
            continue
        h=hashlib.sha256(f.read_bytes()).hexdigest()
        hashes.append({'fichier':f.relative_to(root.parent).as_posix(), 'sha256':h,
                       'taille':f.stat().st_size})
    result={'date':'2026-11-10','jalon':'Q442-J4','fichiers':hashes}
    (root/'preuves/MANIFESTE_SHA256_J4.json').write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return len(hashes)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True,help='Explicit non-production evidence directory')
    args=ap.parse_args()
    out=pathlib.Path(args.output).resolve()
    # No artefacts at any Windows drive root.
    if os.name=='nt' and out.parent==out:
        raise ValueError('Output at drive root forbidden')
    out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):
        raise FileExistsError('Refusing to overwrite an existing evidence directory')
    import io
    buf=io.StringIO()
    suite=collect_suite()
    report=unittest.TextTestRunner(stream=buf,verbosity=2).run(suite)
    (out/'tests_j4_j3.txt').write_text(buf.getvalue(),encoding='utf-8')
    if not report.wasSuccessful():
        print(buf.getvalue())
        raise RuntimeError('TEST FAIL - no acceptance evidence generated')
    result=write_results(out)
    summary={'tests_total':report.testsRun,'tests_erreurs':len(report.errors),
             'tests_echecs':len(report.failures),'tests_skipped':len(report.skipped),
             'state':'PASS_CONTRAT_FICTIF_UNIQUEMENT',
             'families':result['global']['familles']['total'],
             'children':result['global']['enfants']['total'],
             'sites':{s:val['familles']['total'] for s,val in result['sites'].items()},
             'sql_reads':result['lectures_sql'],
             'historical_tiers_certified':result['global']['familles']['categories_tarif_attestees']}
    (out/'VERDICT_J4.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Q442-J4',summary)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
