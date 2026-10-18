#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simulation de besoins en animateurs liee aux commandes de repas (#429).

Le choix des unites, du site et du creneau est volontairement explicite : une
colonne de repas ne definit pas, a elle seule, l'accueil reglementaire.
Aucun enregistrement et aucun nom de mineur dans le compte rendu.
"""

import datetime
import wx
import GestionDB
from Utils.UTILS_Traduction import _
from Utils import UTILS_Encadrement


class Dialog(wx.Dialog):
    def __init__(self, parent, colonnes=None, date_debut=None, date_fin=None):
        wx.Dialog.__init__(self, parent, -1, _(u"Simulation de l'encadrement"),
                           style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.colonnes = [col for col in (colonnes or [])
                         if col.get("categorie") == "numerique_avec_suggestion"
                         and (col.get("parametres") or {}).get("unites")]

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, -1, _(u"Choisissez les colonnes d'un seul site et d'un meme creneau."
                                         u" Cette simulation n'est pas une validation reglementaire.")),
                  0, wx.ALL | wx.EXPAND, 10)
        sizer.Add(wx.StaticText(self, -1, _(u"Colonnes a prendre en compte (les doublons seront elimines) :")),
                  0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        labels = [u"%s (#%s)" % (col["nom_colonne"], col["IDcolonne"])
                  for col in self.colonnes]
        self.ctrl_colonnes = wx.CheckListBox(self, -1, choices=labels)
        if len(self.colonnes) == 1:
            self.ctrl_colonnes.Check(0, True)
        self.ctrl_colonnes.SetMinSize((-1, 100))
        sizer.Add(self.ctrl_colonnes, 1, wx.ALL | wx.EXPAND, 10)

        options = wx.FlexGridSizer(rows=0, cols=2, vgap=7, hgap=9)
        self.ctrl_site = wx.TextCtrl(self, -1, "")
        self.ctrl_creneau = wx.Choice(self, -1, choices=[_(u"Matin"), _(u"Midi"), _(u"Apres-midi"), _(u"Autre")])
        self.ctrl_creneau.SetSelection(0)
        self.ctrl_cadre = wx.Choice(self, -1, choices=[_(u"Periscolaire"), _(u"Extrascolaire")])
        self.ctrl_cadre.SetSelection(0)
        self.ctrl_duree = wx.SpinCtrl(self, -1, min=1, max=24, initial=4)
        self.ctrl_pedt = wx.CheckBox(self, -1, _(u"Dispositif PEDT applicable (explicitement confirme)"))
        self.ctrl_mode = wx.Choice(self, -1, choices=[_(u"Previsionnel : reserves et presents"), _(u"Reel : presents seulement")])
        self.ctrl_mode.SetSelection(0)
        for label, ctrl in [
            (_(u"Site d'accueil :"), self.ctrl_site),
            (_(u"Temps d'accueil :"), self.ctrl_creneau),
            (_(u"Cadre :"), self.ctrl_cadre),
            (_(u"Duree consecutive (heures, si periscolaire) :"), self.ctrl_duree),
            (_(u"PEDT :"), self.ctrl_pedt),
            (_(u"Effectifs utilises :"), self.ctrl_mode),
        ]:
            options.Add(wx.StaticText(self, -1, label), 0, wx.ALIGN_CENTER_VERTICAL)
            options.Add(ctrl, 1, wx.EXPAND)
        options.AddGrowableCol(1)
        sizer.Add(options, 0, wx.ALL | wx.EXPAND, 10)

        self.ctrl_resultats = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.ctrl_resultats.SetMinSize((-1, 160))
        sizer.Add(self.ctrl_resultats, 1, wx.ALL | wx.EXPAND, 10)

        boutons = wx.BoxSizer(wx.HORIZONTAL)
        self.bouton_calculer = wx.Button(self, -1, _(u"Calculer la suggestion"))
        boutons.Add(self.bouton_calculer, 0, wx.RIGHT, 10)
        boutons.Add(wx.Button(self, wx.ID_CANCEL, _(u"Fermer")), 0)
        sizer.Add(boutons, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnCalculer, self.bouton_calculer)
        self.SetSizer(sizer)
        self.SetMinSize((690, 570))
        self.SetSize((750, 650))
        self.CenterOnScreen()

    def ChargerConsommations(self, unites):
        """Lecture seule, identifiants d'unites et dates controles avant SQL.

        Le vieux GestionDB.ExecuterReq ne prend pas de parametres SQL ; aucun
        fragment de requete n'est issu directement d'une saisie utilisateur.
        """
        debut = self.date_debut
        fin = self.date_fin
        if not isinstance(debut, datetime.date) or not isinstance(fin, datetime.date) or debut > fin:
            raise ValueError("periode de commande invalide")
        ids = sorted({int(unite) for _groupe, unite in unites})
        if not ids:
            return [], {}
        liste_ids = ",".join(str(n) for n in ids)
        req = """SELECT c.IDindividu, c.date, c.IDgroupe, c.IDunite, c.etat,
                        i.date_naiss
                 FROM consommations AS c
                 LEFT JOIN individus AS i ON i.IDindividu=c.IDindividu
                 WHERE c.date>='%s' AND c.date<='%s'
                   AND c.IDunite IN (%s)
                   AND c.etat IN ('reservation','present')""" % (
                       debut.isoformat(), fin.isoformat(), liste_ids)
        db = GestionDB.DB()
        try:
            if not db.ExecuterReq(req):
                raise RuntimeError("Impossible de lire les consommations")
            lignes = db.ResultatReq()
        finally:
            db.Close()
        consommations, individus = [], {}
        for ident, jour, groupe, unite, etat, naissance in lignes:
            if (groupe, unite) not in unites:
                continue
            consommations.append({"IDindividu": ident, "date": jour,
                                   "IDgroupe": groupe, "IDunite": unite, "etat": etat})
            individus[ident] = {"date_naiss": naissance}
        return consommations, individus

    def OnCalculer(self, event=None):
        self.ctrl_resultats.SetValue("")
        site = self.ctrl_site.GetValue().strip()
        selection = self.ctrl_colonnes.GetCheckedItems()
        if not site or not selection:
            wx.MessageBox(_(u"Renseignez un site et cochez ses colonnes de repas."),
                          _(u"Simulation incomplete"), wx.OK | wx.ICON_WARNING, self)
            return
        unites = set()
        for num in selection:
            for groupe, unite in self.colonnes[num]["parametres"]["unites"]:
                unites.add((int(groupe), int(unite)))
        cadre = "periscolaire" if self.ctrl_cadre.GetSelection() == 0 else "extrascolaire"
        creneau = ("matin", "midi", "apres-midi", "autre")[self.ctrl_creneau.GetSelection()]
        pedt = self.ctrl_pedt.GetValue()
        duree = self.ctrl_duree.GetValue() if cadre == "periscolaire" else None
        mode = "previsionnel" if self.ctrl_mode.GetSelection() == 0 else "reel"
        config = {cle: {"site": site, "creneau": creneau, "cadre": cadre,
                        "duree_heures": duree, "pedt": pedt}
                  for cle in unites}
        try:
            consommations, individus = self.ChargerConsommations(unites)
            rapport = UTILS_Encadrement.CalculerEncadrement(consommations, individus, config, mode=mode)
        except (ValueError, RuntimeError, TypeError) as erreur:
            wx.MessageBox(_(u"Impossible de simuler l'encadrement : %s") % erreur,
                          _(u"Simulation incomplete"), wx.OK | wx.ICON_WARNING, self)
            return
        if not rapport:
            self.ctrl_resultats.SetValue(_(u"Aucune consommation retenue sur cette periode avec le mode choisi."))
            return
        lignes = []
        for item in rapport:
            lignes.append(_(u"%(date)s - %(site)s / %(creneau)s : %(moins_6)d moins de 6 ans, "
                            u"%(six_et_plus)d de 6 ans et plus -> %(animateurs_suggeres)d animateur(s) suggeres") % item)
            if not item["calcul_complet"]:
                lignes.append(_(u"ATTENTION : %(age_inconnu)d age(s) inconnu(s), "
                                u"%(conflits_sites)d conflit(s) de site : estimation incomplete") % item)
        self.ctrl_resultats.SetValue(u"\n".join(lignes))
