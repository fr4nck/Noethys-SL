import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
from Utils import UTILS_Attestations_repas as repas


def regle(debut='2026-01-01', fin='2026-12-31', montant='3.50', unite=2):
    return dict(IDunite=unite, date_debut=debut, date_fin=fin, montant=montant)


class RepasTests(unittest.TestCase):
    def setUp(self):
        connexion = sqlite3.connect(':memory:')
        self.addCleanup(connexion.close)
        self.db = SimpleNamespace(isNetwork=False, connexion=connexion,
                                  cursor=connexion.cursor(), Commit=connexion.commit)
        connexion.executescript('CREATE TABLE consommations (IDconso INTEGER, IDprestation INTEGER, IDunite INTEGER, date TEXT, quantite INTEGER, IDindividu INTEGER, IDactivite INTEGER); CREATE TABLE prestations (IDprestation INTEGER, IDindividu INTEGER, IDactivite INTEGER, date TEXT); CREATE TABLE parametres (IDparametre INTEGER PRIMARY KEY, categorie TEXT, nom TEXT, parametre TEXT);')

    def conso(self, ID, prestation, unite, date, quantite=1):
        self.db.cursor.execute('INSERT INTO consommations VALUES (?,?,?,?,?,?,?)', (ID, prestation, unite, date, quantite, 100, 1))

    def test_repas_non_lie_demande_verification(self):
        self.conso(1, None, 2, '2026-09-01')
        self.db.cursor.execute("INSERT INTO prestations VALUES (10,100,1,'2026-09-01')")
        with self.assertRaisesRegex(ValueError, 'pas lié'):
            repas.Calculer(self.db, [(10,)], [regle()])

    def test_changement_prix_et_quantite_sans_double_compter(self):
        self.conso(1, 10, 2, '2026-08-31')
        self.conso(2, 11, 2, '2026-09-01', 2)
        self.conso(3, 10, 3, '2026-08-31')  # journée : ne déduit pas un second repas
        self.conso(4, 12, 2, '2026-09-01')  # prestation non sélectionnée
        d = repas.Calculer(self.db, [(10,), (11,), (13,)],
                           [regle(fin='2026-08-31'), regle(debut='2026-09-01', montant='4')])
        self.assertEqual(d, {10: Decimal('3.50'), 11: Decimal('8')})

    def test_aucun_repas_aucune_deduction(self):
        self.assertEqual(repas.Calculer(self.db, [(10,)], [regle()]), {})

    def test_prix_manquant_bloque(self):
        self.conso(1, 10, 2, '2025-12-31')
        with self.assertRaisesRegex(ValueError, 'manque le prix'):
            repas.Calculer(self.db, [(10,)], [regle()])

    def test_periodes_chevauchantes_refusees(self):
        with self.assertRaises(ValueError):
            repas.ValiderRegles([regle(), regle()])

    def test_montants_invalides_refuses(self):
        for valeur in ('-1', 'NaN', 'Infinity', '3.456', 'abc'):
            with self.subTest(valeur=valeur), self.assertRaises(ValueError):
                repas.ValiderRegles([regle(montant=valeur)])

    def test_reglages_persistes_et_remplaces(self):
        repas.Sauver(self.db, [regle()])
        repas.Sauver(self.db, [regle(montant='4,25')])
        self.assertEqual(repas.Charger(self.db), [regle(montant='4.25')])
        self.assertEqual(self.db.cursor.execute('SELECT COUNT(*) FROM parametres').fetchone()[0], 1)

    def test_deduction_et_ajustement_distingues(self):
        self.assertEqual(repas.Appliquer(20, 20, '3.50', '-1'),
                         (Decimal('15.50'), Decimal('15.50'), Decimal('0')))
        self.assertEqual(repas.Appliquer(20, 0, '3.50'),
                         (Decimal('16.50'), Decimal('0'), Decimal('16.50')))

    def test_reglement_partiel_demande_verification(self):
        with self.assertRaisesRegex(ValueError, 'partiellement'):
            repas.Appliquer(20, 10, '3.50')

    def test_montant_repas_excessif_refuse(self):
        with self.assertRaises(ValueError):
            repas.Appliquer(2, 2, '3.50')

    def test_sans_repas_ajustements_existants_conserves(self):
        self.assertEqual(repas.Appliquer(20, 10, 0, -2), (Decimal('18'), Decimal('8'), Decimal('10')))


if __name__ == '__main__':
    unittest.main()
