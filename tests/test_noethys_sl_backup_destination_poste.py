# -*- coding: utf-8 -*-
"""Choix local du dossier : aucune base, aucun profil utilisateur, aucun wx réel."""
import ast
import datetime
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "noethys/Utils/UTILS_Sauvegarde_auto.py"


def isoler(profil, choisi=None, accepter=True):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonctions = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in (
        "ChoisirRepertoirePoste", "MemoriserRepertoirePoste")]
    classe = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "Sauvegarde_auto")
    fonctions += [n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "Start"]
    dialogue = types.SimpleNamespace(ShowModal=lambda: 1 if accepter else 0,
                                     GetPath=lambda: choisi, Destroy=mock.Mock())
    env = dict(os=os, datetime=datetime, _=lambda s: s,
               UTILS_Config=types.SimpleNamespace(
                   GetParametre=lambda nom, defaut=None: profil.get(nom, defaut),
                   SetParametre=lambda nom, valeur: profil.update({nom: valeur}),
                   FichierConfig=lambda: types.SimpleNamespace(
                       SetItemConfig=lambda nom, valeur: profil.update({nom: valeur}))),
               wx=types.SimpleNamespace(DirDialog=mock.Mock(return_value=dialogue),
                   DD_DEFAULT_STYLE=0, DD_DIR_MUST_EXIST=0, ID_OK=1, ID_CANCEL=5101),
               glob=types.SimpleNamespace(glob=mock.Mock(return_value=[])))
    exec(compile(ast.Module(body=fonctions, type_ignores=[]), str(SOURCE), "exec"), env)
    return types.SimpleNamespace(**env)


def procedure(dossier):
    return dict(IDsauvegarde=437, nom="Sauvegarde fictive", sauvegarde_repertoire=dossier,
                sauvegarde_fichiers_reseau="demo_data;demo_documents", sauvegarde_fichiers_locaux=None,
                sauvegarde_nom="Noethys", option_demander="0", option_afficher_interface="0",
                option_confirmation="0", option_suppression=None)


class DestinationPosteTests(unittest.TestCase):
    def test_dossier_final_modifie_dans_interface_est_celui_memorise(self):
        import sys
        with tempfile.TemporaryDirectory() as rep, tempfile.TemporaryDirectory() as final:
            profil = {}
            m = isoler(profil, rep)
            m.Start.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: types.SimpleNamespace(ReqMAJ=lambda *a: None, Close=lambda: None))
            dialogue = types.SimpleNamespace(ShowModal=lambda: None, GetResultat=lambda: True,
                Destroy=lambda: None, ctrl_parametres=types.SimpleNamespace(
                    check_repertoire=types.SimpleNamespace(GetValue=lambda: True),
                    ctrl_repertoire=types.SimpleNamespace(GetValue=lambda: final)))
            package = types.ModuleType("Dlg")
            package.DLG_Sauvegarde = types.SimpleNamespace(Dialog=lambda *a, **k: dialogue)
            p = procedure(rep + "/absent")
            p["option_afficher_interface"] = "1"
            objet = types.SimpleNamespace(parent=None, listeSauvegardes=[p], VerificationConditions=lambda p: True)
            with mock.patch.dict(sys.modules, {"Dlg": package}):
                self.assertTrue(m.Start(objet))
            self.assertEqual(list(profil["sauvegarde_repertoires_poste"].values()), [final])

    def test_memorisation_sur_disque_meme_si_la_configuration_gui_est_deja_sauvee(self):
        profil = {}
        m = isoler(profil)
        m.UTILS_Config.SetParametre = mock.Mock()  # Cache GUI sans écriture disque.
        m.MemoriserRepertoirePoste("cle-fictive", "dossier-fictif")
        self.assertEqual(profil["sauvegarde_repertoires_poste"]["cle-fictive"], "dossier-fictif")

    def test_dossier_existant_conserve_sans_dialogue(self):
        with tempfile.TemporaryDirectory() as rep:
            m = isoler({})
            self.assertEqual(m.ChoisirRepertoirePoste(None, procedure(rep)), (rep, None))
            m.wx.DirDialog.assert_not_called()

    def test_choix_memoire_locale_sans_modifier_procedure_partagee(self):
        with tempfile.TemporaryDirectory() as rep:
            profil = {}
            m = isoler(profil, rep)
            p = procedure(str(Path(rep) / "autre-poste"))
            dossier, cle = m.ChoisirRepertoirePoste(None, p)
            self.assertEqual(dossier, rep)
            self.assertEqual(profil, {}, "ne rien enregistrer avant le succès")
            m.MemoriserRepertoirePoste(cle, dossier)
            self.assertEqual(m.ChoisirRepertoirePoste(None, p), (rep, None))
            self.assertTrue(p["sauvegarde_repertoire"].endswith("autre-poste"))
            self.assertEqual(m.wx.DirDialog.call_count, 1)

    def test_annulation_ne_lance_ni_sauvegarde_ni_purge(self):
        m = isoler({}, accepter=False)
        objet = types.SimpleNamespace(parent=None, listeSauvegardes=[procedure("dossier-absent-437")],
                                       VerificationConditions=lambda p: True, Sauvegarde=mock.Mock())
        self.assertEqual(m.Start(objet), m.wx.ID_CANCEL)
        objet.Sauvegarde.assert_not_called()
        m.glob.glob.assert_not_called()

    def test_echec_ne_memorise_pas_le_nouveau_dossier(self):
        with tempfile.TemporaryDirectory() as rep:
            profil = {}
            m = isoler(profil, rep)
            # Dialogue d'erreur final simulé ; aucun import wx.
            m.wx.MessageDialog = lambda *a, **k: types.SimpleNamespace(ShowModal=lambda: 0, Destroy=lambda: None)
            m.wx.OK = m.wx.ICON_ERROR = 0
            objet = types.SimpleNamespace(parent=None, listeSauvegardes=[procedure(rep + "/absent")],
                                           VerificationConditions=lambda p: True, Sauvegarde=lambda p: False)
            self.assertEqual(m.Start(objet), m.wx.ID_CANCEL)
            self.assertEqual(profil, {})

    def test_succes_memorise_localement_et_ne_change_pas_le_dossier_sql(self):
        with tempfile.TemporaryDirectory() as rep:
            profil = {}
            m = isoler(profil, rep)
            maj = mock.Mock()
            m.Start.__globals__["GestionDB"] = types.SimpleNamespace(DB=lambda: types.SimpleNamespace(ReqMAJ=maj, Close=lambda: None))
            objet = types.SimpleNamespace(parent=None, listeSauvegardes=[procedure(rep + "/absent")],
                                           VerificationConditions=lambda p: True, Sauvegarde=lambda p: True)
            self.assertTrue(m.Start(objet))
            self.assertEqual(list(profil["sauvegarde_repertoires_poste"].values()), [rep])
            self.assertEqual([nom for nom, valeur in maj.call_args.args[1]], ["date_derniere"])

    def test_email_seul_ne_demande_pas_de_dossier(self):
        m = isoler({})
        self.assertEqual(m.ChoisirRepertoirePoste(None, procedure(None)), (None, None))
        m.wx.DirDialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
