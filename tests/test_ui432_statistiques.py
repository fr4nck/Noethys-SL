# -*- coding: utf-8 -*-
"""UI-432J - tests isoles du chargement des statistiques, sans reseau ni DB reelle."""
import ast
import contextlib
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODELES = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"
DIALOGUE = ROOT / "noethys" / "Dlg" / "DLG_Stats.py"


def charger(fichier, classe, methode, espace):
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    definition = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe)
    fonction = next(n for n in definition.body
                    if isinstance(n, ast.FunctionDef) and n.name == methode)
    code = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(code)
    exec(compile(code, str(fichier), "exec"), espace)
    return espace[methode]


class ObjetFictif:
    def __init__(self, categorie="texte", erreur=False):
        self.visible = True
        self.dictParametres = {}
        self.categorie = categorie
        self.erreur = erreur
        self.appels = 0
        self.images = []

    def MAJ(self, DB, dictParametres, figure=None):
        self.appels += 1
        if self.erreur:
            raise RuntimeError("SQL fictif en echec")
        self.dictParametres = dictParametres
        return figure

    def MemoriseImage(self, figure):
        self.images.append(figure)


class ModeleEtapesTests(unittest.TestCase):
    def creer(self, objets=None, activites=None):
        if objets is None:
            objets = [ObjetFictif(), ObjetFictif()]
        if activites is None:
            activites = [7]
        base = mock.Mock()
        figure = object()
        pyplot = SimpleNamespace(figure=mock.Mock(return_value=figure),
                                 close=mock.Mock())
        espace = {
            "GestionDB": SimpleNamespace(DB=mock.Mock(return_value=base)),
            "matplotlib": SimpleNamespace(pyplot=pyplot),
        }
        methode = charger(MODELES, "HTML", "MAJ_etapes", espace)
        modele = SimpleNamespace(
            dictParametres={"listeActivites": activites, "mode": "presents"},
            liste_objets=[{"code": "individus", "pages": [
                {"code": "individus_age", "objets": objets}]}],
        )
        return methode, modele, base, pyplot, espace

    def test_deux_objets_calcules_avec_connexion_fermee(self):
        methode, modele, base, _, _ = self.creer()
        self.assertEqual(list(methode(modele, page="individus_age")),
                         ["statistiques.objet", "statistiques.objet"])
        objets = modele.liste_objets[0]["pages"][0]["objets"]
        self.assertEqual([obj.appels for obj in objets], [1, 1])
        base.Close.assert_called_once_with()
        self.assertEqual(list(methode(modele, page="individus_age")), [])
        self.assertEqual([obj.appels for obj in objets], [1, 1])

    def test_erreur_sql_ferme_connexion(self):
        methode, modele, base, _, _ = self.creer([ObjetFictif(erreur=True)])
        with self.assertRaisesRegex(RuntimeError, "SQL fictif"):
            list(methode(modele, page="individus_age"))
        base.Close.assert_called_once_with()

    def test_interruption_du_generateur_ferme_connexion(self):
        methode, modele, base, _, _ = self.creer()
        etapes = methode(modele, page="individus_age")
        self.assertEqual(next(etapes), "statistiques.objet")
        etapes.close()
        base.Close.assert_called_once_with()

    def test_graphe_converti_et_figure_fermee(self):
        graphe = ObjetFictif("graphe")
        methode, modele, base, pyplot, _ = self.creer([graphe])
        self.assertEqual(list(methode(modele, page="individus_age")),
                         ["statistiques.objet"])
        self.assertEqual(graphe.images, [pyplot.figure.return_value])
        pyplot.close.assert_called_once_with(pyplot.figure.return_value)
        base.Close.assert_called_once_with()

    def test_sans_activite_aucune_connexion(self):
        methode, modele, _, _, espace = self.creer(activites=[])
        self.assertEqual(list(methode(modele, page="individus_age")), [])
        espace["GestionDB"].DB.assert_not_called()

    def test_maj_historique_epuise_les_etapes(self):
        methode, modele, base, _, _ = self.creer()
        modele.MAJ_etapes = lambda **kw: methode(modele, **kw)
        synchroniser = charger(MODELES, "HTML", "MAJ", {})
        self.assertIsNone(synchroniser(modele, page="individus_age"))
        base.Close.assert_called_once_with()

    def test_getfigure_ferme_sql_meme_apres_return(self):
        graphe = ObjetFictif("graphe")
        graphe.code = "fictif"
        methode, modele, base, pyplot, espace = self.creer([graphe])
        getfigure = charger(MODELES, "HTML", "GetFigure", espace)
        modele.dictParametres["listeActivites"] = [7]
        self.assertIs(getfigure(modele, "fictif"), pyplot.figure.return_value)
        base.Close.assert_called_once_with()


