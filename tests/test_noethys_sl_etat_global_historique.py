# -*- coding: utf-8 -*-
"""Contrat de fidélité : État global des consommations d'Ivan Lucas.

Référence : https://github.com/Noethys/Noethys (branche master, commit
199353efb86e37a9785260ec4225b49aced03db9). Les quatre fichiers de la page
doivent rester identiques à l'original. Seules sont admises, dans
DLG_Etat_global.py, les adaptations Python 3 listées dans ADAPTATIONS_PY3, et
dans CTRL_Propertygrid.py l'adaptation wxPython 4.2 de ADAPTATION_WX42 : en les
retirant, on doit retrouver l'empreinte Git exacte du fichier original.

Ces tests n'accèdent à aucune donnée et n'affichent aucune fenêtre sur un
poste de travail (le seul test qui en ouvre une est réservé au runner CI).
"""
import ast
import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

# Empreintes Git (blob) des fichiers originaux de Noethys.
EMPREINTES_ORIGINALES = {
    "Dlg/DLG_Etat_global.py": "8fbf28506b490856f8b8fb800c51d34eb5decffe",
    "Ctrl/CTRL_Etat_global_options.py": "c9948b98107b15dad9dd4da7c4bbab0fec8d42b8",
    "Ctrl/CTRL_Etat_global_parametres.py": "7692529d432aeb3f3191d0382a45a421ed1b6aef",
    "Ctrl/CTRL_Propertygrid.py": "7727b1c4e8f835b19831be5c0a69f74a6b859c2b",
}

# (texte adapté, texte original) : adaptations techniques Python 3 sans
# changement de résultat. Python 2 faisait une division entière avec « / »
# et savait trier None avec des chaînes ou des nombres.
ADAPTATIONS_PY3 = [
    (u"    # Noethys SL : divisions entières explicites (//) pour retrouver sous Python 3\n"
     u"    # le résultat exact de la division entière Python 2 d'origine.\n"
     u"    heures = (valeur.days*24) + (valeur.seconds//3600)\n"
     u"    minutes = valeur.seconds%3600//60\n",
     u"    heures = (valeur.days*24) + (valeur.seconds/3600)\n"
     u"    minutes = valeur.seconds%3600/60\n"),
    (u"        minDecimal = int(minutes)*100//60\n",
     u"        minDecimal = int(minutes)*100/60\n"),
    (u"\ndef CleTriPython2(valeur):\n"
     u"    \"\"\" Noethys SL : ordre de tri de Python 2, où None précède tout, les nombres\n"
     u"    précèdent les autres types et les types différents se classent par nom.\n"
     u"    Python 3 refuse de comparer None à une chaîne ou à un nombre. \"\"\"\n"
     u"    if valeur is None :\n"
     u"        return (0, \"\", 0)\n"
     u"    if isinstance(valeur, (int, float)) :\n"
     u"        return (1, \"\", valeur)\n"
     u"    return (2, type(valeur).__name__, valeur)\n",
     u""),
    (u"        regroupements.sort(key=CleTriPython2)\n",
     u"        regroupements.sort()\n"),
    (u"            if \"Permission denied\" in six.text_type(err) :\n",
     u"            if \"Permission denied\" in err :\n"),
]

# wxPython 4.2 (wxWidgets 3.2) : le bouton « ... » d'un ArrayStringProperty
# appelle DisplayEditorDialog et non OnEvent. Le dialogue C++ refuse les
# identifiants (assertion « Function called for incompatible property ») : la
# méthode ajoutée ouvre le même MultiChoiceDialog que OnEvent.
ADAPTATION_WX42 = (
    u"\n    def DisplayEditorDialog(self, pg, value):\n"
    u"        \"\"\" Noethys SL : avec wxPython 4.2 (wxWidgets 3.2), le bouton du champ appelle\n"
    u"        ce dialogue de ArrayStringProperty sans passer par OnEvent. Le dialogue C++\n"
    u"        attend une liste de textes et échoue sur les identifiants : on ouvre ici le\n"
    u"        même MultiChoiceDialog que OnEvent. \"\"\"\n"
    u"        selections = value if isinstance(value, (list, tuple)) else (self.m_value or [])\n"
    u"        dlg = wx.MultiChoiceDialog(pg, _(u\"Cochez les éléments à sélectionner :\"), _(u\"sélection\"), [x[1] for x in self.liste_choix])\n"
    u"        dlg.SetSelections([index for index, (id, valeur) in enumerate(self.liste_choix) if id in selections])\n"
    u"        if dlg.ShowModal() == wx.ID_OK:\n"
    u"            resultat = (True, [self.liste_choix[index][0] for index in dlg.GetSelections()])\n"
    u"        else:\n"
    u"            resultat = (False, value)\n"
    u"        dlg.Destroy()\n"
    u"        return resultat\n"
)

