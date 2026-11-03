# -*- coding: utf-8 -*-
"""ALSH-C3 wx : details par enfant et commune de domicile datee.

Nouvelle vue NOMINATIVE, rattachee a l'etat financier wx deja existant.
Aucune creation de facture. Les imports et demenagements successifs sont
pris en charge par C2 APRES MIGRATIONS QUALIFIEES ET INSTALLEES.
"""
from datetime import date
from pathlib import Path

import wx
import GestionDB
from Utils import UTILS_ALSH_C3_Session as c3


PARTIES = (('Non qualifiee', None), ('Journee', 'J'),
           ('Matin', 'M'), ('Apres-midi', 'A'), ('Exclure', 'exclu'))


def _erreur(parent, msg, titre='Situation ALSH'):
    wx.MessageBox(str(msg), titre, wx.OK | wx.ICON_ERROR, parent)


def _label(parent, text):
    return wx.StaticText(parent, label=text)


def _liste(parent, titres):
    ctrl = wx.ListCtrl(parent, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
    for i, (titre, largeur) in enumerate(titres):
        ctrl.InsertColumn(i, titre, width=largeur)
    return ctrl


def _remplir(ctrl, rows):
    ctrl.DeleteAllItems()
    for values in rows:
        idx = ctrl.InsertItem(ctrl.GetItemCount(), str(values[0] if values[0] is not None else ''))
        for col, value in enumerate(values[1:], 1):
            ctrl.SetItem(idx, col, '' if value is None else str(value))


def _droit(service, action):
    return service.droits.autoriser(service.acteur, action)


class Correspondance(wx.Dialog):
    """Aucun code INSEE n'est devine a partir d'un seul code postal."""

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title='Ajouter une commune de residence',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.inputs = {}
        box = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1)
        for key, label in (('cp','Code postal (5 chiffres)'),
                           ('ville','Nom de ville dans Noethys'),
                           ('code','Code INSEE confirme (5 caracteres)'),
                           ('libelle','Nom de la commune pour l edition')):
            grid.Add(_label(self, label), 0, wx.ALIGN_CENTER_VERTICAL)
            ctrl = wx.TextCtrl(self)
            self.inputs[key] = ctrl
            grid.Add(ctrl, 1, wx.EXPAND)
        box.Add(grid, 1, wx.EXPAND | wx.ALL, 12)
        box.Add(_label(self, 'Verifier le code INSEE dans le referentiel communal avant d enregistrer.'),
                0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        box.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.ALIGN_RIGHT, 12)
        self.SetSizerAndFit(box)
        self.SetMinSize((560, 220))

    def valeurs(self):
        return [self.inputs[k].GetValue().strip() for k in ('cp','ville','code','libelle')]


