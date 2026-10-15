# -*- coding: utf-8 -*-
"""Suivi sur SQLite temporaire / transport factice. Aucun email ni appel API."""
import json
import concurrent.futures
import os
import queue
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau
import GestionDB
import wx
from Data import DATA_Tables
from Utils import UTILS_Suivi_mailjet as S
import test_noethys_sl_mailjet_acceptation as acceptation

KEY, SECRET = 'CLE-STRICTEMENT-FACTICE', 'SECRET-STRICTEMENT-FACTICE'
MID = '18446744073709551614'


def reponse(data, status=200):
    return SimpleNamespace(status_code=status, json=lambda: {'Data': data})


def record():
    return dict(compte=S.Compte(KEY), message_id=MID, destinataire='test@example.org')


class ConsultationTests(unittest.TestCase):
    def verifier(self, etat='sent', evenements=(), rebonds=()):
        get = mock.Mock(side_effect=[reponse([dict(ID=int(MID), Status=etat, ContactAlt='test@example.org')]),
                                     reponse(list(evenements)), reponse(list(rebonds))])
        return S.Consultation((KEY, SECRET), get).Verifier(record()), get

    def test_identifiant_64_bits_et_transport_get_uniquement(self):
        result, get = self.verifier()
        self.assertEqual(result['etat'], 'sent')
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertTrue(call.args[0].startswith('https://api.mailjet.com/v3/REST/'))
            self.assertTrue(call.args[0].endswith('/' + MID))
            self.assertEqual(call.kwargs['auth'], (KEY, SECRET))
            self.assertEqual(call.kwargs['timeout'], (5, 10))
            self.assertIs(call.kwargs['allow_redirects'], False)
        self.assertEqual(get.call_args_list[0].kwargs['params'], {'ShowContactAlt': 'true'})

    def test_etats_non_confondus_avec_lecture(self):
        for etat in S.ETATS:
            result, _ = self.verifier(etat)
            self.assertEqual(result['etat'], etat)
        self.assertIn('serveur', S.Libelle('sent'))
        self.assertEqual(S.Libelle('opened'), 'Ouverture signalée')
        self.assertIn('non reconnu', S.Libelle('future-status'))

    def test_motif_rebond_et_secrets_masques(self):
        result, get = self.verifier('blocked', [{'EventAt': 1700000000, 'EventType': 'blocked', 'Comment': KEY}],
                                  [{'StateID': 42, 'Reason': SECRET + '\nboîte absente'}])
        self.assertEqual(get.call_count, 3)
        self.assertIn('boîte absente', result['detail'])
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertIn('2023', result['evenement_le'])

    def test_echec_ancien_non_affiche_comme_echec_actuel(self):
        result, _ = self.verifier('sent', [{'EventType': 'softbounced', 'Comment': 'Ancien échec'}])
        self.assertEqual(result['detail'], '')

    def test_historique_indisponible_preserve_etat_autoritaire(self):
        get = mock.Mock(side_effect=[reponse([dict(ID=MID, Status='sent', ContactAlt='test@example.org')]), reponse([], 404)])
        result = S.Consultation((KEY, SECRET), get).Verifier(record())
        self.assertEqual(result['etat'], 'sent')
        self.assertIn('introuvable', result['detail'])

    def test_erreurs_et_redirection_sans_fausse_livraison(self):
        for status in (301, 401, 403, 404, 429, 500):
            with self.subTest(status=status), self.assertRaises(S.ErreurSuivi):
                S.Consultation((KEY, SECRET), lambda *a, **k: reponse([], status)).Verifier(record())

    def test_reponse_incoherente_refusee(self):
        for data in ([], [{'ID': 2, 'Status': 'sent'}], [{'ID': MID, 'Status': 'sent', 'ContactAlt': 'autre@example.org'}],
                     [{'ID': MID, 'Status': False}], [{'ID': MID, 'Status': 'sent', 'ContactAlt': {'Email': 'x'}}]):
            with self.subTest(data=data), self.assertRaises(S.ErreurSuivi):
                S.Consultation((KEY, SECRET), lambda *a, **k: reponse(data)).Verifier(record())

    def test_reponse_json_invalide(self):
        get = mock.Mock(return_value=SimpleNamespace(status_code=200, json=lambda: {'Data': 'invalide'}))
        with self.assertRaises(S.ErreurSuivi):
            S.Consultation((KEY, SECRET), get).Verifier(record())

    def test_erreur_transport_ne_divulgue_pas_secret(self):
        get = mock.Mock(side_effect=RuntimeError(SECRET))
        with self.assertRaises(S.ErreurSuivi) as error:
            S.Consultation((KEY, SECRET), get).Verifier(record())
        self.assertNotIn(SECRET, str(error.exception))

    def test_compte_incorrect_aucune_requete(self):
        get = mock.Mock()
        with self.assertRaises(S.ErreurSuivi):
            S.Consultation(('AUTRE-CLE', SECRET), get).Verifier(record())
        get.assert_not_called()

    def test_identifiants_invalides(self):
        for value in (None, True, 0, -1, 1.5, '1e3', '../x', '18446744073709551616'):
            with self.subTest(value=value), self.assertRaises(S.ErreurSuivi):
                S.MessageID(value)

    def test_travailleur_arret_et_limitation(self):
        for status in (401, 429):
            q = queue.Queue()
            get = mock.Mock(return_value=reponse([], status))
            S.Actualiser([record(), record()], (KEY, SECRET), q, threading.Event(), get)
            self.assertEqual(get.call_count, 1)
            self.assertIsNone(q.get()[1])
            self.assertIsNone(q.get())
        arret = threading.Event()
        arret.set()
        S.Actualiser([record()], (KEY, SECRET), q, arret, get)
        self.assertIsNone(q.get())

    def test_limite_api_sur_historique_arrete_lot_sans_perdre_etat(self):
        get = mock.Mock(side_effect=[reponse([dict(ID=MID, Status='sent', ContactAlt='test@example.org')]), reponse([], 429)])
        q = queue.Queue()
        S.Actualiser([record(), record()], (KEY, SECRET), q, threading.Event(), get)
        self.assertEqual(get.call_count, 2)
        r, resultat, erreur = q.get()
        self.assertEqual(resultat['etat'], 'sent')
        self.assertEqual(erreur, '')
        self.assertIn('Limite', resultat['detail'])
        self.assertIsNone(q.get())


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='noethys-suivi-synthetique-')
        self.addCleanup(self.tmp.cleanup)
        self.fichier = str(Path(self.tmp.name) / 'synthetique.dat')
        db = GestionDB.DB(nomFichier=self.fichier, suffixe=None, modeCreation=True)
        for table in ('parametres', 'adresses_mail'):
            db.CreationTable(table, dicoDB=DATA_Tables.DB_DATA)
        db.Commit()
        db.Close()
        self.journal = S.Journal(self.fichier)

    def enregistrer(self):
        self.journal.Enregistrer(KEY, 'exp@example.org', "Sujet avec ' guillemet", [('test@example.org', 'uuid', MID)])
        return self.journal.Lister()[0]

    def test_journal_identite_destinataire_sans_secrets_corps(self):
        r = self.enregistrer()
        self.assertEqual(r['message_id'], MID)
        self.assertEqual(r['destinataire'], 'test@example.org')
        self.assertNotIn(KEY, r['_raw'])
        self.assertNotIn(SECRET, r['_raw'])
        self.assertEqual(len(self.journal.Lister(S.Compte(KEY))), 1)
        self.assertEqual(self.journal.Lister(S.Compte('AUTRE')), [])

    def test_envoi_simule_enregistre_dans_vrai_journal_sqlite(self):
        email = acceptation.UTILS_Envoi_email
        with mock.patch.object(email.UTILS_Parametres, 'Parametres', return_value='20'):
            moteur = email.Mailjet(email_exp='exp@example.org', nom_exp='Fictif',
                                  parametres='api_key==%s##api_secret==%s' % (KEY, SECRET))
        moteur._suivi_initialise, moteur._base_suivi = True, self.fichier
        moteur.connection = mock.Mock()
        moteur.connection.send.create.return_value = acceptation.succes_mailjet('test@example.org', mid=int(MID))
        msg = acceptation.message('test@example.org')
        self.assertEqual(moteur.Envoyer(msg), 'success')
        self.assertTrue(msg.mailjet_suivi_enregistre)
        self.assertEqual(self.journal.Lister()[0]['message_id'], MID)

    def test_idempotence_ne_reinitialise_pas_un_etat_livre(self):
        r = self.enregistrer()
        self.assertTrue(self.journal.SauverResultat(r, dict(etat='sent', verifie_le=S.Maintenant())))
        r = self.enregistrer()
        self.assertEqual(r['etat'], 'sent')
        self.assertEqual(len(self.journal.Lister()), 1)

    def test_unicode_hors_bmp_preserve_sur_mysql_utf8_historique(self):
        sujet = 'Été \U0001f600'
        self.journal.Enregistrer(KEY, 'exp@example.org', sujet, [('test@example.org', '', MID)])
        r = self.journal.Lister()[0]
        self.assertEqual(r['sujet'], sujet)
        self.assertTrue(r['_raw'].isascii())

    def test_concurrence_deux_postes_actualisation_obsolete_refusee(self):
        poste_a = self.enregistrer()
        poste_b = S.Journal(self.fichier).Lister()[0]
        self.assertTrue(self.journal.SauverResultat(poste_a, dict(etat='opened', verifie_le=S.Maintenant())))
        self.assertFalse(S.Journal(self.fichier).SauverResultat(poste_b, dict(etat='queued')))
        self.assertEqual(self.journal.Lister()[0]['etat'], 'opened')

    def test_panne_consultation_preserve_dernier_etat(self):
        self.journal.SauverResultat(self.enregistrer(), dict(etat='sent', verifie_le='2026-10-15T08:00:00+00:00'))
        self.journal.SauverResultat(self.journal.Lister()[0], erreur='API inaccessible')
        r = self.journal.Lister()[0]
        self.assertEqual(r['etat'], 'sent')
        self.assertEqual(r['verifie_le'], '2026-10-15T08:00:00+00:00')
        self.assertEqual(r['erreur_consultation'], 'API inaccessible')

    def test_rollback_lot_et_parametres_etrangers_preserves(self):
        with sqlite3.connect(self.fichier) as db:
            db.execute("INSERT INTO parametres(categorie,nom,parametre) VALUES ('autre', 'x', 'conserver')")
            db.execute("CREATE TRIGGER refuser_suivi BEFORE INSERT ON parametres WHEN NEW.nom LIKE '%:2' BEGIN SELECT RAISE(ABORT,'echec synthetique'); END")
        with self.assertRaises(Exception):
            self.journal.Enregistrer(KEY, 'x', 's', [('a@example.org', '', '1'), ('b@example.org', '', '2')])
        self.assertEqual(self.journal.Lister(), [])
        with sqlite3.connect(self.fichier) as db:
            self.assertEqual(db.execute('SELECT parametre FROM parametres').fetchall(), [('conserver',)])

    def test_doublons_concurrents_dedoublonnes_sans_effacer(self):
        r = self.enregistrer()
        with sqlite3.connect(self.fichier) as db:
            db.execute('INSERT INTO parametres(categorie,nom,parametre) VALUES (?,?,?)', (S.CATEGORIE, r['_nom'], r['_raw']))
        self.assertEqual(len(self.journal.Lister()), 1)
        self.journal.SauverResultat(self.journal.Lister()[0], dict(etat='sent', verifie_le=S.Maintenant()))
        self.assertEqual(self.journal.Lister()[0]['etat'], 'sent')

    def test_deux_postes_enregistrement_simultane_une_seule_entree(self):
        depart = threading.Barrier(2)
        def poste():
            depart.wait(timeout=5)
            self.enregistrer()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            travaux = [pool.submit(poste) for _ in range(2)]
            for travail in travaux:
                travail.result(timeout=10)
        with sqlite3.connect(self.fichier) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM parametres').fetchone()[0], 1)

    def test_journal_corrompu_refuse_sans_effacement(self):
        self.enregistrer()
        with sqlite3.connect(self.fichier) as db:
            db.execute('UPDATE parametres SET parametre=?', ('{}',))
        with self.assertRaises(S.ErreurSuivi):
            self.journal.Lister()

    def test_comptes_mailjet_uniquement(self):
        with sqlite3.connect(self.fichier) as db:
            for moteur in ('mailjet', 'smtp'):
                db.execute('INSERT INTO adresses_mail(adresse,nom_adresse,moteur,parametres) VALUES (?,?,?,?)',
                           ('exp@example.org', 'Fictif', moteur, 'api_key==%s##api_secret==%s' % (KEY, SECRET)))
        self.assertEqual(len(self.journal.Comptes()), 1)
        self.assertEqual(self.journal.Comptes()[0]['auth'], (KEY, SECRET))

    def test_placeholders_mysql_parametres_non_interpoles(self):
        db = SimpleNamespace(isNetwork=True, cursor=mock.Mock())
        S.Journal._execute(db, 'SELECT parametre FROM parametres WHERE categorie=? AND nom=?', (S.CATEGORIE, "l'été"))
        db.cursor.execute.assert_called_once_with('SELECT parametre FROM parametres WHERE categorie=%s AND nom=%s', (S.CATEGORIE, "l'été"))

    def test_mysql_resultats_consommes_avant_retour_au_pool(self):
        pending = [None]
        def execute(req, args):
            self.assertIsNone(pending[0], 'Resultat MySQL precedent non consomme')
            if req.startswith('SELECT'):
                pending[0] = req
        def fetchone():
            req, pending[0] = pending[0], None
            if 'IDparametre' in req:
                self.assertIn('LIMIT 1', req)
                return None
            return (1,)
        db = SimpleNamespace(isNetwork=True, echec=0, cursor=mock.Mock(), connexion=mock.Mock(),
                             Commit=mock.Mock(), Close=lambda: self.assertIsNone(pending[0]))
        db.cursor.execute.side_effect = execute
        db.cursor.fetchone.side_effect = fetchone
        S.Journal('base-strictement-fictive', fabrique=lambda _: db).Enregistrer(
            KEY, 'exp@example.org', 'Sujet', [('test@example.org', '', MID)])
        self.assertEqual(db.cursor.fetchone.call_count, 3)


