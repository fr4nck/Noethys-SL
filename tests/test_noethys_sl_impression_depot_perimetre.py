# -*- coding: utf-8 -*-
"""Impression des dépôts : colonnes métier, ordre affiché, périmètre
(dépôt complet / vue filtrée) et total des seules lignes imprimées.

wx réel, base SQLite fictive, rendu en mémoire (aucune imprimante, aucun
PDF). Les assertions portent sur les valeurs transmises au moteur
d'impression et sur les textes qu'il dessine page par page.
"""
import datetime
import decimal
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT / "noethys", ROOT / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402,F401
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
import wx  # noqa: E402
from Ctrl.CTRL_ObjectListView import ColumnDefn, Filter  # noqa: E402
from Ol import OL_Reglements_depots as Depot  # noqa: E402
from Utils import UTILS_Printer as P  # noqa: E402

COLONNES_METIER = [u"Date", u"Mode", u"Émetteur", u"N° pièce", u"Famille", u"Payeur", u"Montant", u"Avis",
                   u"Compte", u"Différé", u"Attente", u"Quittancier", u"Observations"]


def reglement(i, montant, compte=1, inclus=True, **valeurs):
    donnees = dict(
        IDreglement=i, date=datetime.date(2026, 10, 1) + datetime.timedelta(days=i % 20),
        IDmode=1, nom_mode=u"Chèque", IDemetteur=None, nom_emetteur=u"Banque fictive",
        numero_piece=u"C-%03d" % i, nomTitulaires=u"Famille fictive %03d" % i, nom_payeur=u"Payeur %d" % i,
        montant=montant, avis_depot=None, email_depots=None, IDcompte=compte,
        nom_compte=u"Compte fictif %d" % compte, date_differe=None, encaissement_attente=0,
        numero_quittancier=None, observations=u"", inclus=inclus,
    )
    donnees.update(valeurs)
    return SimpleNamespace(**donnees)


