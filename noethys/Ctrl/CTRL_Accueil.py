#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-16 Ivan LUCAS
# Licence:         Licence GNU GPL
#-----------------------------------------------------------

import Chemins
from Utils import UTILS_Adaptations
import wx
import datetime
import sqlite3
from Utils import UTILS_Interface
from Utils import UTILS_Config
from Utils import UTILS_FondAccueil
from wx.lib.wordwrap import wordwrap
import six


def ConvertVersionTuple(texteVersion=""):
    """ Convertit un numéro de version texte en tuple """
    tupleTemp = []
    for num in texteVersion.split(".") :
        tupleTemp.append(int(num))
    return tuple(tupleTemp)

def GetAnnonce():
    """ Fonction de récupération de l'annonce é afficher """
    # FORK_MAINTENANCE: ne plus afficher les annonces promotionnelles/historiques embarquées.
    return None
    dateJour = datetime.date.today() 
    dictAnnonce = None
    found = False
    
    # Recherche Annonce Internet
    # try :
    #     fichierAnnonce = urllib2.urlopen('http://www.noethys.com/fichiers/annonce.txt', timeout=5)
    #     texteFichier = fichierAnnonce.read()
    #     fichierAnnonce.close()
    #     if "404 Not Found" not in texteFichier and len(texteFichier) > 10 :
    #         image, titre, texte_html, date_debut, date_fin, version = texteFichier.split(";")
    #         if date_debut <= str(dateJour) and date_fin >= str(dateJour) :
    #             if version != "" :
    #                 versionLogiciel = ConvertVersionTuple("1.0.5.6")#FonctionsPerso.GetVersionLogiciel())
    #                 version = ConvertVersionTuple(version)
    #                 if versionLogiciel < version :
    #                     dictAnnonce = {"IDannonce":None, "image":image, "titre":titre.decode("utf8"), "texte_html":texte_html.decode("utf8")}
    #                     found = True
    #             else :
    #                 dictAnnonce = {"IDannonce":None, "image":image, "titre":titre.decode("utf8"), "texte_html":texte_html.decode("utf8")}
    #                 found = True
    # except :
    #     pass
        
    # Recherche Annonces stockées dans la base de données
    if found == False :
        
        try :
            
            # Init base de données
            con = sqlite3.connect(Chemins.GetStaticPath("Databases/Annonces.dat"))
            cur = con.cursor()
            
            def ListeEnDict(donnees):
                IDannonce, image, titre, texte_html = donnees
                dictAnnonce = {"IDannonce":IDannonce, "image":image, "titre":titre, "texte_html":texte_html}
                return dictAnnonce
                
            # Recherche dans les annonces DATES
            if found == False :
                req = """SELECT IDannonce, image, titre, texte_html FROM annonces_dates
                WHERE date_debut<='%s' AND date_fin>='%s'
                ORDER BY date_debut
                ;""" % (dateJour, dateJour)
                cur.execute(req)
                listeAnnonces = cur.fetchall()
                if len(listeAnnonces) > 0 :
                    dictAnnonce = ListeEnDict(listeAnnonces[0])
                    found = True
            
            # Recherche dans les annonces PERIODES
            if found == False :
                req = """SELECT IDannonce, image, titre, texte_html FROM annonces_periodes
                WHERE jour_debut<=%d AND mois_debut<=%d AND jour_fin>=%d AND mois_fin>=%d
                ORDER BY jour_debut, mois_debut
                ;""" % (dateJour.day, dateJour.month, dateJour.day, dateJour.month)
                cur.execute(req)
                listeAnnonces = cur.fetchall()
                if len(listeAnnonces) > 0 :
                    dictAnnonce = ListeEnDict(listeAnnonces[0])
                    found = True

            # Recherche dans les annonces ALEATOIRES
            if found == False :
                req = """SELECT IDannonce, image, titre, texte_html FROM annonces_aleatoires
                ORDER BY RANDOM() LIMIT 1
                ;"""
                cur.execute(req)
                listeAnnonces = cur.fetchall()
                if len(listeAnnonces) > 0 :
                    dictAnnonce = ListeEnDict(listeAnnonces[0])
                    found = True

            con.close()
        
        except :
            return None
    
    return dictAnnonce
    


