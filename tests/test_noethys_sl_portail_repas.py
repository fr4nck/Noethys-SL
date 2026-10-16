# -*- coding: utf-8 -*-
"""Traitement réel sur grille fictive : ni DB réelle, ni email, ni portail."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401,E402
import copy
import datetime as dt
import concurrent.futures
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from Dlg import DLG_Saisie_portail_demande as ui
from Utils import UTILS_Portail_reservations as rules

DAY = dt.date(2026, 11, 4)


def unit(name, ID):
    return dict(nom=name, IDactivite=1, unites_principales=[ID], unites_secondaires=[])


class Case:
    def __init__(self, state=None, invoice=None, locked=0):
        self.etat, self.IDfacture, self.locked = state, invoice, locked

    def GetListeConso(self):
        return [NS(etat=self.etat, verrouillage=self.locked, IDfacture=self.IDfacture, IDinscription=77)] if self.etat else []


class Grid:
    def __init__(self, full=()):
        self.full, self.cases, self.calls = set(full), {}, []
        self.ctrl_titre = NS(GetNom=lambda: 'Enfant strictement fictif')
        self.grille = NS(dictUnites={ID: dict(nom=str(ID), type='Unitaire') for ID in range(101, 106)})

    def GetCase(self, IDunite, date):
        return self.cases.setdefault((IDunite, date), Case())

    def IsOuvert(self, **kw):
        return True

    def HasPlacesDisponibles(self, IDunite, date):
        return IDunite not in self.full

    def SaisieConso(self, IDunite, date, mode, etat='reservation'):
        case = self.GetCase(IDunite, date)
        # Reproduit le contrat de SaisieConso sur unité unitaire existante.
        case.etat = etat if case.etat else mode
        self.calls.append((IDunite, date, mode, etat))
        return True

    def SupprimeConso(self, IDunite, date):
        self.GetCase(IDunite, date).etat = None
        self.calls.append(('suppression', IDunite, date))
        return True


class ReservationsTests(unittest.TestCase):
    def setUp(self):
        self.units = {1:unit('Matin',101), 2:unit('Repas',102),
                      3:unit('Après-midi',103), 4:unit('Journée',104), 5:unit('Autre',105)}
        self.logs = []
        self.roles = []
        self.requests = []
        self.sql = []

    def request(self, portal, date=DAY, inscription=77, state=1):
        self.requests.append((len(self.requests)+1,date,inscription,portal,state,self.units[portal]['nom']))

    def apply(self, grid):
        owner = self
        class DB:
            def ExecuterReq(self, sql):
                owner.sql.append(sql)
                assert sql.lstrip().upper().startswith('SELECT')
                self.rows = owner.requests if 'FROM portail_reservations' in sql else owner.roles
                return True
            def ResultatReq(self):return self.rows
            def Close(self):pass
        handler = object.__new__(ui.Traitement)
        handler.dict_parametres = dict(IDactivite=1,date_debut_periode=str(DAY),date_fin_periode=str(DAY))
        handler.track = NS(IDaction=1, horodatage=dt.datetime(2026,10,16))
        handler.parent = NS(dictUnites=self.units,dictActivites={1:dict(portail_reservations_absenti=None)})
        handler.EcritLog = lambda text, log=None: self.logs.append(text)
        with patch.object(ui.GestionDB,'DB',DB):
            return handler.Appliquer_reservations(grid)

    def test_either_half_day_waits_meal_even_when_meal_arrived_first(self):
        for full in (101,103):
            with self.subTest(full=full):
                self.requests=[]
                for p in (2,1,3):self.request(p)
                grid=Grid([full])
                self.apply(grid)
                self.assertEqual(grid.GetCase(102,DAY).etat,'attente')
                self.assertEqual(grid.calls[-1][0],102)
                self.assertTrue(all(sql.lstrip().startswith('SELECT') for sql in self.sql))

    def test_single_requested_half_day_is_sufficient_when_confirmed(self):
        for p in (1,3):
            self.requests=[]
            self.request(2);self.request(p)
            grid=Grid()
            self.apply(grid)
            self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_meal_only_action_respects_an_earlier_waiting_period(self):
        self.request(2)
        for ID in (101,103,104):
            grid=Grid();grid.cases[(ID,DAY)]=Case('attente')
            self.apply(grid)
            self.assertEqual(grid.GetCase(102,DAY).etat,'attente')

    def test_cancelled_old_wait_does_not_block_meal_and_meal_does_not_gate_itself(self):
        self.request(1,state=0);self.request(2)
        self.units[4]['unites_principales']=[101,102,103]
        grid=Grid();grid.cases[(101,DAY)]=Case('attente')
        grid.cases[(102,DAY)]=Case('attente')
        self.apply(grid)
        self.assertIsNone(grid.GetCase(101,DAY).etat)
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_existing_wait_from_another_inscription_is_not_used(self):
        self.request(2)
        grid=Grid();case=Case('attente')
        case.GetListeConso=lambda:[NS(etat='attente',IDinscription=88)]
        grid.cases[(101,DAY)]=case
        self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_old_wait_without_identifiable_inscription_requires_manual_processing(self):
        self.request(2)
        grid=Grid();case=Case('attente')
        case.GetListeConso=lambda:[NS(etat='attente',IDinscription=None)]
        grid.cases[(101,DAY)]=case
        self.assertEqual(self.apply(grid),'')
        self.assertEqual(grid.calls,[])

    def test_full_day_waits_meal(self):
        self.request(2);self.request(4)
        grid=Grid([104])
        self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'attente')

    def test_real_grid_saisie_requires_explicit_wait_state_for_existing_meal(self):
        from Dlg import DLG_Badgeage_grille as badgeage
        case=Case('reservation')
        case.ouvert=True
        case.HasPlaceDisponible=lambda *args:True
        case.VerifieCompatibilitesUnites=lambda:None
        case.IsCaseDisponible=lambda *args:False
        case.ModifieEtat=lambda conso,etat:setattr(case,'etat',etat)
        grid=NS(GetCase=lambda *args:case,usage='portail',grille=NS(dictUnites={
            102:dict(type='Unitaire',heure_debut=None,heure_fin=None)}))
        self.assertTrue(badgeage.CTRL.SaisieConso(grid,IDunite=102,date=DAY,mode='attente'))
        self.assertEqual(case.etat,'reservation')  # contrat historique reproduit
        self.assertTrue(badgeage.CTRL.SaisieConso(grid,IDunite=102,date=DAY,mode='attente',etat='attente'))
        self.assertEqual(case.etat,'attente')

    def test_existing_unbilled_meal_is_not_reconfirmed_by_default_etat(self):
        self.request(1);self.request(2)
        grid=Grid([101]);grid.cases[(102,DAY)]=Case('reservation')
        self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'attente')
        self.assertEqual(grid.calls[-1][2:],('attente','attente'))

    def test_reprocessing_can_confirm_waiting_meal_when_requested_period_is_confirmed(self):
        self.request(1);self.request(2)
        grid=Grid([101]);self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'attente')
        grid.full.clear()
        self.apply(grid)
        self.assertEqual(grid.GetCase(101,DAY).etat,'reservation')
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')
        self.assertEqual(sum(bool(c.etat) for c in grid.cases.values()),2)

    def test_ambiguous_multiple_full_day_formulas_require_manual_resolution(self):
        self.roles=[('5','journee')]
        for p in (1,3,4,5,2):self.request(p)
        grid=Grid()
        self.assertEqual(self.apply(grid),'')
        self.assertEqual(grid.calls,[])
        self.assertTrue(any('Plusieurs formules Journée' in line for line in self.logs))

    def test_three_choices_keep_full_day_and_explain_in_response(self):
        for p in (1,2,3,4):self.request(p)
        grid=Grid()
        response=self.apply(grid)
        self.assertEqual([c[0] for c in grid.calls],[104,102])
        self.assertIn('La formule Journée a été retenue',response)
        self.assertIn('Matin et Après-midi',response)
        self.assertIn('04/11/2026',response)

    def test_redundant_halves_cannot_block_a_full_day_with_available_places(self):
        for p in (1,3,4,2):self.request(p)
        grid=Grid([101,103]);self.apply(grid)
        self.assertEqual(grid.GetCase(104,DAY).etat,'reservation')
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_priority_does_not_silently_convert_preexisting_half_day_records(self):
        for p in (1,3,4,2):self.request(p)
        grid=Grid();grid.cases[(101,DAY)]=Case('reservation',invoice=55)
        self.assertEqual(self.apply(grid),'')
        self.assertEqual(grid.calls,[])
        self.assertEqual(grid.GetCase(101,DAY).IDfacture,55)

    def test_waited_full_day_wins_over_available_redundant_halves(self):
        for p in (1,3,4,2):self.request(p)
        grid=Grid([104]);self.apply(grid)
        self.assertEqual([c[0] for c in grid.calls],[104,102])
        self.assertTrue(all(c[2]=='attente' for c in grid.calls))

    def test_no_cross_date_or_cross_inscription_link(self):
        self.request(1);self.request(2,inscription=88)
        self.request(2,date=DAY+dt.timedelta(days=1))
        grid=Grid([101]);self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')
        self.assertEqual(grid.GetCase(102,DAY+dt.timedelta(days=1)).etat,'reservation')

    def test_cancellation_and_independent_choice_do_not_gate_meal(self):
        self.request(1,state=0);self.request(5);self.request(2)
        grid=Grid([105]);self.apply(grid)
        self.assertEqual(grid.calls[0],('suppression',101,DAY))
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_custom_roles_and_explicit_independent_opt_out(self):
        for p in (1,2):self.units[p]['nom']='Libellé personnalisé %s'%p
        self.roles=[('1','matin'),('2','repas')]
        self.request(2);self.request(1)
        grid=Grid([101]);self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'attente')
        self.roles=[('1','normal'),('2','repas')]
        grid=Grid([101]);self.apply(grid)
        self.assertEqual(grid.GetCase(102,DAY).etat,'reservation')

    def test_protected_meal_rejects_before_any_mutation(self):
        self.request(1);self.request(2)
        for case in (Case('reservation',invoice=55),Case('present'),Case('absenti'),Case('reservation',locked=1)):
            with self.subTest(case=vars(case)):
                grid=Grid([101]);grid.cases[(102,DAY)]=case
                previous=copy.deepcopy(vars(case))
                self.assertEqual(self.apply(grid),'')
                self.assertEqual(grid.calls,[])
                self.assertEqual(vars(case),previous)

    def test_closed_period_cannot_silently_confirm_meal(self):
        self.request(1);self.request(2)
        grid=Grid()
        grid.IsOuvert=lambda IDunite,date:IDunite!=101
        self.assertEqual(self.apply(grid),'')
        self.assertEqual(grid.calls,[])

    def test_nonstandard_meal_type_is_left_to_manual_processing(self):
        self.request(1);self.request(2)
        for kind in ('Quantite','Evenement','Multihoraires'):
            grid=Grid()
            grid.grille.dictUnites[102]['type']=kind
            self.assertEqual(self.apply(grid),'')
            self.assertEqual(grid.calls,[])

    def test_prepare_is_pure_and_reentrant(self):
        inputs=[dict(IDreservation=p,date=DAY,IDinscription=77,IDunite=p,etat=1) for p in (1,2,3,4)]
        before=copy.deepcopy(inputs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _: rules.prepare(inputs,self.units),range(12)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(inputs,before)
        self.assertTrue(all('role_portail' not in u for u in self.units.values()))

    def test_compound_names_are_not_silently_classified_as_meals(self):
        self.assertEqual(rules.role(dict(nom='Matin avec repas')),'normal')
        self.assertEqual(rules.role(dict(nom='Accueil journée avec repas')),'normal')

    def test_role_setting_uses_existing_parameters_without_schema_change(self):
        import wx
        from unittest.mock import Mock
        from Dlg import DLG_Saisie_portail_unite as settings
        app = wx.GetApp() or wx.App(False)
        with patch.object(settings.Liste_unites_conso,'MAJ',lambda self:None):
            dialog=settings.Dialog(None,IDactivite=1)
        try:
            self.assertEqual(dialog.ctrl_role.GetSelection(),0)
            self.assertEqual(dialog.ctrl_role.GetCount(),len(rules.ROLES))
            dialog.ctrl_nom.SetValue('Libellé de restauration personnalisé')
            dialog.ctrl_role.SetSelection(rules.ROLES.index('repas'))
            database=NS(ReqInsert=Mock(return_value=23),Close=Mock())
            with patch.object(dialog.ctrl_unites_principales,'GetIDcoches',return_value=[102]), \
                 patch.object(dialog.ctrl_unites_principales,'GetCochesStr',return_value='102'), \
                 patch.object(dialog.ctrl_unites_secondaires,'GetIDcoches',return_value=[]), \
                 patch.object(dialog.ctrl_unites_secondaires,'GetCochesStr',return_value=''), \
                 patch.object(settings.GestionDB,'DB',return_value=database), \
                 patch.object(settings.UTILS_Parametres,'Parametres') as persist, \
                 patch.object(dialog,'EndModal'):
                dialog.OnBoutonOk(None)
            persist.assert_called_once_with(mode='set',categorie=rules.CATEGORY,nom='23',valeur='repas')
            database.Close.assert_called_once()
        finally:
            dialog.Destroy();app.Yield()


if __name__=='__main__':unittest.main()
