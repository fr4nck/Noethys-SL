import sys
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
from Utils import UTILS_Factures_lot as M

class DB:
    isNetwork=False
    echec=0
    def __init__(self, nom=':memory:'):
        self.connexion=sqlite3.connect(nom, timeout=5, isolation_level='DEFERRED')
        self.cursor=self.connexion.cursor()

    def Close(self):
        self.connexion.close()


def setup(db):
    db.cursor.executescript('''
    CREATE TABLE factures (IDfacture INTEGER PRIMARY KEY AUTOINCREMENT, IDprefixe INTEGER, numero INTEGER,
                          IDcompte_payeur INTEGER, total REAL);
    CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, IDcompte_payeur INTEGER, IDfacture INTEGER);
    INSERT INTO prestations VALUES (11,1,NULL),(12,1,NULL),(21,2,NULL),(22,2,NULL);
    ''')
    db.connexion.commit()


def facture(payeur, prestas, prefixe=None):
    return {'IDcompte_payeur':payeur,'champs':[('IDprefixe',prefixe),('numero',None),('IDcompte_payeur',payeur),('total',15.0)],'prestations':prestas}

class Tests(unittest.TestCase):
    def test_deux_prefixes_numerotation_independante(self):
        db=DB();setup(db)
        a=M.EnregistrerLot(db,[facture(1,[11],prefixe=3)],prefixe=3)
        b=M.EnregistrerLot(db,[facture(2,[21],prefixe=4)],prefixe=4)
        self.assertNotEqual(a[0],b[0])
        self.assertEqual(db.cursor.execute('SELECT numero FROM factures ORDER BY IDfacture').fetchall(),[(1,),(1,)])
        db.connexion.close()

    def test_succes_enregistre_et_rattache_tout(self):
        db=DB();setup(db)
        ids=M.EnregistrerLot(db,[facture(1,[11,12]),facture(2,[21])])
        self.assertEqual(len(ids),2)
        self.assertEqual(db.cursor.execute('SELECT numero FROM factures ORDER BY numero').fetchall(),[(1,),(2,)])
        self.assertEqual(db.cursor.execute('SELECT IDfacture FROM prestations WHERE IDprestation=11').fetchone()[0],ids[0])
        self.assertEqual(db.cursor.execute('SELECT IDfacture FROM prestations WHERE IDprestation=21').fetchone()[0],ids[1])
        db.connexion.close()

    def test_echec_milieu_lot_rollback_total(self):
        db=DB();setup(db)
        db.cursor.execute('''CREATE TRIGGER bloque_prestation BEFORE UPDATE ON prestations
            WHEN NEW.IDprestation=21 BEGIN SELECT RAISE(ABORT, 'incident simul e'); END''')
        db.connexion.commit()
        with self.assertRaises(M.EmissionFacturesImpossible):
            M.EnregistrerLot(db,[facture(1,[11,12]),facture(2,[21])])
        self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM factures').fetchone()[0],0)
        self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM prestations WHERE IDfacture IS NOT NULL').fetchone()[0],0)
        db.connexion.close()

    def test_prestation_deja_attribuee_interdit_reemission(self):
        db=DB();setup(db)
        self.assertEqual(len(M.EnregistrerLot(db,[facture(1,[11])])),1)
        with self.assertRaisesRegex(M.EmissionFacturesImpossible, 'prestation'):
            M.EnregistrerLot(db,[facture(1,[11])])
        self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM factures').fetchone()[0],1)
        db.connexion.close()

    def test_numero_demande_occupe_refuse_sans_ecritures(self):
        db=DB();setup(db)
        M.EnregistrerLot(db,[facture(1,[11])])
        with self.assertRaisesRegex(M.EmissionFacturesImpossible, 'Numero'):
            M.EnregistrerLot(db,[facture(2,[21])],premier_numero=1)
        self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM factures').fetchone()[0],1)
        db.connexion.close()

    def test_concurrence_deux_connexions_numeros_distincts(self):
        with tempfile.TemporaryDirectory() as tmp:
            nom=str(Path(tmp)/'test.sqlite')
            db=DB(nom);setup(db);db.connexion.close()
            ev=threading.Barrier(2);resultats=[];erreurs=[]
            def worker(payeur,presta):
                try:
                    d=DB(nom);ev.wait(timeout=3)
                    ids=M.EnregistrerLot(d,[facture(payeur,[presta])]);resultats.extend(ids)
                    d.connexion.close()
                except Exception as e: erreurs.append(e)
            threads=[threading.Thread(target=worker,args=(1,11)),threading.Thread(target=worker,args=(2,21))]
            for t in threads:t.start()
            for t in threads:t.join(timeout=8)
            self.assertFalse(erreurs,erreurs)
            self.assertEqual(len(resultats),2)
            d=DB(nom)
            self.assertEqual(d.cursor.execute('SELECT COUNT(DISTINCT numero),COUNT(*) FROM factures').fetchone(),(2,2))
            d.connexion.close()


