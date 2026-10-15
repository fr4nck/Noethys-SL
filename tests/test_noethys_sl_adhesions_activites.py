"""Rattachement natif multi-activites : aucun profil ni donnees reelles."""
import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401
from test_noethys_sl_adhesions import Env
from test_noethys_sl_adhesions_titulaire import completer
import test_noethys_sl_adhesions_concurrence as concurrence
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Divers

D = datetime.date
JOUR = D(2026, 10, 15)


class ActivitesTests(unittest.TestCase):
    def chaine(self, e, individu=100):
        return e.lire('SELECT activites FROM cotisations WHERE IDindividu=%d ORDER BY date_debut;' % individu)

    def automatique(self, e, individu=100, chaine=None):
        ID = e.adhesion(individu, D(2026, 9, 1), D(2027, 9, 1), observations=A.MARQUEUR_AUTO)
        e.base.db.cursor.execute('UPDATE cotisations SET activites=? WHERE IDcotisation=?', (chaine, ID))
        e.base.db.Commit()
        return ID

    def test_creation_rattache_declencheuse_format_formulaire(self):
        for source in ('conso', 'prestation'):
            with self.subTest(source=source), Env() as e:
                getattr(e, source)(100, D(2026, 10, 7), activite=2)
                e.reconcilier(100, JOUR, D(2026, 10, 7))
                self.assertEqual(self.chaine(e), [('2',)])
                self.assertEqual(UTILS_Divers.ConvertChaineEnListe(self.chaine(e)[0][0]), [2])
                self.assertEqual(e.compte('prestations', "categorie='cotisation'"), 1)

    def test_deux_activites_une_cotisation_une_prestation(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7), activite=1)
            e.conso(100, D(2026, 10, 8), activite=2)
            e.reconcilier(100, JOUR, D(2026, 10, 7))
            self.assertEqual(self.chaine(e), [('1;2',)])
            self.assertEqual(e.compte('cotisations'), 1)
            self.assertEqual(e.compte('prestations', "categorie='cotisation'"), 1)
            before = e.lire('SELECT * FROM prestations ORDER BY IDprestation;')
            actions = e.compte('historique')
            e.reconcilier(100, JOUR, D(2026, 10, 7))
            self.assertEqual(e.lire('SELECT * FROM prestations ORDER BY IDprestation;'), before)
            self.assertEqual(e.compte('historique'), actions)

    def test_complete_sans_creer_meme_si_depuis_est_recent(self):
        with Env() as e:
            ID = self.automatique(e, chaine='1;3')
            e.conso(100, D(2026, 10, 7), activite=2)
            before = e.lire('SELECT IDindividu, IDtype_cotisation, IDunite_cotisation, date_debut, date_fin, IDprestation FROM cotisations;')
            result = e.reconcilier(100, JOUR)
            self.assertEqual(result['statut'], A.STATUT_RIEN)
            self.assertEqual(result['activites_completees'], [ID])
            self.assertEqual(self.chaine(e), [('1;2;3',)])
            self.assertEqual(e.compte('prestations'), 0)
            self.assertEqual(e.lire('SELECT IDindividu, IDtype_cotisation, IDunite_cotisation, date_debut, date_fin, IDprestation FROM cotisations;'), before)

    def test_activites_annulees_futures_hors_validite_non_liees_exclues(self):
        with Env() as e:
            self.automatique(e, chaine='1')
            e.conso(100, D(2026, 8, 30), activite=2)  # avant validite
            e.conso(100, D(2026, 10, 10), activite=2, etat='attente')
            e.conso(100, D(2026, 10, 11), activite=2, etat='absentj')
            e.conso(100, D(2026, 10, 12), activite=2, etat='refus')
            e.conso(100, D(2026, 10, 13), activite=3)  # hors dispositif
            e.conso(100, D(2026, 10, 16), activite=2)  # future
            self.assertEqual(A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR), [])
            self.assertEqual(self.chaine(e), [('1',)])
            self.assertEqual(e.compte('historique'), 0)

    def test_prestation_isolee_et_annulation_ne_reactive_pas(self):
        with Env() as e:
            self.automatique(e, chaine='1')
            e.prestation(100, D(2026, 10, 7), activite=2)
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [('1;2',)])
        with Env() as e:
            self.automatique(e, chaine='1')
            e.prestation(100, D(2026, 10, 7), activite=2)
            e.conso(100, D(2026, 10, 7), activite=2, etat='refus')
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [('1',)])

    def test_annulation_ne_retire_pas_le_rattachement_historique(self):
        with Env() as e:
            self.automatique(e, chaine='1;2')
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [('1;2',)])
            self.assertEqual(e.compte('historique'), 0)

    def test_manuelle_inchangee(self):
        with Env() as e:
            ID = e.adhesion(100, D(2026, 9, 1), D(2027, 9, 1), observations='manuelle')
            e.base.db.cursor.execute("UPDATE cotisations SET activites='3' WHERE IDcotisation=?", (ID,))
            e.base.db.Commit()
            e.conso(100, D(2026, 10, 7), activite=2)
            before = e.lire('SELECT * FROM cotisations;')
            e.reconcilier(100, JOUR, D(2026, 10, 7))
            self.assertEqual(e.lire('SELECT * FROM cotisations;'), before)
            self.assertEqual(e.compte('historique'), 0)

    def test_structure_sections_union_sans_fuite_entre_familles(self):
        with Env() as e:
            completer(e)
            self.automatique(e, individu=200)
            self.automatique(e, individu=210)
            e.conso(201, D(2026, 10, 7), activite=1, payeur=12)
            e.conso(202, D(2026, 10, 8), activite=2, payeur=12)
            e.conso(201, D(2026, 10, 9), activite=2, payeur=14)
            for ID in (201, 202):
                e.reconcilier(ID, JOUR, D(2026, 10, 7))
            self.assertEqual(self.chaine(e, 200), [('1;2',)])
            self.assertEqual(self.chaine(e, 210), [('2',)])
            self.assertEqual(e.compte('prestations'), 0)

    def test_erreur_historique_annule_update_activites(self):
        with Env() as e:
            self.automatique(e, chaine='1')
            e.conso(100, D(2026, 10, 7), activite=2)
            with mock.patch.object(A._AccesStrict, 'Inserer', side_effect=RuntimeError('synthetique')):
                with self.assertRaises(RuntimeError):
                    A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [('1',)])
            self.assertEqual(e.compte('historique'), 0)

    def test_borne_inclusive_et_pas_de_debordement_sur_adhesion_suivante(self):
        with Env() as e:
            e.adhesion(100, D(2025, 9, 1), D(2026, 9, 1), observations=A.MARQUEUR_AUTO)
            self.automatique(e, chaine='1')
            e.conso(100, D(2026, 9, 2), activite=2)
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [(None,), ('1;2',)])

    def test_periode_verrouillee_aucun_update(self):
        with Env() as e:
            self.automatique(e, chaine='1')
            e.conso(100, D(2026, 10, 7), activite=2)
            e.base.inserer('periodes_gestion', ['date_debut', 'date_fin', 'verrou_cotisations'],
                           [('2026-09-01', '2026-09-30', 1)])
            self.assertEqual(A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR), [])
            self.assertEqual(self.chaine(e), [('1',)])

    def test_texte_invalide_non_ecrase(self):
        with Env() as e:
            self.automatique(e, chaine='ancien-format-invalide')
            e.conso(100, D(2026, 10, 7), activite=2)
            with self.assertRaises(ValueError):
                A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [('ancien-format-invalide',)])

    def test_liste_trop_longue_non_tronquee(self):
        with Env() as e:
            chaine = ';'.join(str(i) for i in range(1000, 1090))
            self.automatique(e, chaine=chaine)
            e.conso(100, D(2026, 10, 7), activite=2)
            with self.assertRaises(ValueError):
                A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), JOUR)
            self.assertEqual(self.chaine(e), [(chaine,)])

    def test_ajout_activite_ne_modifie_pas_facture_ni_ventilation(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7), activite=1)
            e.reconcilier(100, JOUR, D(2026, 10, 7))
            IDprestation = e.lire('SELECT IDprestation FROM cotisations;')[0][0]
            e.base.db.cursor.execute('UPDATE prestations SET IDfacture=7 WHERE IDprestation=?', (IDprestation,))
            e.base.db.Commit()
            e.base.inserer('ventilation', ['IDprestation', 'IDreglement', 'IDcompte_payeur', 'montant'],
                           [(IDprestation, 8, 11, 7.5)])
            before = (e.lire('SELECT * FROM prestations;'), e.lire('SELECT * FROM ventilation;'))
            e.conso(100, D(2026, 10, 8), activite=2)
            e.reconcilier(100, JOUR)
            self.assertEqual(self.chaine(e), [('1;2',)])
            self.assertEqual((e.lire('SELECT * FROM prestations;'), e.lire('SELECT * FROM ventilation;')), before)
            self.assertEqual(e.compte('cotisations'), 1)

    def test_deux_annees_activites_rattachees_a_leur_periode(self):
        with Env() as e:
            self.automatique(e)
            e.adhesion(100, D(2027, 9, 2), D(2028, 9, 2), observations=A.MARQUEUR_AUTO)
            e.conso(100, D(2026, 10, 7), activite=1)
            e.conso(100, D(2027, 10, 7), activite=2)
            A.CompleterActivitesAutomatiques(100, 100, A.ResoudreConfiguration(), D(2027, 10, 15))
            self.assertEqual(self.chaine(e), [('1',), ('2',)])