class _Base(unittest.TestCase):
    verrouille = False

    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def setUp(self):
        self.frame = wx.Frame(None, name="DLG_Saisie_depot")
        self.addCleanup(self.frame.Destroy)
        etat = u"Dépôt verrouillé" if self.verrouille else u"Dépôt non verrouillé"
        self.frame.GetLabelParametres = lambda: u"Nom du dépôt : Dépôt fictif | %s" % etat
        panel = wx.Panel(self.frame)
        with patch.object(Depot.UTILS_Titulaires, "GetTitulaires", return_value={}):
            self.liste = Depot.ListView(panel, style=wx.LC_REPORT)
        self.liste.SetColumns([
            ColumnDefn(u"Date", "left", 80, "date"),
            ColumnDefn(u"Famille", "left", 160, "nomTitulaires"),
            ColumnDefn(u"Montant", "right", 80, "montant"),
        ])
        self.messages = []

    def charger(self, tracks, IDcompte=None, IDmode=None):
        self.liste.InitModel(tracks, IDcompte=IDcompte, IDmode=IDmode)
        self.liste.SetObjects(self.liste.donnees)

    def imprimer(self, apercu=True):
        """Lance l'impression ; retourne (vue, paramètres) transmis au moteur."""
        def message(parent, texte, *args, **kwargs):
            self.messages.append(texte)
            return _Muet()
        with patch.object(Depot.wx, "MessageDialog", side_effect=message), \
                patch.object(P, "ObjectListViewPrinter") as classe:
            resultat = self.liste.Apercu() if apercu else self.liste.Imprimer()
        if not classe.called:
            return None, None, resultat
        appel = classe.call_args
        return appel.args[0], appel.kwargs, resultat

    def textes_vue(self, vue):
        return [[vue.GetItem(l, c).GetText() for c in range(vue.GetColumnCount())] for l in range(vue.GetItemCount())]

    def rendu(self, vue, parametres):
        """Rendu réel page par page en mémoire : textes d'en-têtes et de lignes par page."""
        with patch.object(P.DLG_Options_impression_listes.Dialog, "ShowModal", return_value=wx.ID_OK), \
                patch.object(P.ObjectListViewPrinter, "GetNomOrganisateur", return_value=u"Organisme fictif"):
            imprimante = P.ObjectListViewPrinter(vue, titre=parametres["titre"], intro=parametres["intro"],
                                                 total=parametres["total"], orientation=parametres["orientation"])
            self.assertTrue(imprimante.InitParametres())
        pages = {}
        classe_cellule = P.ListCtrlPrinter.CellBlock
        original = classe_cellule.DrawSelf

        def dessin(bloc, dc, bornes):
            # Seuls les blocs réellement dessinés sur une page sont relevés.
            if isinstance(bloc, (P.ListCtrlPrinter.RowBlock, P.ListCtrlPrinter.ColumnHeaderBlock)):
                genre = "lignes" if isinstance(bloc, P.ListCtrlPrinter.RowBlock) else "entetes"
                pages.setdefault(imprimante.printer.engine.currentPage, {"entetes": [], "lignes": []})[genre].append(
                    list(bloc.GetTexts()))
            return original(bloc, dc, bornes)
        bitmap = wx.Bitmap(1100, 750)
        dc = wx.MemoryDC(bitmap)
        try:
            dc.SetBackground(wx.WHITE_BRUSH)
            dc.Clear()
            bornes = wx.Rect(10, 10, 1080, 730)
            nombre = imprimante.printer.CalculateTotalPages(dc, bornes)
            with patch.object(classe_cellule, "DrawSelf", dessin):
                imprimante.printer.StartPrinting()
                for page in range(1, nombre + 1):
                    imprimante.printer.PrintPage(dc, page, bornes)
        finally:
            dc.SelectObject(wx.NullBitmap)
        return nombre, pages, P.ListCtrlPrinter.LISTFOOTER, P.ListCtrlPrinter.LISTINTRO


class _Muet(object):
    def ShowModal(self):
        return wx.ID_OK

    def Destroy(self):
        pass


class ColonnesEtValeursTests(_Base):
    def test_colonnes_metier_retablies_et_valeurs_transmises(self):
        self.charger([
            reglement(1, 120.5, avis_depot=datetime.date(2026, 10, 3), date_differe=datetime.date(2026, 11, 2),
                      encaissement_attente=1, numero_quittancier=u"Q-17", observations=u"Réglé à l'accueil"),
            reglement(2, 30.0, email_depots=u"abonnée"),
        ])
        vue, parametres, _ = self.imprimer()
        self.assertEqual([vue.GetColumn(c).GetText() for c in range(vue.GetColumnCount())], COLONNES_METIER)
        lignes = self.textes_vue(vue)
        self.assertEqual(lignes[0], [u"02/10/2026", u"Chèque", u"Banque fictive", u"C-001",
                                     u"Famille fictive 001", u"Payeur 1", u"120.50 €", u"03/10/2026",
                                     u"Compte fictif 1", u"02/11/2026", u"Attente !", u"Q-17", u"Réglé à l'accueil"])
        self.assertEqual(lignes[1][7], u"Non envoyé")
        self.assertEqual(lignes[1][9:12], [u"", u"", u""])
        self.assertEqual(vue.GetColumn(6).GetAlign(), wx.LIST_FORMAT_RIGHT)

    def test_montants_positifs_negatifs_nuls_au_centime(self):
        montants = [0.1, 0.1, 0.1, -12.35, 0.0, 1234.56, None]
        self.charger([reglement(i + 1, m) for i, m in enumerate(montants)])
        vue, parametres, _ = self.imprimer()
        self.assertEqual([l[6] for l in self.textes_vue(vue)],
                         [u"0.10 €", u"0.10 €", u"0.10 €", u"-12.35 €", u"0.00 €", u"1234.56 €", u""])
        attendu = sum(decimal.Decimal(str(m or 0)) for m in montants)
        self.assertEqual(attendu, decimal.Decimal("1222.51"))
        self.assertIn(u"7 règlements (1222.51 €)", parametres["total"])

    def test_libelles_longs_accents_et_valeurs_absentes_dessines(self):
        long_texte = u"Règlement reçu après relance ; échéancier accordé à la famille Éloïse-Noël " * 4
        self.charger([reglement(1, 10.0, observations=long_texte, numero_piece=None, nom_emetteur=None,
                                nom_payeur=u"Œdipe Ça Àlice")])
        vue, parametres, _ = self.imprimer()
        ligne = self.textes_vue(vue)[0]
        self.assertEqual(ligne[12], long_texte)
        self.assertEqual((ligne[2], ligne[3]), (u"", u""))
        with BaseTest() as base, RedirectionGestionDB(base.chemin):
            nombre, pages, conclusion, intro = self.rendu(vue, parametres)
        dessinees = [t for page in pages.values() for l in page["lignes"] for t in l]
        self.assertIn(long_texte, dessinees)
        self.assertIn(u"Œdipe Ça Àlice", dessinees)