@unittest.skipUnless(os.environ.get('NOETHYS_TEST_MYSQL_HOST'), 'MySQL local jetable non déclaré')
class JournalMySQLTests(unittest.TestCase):
    def test_schema_natif_enregistrement_concurrent_et_cas(self):
        # Reutiliser la fixture gardee : base zz_test_adh_* neuve, serveur
        # localhost explicitement declare, suppression de sa seule base neuve.
        import test_noethys_sl_adhesions_concurrence as fixture
        env = fixture.ConcurrenceMySQLTests()
        env.setUp()
        self.addCleanup(env.tearDown)
        fichier = env._nom(env.base)
        db = GestionDB.DB(nomFichier=fichier, suffixe=None)
        try:
            db.CreationTable('parametres', dicoDB=DATA_Tables.DB_DATA)
            db.Commit()
        finally:
            db.Close()
        journal = S.Journal(fichier)
        def poste():
            journal.Enregistrer(KEY, 'exp@example.org', 'Été synthétique', [('test@example.org', '', MID)])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            travaux = [pool.submit(poste) for _ in range(2)]
            for travail in travaux:
                travail.result(timeout=15)
        self.assertEqual(env._compter('SELECT COUNT(*) FROM parametres'), 1)
        a, b = journal.Lister()[0], journal.Lister()[0]
        self.assertTrue(journal.SauverResultat(a, dict(etat='sent', verifie_le=S.Maintenant())))
        self.assertFalse(journal.SauverResultat(b, dict(etat='queued')))
        self.assertEqual(journal.Lister()[0]['etat'], 'sent')
        self.assertEqual(env._compter('SELECT COUNT(*) FROM consommations'), 1)


