# -*- coding: utf-8 -*-
"""#432 : ouverture directe d'une fiche individuelle depuis la liste wx.

Qualification de la navigation sans base réelle, sans wx.App, sans réseau :
le clic droit/Shift n'ouvre plus la famille avant l'individu ; la fermeture
rend la main directement à la liste qui a lancé le dialogue.
"""
import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main, mock
import sys


SOURCE = Path(__file__).resolve().parents[1] / "noethys/Ol/OL_Individus.py"


def _charger_methodes():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    classe = next(node for node in arbre.body
                  if isinstance(node, ast.ClassDef) and node.name == "ListView")
    fonctions = [
        next(node for node in classe.body
             if isinstance(node, ast.FunctionDef) and node.name == nom)
        for nom in ("Modifier", "OuvrirFicheIndividu", "OuvrirFicheFamille")
    ]
    droits = SimpleNamespace(
        VerificationDroitsUtilisateurActuel=mock.Mock(return_value=True)
    )
    hote = object()
    etat = {"touche": None}
    wx = SimpleNamespace(
        ID_OK=5100,
        WXK_CONTROL=308,
        WXK_SHIFT=306,
        GetKeyState=lambda cle: cle == etat["touche"],
        GetTopLevelParent=mock.Mock(return_value=hote),
    )
    ns = {"wx": wx, "UTILS_Utilisateurs": droits, "_": lambda s: s}
    code = compile(
        ast.fix_missing_locations(ast.Module(body=fonctions, type_ignores=[])),
        str(SOURCE), "exec"
    )
    exec(code, ns)
    return ns, droits, wx, etat, hote


