# -*- coding: utf-8 -*-
"""Garde de l'interface de sauvegarde existante (référence : tag RC10)."""
import ast
import json
from pathlib import Path
import unittest

RACINE = Path(__file__).resolve().parents[1]


class InterfaceHistoriqueTests(unittest.TestCase):
    def test_libelles_traduits_identiques_a_rc10(self):
        reference = json.loads((RACINE / "tests/fixtures/backup_ui_rc10.json").read_text(encoding="utf-8"))
        for fichier, attendu in reference.items():
            arbre = ast.parse((RACINE / "noethys/Utils" / fichier).read_text(encoding="utf-8"))
            actuel = {n.args[0].value for n in ast.walk(arbre)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id == "_" and n.args and isinstance(n.args[0], ast.Constant)
                      and isinstance(n.args[0].value, str)}
            # Les nouveaux textes n'apparaissent qu'en cas de destination
            # inutilisable. Aucun libelle historique ne doit disparaitre.
            ajouts = {
                "UTILS_Sauvegarde_auto.py": {
                    "Le dossier de sauvegarde configure pour cette procedure est indisponible sur cet ordinateur :\n\n%s\n\n%s\n\nChoisissez un autre dossier. Ce choix sera conserve uniquement sur cet ordinateur apres une sauvegarde reussie.",
                    "Impossible d'utiliser le dossier choisi :\n\n%s",
                    "La sauvegarde est creee, mais le nouveau dossier n'a pas pu etre memorise sur cet ordinateur."
                },
                "UTILS_Sauvegarde.py": {
                    "Impossible d'enregistrer la sauvegarde dans le dossier :\n\n%s\n\nErreur système : %s"
                }
            }
            self.assertEqual(actuel, set(attendu) | ajouts.get(fichier, set()), fichier)

    def test_prevol_destination_sans_export_ni_trace(self):
        import os
        import tempfile
        import types
        from unittest import mock

        source = RACINE / "noethys/Utils/UTILS_Sauvegarde_auto.py"
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_VerifierRepertoireDestination")
        env = {"os": os, "tempfile": tempfile}
        exec(compile(ast.Module(body=[fonction], type_ignores=[]), str(source), "exec"), env)

        with tempfile.TemporaryDirectory() as rep:
            self.assertEqual(env["_VerifierRepertoireDestination"](rep), (True, None))
            self.assertEqual(os.listdir(rep), [])
            ok, erreur = env["_VerifierRepertoireDestination"](os.path.join(rep, "absent"))
            self.assertFalse(ok)
            self.assertIn("introuvable", erreur)
            with mock.patch.object(tempfile, "NamedTemporaryFile",
                                   side_effect=PermissionError("interdit")):
                ok, erreur = env["_VerifierRepertoireDestination"](rep)
                self.assertFalse(ok)
                self.assertIn("Ecriture impossible", erreur)

    def test_prevol_local_sans_modification_de_procedure(self):
        import datetime
        import hashlib
        import json
        import os
        import tempfile
        import types
        from unittest import mock

        source = RACINE / "noethys/Utils/UTILS_Sauvegarde_auto.py"
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        noms = {"_CleRepertoirePoste", "_VerifierRepertoireDestination",
                "ChoisirRepertoirePoste", "MemoriserRepertoirePoste"}
        fonctions = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in noms]
        with tempfile.TemporaryDirectory() as rep:
            config = {}
            saved = {}
            class FauxDialog:
                def __init__(self, *args, **kwargs):
                    pass
                def ShowModal(self):
                    return 1
                def GetPath(self):
                    return rep
                def Destroy(self):
                    pass
            wx = types.SimpleNamespace(
                ID_OK=1, DD_DEFAULT_STYLE=0, DD_DIR_MUST_EXIST=0,
                DirDialog=FauxDialog, MessageDialog=FauxDialog, OK=0, ICON_ERROR=0)
            cfg = types.SimpleNamespace(
                GetParametre=lambda key, defaut=None: config.get(key, defaut),
                SetParametre=lambda key, value: config.update({key: value}),
                FichierConfig=lambda: types.SimpleNamespace(
                    SetItemConfig=lambda key, value: saved.update({key: value})))
            env = {"os": os, "tempfile": tempfile, "hashlib": hashlib, "json": json,
                   "_": lambda s: s, "wx": wx, "UTILS_Config": cfg}
            exec(compile(ast.Module(body=fonctions, type_ignores=[]), str(source), "exec"), env)
            procedure = {
                "IDsauvegarde": 42, "nom": "Ma sauvegarde",
                "sauvegarde_repertoire": os.path.join(rep, "inexistant"),
                "sauvegarde_fichiers_locaux": None,
                "sauvegarde_fichiers_reseau": "exemple_DATA"}
            ancien = dict(procedure)
            chemin, cle = env["ChoisirRepertoirePoste"](None, procedure)
            self.assertEqual(chemin, rep)
            self.assertTrue(cle)
            self.assertEqual(procedure, ancien)
            self.assertFalse(config)
            env["MemoriserRepertoirePoste"](cle, chemin)
            self.assertEqual(saved["sauvegarde_repertoires_poste"][cle], rep)
            wx.DirDialog = lambda *args, **kwargs: self.fail("dialogue inattendu")
            self.assertEqual(env["ChoisirRepertoirePoste"](None, procedure), (rep, None))
            # Une annulation de selection ne modifie aucune procedure partagee.
            procedure_annulee = dict(procedure, IDsauvegarde=43)
            class FauxAnnulation(FauxDialog):
                def ShowModal(self):
                    return 0
            wx.DirDialog = FauxAnnulation
            self.assertEqual(
                env["ChoisirRepertoirePoste"](None, procedure_annulee),
                (False, None))
            self.assertEqual(procedure_annulee["sauvegarde_repertoire"],
                             ancien["sauvegarde_repertoire"])

    def test_annulation_destination_ne_lance_pas_export(self):
        import datetime
        import types
        from unittest import mock

        source = RACINE / "noethys/Utils/UTILS_Sauvegarde_auto.py"
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        classe = next(n for n in arbre.body if isinstance(n, ast.ClassDef)
                      and n.name == "Sauvegarde_auto")
        depart = next(n for n in classe.body if isinstance(n, ast.FunctionDef)
                      and n.name == "Start")
        env = {"datetime": datetime, "wx": types.SimpleNamespace(ID_CANCEL=5101),
               "ChoisirRepertoirePoste": lambda p, d: (False, None)}
        exec(compile(ast.Module(body=[depart], type_ignores=[]), str(source), "exec"), env)
        exporter = mock.Mock(side_effect=AssertionError("export interdit"))
        procedure = {
            "IDsauvegarde": 42, "nom": "Ma sauvegarde",
            "sauvegarde_nom": "Noethys", "sauvegarde_repertoire": "absent",
            "option_demander": "0", "option_afficher_interface": "0",
            "option_suppression": None}
        objet = types.SimpleNamespace(parent=None, listeSauvegardes=[procedure],
                                     VerificationConditions=lambda d: True,
                                     Sauvegarde=exporter)
        self.assertEqual(env["Start"](objet), 5101)
        exporter.assert_not_called()

    def test_presentation_du_dialogue_de_progression_conservee(self):
        arbre = ast.parse((RACINE / "noethys/Utils/UTILS_Sauvegarde.py").read_text(encoding="utf-8"))
        fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "Sauvegarde")
        appel = next(n for n in ast.walk(fonction) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "ProgressDialog")
        style = next(k.value for k in appel.keywords if k.arg == "style")
        self.assertEqual({n.attr for n in ast.walk(style) if isinstance(n, ast.Attribute)},
                         {"PD_SMOOTH", "PD_AUTO_HIDE", "PD_APP_MODAL"})


if __name__ == "__main__":
    unittest.main()