class ClauseTarif(wx.Dialog):
    """Clause datée à confirmer sur la convention signée, jamais un tarif implicite."""

    def __init__(self, parent, communes, couples):
        wx.Dialog.__init__(self, parent, title='Tarif de convention communal',
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.codes = [r['code_insee'] for r in communes]
        self.couples = list(couples)
        b = wx.BoxSizer(wx.VERTICAL)
        g = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=10)
        g.AddGrowableCol(1)
        g.Add(_label(self, 'Commune'), 0, wx.ALIGN_CENTER_VERTICAL)
        self.commune = wx.Choice(self, choices=[
            '%s (%s)' % (r['libelle_commune'], r['code_insee']) for r in communes])
        if self.codes: self.commune.SetSelection(0)
        g.Add(self.commune, 1, wx.EXPAND)
        g.Add(_label(self, 'Activite / groupe'), 0, wx.ALIGN_CENTER_VERTICAL)
        self.groupe = wx.Choice(self, choices=[
            '%s / %s [%d/%d]' % (r['activite'],r['groupe'],r['IDactivite'],r['IDgroupe'])
            for r in couples])
        if self.couples: self.groupe.SetSelection(0)
        g.Add(self.groupe, 1, wx.EXPAND)
        self.inputs = {}
        for key, label, initial in (
                ('date_debut','Debut inclus (AAAA-MM-JJ)',''),
                ('date_fin','Fin exclue (AAAA-MM-JJ)',''),
                ('prix_jour','Participation par journee (EUR)',''),
                ('reference','Reference convention signee','')):
            g.Add(_label(self,label), 0, wx.ALIGN_CENTER_VERTICAL)
            tc=wx.TextCtrl(self, value=initial)
            self.inputs[key]=tc
            g.Add(tc,1,wx.EXPAND)
        b.Add(g,1,wx.EXPAND|wx.ALL,12)
        b.Add(_label(self, 'La demi-journee sera calculee selon l unite et la clause retenue.'),
              0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 12)
        b.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALL|wx.ALIGN_RIGHT,12)
        self.SetSizerAndFit(b)
        self.SetMinSize((590, 290))

    def valeurs(self):
        a=self.commune.GetSelection()
        b=self.groupe.GetSelection()
        if a<0 or b<0:
            raise ValueError('Choisir une commune et une activite')
        couple=self.couples[b]
        return dict(code_insee=self.codes[a], IDactivite=couple['IDactivite'],
                    IDgroupe=couple['IDgroupe'],
                    **{k:v.GetValue().strip() for k,v in self.inputs.items()})