class OrdreEtPerimetreTests(_Base):
    def setUp(self):
        _Base.setUp(self)
        self.tracks = [reglement(1, 50.0, compte=1), reglement(2, 10.0, compte=2), reglement(3, 30.0, compte=1),
                       reglement(4, 20.0, compte=2), reglement(5, 40.0, compte=1),
                       reglement(6, 99.0, inclus=False)]

    def test_tri_affiche_croissant_et_decroissant(self):
        self.charger(self.tracks)
        for ascendant, attendu in ((True, [u"10.00 €", u"20.00 €", u"30.00 €", u"40.00 €", u"50.00 €"]),
                                   (False, [u"50.00 €", u"40.00 €", u"30.00 €", u"20.00 €", u"10.00 €"])):
            self.liste.SortBy(2, ascending=ascendant)
            affiche = [self.liste.GetObjectAt(i).montant for i in range(self.liste.GetItemCount())]
            vue, parametres, _ = self.imprimer()
            self.assertEqual([l[6] for l in self.textes_vue(vue)], attendu)
            self.assertEqual([u"%.2f €" % m for m in affiche], attendu)

    def test_depot_complet_titre_nombre_et_total(self):
        self.charger(self.tracks)
        vue, parametres, _ = self.imprimer()
        self.assertEqual(vue.GetItemCount(), 5)
        self.assertEqual(parametres["titre"], u"Règlements du dépôt - Dépôt complet")
        self.assertTrue(parametres["total"].startswith(u"Dépôt complet : 5 règlements (150.00 €)"))
        self.assertNotIn(u"99.00", parametres["total"])  # règlement hors dépôt

    def test_vue_filtree_plusieurs_resultats(self):
        self.liste.inclus = True
        self.charger(self.tracks, IDcompte=1)
        vue, parametres, _ = self.imprimer()
        self.assertEqual([l[4] for l in self.textes_vue(vue)],
                         [u"Famille fictive 001", u"Famille fictive 003", u"Famille fictive 005"])
        self.assertEqual(parametres["titre"], u"Règlements du dépôt - Vue filtrée")
        self.assertIn(u"compte Compte fictif 1", parametres["total"])
        self.assertIn(u"3 règlement(s) imprimé(s) sur 5", parametres["total"])
        self.assertIn(u"3 règlements (120.00 €)", parametres["total"])
        self.assertNotIn(u"150.00", parametres["total"])
        self.assertNotIn(u"Dépôt complet", parametres["titre"] + parametres["total"])

    def test_vue_filtree_un_resultat_par_recherche(self):
        self.charger(self.tracks)
        self.liste.SetFilter(Filter.Predicate(lambda track: track.IDreglement == 4))
        self.liste.RepopulateList()
        vue, parametres, _ = self.imprimer()
        self.assertEqual(self.textes_vue(vue)[0][6], u"20.00 €")
        self.assertEqual(vue.GetItemCount(), 1)
        self.assertEqual(parametres["titre"], u"Règlements du dépôt - Vue filtrée")
        self.assertIn(u"1 règlement(s) imprimé(s) sur 5", parametres["total"])
        self.assertIn(u"1 règlements (20.00 €)", parametres["total"])

    def test_vue_filtree_sans_resultat_n_imprime_rien(self):
        self.charger(self.tracks, IDcompte=3)
        vue, parametres, resultat = self.imprimer()
        self.assertIsNone(vue)
        self.assertFalse(resultat)
        self.assertIn(u"filtre", self.messages[0])

    def test_reglements_disponibles_sans_filtre(self):
        self.liste.inclus = False
        self.charger(self.tracks)
        vue, parametres, _ = self.imprimer()
        self.assertEqual(vue.GetItemCount(), 1)
        self.assertEqual(parametres["titre"], u"Règlements disponibles - Liste complète")