def deux_postes(test, mode, cible):
    aide = str(Path(__file__).with_name('_aide_concurrence_adhesions_activites.py'))
    with tempfile.TemporaryDirectory(prefix='cotisations-activites-synthetique-') as tmp:
        barriere = Path(tmp)
        a = subprocess.Popen([sys.executable, aide, mode, cible, 'A', tmp])
        b = None
        try:
            test.assertTrue(concurrence._attendre(lambda: (barriere / 'A_dans_section').exists()))
            b = subprocess.Popen([sys.executable, aide, mode, cible, 'B', tmp])
            test.assertTrue(concurrence._attendre(lambda: (barriere / 'B_avant_verrou').exists()))
            time.sleep(0.2)
            test.assertFalse((barriere / 'B.json').exists())
            test.assertIsNone(b.poll())
            (barriere / 'continuer').write_text('1')
            test.assertEqual(a.wait(20), 0)
            test.assertEqual(b.wait(20), 0)
        finally:
            (barriere / 'continuer').write_text('1')
            for process in (a, b):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(5)


class ConcurrenceActivitesSQLiteTests(unittest.TestCase):
    def test_deux_postes_conservent_les_deux_ajouts(self):
        with Env() as e:
            completer(e)
            e.adhesion(200, D(2026, 9, 1), D(2027, 9, 1), observations=A.MARQUEUR_AUTO)
            e.conso(201, D(2026, 10, 7), activite=1, payeur=12)
            e.conso(202, D(2026, 10, 8), activite=2, payeur=12)
            deux_postes(self, 'sqlite', e.base.chemin)
            self.assertEqual(e.lire('SELECT activites FROM cotisations;'), [('1;2',)])
            self.assertEqual(e.compte('cotisations'), 1)
            self.assertEqual(e.compte('prestations'), 0)
            self.assertEqual(e.compte('historique'), 2)