class Profil(wx.Dialog):
    """Profil immutable C2 : activites/groups, classification d'unites, clauses.

    Unites non qualifiees refusées ; aucun type de jour n'est infere du libelle.
    """

    def __init__(self, parent, service):
        wx.Dialog.__init__(self, parent, title='Nouveau profil ALSH',
                           size=(930,720), style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.service=service
        self.couples=service.perimetres()
        self.tarifs=[]
        self.choix_unites={}
        b=wx.BoxSizer(wx.VERTICAL)
        b.Add(_label(self,'Un nouveau profil est conserve comme version distincte. Aucun tarif n est propose automatiquement.'),
              0,wx.ALL,10)
        row=wx.BoxSizer(wx.HORIZONTAL)
        row.Add(_label(self,'Nom du profil :'),0,wx.ALIGN_CENTER_VERTICAL|wx.RIGHT,8)
        self.nom=wx.TextCtrl(self)
        row.Add(self.nom,1,wx.EXPAND)
        b.Add(row,0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,12)
        b.Add(_label(self,'Selectionner les ACTIVITES/GROUPES ALSH (ne pas inclure sport, restauration, etc.) :'),
              0,wx.LEFT|wx.RIGHT,12)
        self.liste_couples=wx.CheckListBox(self, choices=[
            '%s / %s [act=%d, grp=%d]' %
            (r['activite'],r['groupe'],r['IDactivite'],r['IDgroupe']) for r in self.couples])
        self.liste_couples.SetMinSize((-1,140))
        b.Add(self.liste_couples,0,wx.EXPAND|wx.ALL,10)
        self.liste_couples.Bind(wx.EVT_CHECKLISTBOX,self._actualiser_unites)
        b.Add(_label(self,'Classer chaque unite : journee, matin, apres-midi ou exclue :'),
              0,wx.LEFT|wx.RIGHT,12)
        self.scroll=wx.ScrolledWindow(self, style=wx.VSCROLL|wx.BORDER_SUNKEN)
        self.scroll.SetScrollRate(0,12)
        self.unit_sizer=wx.BoxSizer(wx.VERTICAL)
        self.scroll.SetSizer(self.unit_sizer)
        b.Add(self.scroll,1,wx.EXPAND|wx.ALL,10)
        b.Add(_label(self,'Clauses contractuelles confirmees (commune, activite/groupe, dates, prix) :'),
              0,wx.LEFT|wx.RIGHT,12)
        self.liste_tarifs=_liste(self,[('Commune',85),('Activite / Groupe',130),
                                      ('Debut',95),('Fin exclue',95),('EUR/j',75),('Convention',210)])
        self.liste_tarifs.SetMinSize((-1,100))
        b.Add(self.liste_tarifs,0,wx.EXPAND|wx.ALL,10)
        outils=wx.BoxSizer(wx.HORIZONTAL)
        ajouter=wx.Button(self,label='Ajouter une clause')
        retirer=wx.Button(self,label='Retirer la clause selectionnee')
        outils.Add(ajouter,0,wx.RIGHT,8)
        outils.Add(retirer,0)
        b.Add(outils,0,wx.LEFT|wx.RIGHT|wx.BOTTOM,12)
        ajouter.Bind(wx.EVT_BUTTON,self.OnAjouterTarif)
        retirer.Bind(wx.EVT_BUTTON,self.OnRetirerTarif)
        b.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALL|wx.ALIGN_RIGHT,12)
        self.Bind(wx.EVT_BUTTON,self.OnOK,id=wx.ID_OK)
        self.SetSizer(b)
        self.Layout()

    def _selection(self):
        return [self.couples[i] for i in range(len(self.couples))
                if self.liste_couples.IsChecked(i)]

    def _actualiser_unites(self,event=None):
        olds={k:v.GetSelection() for k,v in self.choix_unites.items()}
        self.scroll.Freeze()
        self.scroll.DestroyChildren()
        self.unit_sizer=wx.BoxSizer(wx.VERTICAL)
        self.scroll.SetSizer(self.unit_sizer)
        self.choix_unites={}
        selected=self._selection()
        if selected:
            units=self.service.unites([r['IDactivite'] for r in selected])
            for u in units:
                line=wx.BoxSizer(wx.HORIZONTAL)
                line.Add(_label(self.scroll,'%s [ID %d, act. %d]' %
                                (u['nom'],u['IDunite'],u['IDactivite'])),1,
                         wx.ALIGN_CENTER_VERTICAL|wx.LEFT,5)
                choice=wx.Choice(self.scroll,choices=[x[0] for x in PARTIES])
                choice.SetSelection(olds.get(u['IDunite'],0))
                line.Add(choice,0,wx.ALL,2)
                self.unit_sizer.Add(line,0,wx.EXPAND|wx.ALL,2)
                self.choix_unites[u['IDunite']]=choice
        self.scroll.Layout()
        self.scroll.FitInside()
        self.scroll.Thaw()

    def OnAjouterTarif(self,event):
        selection=self._selection()
        if not selection:
            _erreur(self,'Selectionner les activites et groupes avant les tarifs')
            return
        dlg=ClauseTarif(self,self.service.communes(),selection)
        try:
            if dlg.ShowModal()!=wx.ID_OK:
                return
            tariff=dlg.valeurs()
            self.service.moteur._tarifs(self.tarifs+[tariff])
            self.tarifs.append(tariff)
            r=tariff
            idx=self.liste_tarifs.InsertItem(self.liste_tarifs.GetItemCount(),r['code_insee'])
            for col,val in enumerate(('%d/%d'%(r['IDactivite'],r['IDgroupe']),
                                    r['date_debut'],r['date_fin'],r['prix_jour'],
                                    r['reference']),1):
                self.liste_tarifs.SetItem(idx,col,str(val))
        except Exception as exc:
            _erreur(self,exc)
        finally:
            dlg.Destroy()

    def OnRetirerTarif(self,event):
        i=self.liste_tarifs.GetFirstSelected()
        if i>=0:
            del self.tarifs[i]
            self.liste_tarifs.DeleteItem(i)

    def OnOK(self,event):
        try:
            selected=self._selection()
            if not selected:
                raise ValueError('Aucune activite ALSH selectionnee')
            if not self.choix_unites or any(c.GetSelection()==0 for c in self.choix_unites.values()):
                raise ValueError('Toutes les unites doivent etre classees')
            if not self.tarifs:
                raise ValueError('Ajouter les clauses des conventions signees avant de calculer')
            nom=self.nom.GetValue().strip()
            if not nom:
                raise ValueError('Nom de profil obligatoire')
            self.donnees=(nom,[[r['IDactivite'],r['IDgroupe']] for r in selected],
                          {k:PARTIES[c.GetSelection()][1] for k,c in self.choix_unites.items()},
                          list(self.tarifs))
            self.EndModal(wx.ID_OK)
        except Exception as exc:
            _erreur(self,exc)


