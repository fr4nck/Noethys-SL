# -*- coding: utf-8 -*-
"""Recette de l'accueil sur données intégralement fictives ; aucun portail joint."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401,E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
import datetime as dt
import sqlite3
import unittest
from unittest.mock import patch, Mock
from Utils import UTILS_Accueil_jour as day
from Utils import UTILS_Ephemerides as weather


class ReadOnlyFixture:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
        CREATE TABLE activites(IDactivite,nom,abrege,date_debut,date_fin);
        CREATE TABLE unites(IDunite,IDactivite,heure_debut,heure_fin,date_debut,date_fin);
        CREATE TABLE ouvertures(IDunite,date);
        CREATE TABLE evenements(IDactivite,date);
        CREATE TABLE consommations(IDactivite,IDindividu,IDunite,date,etat,heure_debut,heure_fin);
        INSERT INTO activites VALUES(1,'Accueil de loisirs fictif','ALSH',NULL,NULL),
        (2,'Couture fictive','Couture',NULL,NULL),(3,'Ancienne activité','Ancien',NULL,'2025-01-01'),
        (4,'Sport santé fictif','Sport',NULL,NULL),(5,'Sans séance','Rien',NULL,NULL);
        INSERT INTO unites(IDunite,IDactivite,heure_debut,heure_fin,date_debut,date_fin) VALUES(1,1,'08:00','12:00',NULL,NULL),(2,1,'12:00','18:00',NULL,NULL),
        (3,2,'10:00','11:00',NULL,NULL),(4,3,'10:00','11:00',NULL,NULL);
        INSERT INTO ouvertures VALUES(1,'2026-10-16'),(2,'2026-10-16'),(3,'2026-10-16'),(4,'2026-10-16');
        INSERT INTO evenements VALUES(4,'2026-10-16');
        INSERT INTO consommations VALUES
        (1,101,1,'2026-10-16','reservation',NULL,NULL),
        (1,101,1,'2026-10-16','present',NULL,NULL),
        (1,101,2,'2026-10-16','reservation',NULL,NULL),
        (1,102,2,'2026-10-16','reservation',NULL,NULL),
        (1,103,1,'2026-10-16','attente',NULL,NULL),
        (1,104,1,'2026-10-16','absentj',NULL,NULL),
        (1,105,1,'2026-10-16','absenti',NULL,NULL),
        (1,106,1,'2026-10-15','reservation',NULL,NULL),
        (3,107,4,'2026-10-16','reservation',NULL,NULL);
        ALTER TABLE ouvertures ADD COLUMN IDgroupe DEFAULT 10;
        ALTER TABLE evenements ADD COLUMN IDgroupe DEFAULT 10;
        ALTER TABLE consommations ADD COLUMN IDgroupe DEFAULT 10;
        CREATE TABLE groupes(IDgroupe,nom,abrege);
        INSERT INTO groupes VALUES(10,'Bais moins de six ans','Bais −6'),
        (11,'Moutiers moins de six ans','Mout. −6');
        ALTER TABLE consommations ADD COLUMN etiquettes;
        CREATE TABLE unites_remplissage(IDunite_remplissage,IDactivite,nom,abrege,heure_min,heure_max,etiquettes,date_debut,date_fin);
        CREATE TABLE unites_remplissage_unites(IDunite_remplissage,IDunite);
        INSERT INTO unites_remplissage VALUES(101,1,'Matin','MAT',NULL,NULL,NULL,NULL,NULL),
        (102,1,'Après-midi','APM',NULL,NULL,NULL,NULL,NULL);
        INSERT INTO unites_remplissage_unites VALUES(101,1),(102,2);
        ''')
        self.db.executescript('ALTER TABLE unites ADD COLUMN nom; ALTER TABLE consommations ADD COLUMN IDevenement; ALTER TABLE evenements ADD COLUMN IDunite; ALTER TABLE evenements ADD COLUMN IDevenement; ALTER TABLE evenements ADD COLUMN heure_debut; ALTER TABLE evenements ADD COLUMN heure_fin; ALTER TABLE evenements ADD COLUMN nom;')
        self.before = self.db.total_changes

    def ExecuterReq(self, sql):
        assert sql.lstrip().upper().startswith('SELECT'), sql
        self.cursor = self.db.execute(sql)
        return True

    def ResultatReq(self):
        return self.cursor.fetchall()


class ProgrammeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReadOnlyFixture()
        self.addCleanup(self.fixture.db.close)

    def read(self, settings=None):
        result = day.read_day(self.fixture, dt.date(2026, 10, 16), settings)
        self.assertEqual(self.fixture.db.total_changes, self.fixture.before)
        return result

    def test_context_and_distinct_half_day_counts(self):
        rows, choices = self.read()
        self.assertEqual([r['id'] for r in rows], [1, 2, 4])
        self.assertEqual((rows[0]['total'],rows[0]['morning'],rows[0]['afternoon']), (2,1,2))
        self.assertEqual(rows[1]['total'], 0)  # ouverture sans réservation
        self.assertEqual(rows[2]['total'], 0)  # événement sans réservation
        self.assertNotIn(3, [r['id'] for r in choices])
        self.assertIn(5, [r['id'] for r in choices])  # active mais pas aujourd'hui

    def test_visibility_classification_order_and_inactive_cannot_be_forced(self):
        rows, _ = self.read(dict(activities={'1':dict(visible=False),
                  '4':dict(visible=True,alsh=False,order=1), '3':dict(visible=True,alsh=True)}))
        self.assertEqual([r['id'] for r in rows], [4,2])

    def test_unknown_period_mapping_does_not_show_false_zero(self):
        self.fixture.db.execute("DELETE FROM unites_remplissage WHERE IDunite_remplissage=102")
        self.fixture.before = self.fixture.db.total_changes
        rows, _ = self.read()
        self.assertIsNone(rows[0]['morning'])
        self.assertIsNone(rows[0]['afternoon'])
        self.assertEqual(rows[0]['total'],2)

    def test_native_mysql_time_values(self):
        self.assertEqual(day.minutes(dt.timedelta(hours=8,minutes=30)),510)
        self.assertEqual(day.minutes(dt.time(13,30)),810)
        self.assertIsNone(day.minutes(None))

    def test_bad_preferences_and_no_fixed_event_limit(self):
        self.assertEqual(day.preferences({'activities':'bad'})['activities'],{})
        self.assertEqual(day.preferences({'event_count':12000})['event_count'],12000)
        self.assertEqual(day.preferences()['event_count'],0)

    def test_full_day_participation_counts_in_both_periods(self):
        self.fixture.db.execute("INSERT INTO unites_remplissage_unites VALUES(102,1)")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        self.assertEqual((rows[0]['total'],rows[0]['morning'],rows[0]['afternoon']),(2,1,2))

    def test_alsh_separates_groups_without_mixing_sites_or_ages(self):
        self.fixture.db.execute("INSERT INTO ouvertures VALUES(1,'2026-10-16',11)")
        self.fixture.db.execute("INSERT INTO consommations(IDactivite,IDindividu,IDunite,date,etat,heure_debut,heure_fin,IDgroupe,etiquettes) VALUES(1,201,1,'2026-10-16','reservation',NULL,NULL,11,NULL)")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        alsh=[r for r in rows if r['alsh']]
        self.assertEqual([(r['label'],r['morning'],r['afternoon']) for r in alsh],
                         [('Bais −6',1,2),('Mout. −6',1,0)])

    def test_meal_alone_is_not_an_afternoon_even_when_it_starts_at_noon(self):
        self.fixture.db.execute("INSERT INTO unites(IDunite,IDactivite,heure_debut,heure_fin,date_debut,date_fin) VALUES(9,1,'12:00','13:00',NULL,NULL)")
        self.fixture.db.execute("INSERT INTO consommations(IDactivite,IDindividu,IDunite,date,etat,heure_debut,heure_fin,IDgroupe,etiquettes) VALUES(1,999,9,'2026-10-16','reservation',NULL,NULL,10,NULL)")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        self.assertEqual((rows[0]['morning'],rows[0]['afternoon']),(1,2))

    def test_configured_time_and_tag_conditions_match_filling_contract(self):
        self.fixture.db.execute("UPDATE unites_remplissage SET heure_min='09:00',heure_max='11:00',etiquettes='7' WHERE IDunite_remplissage=101")
        self.fixture.db.execute("UPDATE consommations SET heure_debut='08:00',heure_fin='12:00',etiquettes='7;9' WHERE IDindividu=101")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        self.assertEqual(rows[0]['morning'],1)
        self.fixture.db.execute("UPDATE consommations SET etiquettes='9' WHERE IDindividu=101")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        self.assertEqual(rows[0]['morning'],0)

    def test_explicit_period_choice_for_nonstandard_unit_names(self):
        self.fixture.db.execute("UPDATE unites_remplissage SET nom='Créneau spécial',abrege='Special' WHERE IDunite_remplissage=102")
        self.fixture.before=self.fixture.db.total_changes
        rows,_=self.read()
        self.assertIsNone(rows[0]['afternoon'])
        rows,_=self.read(dict(activities={'1':dict(visible=True,alsh=True,morning_unit=101,afternoon_unit=102)}))
        self.assertEqual((rows[0]['morning'],rows[0]['afternoon']),(1,2))

    def test_query_failure_cannot_look_like_empty_programme(self):
        with patch.object(self.fixture,'ExecuterReq',return_value=False):
            with self.assertRaises(ValueError):self.read()

    def test_non_alsh_separates_slots_and_deduplicates_each_slot(self):
        self.fixture.db.executescript("""
        INSERT INTO unites(IDunite,IDactivite,heure_debut,heure_fin) VALUES(5,2,'14:00','15:00');
        INSERT INTO ouvertures VALUES(5,'2026-10-16',10);
        INSERT INTO consommations(IDactivite,IDindividu,IDunite,date,etat,IDgroupe)
        VALUES(2,201,3,'2026-10-16','reservation',10),
        (2,201,3,'2026-10-16','present',10),
        (2,201,5,'2026-10-16','reservation',10),
        (2,202,5,'2026-10-16','reservation',10),
        (2,203,5,'2026-10-16','attente',10);
        """)
        self.fixture.before = self.fixture.db.total_changes
        rows, choices = self.read()
        slots = [r for r in rows if r['id'] == 2]
        self.assertEqual([r['total'] for r in slots], [1, 2])
        self.assertIn('10h00–11h00', slots[0]['label'])
        self.assertIn('14h00–15h00', slots[1]['label'])
        self.assertEqual(len([r for r in choices if r['id'] == 2]), 1)

    def test_event_identity_and_unknown_link_do_not_merge_same_time_sessions(self):
        self.fixture.db.executescript("""
        UPDATE evenements SET IDunite=30, IDevenement=501, nom='Séance A', heure_debut='09:00',heure_fin='10:00' WHERE IDactivite=4;
        INSERT INTO evenements(IDactivite,date,IDgroupe,IDunite,IDevenement,nom,heure_debut,heure_fin)
        VALUES(4,'2026-10-16',10,30,502,'Séance B','09:00','10:00');
        INSERT INTO consommations(IDactivite,IDindividu,IDunite,date,etat,IDgroupe,IDevenement)
        VALUES(4,201,30,'2026-10-16','reservation',10,501),
        (4,202,30,'2026-10-16','reservation',10,502),
        (4,203,30,'2026-10-16','reservation',10,NULL);
        """)
        self.fixture.before = self.fixture.db.total_changes
        rows, _ = self.read()
        slots = [r for r in rows if r['id'] == 4]
        self.assertEqual([r['total'] for r in slots], [1, 1, 1])
        self.assertIn('Séance A', slots[0]['label'])
        self.assertIn('Séance B', slots[1]['label'])
        self.assertIn('horaire non renseigné', slots[2]['label'])

    def test_same_time_different_groups_remain_distinct_even_without_reservations(self):
        self.fixture.db.execute("INSERT INTO ouvertures VALUES(3,'2026-10-16',11)")
        self.fixture.before = self.fixture.db.total_changes
        rows, _ = self.read()
        slots = [r for r in rows if r['id'] == 2]
        self.assertEqual(len(slots), 2)
        self.assertEqual({r['group'] for r in slots}, {10, 11})
        self.assertTrue(all(r['total'] == 0 for r in slots))

    def test_circular_wind_and_unknown_cache(self):
        from test_ephemerides import forecast
        p = forecast(1)
        p['hourly']['wind_direction_10m'] = [359,1]*12
        rows = weather.aggregate_weather(p)
        self.assertEqual(weather.wind_arrow(rows[0]['wind_direction_10m']),'↑')
        del p['hourly']['wind_direction_10m']
        self.assertIsNone(weather.aggregate_weather(p)[0]['wind_direction_10m'])
        self.assertEqual(weather.wind_arrow(None),'—')


class NativeAccueilTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.GetApp() or wx.App(False)

    def test_native_settings_round_trip_and_count(self):
        import wx
        from Ctrl import CTRL_Ephemeride as ui
        frame=wx.Frame(None)
        fixture=ReadOnlyFixture()
        self.addCleanup(fixture.db.close)
        items,_=day.read_day(fixture,dt.date(2026,10,16))
        panel=ui.CTRL(frame)
        dialog=ui.Settings(frame,{},weather.normalize_dashboard_layout(),items)
        try:
            dialog.event_count.SetValue('42')
            dialog.activity_grid.SetCellValue(0,0,'')
            value=dialog.layout_values()
            self.assertEqual(value['day']['event_count'],42)
            self.assertFalse(value['day']['activities']['1']['visible'])
            panel._layout=value
            panel.render_events()
            self.assertEqual(panel.events_scroll.GetParent(),panel.block_panels['events'])
            self.assertIs(panel.detail,panel.weather)
            self.assertFalse(panel._timer.IsRunning())  # pas de démarrage réseau implicite
        finally:
            dialog.Destroy();frame.Destroy();self.app.Yield()

    def test_compact_connecthys_states_and_late_callbacks(self):
        import wx
        from Ctrl import CTRL_Portail_serveur as portal
        frame=wx.Frame(None)
        frame.taskBarIcon=Mock()
        class DB:
            def ExecuterReq(self,sql):return True
            def ResultatReq(self):return [(1,'fictif')]
            def Close(self):pass
        with patch.object(portal.GestionDB,'DB',return_value=DB()):
            panel=portal.Panel(frame,compact=True,owner=frame)
        try:
            self.assertIn('1 demande',panel.bouton_traiter.GetLabel())
            panel._AfficherEtat('busy')
            self.assertTrue(panel.gauge.IsShown())
            with patch.object(portal.GestionDB,'DB',return_value=Mock(ExecuterReq=Mock(return_value=False))):
                self.assertFalse(panel.MAJ_bouton())
            self.assertIn('1 demande',panel.bouton_traiter.GetLabel())
            panel._AfficherEtat('success')
            success=panel._last_success
            panel._AfficherEtat('error')
            self.assertFalse(panel.gauge.IsShown())
            self.assertIn('Échec',panel.ctrl_etat.GetLabel())
            self.assertEqual(panel._last_success,success)
            self.assertIn('1 demande',panel.bouton_traiter.GetLabel())
            panel._alive=False
            panel._AfficherEtat('success')  # aucune écriture wx après fermeture
        finally:
            frame.Destroy();self.app.Yield()

    def test_four_headings_align_and_connecthys_fits_the_body(self):
        import wx
        from Ctrl import CTRL_Ephemeride as ui
        from Ctrl import CTRL_Portail_serveur as portal
        frame=wx.Frame(None)
        frame.SetClientSize((1200,360))
        frame.taskBarIcon=Mock()
        panel=ui.CTRL(frame)
        db=Mock(ExecuterReq=Mock(return_value=True),ResultatReq=Mock(return_value=[]))
        with patch.object(portal.GestionDB,'DB',return_value=db):
            connect=portal.Panel(panel,compact=True,owner=frame)
        try:
            panel.AttachConnecthys(connect)
            outer=wx.BoxSizer(wx.VERTICAL)
            outer.Add(panel,1,wx.EXPAND)
            frame.SetSizer(outer)
            panel.Show();frame.Layout();panel.Layout()
            labels=[p.heading for p in panel.block_panels.values()]
            labels.append(connect.GetSizer().GetItem(0).GetWindow())
            self.assertEqual(len({w.GetScreenPosition().y for w in labels}),1)
            right=connect.GetScreenPosition().x+connect.GetSize().width
            self.assertLessEqual(right,panel.GetScreenPosition().x+panel.GetClientSize().width)
        finally:
            frame.Destroy();self.app.Yield()

    def test_weather_icons_render_all_categories_on_native_dc(self):
        import wx
        from Ctrl import CTRL_Accueil_compact as compact
        frame=wx.Frame(None)
        panel=compact.Meteo(frame,Mock())
        bitmap=wx.Bitmap(320,120)
        dc=wx.MemoryDC(bitmap)
        try:
            for index,code in enumerate([None,0,3,45,61,71,95]):
                panel.icon(dc,index*40,20,code)
            self.assertTrue(bitmap.IsOk())
        finally:
            dc.SelectObject(wx.NullBitmap)
            frame.Destroy();self.app.Yield()

    def test_cycle_reports_boolean_failure_and_exception_without_sticking_busy(self):
        from Ctrl import CTRL_Portail_serveur as portal
        for outcome in (True,False,RuntimeError('synthetic')):
            parent=Mock(last_synchro=dt.datetime.now(),delai=60,synchro_ouverture=False)
            server=portal.Serveur(parent)
            server.start_synchro=True
            instance=Mock()
            if isinstance(outcome,Exception):instance.Synchro_totale.side_effect=outcome
            else:instance.Synchro_totale.return_value=outcome
            with patch.object(portal.UTILS_Portail_synchro,'Synchro',return_value=instance):
                if isinstance(outcome,Exception):
                    with self.assertRaises(RuntimeError):server.EffectuerCycle()
                else:server.EffectuerCycle()
            self.assertFalse(server.synchro_en_cours)
            self.assertEqual([c.args[0] for c in parent.SetEtatSynchro.call_args_list],
                             ['busy','success' if outcome is True else 'error'])


if __name__=='__main__':unittest.main()