@unittest.skipUnless(os.environ.get('NOETHYS_TEST_MYSQL_HOST'), 'serveur MySQL local synthetique non declare')
class ConcurrenceActivitesMySQLTests(unittest.TestCase):
    setUp = concurrence.ConcurrenceMySQLTests.setUp
    tearDown = concurrence.ConcurrenceMySQLTests.tearDown
    _nom = concurrence.ConcurrenceMySQLTests._nom
    _compter = concurrence.ConcurrenceMySQLTests._compter

    def test_deux_postes_mysql_conservent_les_ajouts(self):
        import GestionDB
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        try:
            for req in (
                "INSERT INTO individus (IDindividu, IDcivilite) VALUES (200, 7), (201, 7), (202, 7);",
                "INSERT INTO familles (IDfamille) VALUES (2);",
                "INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (12, 2);",
                "INSERT INTO rattachements (IDrattachement, IDindividu, IDfamille, titulaire) VALUES (20, 200, 2, 1), (21, 201, 2, 0), (22, 202, 2, 0);",
                "INSERT INTO activites (IDactivite, nom) VALUES (2, 'Synthetique B');",
                "INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (2, 1);",
                "INSERT INTO cotisations (IDindividu, IDtype_cotisation, date_debut, date_fin, observations) VALUES (200, 1, '2026-09-01', '2027-09-01', '[adhesion-auto]');",
                "INSERT INTO consommations (IDindividu, IDactivite, date, etat, IDcompte_payeur) VALUES (201, 1, '2026-10-07', 'present', 12), (202, 2, '2026-10-08', 'present', 12);",
            ):
                db.cursor.execute(req)
            db.Commit()
        finally:
            db.Close()
        deux_postes(self, 'mysql', self.base)
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        try:
            db.cursor.execute('SELECT activites FROM cotisations WHERE IDindividu=200;')
            self.assertEqual(list(db.cursor.fetchall()), [('1;2',)])
        finally:
            db.Close()
        self.assertEqual(self._compter("SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 0)


if __name__ == '__main__':
    unittest.main()