# Ajouts retirés : ils ne doivent pas revenir dans la page ni dans son calcul.
AJOUTS_RETIRES = (
    "presence_midi", "bouton_afas", "OnAFAS", "AFAS", "CTRL_Grille_periode",
    "ctrl_periode", "CalculateurEtatGlobal", "ErreurCalculEtatGlobal",
    "DecoderArrondi", "listeGroupes", "listeCouples", "controle_doublons",
    "controle_temps_facture",
)

MODULES_AFAS_V1_RETIRES = (
    "Dlg/DLG_AFAS_Actualisation.py",
    "Utils/UTILS_AFAS_Actualisation.py",
    "Utils/UTILS_AFAS_Donnees.py",
    "Utils/UTILS_AFAS_Perimetre.py",
    "Utils/UTILS_AFAS_Historique.py",
    "Utils/UTILS_AFAS_ProfilsHistoriques.py",
)


def texte_normalise(relatif):
    """ Contenu tel que Git le stocke (fins de ligne LF). """
    return (NOETHYS / relatif).read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


def empreinte_git(texte):
    donnees = texte.encode("utf-8")
    return hashlib.sha1(b"blob %d\0" % len(donnees) + donnees).hexdigest()


_APPLICATION = []


def application_wx(wx):
    """ Une seule wx.App, conservée jusqu'à la fin du processus : détruire
    puis recréer une application wx fait planter wxPython sous Windows. """
    if wx.GetApp() is None:
        _APPLICATION.append(wx.App(False))
    return wx.GetApp()


def methode(fichier, classe, fonction):
    arbre = ast.parse(texte_normalise(fichier))
    objet = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe)
    return next(n for n in objet.body if isinstance(n, ast.FunctionDef) and n.name == fonction)


