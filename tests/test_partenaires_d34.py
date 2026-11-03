# -*- coding: utf-8 -*-
"""Recette D3-D4 : SQLite memoire, D1/D2 fictifs, aucune base historique connectee."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
from Utils.UTILS_Partenaires_D1 import AnnuairePartenaires, AutorisationRefusee  # noqa: E402
from Utils.UTILS_Partenaires_D2 import RegistreConventions  # noqa: E402
from Utils.UTILS_Partenaires_D34 import (  # noqa: E402
    InterventionsPartenaires, PlanningInvalide, PlanningConflit,
)

MIGRATIONS = [ROOT / 'noethys/Data/Migrations' / ('partenaires_' + f)
              for f in ('d1_sqlite.sql', 'd2_sqlite.sql', 'd34_sqlite.sql')]
MYSQL = ROOT / 'noethys/Data/Migrations/partenaires_d34_mysql57.sql'


class D34Tests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('PRAGMA foreign_keys=ON')
        for table, ident in (('familles', 'IDfamille'), ('consommations', 'IDconso'),
                             ('prestations', 'IDprestation'), ('factures', 'IDfacture'),
                             ('compta_tiers', 'IDtiers')):
            self.conn.execute('CREATE TABLE %s (%s INTEGER PRIMARY KEY, val TEXT)' % (table, ident))
            self.conn.execute('INSERT INTO %s VALUES (1, ?)' % table, ('sentinelle '+table,))
        self.conn.commit()
        self.sentinelles = self.lecture_sentinelles()
        for script in MIGRATIONS:
            self.conn.executescript(script.read_text(encoding='utf-8'))
        self.droit = lambda acteur, action: acteur == 'direction'
        self.d1 = AnnuairePartenaires(self.conn, autoriser=self.droit)
        self.d2 = RegistreConventions(self.conn, autoriser=self.droit)
        self.d34 = InterventionsPartenaires(self.conn, autoriser=self.droit)
        self.partenaire = self.d1.creer_structure({'raison_sociale': 'Ecole fictive',
                                                  'categorie': 'ecole'}, acteur='direction')
        self.cid = self.d2.creer_convention(self.partenaire, 'C-2025', 'Education physique',
             'scolaire', '2025-09-01', '2026-08-31', acteur='direction')
        self.vid = self.d2.ouvrir_version(self.cid, '2025-09-01', 'Clauses scolaires fictives',
                                         'word', 'Modele-test', 'payante', acteur='direction')
        self.d2.remplacer_tarifs(self.vid, [{'categorie': 'scolaires', 'libelle': 'EPS',
            'unite': 'heure', 'montant': '20.00', 'date_debut': '2025-09-01',
            'date_fin': '2026-08-31'}], acteur='direction')
        self.d2.signer_version(self.vid, '2025-08-25', 'Direction fictive',
                               'a' * 64, acteur='direction')
        self.pid = self.d34.creer_programmation(self.vid, 'P-2025', 'Cycle primaire',
                                                '2025-09-01', '2026-06-30', acteur='direction')

    def tearDown(self):
        self.conn.close()

    def lecture_sentinelles(self):
        return {t: self.conn.execute('SELECT * FROM %s' % t).fetchall() for t in
                ('familles', 'consommations', 'prestations', 'factures', 'compta_tiers')}

    def creneau(self, *, pid=None, debut='2025-10-01', fin='2025-10-31',
                jour=3, groupe='Cycle 2-A', horaire=('09:00', '10:00'),
                intervenant='Educateur 1', recurrence='hebdomadaire', categorie='scolaires'):
        return self.d34.ajouter_creneau(pid or self.pid, recurrence, debut, fin,
            horaire[0], horaire[1], groupe, 'EPS', categorie, acteur='direction',
            jour_semaine=jour, lieu='Gymnase', intervenant=intervenant)

    def valide(self):
        self.creneau()
        return self.d34.valider_programmation(self.pid, acteur='direction')

    def interventions(self):
        return self.d34.lister_interventions(self.pid, acteur='direction')

    def test_scripts_d34_creent_sept_tables_sans_alterer_historique(self):
        self.assertEqual(self.lecture_sentinelles(), self.sentinelles)
        tables = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({'partenaires_programmations', 'partenaires_creneaux',
            'partenaires_exclusions', 'partenaires_exceptions', 'partenaires_interventions',
            'partenaires_interventions_historique', 'partenaires_plan_evenements'} <= tables)
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_migration_replay_echoue_sans_drop(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.executescript(MIGRATIONS[-1].read_text(encoding='utf-8'))
        self.assertNotIn('DROP TABLE', MIGRATIONS[-1].read_text(encoding='utf-8').upper())

    def test_mysql_proposition_fk_uniques_et_non_execution(self):
        texte = MYSQL.read_text(encoding='utf-8')
        for symbole in ('ENGINE=InnoDB', 'UNIQUE KEY uq_part_interventions_occurrence',
                        'REFERENCES partenaires_conventions_versions',
                        'ON DELETE RESTRICT', 'DATE NOT NULL'):
            self.assertIn(symbole, texte)

    def test_fail_closed_sans_autorisation_lecture_et_ecriture(self):
        sans = InterventionsPartenaires(self.conn)
        for action in (lambda: sans.apercu_programmation(self.pid, acteur='direction'),
                       lambda: sans.lister_interventions(self.pid, acteur='direction'),
                       lambda: sans.creer_programmation(self.vid, 'x', 'x',
                                               '2025-09-01','2025-09-02', acteur='direction')):
            with self.assertRaises(AutorisationRefusee): action()
        with self.assertRaises(AutorisationRefusee):
            self.d34.apercu_programmation(self.pid, acteur='observateur')

    def test_aucune_session_avant_validation(self):
        self.creneau()
        self.assertEqual(self.interventions(), [])
        self.assertEqual(len(self.d34.apercu_programmation(self.pid, acteur='direction')['seances']), 5)

    def test_validation_idempotente_cree_cinq_jeudis(self):
        r = self.valide()
        self.assertEqual(r['nombre_seances'], 5)
        self.assertFalse(r['deja_validee'])
        self.assertTrue(self.d34.valider_programmation(self.pid, acteur='direction')['deja_validee'])
        dates = [i['date_prevue'] for i in self.interventions()]
        self.assertEqual(dates, ['2025-10-02','2025-10-09','2025-10-16','2025-10-23','2025-10-30'])
        self.assertEqual(len(set(i['IDintervention'] for i in self.interventions())), 5)
        self.assertEqual({i['etat'] for i in self.interventions()}, {'prevue'})
        self.assertEqual({i['decision_facturation'] for i in self.interventions()}, {'a_arbitrer'})

    def test_annexe_previsionnelle_validee_sans_export_implicite(self):
        self.creneau()
        with self.assertRaises(PlanningInvalide):
            self.d34.preparer_annexe(self.pid, acteur='direction')
        r=self.d34.valider_programmation(self.pid, acteur='direction')
        annexe=self.d34.preparer_annexe(self.pid, acteur='direction')
        self.assertEqual(annexe['empreinte'],r['empreinte'])
        self.assertEqual((annexe['nombre'],annexe['minutes']), (5,300))
        self.assertFalse(annexe['document_genere'])
        self.assertFalse(annexe['signature_partenaire_verifiee'])
        i=self.interventions()[0]['IDintervention']
        self.d34.annuler_intervention(i,'Motif','partenaire',True,acteur='direction')
        apres=self.d34.preparer_annexe(self.pid, acteur='direction')
        self.assertEqual(apres['lignes'],annexe['lignes'])

    def test_une_seance_ponctuelle_hors_recurrence(self):
        self.creneau(recurrence='ponctuel', debut='2025-10-09', fin='2025-10-09', jour=None)
        self.assertEqual(self.d34.valider_programmation(self.pid, acteur='direction')['nombre_seances'],1)

    def test_validation_interdite_sans_seance(self):
        with self.assertRaises(PlanningInvalide):
            self.d34.valider_programmation(self.pid, acteur='direction')

    def test_vacances_explicites_sans_inference(self):
        self.creneau()
        self.d34.ajouter_exclusion(self.pid, '2025-10-20','2025-11-02',
                                   'vacances','Vacances declarees',acteur='direction')
        apercu = self.d34.apercu_programmation(self.pid, acteur='direction')
        self.assertEqual([x['date_origine'] for x in apercu['exclusions']],
                         ['2025-10-23','2025-10-30'])
        self.assertEqual(len(apercu['seances']),3)
        self.assertEqual(self.d34.valider_programmation(self.pid,acteur='direction')['nombre_seances'],3)

    def test_correction_horaire_du_9_octobre(self):
        c = self.creneau()
        self.d34.ajouter_exception(c, '2025-10-09','deplacer','Exception ecole',
            date_remplacement='2025-10-09', heure_debut='13:15', heure_fin='14:15',
            acteur='direction')
        p = self.d34.apercu_programmation(self.pid,acteur='direction')['seances']
        self.assertEqual(next(x for x in p if x['date_origine']=='2025-10-09')['heure_debut_prevue'],'13:15')
        self.assertEqual(sum(x['minutes_prevues'] for x in p),300)

    def test_retrait_ponctuel_exclu_sans_creer_intervention(self):
        c=self.creneau()
        self.d34.ajouter_exception(c,'2025-10-09','supprimer','Salle indisponible',acteur='direction')
        self.assertEqual(len(self.d34.apercu_programmation(self.pid,acteur='direction')['seances']),4)
        self.d34.valider_programmation(self.pid,acteur='direction')
        self.assertNotIn('2025-10-09',[x['date_origine'] for x in self.interventions()])

    def test_exception_ne_peut_correspondre_a_une_date_absente(self):
        c=self.creneau()
        with self.assertRaises(PlanningInvalide):
            self.d34.ajouter_exception(c,'2025-10-10','supprimer','Pas de vendredi',acteur='direction')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM partenaires_exceptions').fetchone()[0],0)

    def test_une_seule_exception_par_occurrence(self):
        c=self.creneau()
        self.d34.ajouter_exception(c,'2025-10-09','supprimer','Motif 1',acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.ajouter_exception(c,'2025-10-09','supprimer','Motif 2',acteur='direction')

    def test_deplacement_vers_date_vacances_refuse(self):
        c=self.creneau()
        self.d34.ajouter_exclusion(self.pid,'2025-10-20','2025-11-02',
            'vacances','Vacances explicites',acteur='direction')
        self.d34.ajouter_exception(c,'2025-10-16','deplacer','Demande',
            date_remplacement='2025-10-23',heure_debut='13:00',heure_fin='14:00',acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.valider_programmation(self.pid,acteur='direction')
        self.assertEqual(self.interventions(),[])

    def test_exclusions_chevauchantes_refusees(self):
        self.creneau()
        self.d34.ajouter_exclusion(self.pid,'2025-10-20','2025-10-26','vacances',
                                    'Vacances de test',acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.ajouter_exclusion(self.pid,'2025-10-25','2025-11-02','fermeture',
                                       'Conflit de source',acteur='direction')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM partenaires_exclusions').fetchone()[0],1)

    def test_report_entraine_conflit_groupe_avec_rollback(self):
        self.valide()
        a=self.interventions()[0]['IDintervention']
        # Le jeudi 02/10 rejoint le jeudi 09/10, meme groupe et horaire.
        with self.assertRaises(PlanningConflit):
            self.d34.reporter_intervention(a,'2025-10-09','09:00','10:00',
                                          'Essai conflit',acteur='direction')
        self.assertEqual(self.d34.lister_historique(a,acteur='direction'),[])
        self.assertEqual(self.interventions()[0]['date_prevue'],'2025-10-02')

    def test_arbitrage_non_facturable_explicite_ne_cree_aucune_facture(self):
        self.valide()
        a=self.interventions()[0]['IDintervention']
        self.d34.annuler_intervention(a,'Annulation de test','partenaire',True,acteur='direction')
        self.d34.decider_facturation(a,'non_facturable','Decide apres examen',acteur='direction')
        self.assertEqual(self.interventions()[0]['decision_facturation'],'non_facturable')
        self.assertEqual(self.lecture_sentinelles(),self.sentinelles)

    def test_remplacement_interdit_apres_eligibilite_financiere(self):
        self.valide()
        a=self.interventions()[0]['IDintervention']
        self.d34.marquer_realisee(a,'2025-10-02','09:00','10:00',
                                  'Educateur 1',acteur='direction')
        self.d34.decider_facturation(a,'eligible','Validation',acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.remplacer_intervenant(a,'Educateur 2','Modification tardive',acteur='direction')

    def test_chevauchement_meme_groupe_ou_meme_intervenant_refuse(self):
        self.creneau()
        self.creneau(groupe='Cycle 2-B',intervenant='Educateur 1',horaire=('09:30','10:30'))
        with self.assertRaises(PlanningConflit):
            self.d34.valider_programmation(self.pid,acteur='direction')
        self.assertEqual(self.interventions(),[])

    def test_creneaux_juxtaposes_acceptes(self):
        self.creneau(horaire=('09:00','10:00'))
        self.creneau(groupe='Cycle 2-B',intervenant='Educateur 1',horaire=('10:00','11:00'))
        self.assertEqual(self.d34.valider_programmation(self.pid,acteur='direction')['nombre_seances'],10)

    def test_multi_classes_et_lieux_distincts_acceptes(self):
        self.creneau(groupe='CE1',intervenant='A',horaire=('09:00','10:00'))
        self.creneau(groupe='CE2',intervenant='B',horaire=('09:00','10:00'))
        self.assertEqual(self.d34.valider_programmation(self.pid,acteur='direction')['nombre_seances'],10)

    def test_double_generation_ne_reset_pas_realisation(self):
        self.valide()
        i = self.interventions()[0]['IDintervention']
        self.d34.marquer_realisee(i,'2025-10-02','09:05','10:00','Educateur 1',acteur='direction')
        self.assertTrue(self.d34.valider_programmation(self.pid,acteur='direction')['deja_validee'])
        self.assertEqual(self.interventions()[0]['etat'],'realisee')
        self.assertEqual(self.interventions()[0]['minutes_reelles'],55)

    def test_calendrier_immuable_apres_validation(self):
        self.valide()
        with self.assertRaises(PlanningConflit): self.creneau()
        with self.assertRaises(PlanningConflit):
            self.d34.ajouter_exclusion(self.pid,'2025-10-02','2025-10-02',
                'fermeture','Fermeture tardive',acteur='direction')
        self.assertEqual(len(self.interventions()),5)

    def test_modification_directe_du_calendrier_valide_detectee(self):
        self.valide()
        c=self.conn.execute('SELECT IDcreneau FROM partenaires_creneaux').fetchone()[0]
        self.conn.execute('UPDATE partenaires_creneaux SET heure_debut=? WHERE IDcreneau=?',('08:00',c))
        self.conn.commit()
        with self.assertRaises(PlanningConflit):
            self.d34.apercu_programmation(self.pid,acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.valider_programmation(self.pid,acteur='direction')

    def test_annulation_conserve_motif_origine_et_arbitrage(self):
        self.valide()
        i = self.interventions()[0]['IDintervention']
        self.d34.annuler_intervention(i,'Maladie enseignant','partenaire',True,acteur='direction')
        z=self.interventions()[0]
        self.assertEqual((z['etat'],z['decision_facturation'],z['origine_annulation'],
                          z['justification_annulation']),('annulee','a_arbitrer','partenaire',1))
        with self.assertRaises(PlanningInvalide):
            self.d34.decider_facturation(i,'eligible','Essai',acteur='direction')
        self.assertEqual(self.d34.lister_historique(i,acteur='direction')[0]['action'],'annulation')

    def test_realisation_duree_reelle_distincte_et_tarif_non_auto(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.d34.marquer_realisee(i,'2025-10-02','09:00','09:40','Educateur 1',acteur='direction')
        s=self.d34.resume_programmation(self.pid,acteur='direction')
        self.assertEqual(s['minutes_initialement_prevues'],300)
        self.assertEqual(s['minutes_realisees'],40)
        self.assertEqual(s['eligibles'],0)
        self.assertEqual(s['a_arbitrer'],5)

    def test_une_reservation_ne_peut_devenir_eligible(self):
        self.valide()
        with self.assertRaises(PlanningInvalide):
            self.d34.decider_facturation(self.interventions()[0]['IDintervention'],
                'eligible','Simple calendrier',acteur='direction')

    def test_decision_eligible_seulement_realisee_avec_tarif_signe(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.d34.marquer_realisee(i,'2025-10-02','09:00','10:00','Educateur 1',acteur='direction')
        self.d34.decider_facturation(i,'eligible','Controle valide',acteur='direction')
        self.assertEqual(self.d34.resume_programmation(self.pid,acteur='direction')['eligibles'],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM prestations').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM factures').fetchone()[0],1)

    def test_report_conserve_occurrence_et_necessite_motif(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.d34.reporter_intervention(i,'2025-10-03','11:00','12:00','Salle occupee',acteur='direction')
        z=self.d34.lister_interventions(self.pid,acteur='direction')[0]
        self.assertEqual((z['IDintervention'],z['date_origine'],z['date_prevue'],z['etat']),
                         (i,'2025-10-02','2025-10-03','reportee'))
        hist=self.d34.lister_historique(i,acteur='direction')
        self.assertEqual((hist[0]['date_precedente'],hist[0]['date_suivante']),
                         ('2025-10-02','2025-10-03'))
        self.assertEqual(self.d34.resume_programmation(self.pid,acteur='direction')['nombre'],5)

    def test_report_hors_programmation_demande_ecrite(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        with self.assertRaises(PlanningInvalide):
            self.d34.reporter_intervention(i,'2026-07-10','11:00','12:00','Exception',acteur='direction')
        self.d34.reporter_intervention(i,'2026-07-10','11:00','12:00','Exception',
            acteur='direction',reference_ecrite='Demande REC-99')
        h=self.d34.lister_historique(i,acteur='direction')
        self.assertEqual(h[0]['reference_ecrite'],'Demande REC-99')

    def test_remplacement_sans_double_compte(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.d34.remplacer_intervenant(i,'Educateur 2','Indisponibilite',acteur='direction')
        self.assertEqual(self.d34.resume_programmation(self.pid,acteur='direction')['nombre'],5)
        self.assertEqual(self.d34.lister_historique(i,acteur='direction')[0]['intervenant_suivant'],
                         'Educateur 2')

    def test_brouillon_contractuel_interdit(self):
        cid=self.d2.creer_convention(self.partenaire,'C2','Essai','scolaire',
            '2025-09-01','2026-08-31',acteur='direction')
        v=self.d2.ouvrir_version(cid,'2025-09-01','Clauses','word','Essai','gratuite',acteur='direction')
        with self.assertRaises(PlanningInvalide):
            self.d34.creer_programmation(v,'X','Essai','2025-10-01','2025-12-31',acteur='direction')

    def test_avenant_a_date_effet_scinde_programmation(self):
        v2=self.d2.ouvrir_version(self.cid,'2026-01-01','Avenant','word','Modele','payante',acteur='direction')
        self.d2.remplacer_tarifs(v2,[{'categorie':'scolaires','libelle':'EPS',
            'unite':'heure','montant':'21.00','date_debut':'2026-01-01',
            'date_fin':'2026-08-31'}],acteur='direction')
        self.d2.signer_version(v2,'2025-12-20','Direction','b'*64,acteur='direction')
        with self.assertRaises(PlanningInvalide):
            self.creneau()
            # L'ancien programme traverse l'entree en vigueur du nouvel avenant.
            self.d34.valider_programmation(self.pid,acteur='direction')
        p2=self.d34.creer_programmation(v2,'Nouvelle','Suite','2026-01-01','2026-06-30',acteur='direction')
        self.assertGreater(p2,self.pid)

    def test_durees_dates_jours_et_motifs_invalides(self):
        for d,f in [('2025-10-01','2025-09-30'),('2025-10-01','2026-12-01')]:
            with self.subTest(d=d), self.assertRaises(PlanningInvalide):
                self.creneau(debut=d,fin=f)
        for jour in (-1,7,True,None):
            with self.subTest(jour=jour), self.assertRaises(PlanningInvalide):
                self.creneau(jour=jour)
        for times in [('10:00','09:00'),('13:00','13:00'),('12:00','25:00')]:
            with self.subTest(times=times),self.assertRaises(PlanningInvalide):
                self.creneau(horaire=times)

    def test_prix_gratuit_ne_peut_etre_eligible(self):
        cid=self.d2.creer_convention(self.partenaire,'GRAT','Essai gratuit','scolaire',
            '2025-09-01','2026-08-31',acteur='direction')
        v=self.d2.ouvrir_version(cid,'2025-09-01','Clauses','word','Essai','gratuite',acteur='direction')
        self.d2.signer_version(v,'2025-08-26','Direction','b'*64,acteur='direction')
        p=self.d34.creer_programmation(v,'G','Seance','2025-10-01','2025-10-31',acteur='direction')
        self.creneau(pid=p)
        self.d34.valider_programmation(p,acteur='direction')
        i=self.d34.lister_interventions(p,acteur='direction')[0]['IDintervention']
        self.d34.marquer_realisee(i,'2025-10-02','09:00','10:00','Educateur 1',acteur='direction')
        with self.assertRaises(PlanningInvalide):
            self.d34.decider_facturation(i,'eligible','Test gratuit',acteur='direction')

    def test_rollback_sur_violation_de_contrainte(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.conn.execute("CREATE TRIGGER test_rollback BEFORE UPDATE ON partenaires_interventions "
                          "BEGIN SELECT RAISE(ABORT, 'blocage test'); END;")
        with self.assertRaises(PlanningConflit):
            self.d34.annuler_intervention(i,'Erreur', 'organisation', True,acteur='direction')
        self.assertEqual(self.interventions()[0]['etat'],'prevue')
        self.assertEqual(len(self.d34.lister_historique(i,acteur='direction')),0)

    def test_sauvegarde_restauration_sqlite_fictive(self):
        self.valide()
        source=tempfile.NamedTemporaryFile(suffix='.sqlite',delete=False)
        source.close()
        try:
            avec=sqlite3.connect(source.name)
            self.conn.backup(avec)
            avec.execute('PRAGMA foreign_keys=ON')
            copie=InterventionsPartenaires(avec,autoriser=self.droit)
            self.assertEqual(len(copie.lister_interventions(self.pid,acteur='direction')),5)
            self.assertEqual(copie.apercu_programmation(self.pid,acteur='direction')['total_minutes'],300)
            avec.close()
        finally:
            os.unlink(source.name)

    def test_aucun_historique_financier_ni_rattachement_modifie(self):
        self.valide()
        self.d34.annuler_intervention(self.interventions()[0]['IDintervention'],
            'Annulation justifiee', 'partenaire', True,acteur='direction')
        self.assertEqual(self.lecture_sentinelles(),self.sentinelles)


    def test_reconstitution_130_heures_scolaires_sur_calendrier_explicite(self):
        """Calendrier fictif calque sur les plages de la recette ecole 2025-26.

        Deux exceptions horaires 09-10 octobre, vacances explicitement
        renseignees, aucune conversion de ces reservations en presences.
        """
        e = self.d34
        p = self.pid
        e.ajouter_exclusion(p, '2025-10-20', '2025-11-02', 'vacances',
                           'Interruption calendrier', acteur='direction')
        e.ajouter_exclusion(p, '2025-12-20', '2026-01-04', 'vacances',
                           'Interruption calendrier', acteur='direction')
        def bloc(groupe, debut, fin, horaires, activite):
            resultats=[]
            for jour, debut_h, fin_h in horaires:
                resultats.append(e.ajouter_creneau(p, 'hebdomadaire', debut, fin,
                    debut_h, fin_h, groupe, activite, 'scolaires',
                    acteur='direction',jour_semaine=jour,lieu='Lieu explicite',
                    intervenant='Educateur fictif'))
            return resultats
        cycle2 = bloc('Cycle 2', '2025-09-11', '2025-10-10',
            [(3,'09:00','12:00'),(4,'09:00','12:00')], 'Athletisme')
        bloc('Cycle 2', '2026-05-21', '2026-06-19',
            [(3,'09:00','12:00'),(4,'09:00','12:00')], 'Tennis')
        bloc('Cycle 3', '2025-10-09', '2025-11-21',
            [(3,'09:00','11:00'),(4,'09:00','11:00')], 'Lutte')
        bloc('Cycle 3', '2026-03-12', '2026-04-10',
            [(3,'10:00','12:00'),(4,'10:00','12:00')], 'Bumball')
        bloc('Cycle 1', '2025-11-27', '2026-01-09',
            [(3,'09:00','11:00'),(4,'10:00','11:00')], 'Motricite')
        bloc('Cycle 1', '2026-01-15', '2026-02-13',
            [(3,'09:00','11:00'),(4,'10:00','11:00')], 'Acrosport')
        for c, jour in zip(cycle2, ('2025-10-09','2025-10-10')):
            e.ajouter_exception(c, jour, 'deplacer', 'Horaire exceptionnel scolaire',
                date_remplacement=jour,heure_debut='13:15',heure_fin='16:15',
                acteur='direction')
        preview = e.apercu_programmation(p, acteur='direction')
        self.assertEqual(preview['total_minutes'], 130*60)
        self.assertEqual(len(preview['seances']), 60)  # 20+20+20 lignes de groupe
        self.assertEqual(e.valider_programmation(p,acteur='direction')['nombre_seances'],60)
        self.assertEqual(e.resume_programmation(p,acteur='direction')['minutes_realisees'],0)
        self.assertEqual(e.resume_programmation(p,acteur='direction')['eligibles'],0)
        self.assertEqual(self.lecture_sentinelles(),self.sentinelles)

    def test_recurrence_associative_differenciee_sans_facturation(self):
        club=self.d1.creer_structure({'categorie':'association','raison_sociale':'Club fictif'},
                                     acteur='direction')
        contrat=self.d2.creer_convention(club,'2026-27','Encadrement',
            'associative','2026-09-01','2027-06-30',acteur='direction')
        v=self.d2.ouvrir_version(contrat,'2026-09-01','Clauses associatives',
            'word','Modele-fictif','payante',acteur='direction')
        self.d2.remplacer_tarifs(v,[
            {'categorie':c,'libelle':l,'unite':'heure','montant':m,
             'date_debut':'2026-09-01','date_fin':'2027-06-30'}
            for c,l,m in [('adultes','Fitness','36.50'),('enfants','Badminton','24.00')]
        ],acteur='direction')
        self.d2.signer_version(v,'2026-08-31','Direction','b'*64,acteur='direction')
        p=self.d34.creer_programmation(v,'Septembre','Semaine scolaire',
            '2026-09-07','2026-09-13',acteur='direction')
        for jour,d,f,categorie,activite in (
            (0,'19:30','20:30','adultes','Fitness'),
            (2,'17:30','19:00','enfants','Badminton'),
            (3,'10:00','11:00','adultes','Fitness')):
            self.d34.ajouter_creneau(p,'hebdomadaire','2026-09-07','2026-09-13',
                d,f,activite,activite,categorie,acteur='direction',jour_semaine=jour,
                lieu='Salle declaree',intervenant='Educateur fictif')
        preview=self.d34.apercu_programmation(p,acteur='direction')
        self.assertEqual(preview['total_minutes'],210)
        self.assertEqual(self.d34.valider_programmation(p,acteur='direction')['nombre_seances'],3)
        self.assertEqual({z['categorie_tarif'] for z in
            self.d34.lister_interventions(p,acteur='direction')},{'adultes','enfants'})
        self.assertEqual(self.d34.resume_programmation(p,acteur='direction')['eligibles'],0)

    def test_reference_ecrite_et_historique_remplacement_visibles(self):
        self.valide()
        i=self.interventions()[0]['IDintervention']
        self.d34.remplacer_intervenant(i,'Educateur 2','Absence en formation',acteur='direction')
        self.d34.marquer_realisee(i,'2025-10-02','09:00','10:00','Educateur 2',acteur='direction')
        h=self.d34.lister_historique(i,acteur='direction')
        self.assertEqual([x['action'] for x in h], ['remplacement','realisation'])
        self.assertEqual(len(self.interventions()),5)

    def test_convention_signee_alteree_detectee_au_planning(self):
        self.creneau()
        self.conn.execute("UPDATE partenaires_conventions_versions SET clauses='hack' WHERE IDversion=?",
                          (self.vid,))
        self.conn.commit()
        with self.assertRaises(Exception) as msg:
            self.d34.apercu_programmation(self.pid,acteur='direction')
        self.assertIn('Modification detectee',str(msg.exception))


if __name__ == '__main__': unittest.main()