class DateEffet(wx.Dialog):
    """Correction exceptionnelle avec piece, sur observation selectionnee."""

    def __init__(self,parent,service):
        wx.Dialog.__init__(self,parent,title='Corriger une date de demenagement',
                           size=(790,470),style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.service=service
        self.observations=[]
        b=wx.BoxSizer(wx.VERTICAL)
        b.Add(_label(self,'Si la date d enregistrement differe de la date reelle : une preuve est obligatoire.'),
              0,wx.ALL,12)
        h=wx.BoxSizer(wx.HORIZONTAL)
        h.Add(_label(self,'ID individu ou representant :'),0,wx.ALIGN_CENTER_VERTICAL|wx.RIGHT,8)
        self.ident=wx.TextCtrl(self)
        h.Add(self.ident,1,wx.RIGHT,8)
        load=wx.Button(self,label='Lire les changements')
        h.Add(load,0)
        load.Bind(wx.EVT_BUTTON,self.OnLire)
        b.Add(h,0,wx.EXPAND|wx.LEFT|wx.RIGHT,12)
        self.liste=_liste(self,[('ID observation',95),('Date constatee',110),
                                ('Source',110),('Rue',250),('CP',70),('Ville',160)])
        b.Add(self.liste,1,wx.EXPAND|wx.ALL,12)
        g=wx.FlexGridSizer(rows=0,cols=2,vgap=8,hgap=10)
        g.AddGrowableCol(1)
        g.Add(_label(self,'Date reelle d effet (AAAA-MM-JJ)'),0,wx.ALIGN_CENTER_VERTICAL)
        self.date=wx.TextCtrl(self)
        g.Add(self.date,1,wx.EXPAND)
        g.Add(_label(self,'Reference justificatif'),0,wx.ALIGN_CENTER_VERTICAL)
        self.preuve=wx.TextCtrl(self)
        g.Add(self.preuve,1,wx.EXPAND)
        b.Add(g,0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,12)
        b.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALL|wx.ALIGN_RIGHT,12)
        self.Bind(wx.EVT_BUTTON,self.OnValider,id=wx.ID_OK)
        self.SetSizer(b)

    def OnLire(self,event):
        try:
            self.observations=self.service.observations(int(self.ident.GetValue().strip()))
            _remplir(self.liste,[(r['IDobservation'],r['jour_constat'],r['source'],
                                   r['rue_resid'],r['cp_resid'],r['ville_resid'])
                                  for r in self.observations])
        except Exception as exc:
            _erreur(self,exc)

    def OnValider(self,event):
        try:
            index=self.liste.GetFirstSelected()
            if index<0 or index>=len(self.observations):
                raise ValueError('Selectionner un changement dans la liste')
            self.service.confirmer_demenagement(
                self.observations[index]['IDobservation'],
                self.date.GetValue().strip(),self.preuve.GetValue().strip())
            self.EndModal(wx.ID_OK)
        except Exception as exc:
            _erreur(self,exc)