class FideliteOriginalTests(unittest.TestCase):

    def test_controles_identiques_a_l_original(self):
        for relatif in ("Ctrl/CTRL_Etat_global_options.py",
                        "Ctrl/CTRL_Etat_global_parametres.py"):
            self.assertEqual(empreinte_git(texte_normalise(relatif)),
                             EMPREINTES_ORIGINALES[relatif], relatif)

    def test_propertygrid_identique_a_l_original_hors_adaptation_wx42(self):
        texte = texte_normalise("Ctrl/CTRL_Propertygrid.py")
        self.assertEqual(texte.count(ADAPTATION_WX42), 1)
        texte = texte.replace(ADAPTATION_WX42, u"")
        self.assertEqual(empreinte_git(texte), EMPREINTES_ORIGINALES["Ctrl/CTRL_Propertygrid.py"])

    def test_dialogue_identique_a_l_original_hors_adaptations_python3(self):
        texte = texte_normalise("Dlg/DLG_Etat_global.py")
        for adapte, original in ADAPTATIONS_PY3:
            self.assertEqual(texte.count(adapte), 1, adapte)
            texte = texte.replace(adapte, original)
        self.assertEqual(empreinte_git(texte), EMPREINTES_ORIGINALES["Dlg/DLG_Etat_global.py"])

    def test_aucun_ajout_retire_ne_revient(self):
        for relatif in ("Dlg/DLG_Etat_global.py", "Ctrl/CTRL_Etat_global_options.py"):
            texte = texte_normalise(relatif)
            for ajout in AJOUTS_RETIRES:
                self.assertNotIn(ajout, texte, (relatif, ajout))

    def test_chaine_afas_v1_retiree(self):
        for relatif in MODULES_AFAS_V1_RETIRES:
            self.assertFalse((NOETHYS / relatif).exists(), relatif)

    def test_periode_par_deux_dates_comme_l_original(self):
        initialisation = ast.unparse(methode("Dlg/DLG_Etat_global.py", "Parametres", "__init__"))
        self.assertIn("self.ctrl_date_debut = CTRL_Saisie_date.Date2(self)", initialisation)
        self.assertIn("self.ctrl_date_fin = CTRL_Saisie_date.Date2(self)", initialisation)

    def test_trois_boutons_d_origine(self):
        disposition = ast.unparse(methode("Dlg/DLG_Etat_global.py", "Dialog", "__do_layout"))
        self.assertIn("wx.FlexGridSizer(rows=1, cols=4, vgap=10, hgap=10)", disposition)
        for bouton in ("bouton_aide", "bouton_ok", "bouton_fermer"):
            self.assertIn("grid_sizer_boutons.Add(self.%s" % bouton, disposition)

    def test_etats_de_consommation_d_origine(self):
        fonction = methode("Ctrl/CTRL_Etat_global_options.py", "CTRL", "Remplissage")
        listes = [
            n for n in ast.walk(fonction)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "liste_codes_etats" for t in n.targets)
        ]
        self.assertEqual(len(listes), 1)
        self.assertEqual(ast.literal_eval(listes[0].value), ["reservation", "present", "absentj", "absenti"])

    def test_profil_recharge_tel_qu_enregistre(self):
        rechargement = ast.unparse(methode("Dlg/DLG_Etat_global.py", "Dialog", "SetParametres"))
        self.assertIn("self.ctrl_parametres.SetParametres(dictParametres)", rechargement)
        self.assertIn("self.ctrl_options.SetParametres(dictParametres)", rechargement)
        self.assertNotIn("MessageBox", rechargement)


class ProfilsWxTests(unittest.TestCase):
    """ Un profil enregistré par une version précédente (options du midi
    comprises) se recharge sans erreur : les clés inconnues sont ignorées,
    comme dans l'original. Les contrôles sont créés sans être affichés. """

    @classmethod
    def setUpClass(cls):
        try:
            import wx
            from Ctrl import CTRL_Etat_global_options
        except (ImportError, RuntimeError):
            raise unittest.SkipTest("wxPython indisponible sur ce runner")
        cls.wx = wx
        cls.module = CTRL_Etat_global_options

    def test_profil_ancien_recharge_et_resauvegarde_sans_cle_parasite(self):
        wx = self.wx
        application_wx(wx)
        cadre = wx.Frame(None)
        try:
            with mock.patch("GestionDB.DB") as base:
                base.return_value.ResultatReq.return_value = []
                ctrl = self.module.CTRL(cadre)
            ancien_profil = dict(ctrl.GetParametres())
            ancien_profil.update({
                "forfait_presence_midi": 45,
                "heure_debut_presence_midi": "12:30",
                "heure_fin_presence_midi": "13:30",
                "etat_consommations": ["present", "absenti"],
                "plafond_journalier_individu": 600,
                "format_donnees": "decimal",
            })
            ctrl.SetParametres(ancien_profil)
            parametres = ctrl.GetParametres()
            self.assertEqual(parametres["etat_consommations"], ["present", "absenti"])
            self.assertEqual(parametres["plafond_journalier_individu"], 600)
            self.assertEqual(parametres["format_donnees"], "decimal")
            for cle in ("forfait_presence_midi", "heure_debut_presence_midi", "heure_fin_presence_midi"):
                self.assertNotIn(cle, parametres)
        finally:
            cadre.Destroy()