class AncienHistoriqueTests(unittest.TestCase):
    def test_reprise_seulement_suffixe_complet_categorie_email(self):
        action = "Envoi de l'Email 'Facture' (accepté par Mailjet, MessageID 123, 456)"
        def trace(texte, categorie=33):
            return SimpleNamespace(action=texte, IDcategorie=categorie, date='2026-10-15', heure='10:20:30')
        self.assertEqual([r['message_id'] for r in S.AnciensMessages([trace(action)])], ['123', '456'])
        for t in (trace(action[:-1]), trace(action + ' suite'), trace(action, 2), trace('MessageID 123')):
            self.assertEqual(S.AnciensMessages([t]), [])


class EnregistrementApresAcceptationTests(acceptation._Base):
    def test_capture_ui_puis_connexion_worker_sans_resolution_base(self):
        m = self.mailjet([])
        with mock.patch.object(S, 'BaseCourante', return_value='base-fictive') as base:
            m.PreparerSuivi()
        base.assert_called_once_with()
        client = mock.Mock()
        with mock.patch.dict(sys.modules, {'mailjet_rest': SimpleNamespace(Client=client)}), \
                mock.patch.object(S, 'BaseCourante', side_effect=AssertionError('Acces UI depuis worker')) as base:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(m.Connecter).result(3)
        base.assert_not_called()
        self.assertEqual(m._base_suivi, 'base-fictive')

    def test_connexion_worker_non_preparee_signale_suivi_absent(self):
        m = self.mailjet([])
        with mock.patch.dict(sys.modules, {'mailjet_rest': SimpleNamespace(Client=mock.Mock())}), \
                mock.patch.object(S, 'BaseCourante') as base:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(m.Connecter).result(3)
        base.assert_not_called()
        self.assertTrue(m._suivi_initialise)
        self.assertIsNone(m._base_suivi)

    def test_journal_apres_acceptation_et_tous_destinataires(self):
        response = acceptation.succes_mailjet('test@example.org', mid=int(MID))
        m = self.mailjet([response])
        m._suivi_initialise, m._base_suivi = True, 'fichier-synthetique'
        msg = acceptation.message('test@example.org')
        with mock.patch.object(S, 'Journal') as journal:
            self.assertEqual(m.Envoyer(msg), 'success')
        journal.return_value.Enregistrer.assert_called_once_with(acceptation.CLE_FACTICE, 'e@example.org', msg.sujet,
                                                                 [('test@example.org', 'uuid-1', int(MID))])
        self.assertTrue(msg.mailjet_suivi_enregistre)

    def test_panne_journal_n_entraine_pas_reenvoi(self):
        m = self.mailjet([acceptation.succes_mailjet('a@example.org')])
        m._suivi_initialise, m._base_suivi = True, 'fictif'
        with mock.patch.object(S, 'Journal', side_effect=RuntimeError('panne fictive')):
            succes, dialogues = self.lancer(m, [acceptation.message('a@example.org')], [], confirmation=False)
        self.assertEqual(len(succes), 1)
        self.assertEqual(m.connection.send.create.call_count, 1)
        self.assertIn('ne les renvoyez pas', dialogues.texte_comptes_rendus())

    def test_refus_mailjet_aucune_ecriture_suivi(self):
        m = self.mailjet([acceptation.reponse_mailjet({'Messages': [{'Status': 'error'}]}, status=400)])
        m._suivi_initialise = True
        with mock.patch.object(S, 'Journal') as journal, self.assertRaises(Exception):
            m.Envoyer(acceptation.message('a@example.org'))
        journal.assert_not_called()


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def setUp(self):
        from Dlg import DLG_Suivi_mailjet
        self.module = DLG_Suivi_mailjet
        self.journal = mock.Mock()
        self.journal.Lister.return_value = [dict(record(), sujet='Facture fictive', date_envoi='2026-10-15', etat='accepted',
                                                 verifie_le='', evenement_le='', detail='', erreur_consultation='')]
        self.get = mock.Mock(side_effect=[reponse([dict(ID=MID, Status='sent', ContactAlt='test@example.org')]), reponse([])])
        self.dlg = DLG_Suivi_mailjet.Dialog(None, self.journal, [dict(adresse='exp@example.org', compte=S.Compte(KEY), auth=(KEY, SECRET))], get=self.get)
        self.addCleanup(self.detruire)

    def detruire(self):
        if self.dlg:
            self.dlg.Arreter()
            self.dlg.Destroy()
            self.app.ProcessPendingEvents()

    def test_ouverture_sans_appel_api_et_actualisation_hors_ui(self):
        self.get.assert_not_called()
        self.dlg.liste.Select(0)
        threads = []
        self.get.side_effect = lambda *a, **k: (threads.append(threading.get_ident()) or
                                               reponse([dict(ID=MID, Status='sent', ContactAlt='test@example.org')]
                                                       if '/message/' in a[0] else []))
        self.dlg.Verifier()
        limite = time.monotonic() + 5
        while self.dlg.occupe and time.monotonic() < limite:
            self.dlg.Recevoir()
            time.sleep(.01)
        self.assertFalse(self.dlg.occupe)
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)
        self.journal.SauverResultat.assert_called_once()

    def test_fermeture_pendant_requete_aucune_ecriture_differee(self):
        entre, libere = threading.Event(), threading.Event()
        def get(*a, **k):
            entre.set()
            libere.wait(5)
            return reponse([dict(ID=MID, Status='sent', ContactAlt='test@example.org')] if '/message/' in a[0] else [])
        self.dlg.get = get
        self.dlg.liste.Select(0)
        self.dlg.Verifier()
        try:
            self.assertTrue(entre.wait(2))
            self.dlg.Arreter()
            self.dlg.Recevoir()
        finally:
            libere.set()
        self.journal.SauverResultat.assert_not_called()

    def test_acces_refuse_avant_lecture_base(self):
        from Utils import UTILS_Utilisateurs
        with mock.patch.object(UTILS_Utilisateurs, 'VerificationDroitsUtilisateurActuel', return_value=False), \
                mock.patch.object(S, 'BaseCourante') as base:
            self.module.Ouvrir(None)
        base.assert_not_called()


if __name__ == '__main__':
    unittest.main()