class InterfaceFacturesTests(unittest.TestCase):
    """Teste la methode reelle via AST, sans importer wx ni contacter PMSL."""

    def _emission(self, base, bloquer=False):
        import ast
        import datetime
        import traceback
        import types
        db0=DB(base);setup(db0)
        for nom, sqltype in (
            ('date_edition','TEXT'),('date_echeance','TEXT'),('activites','TEXT'),
            ('individus','TEXT'),('IDutilisateur','INTEGER'),('date_debut','TEXT'),
            ('date_fin','TEXT'),('regle','REAL'),('solde','REAL'),('IDlot','INTEGER'),
            ('prestations','TEXT'),('IDregie','INTEGER'),('mention1','TEXT'),
            ('mention2','TEXT'),('mention3','TEXT')):
            db0.cursor.execute('ALTER TABLE factures ADD COLUMN '+nom+' '+sqltype)
        if bloquer:
            db0.cursor.execute("CREATE TRIGGER stop_fact BEFORE UPDATE ON prestations "
                               "WHEN NEW.IDprestation=11 BEGIN SELECT RAISE(ABORT, 'simulation'); END")
        db0.connexion.commit();db0.connexion.close()

        source = Path(__file__).resolve().parents[1] / 'noethys/Dlg/DLG_Factures_generation_selection.py'
        arbre=ast.parse(source.read_text(encoding='utf8'))
        classe=next(x for x in arbre.body if isinstance(x,ast.ClassDef) and x.name=='Panel')
        methode=next(x for x in classe.body if isinstance(x,ast.FunctionDef) and x.name=='SauvegardeFactures')
        fonction=compile(ast.fix_missing_locations(ast.Module(body=[methode],type_ignores=[])),str(source),'exec')

        class Dialog:
            def __init__(self,*args,**kwargs):pass
            def Update(self,*args,**kwargs):pass
            def Destroy(self):pass
            def ShowModal(self):return 0
        wx=types.SimpleNamespace(ProgressDialog=Dialog,MessageDialog=Dialog,
             PD_SMOOTH=0,PD_AUTO_HIDE=0,PD_APP_MODAL=0,OK=0,ICON_ERROR=0)
        g={'wx':wx,'_':lambda s:s,'UTILS_Identification':types.SimpleNamespace(GetIDutilisateur=lambda:12),
           'UTILS_Factures_lot':M,'GestionDB':types.SimpleNamespace(DB=lambda pooling=False: DB(base)),
           'traceback':traceback,'sys':sys}
        exec(fonction,g)
        date=datetime.date(2026,11,1)
        compte={'listePrestations':[(101,11)],'total':15.0,'ventilation':0.0,
                'date_edition':date,'date_echeance':date,'liste_activites':[],
                'individus':{101:{'select':True}},'date_debut':date,'date_fin':date}
        param={'prochain_numero':None,'IDprefixe':None,'IDlot':None,
               'prestations':['consommation'],'IDregie':None,
               'mention1':None,'mention2':None,'mention3':None}
        liste=types.SimpleNamespace(GetTracksCoches=lambda:[
            types.SimpleNamespace(nomSansCivilite='Fictif',IDcompte_payeur=1)],dictComptes={1:compte})
        page=types.SimpleNamespace(ctrl_factures=liste,parent=types.SimpleNamespace(dictParametres=param),
              EcritStatusbar=lambda *a:None)
        return g['SauvegardeFactures'](page)

    def test_interface_sauvegarde_une_facture_et_lie_prestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            nom=str(Path(tmp)/'fact.sqlite')
            ids=self._emission(nom)
            self.assertEqual(len(ids),1)
            db=DB(nom)
            self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM factures').fetchone(),(1,))
            self.assertEqual(db.cursor.execute('SELECT IDfacture FROM prestations WHERE IDprestation=11').fetchone(),(ids[0],))
            db.connexion.close()

    def test_interface_echec_prestation_aucune_facture(self):
        with tempfile.TemporaryDirectory() as tmp:
            nom=str(Path(tmp)/'fact.sqlite')
            self.assertFalse(self._emission(nom,bloquer=True))
            db=DB(nom)
            self.assertEqual(db.cursor.execute('SELECT COUNT(*) FROM factures').fetchone(),(0,))
            self.assertEqual(db.cursor.execute('SELECT IDfacture FROM prestations WHERE IDprestation=11').fetchone(),(None,))
            db.connexion.close()

if __name__ == '__main__':unittest.main()