class OuvrirIndividuDirectement(TestCase):
    def setUp(self):
        self.ns, self.droits, self.wx, self.etat, self.hote = _charger_methodes()
        self.track = SimpleNamespace(
            IDindividu=17,
            GetRattachements=mock.Mock(side_effect=AssertionError(
                "Ne doit pas consulter les rattachements familiaux"
            )),
        )
        self.parent = SimpleNamespace(
            GetName=lambda: "general",
            MAJ=mock.Mock(),
        )
        self.vue = SimpleNamespace(
            GetParent=lambda: self.parent,
            GetGrandParent=lambda: self.parent,
            Selection=lambda: [self.track],
            MAJ=mock.Mock(),
            historique=[],
            OuvrirFicheFamille=mock.Mock(),
            OuvrirFicheIndividu=mock.Mock(),
        )

    def test_clic_droit_fiche_individuelle_sans_demander_la_famille(self):
        evt = SimpleNamespace(GetId=lambda: 70)
        self.ns["Modifier"](self.vue, evt)
        self.vue.OuvrirFicheFamille.assert_called_once_with(
            self.track, False, True
        )

    def test_famille_et_calendrier_restent_des_actions_distinctes(self):
        for identifiant, grille, individuel in (
            (20, False, False), (60, True, False)
        ):
            with self.subTest(identifiant=identifiant):
                self.vue.OuvrirFicheFamille.reset_mock()
                self.ns["Modifier"](self.vue, SimpleNamespace(
                    GetId=lambda: identifiant
                ))
                self.vue.OuvrirFicheFamille.assert_called_once_with(
                    self.track, grille, individuel
                )

    def test_double_clic_normal_garde_la_famille(self):
        self.ns["Modifier"](self.vue, None)
        self.vue.OuvrirFicheFamille.assert_called_once_with(
            self.track, False, False
        )

    def test_shift_double_clic_demande_la_fiche_individuelle(self):
        self.etat["touche"] = self.wx.WXK_SHIFT
        self.ns["Modifier"](
            self.vue, SimpleNamespace(GetId=lambda: 20)
        )
        self.vue.OuvrirFicheFamille.assert_called_once_with(
            self.track, False, True
        )

    def test_contourne_rattachements_et_famille_si_fiche_individuelle(self):
        self.vue.OuvrirFicheIndividu.return_value = "fiche directe"
        retour = self.ns["OuvrirFicheFamille"](
            self.vue, self.track, ouvrirFicheInd=True,
        )
        self.assertEqual(retour, "fiche directe")
        self.vue.OuvrirFicheIndividu.assert_called_once_with(self.track)
        self.track.GetRattachements.assert_not_called()

    def test_individu_sans_famille_confirmation_ouvre_directement(self):
        self.track.GetRattachements.side_effect = None
        self.track.GetRattachements.return_value = (None, {}, "")
        self.wx.YES_NO = 2
        self.wx.YES_DEFAULT = 4
        self.wx.CANCEL = 8
        self.wx.ICON_INFORMATION = 16
        self.wx.ID_YES = 5103
        ferme = mock.Mock()
        self.wx.MessageDialog = mock.Mock(return_value=SimpleNamespace(
            ShowModal=lambda: self.wx.ID_YES, Destroy=ferme,
        ))
        self.vue.OuvrirFicheIndividu.return_value = "retour liste"
        valeur = self.ns["OuvrirFicheFamille"](self.vue, self.track)
        self.assertEqual(valeur, "retour liste")
        self.vue.OuvrirFicheIndividu.assert_called_once_with(self.track)
        ferme.assert_called_once_with()

    def test_plus_aucune_fiche_individuelle_sans_parent_modal(self):
        texte = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("DLG_Individu.Dialog(None", texte)

    def _creer_module_factice(self, resultat, echec=False):
        journal = []
        module = ModuleType("Dlg")
        classe = SimpleNamespace()
        def creer(parent, IDindividu):
            journal.append(("creation", parent, IDindividu))
            def afficher():
                journal.append(("modal",))
                if echec:
                    raise RuntimeError("simulation de fermeture en erreur")
                return resultat
            def detruire():
                journal.append(("destroy",))
            return SimpleNamespace(ShowModal=afficher, Destroy=detruire)
        classe.Dialog = creer
        module.DLG_Individu = classe
        return module, journal

    def test_ouverture_parentale_correcte_et_retour_direct_liste(self):
        module, journal = self._creer_module_factice(self.wx.ID_OK)
        with mock.patch.dict(sys.modules, {"Dlg": module}):
            self.ns["OuvrirFicheIndividu"](self.vue, self.track)
        self.assertEqual(journal, [
            ("creation", self.hote, 17), ("modal",), ("destroy",)
        ])
        self.wx.GetTopLevelParent.assert_called_once_with(self.vue)
        self.vue.MAJ.assert_called_once_with(17)
        self.parent.MAJ.assert_called_once_with()
        self.assertEqual(self.vue.historique, [17])
        self.track.GetRattachements.assert_not_called()

    def test_annuler_revient_a_la_liste_sans_confirmer_sauvegarde(self):
        module, journal = self._creer_module_factice(5101)
        with mock.patch.dict(sys.modules, {"Dlg": module}):
            self.ns["OuvrirFicheIndividu"](self.vue, self.track)
        self.vue.MAJ.assert_not_called()
        self.parent.MAJ.assert_called_once_with()
        self.assertEqual(journal[-1], ("destroy",))

    def test_dialogue_detruit_meme_si_showmodal_echoue(self):
        module, journal = self._creer_module_factice(None, echec=True)
        with mock.patch.dict(sys.modules, {"Dlg": module}):
            with self.assertRaises(RuntimeError):
                self.ns["OuvrirFicheIndividu"](self.vue, self.track)
        self.assertEqual(journal[-1], ("destroy",))

    def test_autorisation_individu_modifier_conservee(self):
        self.droits.VerificationDroitsUtilisateurActuel.return_value = False
        module, journal = self._creer_module_factice(self.wx.ID_OK)
        with mock.patch.dict(sys.modules, {"Dlg": module}):
            self.ns["OuvrirFicheIndividu"](self.vue, self.track)
        self.assertEqual(journal, [])
        self.vue.MAJ.assert_not_called()
        self.droits.VerificationDroitsUtilisateurActuel.assert_called_with(
            "individus_fiche", "modifier"
        )

    def test_historique_borne_a_trente_et_sans_doublon(self):
        self.vue.historique = list(range(1, 31))
        module, _ = self._creer_module_factice(self.wx.ID_OK)
        with mock.patch.dict(sys.modules, {"Dlg": module}):
            self.ns["OuvrirFicheIndividu"](self.vue, self.track)
        self.assertEqual(len(self.vue.historique), 30)
        self.assertEqual(self.vue.historique.count(17), 1)

    def test_aucune_maximisation_forcee_ni_fenetre_famille_dans_la_methode(self):
        source = SOURCE.read_text(encoding="utf-8")
        classe = next(n for n in ast.parse(source).body
                      if isinstance(n, ast.ClassDef) and n.name == "ListView")
        methode = next(n for n in classe.body
                       if isinstance(n, ast.FunctionDef)
                       and n.name == "OuvrirFicheIndividu")
        segment = ast.get_source_segment(source, methode)
        self.assertNotIn("Maximize(", segment)
        self.assertNotIn("Iconize(", segment)
        self.assertNotIn("DLG_Famille", segment)
        self.assertIn("wx.GetTopLevelParent(self)", segment)


if __name__ == "__main__":
    main()