class RenduEtDonneesTests(_Base):
    def rendu_depot(self, nombre):
        tracks = [reglement(i, 10.0 + i) for i in range(1, nombre + 1)]
        with BaseTest() as base, RedirectionGestionDB(base.chemin):
            base.inserer("prestations", ["IDprestation", "label", "montant", "IDfamille"], [(1, u"Fictive", 10.0, 1)])
            avant = list(base.db.connexion.execute("SELECT * FROM prestations"))
            schema = list(base.db.connexion.execute("SELECT name FROM sqlite_master ORDER BY name"))
            self.charger(tracks)
            vue, parametres, _ = self.imprimer(apercu=False)
            resultat = self.rendu(vue, parametres)
            self.assertEqual(list(base.db.connexion.execute("SELECT * FROM prestations")), avant)
            self.assertEqual(list(base.db.connexion.execute("SELECT name FROM sqlite_master ORDER BY name")), schema)
        self.assertEqual([t.montant for t in tracks], [10.0 + i for i in range(1, nombre + 1)])
        return tracks, parametres, resultat

    def test_document_multipage_entetes_repetes_toutes_lignes(self):
        tracks, parametres, (nombre, pages, conclusion, intro) = self.rendu_depot(120)
        self.assertGreater(nombre, 1)
        for page in range(1, nombre + 1):
            self.assertTrue(pages[page]["entetes"], "en-têtes absents page %d" % page)
            self.assertEqual(pages[page]["entetes"][0], COLONNES_METIER)
        dessinees = [l[4] for page in pages.values() for l in page["lignes"]]
        self.assertEqual(dessinees, [t.nomTitulaires for t in tracks])
        total = sum(decimal.Decimal(str(t.montant)) for t in tracks).quantize(decimal.Decimal("0.01"))
        self.assertIn(u"120 règlements (%s €)" % total, conclusion)
        self.assertIn(u"Dépôt non verrouillé", intro)

    def test_depot_vide_garde_l_interdiction_d_apercu_vide(self):
        self.charger([])
        vue, parametres, resultat = self.imprimer()
        self.assertIsNone(vue)
        self.assertFalse(resultat)
        self.assertIn(u"Aucun règlement", self.messages[0])


class DepotVerrouilleTests(RenduEtDonneesTests):
    verrouille = True

    def test_document_multipage_entetes_repetes_toutes_lignes(self):
        tracks, parametres, (nombre, pages, conclusion, intro) = self.rendu_depot(60)
        self.assertGreater(nombre, 1)
        self.assertIn(u"Dépôt verrouillé", intro)
        self.assertEqual(sum(len(p["lignes"]) for p in pages.values()), 60)


if __name__ == "__main__":
    unittest.main()