class DialogueStatistiquesTests(unittest.TestCase):
    def creer(self, visible=True):
        html = mock.Mock()
        modele = mock.Mock()
        modele.MAJ_etapes.side_effect = lambda **kw: iter(("statistiques.objet",))
        modele.GetHTML.return_value = "<HTML>fictif</HTML>"
        fenetre = SimpleNamespace(
            listeObjets=[{"visible": True, "code": "individus",
                          "pages": [{"visible": True, "code": "individus_age",
                                     "ctrl_html": html}]}],
            baseHTML=modele, IsShownOnScreen=lambda: visible,
        )
        principale = object()
        def executer(parent, etapes, **options):
            self.assertIs(parent, fenetre)
            self.assertEqual(list(etapes), ["statistiques.objet"])
            self.assertEqual(options["titre"], "Statistiques")
        attente = mock.Mock(side_effect=lambda *args: contextlib.nullcontext())
        sequence = mock.Mock(side_effect=executer)
        espace = {
            "wx": SimpleNamespace(
                GetApp=lambda: SimpleNamespace(GetTopWindow=lambda: principale),
                IsMainThread=lambda: True),
            "_": lambda txt: txt,
            "UTILS_Diagnostic_ui": SimpleNamespace(
                mesurer=lambda *args: contextlib.nullcontext()),
            "UTILS_Etapes_ui": SimpleNamespace(Executer=sequence),
            "UTILS_Attente": SimpleNamespace(BusyInfo=attente),
        }
        methode = charger(DIALOGUE, "Dialog", "MAJpage", espace)
        return methode, fenetre, modele, html, sequence, attente

    def test_dialogue_visible_execute_etapes_et_affiche_html(self):
        methode, fenetre, modele, html, sequence, attente = self.creer()
        methode(fenetre, 0, 0)
        sequence.assert_called_once()
        attente.assert_not_called()
        modele.MAJ.assert_not_called()
        html.SetPage.assert_called_once_with("<HTML>fictif</HTML>")

    def test_dialogue_masque_attente_parentee(self):
        methode, fenetre, modele, html, sequence, attente = self.creer(False)
        methode(fenetre, 0, 0)
        sequence.assert_not_called()
        modele.MAJ.assert_called_once_with(page="individus_age")
        self.assertIs(attente.call_args.args[1], fenetre)
        html.SetPage.assert_called_once()

    def test_page_invalide_sans_attente(self):
        methode, fenetre, _, html, sequence, attente = self.creer()
        self.assertIsNone(methode(fenetre, 3, 7))
        sequence.assert_not_called()
        attente.assert_not_called()
        html.SetPage.assert_not_called()

    def test_premiere_ouverture_planifie_apres_showmodal(self):
        suite = []
        params = {"listeActivites": [7], "mode": "presents"}
        dialogue = mock.Mock()
        dialogue.ShowModal.return_value = 5100
        dialogue.GetDictParametres.return_value = params
        principale = object()
        visible = [False]
        proprietaires = []
        vue = SimpleNamespace(
            dictParametres={}, ctrl_parametres=mock.Mock(),
            baseHTML=mock.Mock(), MAJpageAffichee=mock.Mock(),
            IsShownOnScreen=lambda: visible[0],
            GetParent=lambda: principale,
        )
        def creer_parametres(owner):
            proprietaires.append(owner)
            return dialogue
        espace = {
            "datetime": datetime,
            "DLG_Stats_parametres": SimpleNamespace(Dialog=creer_parametres),
            "wx": SimpleNamespace(ID_OK=5100, CallAfter=lambda fn: suite.append(fn)),
        }
        methode = charger(DIALOGUE, "Dialog", "ModificationParametres", espace)
        self.assertTrue(methode(vue, premiere=True))
        self.assertIs(proprietaires[0], principale,
                      "Le dialogue initial ne doit pas appartenir a Stats cachee")
        vue.MAJpageAffichee.assert_not_called()
        self.assertEqual(suite, [vue.MAJpageAffichee])
        suite[0]()
        vue.MAJpageAffichee.assert_called_once()
        visible[0] = True
        self.assertTrue(methode(vue, premiere=False))
        self.assertIs(proprietaires[1], vue,
                      "Les modifications ulterieures appartiennent a Stats visible")
        self.assertEqual(vue.MAJpageAffichee.call_count, 2)
        self.assertEqual(dialogue.Destroy.call_count, 2)


if __name__ == "__main__":
    unittest.main()