class ContratEditeurWxTests(unittest.TestCase):
    """ Sélection multiple native d'origine (wx.MultiChoiceDialog). """

    @classmethod
    def setUpClass(cls):
        try:
            import wx
            from Ctrl import CTRL_Propertygrid
        except (ImportError, RuntimeError):
            raise unittest.SkipTest("wxPython indisponible sur ce runner")
        cls.wx = wx
        cls.controle = CTRL_Propertygrid.Propriete_multichoix

    @unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                         "Dialogue affiché uniquement sur le runner Windows isolé")
    def test_wxpython_natif_propose_reellement_quatre_entrees(self):
        wx = self.wx
        application_wx(wx)
        choix = ["Pointage en attente", "Présent", "Absence justifiée", "Absence injustifiée"]
        dlg = wx.MultiChoiceDialog(None, "Cochez les états à inclure", "États des consommations", choix)
        try:
            dlg.SetSelections([0, 1, 2, 3])
            dlg.Show()
            wx.YieldIfNeeded()

            def trouver_listes(element):
                resultats = []
                for enfant in element.GetChildren():
                    if isinstance(enfant, wx.ListBox):
                        resultats.append(enfant)
                    resultats.extend(trouver_listes(enfant))
                return resultats

            self.assertTrue(any(liste.GetCount() == 4 for liste in trouver_listes(dlg)),
                            "Le dialogue multichoix n'a pas rendu ses quatre lignes")
        finally:
            dlg.Destroy()

    def _faux(self, liste_choix, valeur):
        class FauxPropriete:
            def __init__(self):
                self.liste_choix = liste_choix
                self.m_value = list(valeur)
                self.recu = None

            def SetValueInEvent(self, valeurs):
                self.recu = valeurs
        return FauxPropriete()

    def _clic(self):
        wx = self.wx

        class FauxEvenement:
            def GetEventType(self):
                return wx.wxEVT_COMMAND_BUTTON_CLICKED
        return FauxEvenement()

    def test_dialogue_recoit_les_libelles_et_initialise_les_coches(self):
        wx = self.wx
        etats = [(0, "Pointage en attente"), (1, "Présent"), (2, "Absence justifiée"), (3, "Absence injustifiée")]
        faux = self._faux(etats, [1, 3])
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            dialogue = cree_dialogue.return_value
            dialogue.ShowModal.return_value = wx.ID_OK
            dialogue.GetSelections.return_value = [0, 1, 2, 3]
            self.assertTrue(self.controle.OnEvent(faux, None, None, self._clic()))
            self.assertEqual(faux.recu, [0, 1, 2, 3])
            self.assertEqual(cree_dialogue.call_args.args[3], [libelle for _, libelle in etats])
            dialogue.SetSelections.assert_called_once_with([1, 3])
            dialogue.Destroy.assert_called_once()

    def test_bouton_wx42_ouvre_le_meme_dialogue_et_rend_les_identifiants(self):
        wx = self.wx
        jours = [(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")]
        faux = self._faux(jours, [])
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            dialogue = cree_dialogue.return_value
            dialogue.ShowModal.return_value = wx.ID_OK
            dialogue.GetSelections.return_value = [2, 5]
            self.assertEqual(self.controle.DisplayEditorDialog(faux, None, [0, 1, 2, 3, 4]), (True, [2, 5]))
            self.assertEqual(cree_dialogue.call_args.args[3], [libelle for _, libelle in jours])
            dialogue.SetSelections.assert_called_once_with([0, 1, 2, 3, 4])
            dialogue.Destroy.assert_called_once()

    def test_bouton_wx42_annuler_garde_la_valeur(self):
        wx = self.wx
        faux = self._faux([(0, "Réservation"), (1, "Présent")], [1])
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            cree_dialogue.return_value.ShowModal.return_value = wx.ID_CANCEL
            self.assertEqual(self.controle.DisplayEditorDialog(faux, None, None), (False, None))
            cree_dialogue.return_value.SetSelections.assert_called_once_with([1])

    def test_annuler_ne_change_pas_les_etats_enregistres(self):
        wx = self.wx
        faux = self._faux([(0, "Réservation"), (1, "Présent")], [0, 1])
        with mock.patch.object(wx, "MultiChoiceDialog") as cree_dialogue:
            cree_dialogue.return_value.ShowModal.return_value = wx.ID_CANCEL
            self.assertFalse(self.controle.OnEvent(faux, None, None, self._clic()))
        self.assertIsNone(faux.recu)


if __name__ == "__main__":
    unittest.main()