class Panel(wx.Panel):
    def __init__(self, parent, size=(-1, -1)):
        wx.Panel.__init__(self, parent, name="panel_accueil", id=-1, size=size, style=wx.TAB_TRAVERSAL)

        # Récupération des données de l'interface
        theme = UTILS_Interface.GetTheme()
        nom_fichier = "Fond.jpg"
        if six.PY3 and theme == "Vert":
            nom_fichier = "Fond_2019.jpg"

        self.chemin_image_fond = Chemins.GetStaticPath("Images/Interface/%s/%s" % (theme, nom_fichier))
        self.image_fond = wx.Image(self.chemin_image_fond, wx.BITMAP_TYPE_ANY)
        self.mode_fond = UTILS_FondAccueil.NormaliserMode(
            UTILS_Config.GetParametre("fond_accueil_mode", UTILS_FondAccueil.MODE_FOND_DEFAUT)
        )
        try:
            self.attenuation_fond = int(UTILS_Config.GetParametre("fond_accueil_attenuation", 20))
        except Exception:
            self.attenuation_fond = 20
        self.attenuation_fond = max(0, min(60, self.attenuation_fond))

        self._bitmap_fond_cache = None
        self._cle_fond_cache = None
        self.SetBackgroundColour(wx.Colour(242, 242, 242))

        # Binds
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda x:None)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def OnSize(self, event):
        self._bitmap_fond_cache = None
        self._cle_fond_cache = None
        self.Refresh()
        event.Skip()

    def _GetBitmapFond(self, largeur, hauteur):
        if not self.image_fond.IsOk() or largeur <= 0 or hauteur <= 0:
            return None

        cle = (int(largeur), int(hauteur))
        if cle == self._cle_fond_cache and self._bitmap_fond_cache is not None:
            return self._bitmap_fond_cache

        if largeur == self.image_fond.GetWidth() and hauteur == self.image_fond.GetHeight():
            bitmap = wx.Bitmap(self.image_fond)
        else:
            image = self.image_fond.Copy()
            image.Rescale(int(largeur), int(hauteur), wx.IMAGE_QUALITY_HIGH)
            bitmap = wx.Bitmap(image)

        self._cle_fond_cache = cle
        self._bitmap_fond_cache = bitmap
        return bitmap

    def _DessinerAttenuation(self, dc, largeur, hauteur):
        if self.attenuation_fond <= 0 or largeur <= 0 or hauteur <= 0:
            return
        try:
            alpha = int(round(255.0 * self.attenuation_fond / 100.0))
            gc = wx.GraphicsContext.Create(dc)
            gc.SetPen(wx.Pen(wx.Colour(242, 242, 242, 0)))
            gc.SetBrush(wx.Brush(wx.Colour(242, 242, 242, alpha)))
            gc.DrawRectangle(0, 0, largeur, hauteur)
        except Exception:
            # L'atténuation est cosmétique : le fond reste utilisable si le
            # backend graphique ne gère pas l'alpha.
            pass

    def OnPaint(self, event):
        """Préparation du DC et rendu adaptatif du fond d'accueil."""
        dc = wx.BufferedPaintDC(self)
        if wx.VERSION < (2, 9, 0, 0):
            self.PrepareDC(dc)

        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()

        largeur_zone, hauteur_zone = self.GetClientSize()
        if self.image_fond.IsOk() and largeur_zone > 0 and hauteur_zone > 0:
            x, y, largeur, hauteur = UTILS_FondAccueil.CalculerPlacementFond(
                self.image_fond.GetWidth(),
                self.image_fond.GetHeight(),
                largeur_zone,
                hauteur_zone,
                self.mode_fond,
            )
            bitmap = self._GetBitmapFond(largeur, hauteur)
            if bitmap is not None:
                # useMask=True permet aussi de conserver une éventuelle
                # transparence si le fond passe ultérieurement en PNG.
                dc.DrawBitmap(bitmap, x, y, True)
                self._DessinerAttenuation(dc, largeur_zone, hauteur_zone)

        # Récupére l'annonce
        dictAnnonce = GetAnnonce()
        if dictAnnonce != None:

            nomImage = dictAnnonce["image"]
            bmp = wx.Bitmap(Chemins.GetStaticPath("Images/16x16/%s.png" % nomImage), wx.BITMAP_TYPE_ANY)
            titre = dictAnnonce["titre"]
            texte_html = dictAnnonce["texte_html"]

            # Préparation du dessin
            x, y = 20, 20
            taille_police = 8
            largeurTexte = 300
            if six.PY2:
                dc.SetTextForeground((255, 255, 255))
            if six.PY3:
                dc.SetTextForeground("#6A9742")

            # Dessine l'image
            dc.DrawBitmap(bmp, int(x), int(y))

            # Dessine le titre
            dc.SetFont(wx.Font(taille_police, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "MS Shell Dlg 2"))
            dc.DrawText(titre, x+22, y)

            # Dessine le texte
            dc.SetFont(wx.Font(taille_police, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "MS Shell Dlg 2"))
            texte = wordwrap(texte_html, largeurTexte, dc, breakLongWords=True)
            if 'phoenix' in wx.PlatformInfo:
                largeur, hauteur, hauteurLigne = dc.GetFullMultiLineTextExtent(texte)
            else:
                largeur, hauteur, hauteurLigne = dc.GetMultiLineTextExtent(texte)
            dc.DrawLabel(texte, wx.Rect(int(x), int(y + 22), int(largeurTexte), int(hauteur)))



class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        wx.Frame.__init__(self, *args, **kwds)
        panel = wx.Panel(self, -1)
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add(panel, 1, wx.ALL|wx.EXPAND)
        self.SetSizer(sizer_1)
        self.ctrl= Panel(panel)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        sizer_2.Add(self.ctrl, 1, wx.ALL|wx.EXPAND, 4)
        panel.SetSizer(sizer_2)
        self.SetSize((1100, 900))
        self.Layout()
        self.CentreOnScreen()

if __name__ == '__main__':
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    frame_1 = MyFrame(None, -1, "TEST")
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()