class Dialog(wx.Dialog):
    """Consultation C2, filtres et exports, aucun nouvel appel a la facturation."""

    def __init__(self,parent):
        wx.Dialog.__init__(self,parent,title='Frequentation ALSH par commune et par enfant',
                           size=(1180,790),
                           style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER|wx.MAXIMIZE_BOX)
        self.db=None
        self.session=None
        self.resultat=None
        self.codes=[None]
        self._ouvrir()
        self._construire()
        self._charger_options()
        self.Bind(wx.EVT_CLOSE,self.OnFermer)
        self.CentreOnParent()

    def _ouvrir(self):
        try:
            user=getattr(wx.GetApp().GetTopWindow(),'dictUtilisateur',None)
            droits=c3.DroitsSituation(user)
            droits.imposer('frequentation_lire_nominatif')
            db=GestionDB.DB(pooling=False)
            self.db=db
            if db.echec:
                raise RuntimeError('Base Noethys indisponible')
            tables={r[0] for r in db.GetListeTables()}
            requis={'alsh_communes_domiciles','alsh_communes_exports',
                    'alsh_communes_c2_observations','alsh_communes_c2_correspondances',
                    'alsh_communes_c2_profils','alsh_communes_c2_dates_validees'}
            manquantes=sorted(requis-tables)
            if manquantes:
                raise RuntimeError('ALSH C1/C2 non installe : %s.\n'
                                   'Tester d abord les migrations sur une copie de la base.'
                                   % ', '.join(manquantes))
            if not db.isNetwork:
                db.connexion.execute('PRAGMA foreign_keys=ON')
            self.session=c3.SituationC3(db.connexion,user,
                                        dialecte='mysql' if db.isNetwork else 'sqlite')
        except Exception:
            if self.db is not None:
                self.db.Close()
                self.db=None
            raise

    def _construire(self):
        outer=wx.BoxSizer(wx.VERTICAL)
        self.banner=_label(self,'BROUILLON NON FACTURABLE  |  Domiciles dates  |  Aucun mouvement sur factures / prestations')
        outer.Add(self.banner,0,wx.ALL,10)
        filters=wx.BoxSizer(wx.HORIZONTAL)
        for text in ('Profil ALSH','Du (AAAA-MM-JJ)','Au (AAAA-MM-JJ)','Commune de residence'):
            filters.Add(_label(self,text),0,wx.ALIGN_CENTER_VERTICAL|wx.RIGHT,6)
            if text=='Profil ALSH':
                self.profil=wx.Choice(self,choices=[])
                ctrl=self.profil
            elif text.startswith('Du '):
                self.debut=wx.TextCtrl(self,value='%d-01-01'%date.today().year,size=(112,-1))
                ctrl=self.debut
            elif text.startswith('Au '):
                self.fin=wx.TextCtrl(self,value='%d-12-31'%date.today().year,size=(112,-1))
                ctrl=self.fin
            else:
                self.commune=wx.Choice(self,choices=['Toutes (anonyme)'])
                ctrl=self.commune
            filters.Add(ctrl,1 if text in ('Profil ALSH','Commune de residence') else 0,
                        wx.RIGHT|wx.EXPAND,12)
        outer.Add(filters,0,wx.EXPAND|wx.ALL,10)
        outils_panneau=wx.BoxSizer(wx.VERTICAL)
        outils_ligne=wx.BoxSizer(wx.HORIZONTAL)
        for idx,(name,callback) in enumerate((
             ('Recalculer automatiquement',self.OnCalculer),
             ('Configurer les communes',self.OnCorrespondance),
             ('Nouveau profil ALSH',self.OnProfil),
             ('Corriger date d adresse',self.OnDateEffet),
             ('Exporter recap enfants CSV',self.OnExportRecap),
             ('Exporter detail dates CSV',self.OnExportDetail),
             ('Synthese anonyme CSV',self.OnExportAnonyme))):
            if idx == 4:
                outils_panneau.Add(outils_ligne,0,wx.BOTTOM,6)
                outils_ligne=wx.BoxSizer(wx.HORIZONTAL)
            button=wx.Button(self,label=name)
            button.Bind(wx.EVT_BUTTON,callback)
            outils_ligne.Add(button,0,wx.RIGHT,5)
            if name.startswith('Configurer') or name.startswith('Nouveau') or name.startswith('Corriger'):
                button.Enable(_droit(self.session,'communes_parametrer') or
                              (name.startswith('Corriger') and _droit(self.session,'domicile_ecrire')))
        outils_panneau.Add(outils_ligne,0)
        outer.Add(outils_panneau,0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,10)
        self.status=_label(self,'Selectionner un profil ; les presences sont recalculees depuis Noethys a chaque demande.')
        outer.Add(self.status,0,wx.LEFT|wx.RIGHT|wx.BOTTOM,10)
        self.tabs=wx.Notebook(self)
        self.synthese=_liste(self.tabs,[('Commune',245),('INSEE',80),('Enfants distincts',125),
                                          ('Journees enfants',125),('Participation EUR',150)])
        self.enfants=_liste(self.tabs,[('Nom',140),('Prenom',120),('Adresse complete a la date',375),
                                         ('Domicile du',105),('Domicile au',105),
                                         ('Jours',75),('Participation EUR',120)])
        self.details=_liste(self.tabs,[('Date',105),('Nom',130),('Prenom',105),('Adresse complete',300),
                                         ('ALSH',160),('Groupe',135),('Unite',130),
                                         ('Journees',75),('EUR',90),('Etat',125),('IDconso',75)])
        self.anomalies=_liste(self.tabs,[('Consommation',110),('Probleme a qualifier',750)])
        for label,ctrl in [('Synthese',self.synthese),('Enfants / adresses',self.enfants),
                           ('Presences datees',self.details),('Anomalies',self.anomalies)]:
            self.tabs.AddPage(ctrl,label)
        outer.Add(self.tabs,1,wx.EXPAND|wx.ALL,10)
        bottom=wx.BoxSizer(wx.HORIZONTAL)
        bottom.Add(_label(self,'Une ligne nominative n apparait que lorsqu UNE commune est choisie.'),
                   1,wx.ALIGN_CENTER_VERTICAL)
        close=wx.Button(self,wx.ID_CLOSE,label='Fermer')
        close.Bind(wx.EVT_BUTTON,self.OnFermer)
        bottom.Add(close,0)
        outer.Add(bottom,0,wx.EXPAND|wx.ALL,10)
        self.SetSizer(outer)
        self.commune.Bind(wx.EVT_CHOICE,self.OnFiltrer)
        self.profil.Bind(wx.EVT_CHOICE,self.OnInvalider)
        self.debut.Bind(wx.EVT_TEXT,self.OnInvalider)
        self.fin.Bind(wx.EVT_TEXT,self.OnInvalider)
        self.Layout()

    def _charger_options(self):
        profils=self.session.profils()
        selected=self.profil.GetStringSelection()
        self.profil.Set(profils)
        if selected in profils:
            self.profil.SetStringSelection(selected)
        elif profils:
            self.profil.SetSelection(0)
        communes=self.session.communes()
        self.codes=[None]+[x['code_insee'] for x in communes]
        self.commune.Set(['Toutes les communes (anonyme)']+
                         ['%s (%s)'%(x['libelle_commune'],x['code_insee']) for x in communes])
        self.commune.SetSelection(0)
        self._afficher()

    def _filtre(self):
        i=self.commune.GetSelection()
        return self.codes[i] if 0<=i<len(self.codes) else None

    def OnInvalider(self,event=None):
        self.resultat=None
        self._afficher()
        self.status.SetLabel('Parametres modifies : cliquer sur Recalculer automatiquement.')

    def OnFiltrer(self,event=None):
        self._afficher()

    def OnCalculer(self,event=None):
        try:
            nom=self.profil.GetStringSelection()
            if not nom:
                raise ValueError('Creer ou selectionner un profil ALSH avant le calcul')
            self.resultat=None
            r=self.session.recalculer(self.debut.GetValue().strip(),
                                       self.fin.GetValue().strip(),nom)
            self.resultat=r
            self._afficher()
            self.status.SetLabel('%d enfant(s) distinct(s)  |  %s journee(s)  |  %d anomalie(s)  |  BROUILLON NON FACTURABLE' %
                                 (r['enfants_distincts_global'],r['journees_global'],len(r['anomalies'])))
        except Exception as exc:
            self.resultat=None
            self._afficher()
            _erreur(self,exc,'Calcul ALSH')

    def _afficher(self):
        for ctrl in (self.synthese,self.enfants,self.details,self.anomalies):
            ctrl.DeleteAllItems()
        if self.resultat is None:
            return
        vue=self.session.vue(self.resultat,self._filtre())
        _remplir(self.synthese,[(x['commune'],x['code_insee'],x['enfants_distincts'],
                                 x['journees'],x['montant_eur']) for x in vue['communes']])
        _remplir(self.enfants,[(x['nom'],x['prenom'],x['adresse_complete'],
                                x['domicile_date_debut'],x['domicile_date_fin'],
                                x['journees'],x['montant_eur']) for x in vue['enfants']])
        _remplir(self.details,[(x['date'],x['nom'],x['prenom'],x['adresse_complete'],
                                x['activite'],x['groupe'],x['unite'],x['unite_jour'],
                                x['montant_eur'],x['statut'],x['IDconso']) for x in vue['lignes']])
        # Ne pas montrer les noms ou les adresses des autres communes dans les anomalies.
        _remplir(self.anomalies,[(a.get('IDconso'),a.get('motif'))
                                 for a in self.resultat['anomalies']])
        self.enfants.Enable(self._filtre() is not None)
        self.details.Enable(self._filtre() is not None)

    def OnCorrespondance(self,event):
        dlg=Correspondance(self)
        try:
            if dlg.ShowModal()==wx.ID_OK:
                self.session.ajouter_correspondance(*dlg.valeurs())
                self._charger_options()
                self.OnInvalider()
        except Exception as exc:
            _erreur(self,exc)
        finally:
            dlg.Destroy()

    def OnProfil(self,event):
        dlg=None
        try:
            dlg=Profil(self,self.session)
            if dlg.ShowModal()==wx.ID_OK:
                self.session.creer_profil(*dlg.donnees)
                self._charger_options()
                self.profil.SetStringSelection(dlg.donnees[0])
                self.OnInvalider()
        except Exception as exc:
            _erreur(self,exc)
        finally:
            if dlg is not None: dlg.Destroy()

    def OnDateEffet(self,event):
        dlg=DateEffet(self,self.session)
        try:
            if dlg.ShowModal()==wx.ID_OK:
                self.OnInvalider()
        finally:
            dlg.Destroy()

    def _exporter(self,nature):
        if self.resultat is None:
            _erreur(self,'Recalculer les presences avant tout export')
            return
        code=self._filtre()
        if nature!='anonyme' and code is None:
            _erreur(self,'Choisir une seule commune pour un export nominatif')
            return
        with wx.FileDialog(self,'Exporter la situation ALSH (CSV)',
                           wildcard='CSV (Excel, LibreOffice)|*.csv',
                           style=wx.FD_SAVE) as picker:
            if picker.ShowModal()!=wx.ID_OK:
                return
            path=Path(picker.GetPath())
        try:
            if path.exists():
                raise FileExistsError('Le fichier existe deja : choisir un autre nom')
            texte=self.session.csv(self.resultat,nature,code)
            c3.enregistrer_csv_nouveau(path,texte)
            wx.MessageBox('Document preparatoire cree. Aucun montant facture.',
                          'Export effectue',wx.OK|wx.ICON_INFORMATION,self)
        except Exception as exc:
            _erreur(self,exc,'Export ALSH')

    def OnExportRecap(self,event): self._exporter('recap')
    def OnExportDetail(self,event): self._exporter('detail')
    def OnExportAnonyme(self,event): self._exporter('anonyme')

    def OnFermer(self,event=None):
        if self.db is not None:
            self.db.Close()
            self.db=None
        self.EndModal(wx.ID_CLOSE)


def ouvrir(parent):
    """Porte d'entree : si C1/C2 non installe, pas de plantage du menu."""
    dlg=None
    try:
        dlg=Dialog(parent)
        dlg.ShowModal()
    except Exception as exc:
        _erreur(parent,exc,'Frequentation par commune ALSH')
    finally:
        if dlg is not None:
            if dlg.db is not None:
                dlg.db.Close()
                dlg.db=None
            dlg.Destroy()
