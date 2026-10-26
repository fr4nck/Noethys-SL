# -*- coding: utf-8 -*-
"""UI-3B : verrou local anti-reentrance du traitement Connecthys.

Contre-epreuve sur le meme corps de methode avec et sans la protection.
Aucune base, aucun email, aucun composant wx instancie.
"""
from __future__ import annotations

import ast
import copy
import datetime
import types
import unittest
from contextlib import nullcontext
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py"


def charger_fonctions():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    garde = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_RefuserTraitementReentrant")
    dialogue = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name == "Dialog")
    methode = next(n for n in dialogue.body if isinstance(n, ast.FunctionDef)
                   and n.name == "Traitement")

    def charger(decorer):
        cible = copy.deepcopy(methode)
        if not decorer:
            cible.decorator_list = []
        bloc = ast.Module(body=[copy.deepcopy(garde), cible], type_ignores=[])
        namespace = {"datetime": datetime}
        exec(compile(ast.fix_missing_locations(bloc), str(SOURCE), "exec"),
             namespace)
        return namespace["_RefuserTraitementReentrant"], namespace["Traitement"]
    return source, methode, charger


class DoubleDialogue:
    def __init__(self):
        self.track = types.SimpleNamespace(IDfamille=1)
        self.ctrl_solde = types.SimpleNamespace(MAJ=lambda **kw: None)
        self.calls = []
        self._traitement_en_cours = False
        self.Traitement = None
        self.diagnostic = types.SimpleNamespace(mesurer=lambda *a, **kw: nullcontext())

    def MAJ_informations(self):
        return None


class ProtectionsTests(unittest.TestCase):
    def test_les_deux_boutons_appellent_la_meme_methode_protegee(self):
        source, methode, charger = charger_fonctions()
        self.assertEqual([n.id for n in methode.decorator_list
                          if isinstance(n, ast.Name)], ["_RefuserTraitementReentrant"])
        dialogue = next(n for n in ast.parse(source).body if
                        isinstance(n, ast.ClassDef) and n.name == "Dialog")
        for nom, mode in (("OnBoutonAutomatique", "automatique"),
                          ("OnBoutonManuel", "manuel")):
            fn = next(n for n in dialogue.body
                      if isinstance(n, ast.FunctionDef) and n.name == nom)
            segment = ast.get_source_segment(source, fn)
            self.assertIn('self.Traitement(mode="%s")' % mode, segment)

    def test_preuve_contradictoire_un_dialogue_modal_peut_relancer_traitement(self):
        _, _, charger = charger_fonctions()

        def scenario(decorer):
            dialogue = DoubleDialogue()

            class TraitementFictif:
                def __init__(self, parent, track, mode):
                    self.parent = parent
                    self.mode = mode

                def Traiter(self):
                    dialogue.calls.append(self.mode)
                    if len(dialogue.calls) == 1:
                        # Simule un second clic servi dans une boucle modale.
                        dialogue.Traitement(mode="manuel")
                    return {"etat": False}

            garde, fonction = charger(decorer)
            fonction.__globals__["UTILS_Diagnostic_ui"] = dialogue.diagnostic
            fonction.__globals__["Traitement"] = TraitementFictif
            dialogue.Traitement = types.MethodType(fonction, dialogue)
            dialogue.Traitement(mode="automatique")
            return dialogue.calls, dialogue._traitement_en_cours

        # Sans la garde (meme corps de methode), le travail part deux fois.
        appels_anciens, _ = scenario(False)
        self.assertEqual(appels_anciens, ["automatique", "manuel"])

        # Avec la garde, le second clic est refuse, sans recursivite.
        appels_nouveaux, encours = scenario(True)
        self.assertEqual(appels_nouveaux, ["automatique"])
        self.assertFalse(encours)

    def test_la_garde_restitue_la_valeur_et_permet_deux_actions_successives(self):
        _, _, charger = charger_fonctions()
        garde, _ = charger(True)
        objet = DoubleDialogue()
        appels = []

        @garde
        def traiter(self, *, mode):
            appels.append(mode)
            return mode.upper()

        self.assertEqual(traiter(objet, mode="automatique"), "AUTOMATIQUE")
        self.assertEqual(traiter(objet, mode="manuel"), "MANUEL")
        self.assertEqual(appels, ["automatique", "manuel"])
        self.assertFalse(objet._traitement_en_cours)

    def test_une_exception_libere_toujours_la_garde(self):
        _, _, charger = charger_fonctions()
        garde, _ = charger(True)
        objet = DoubleDialogue()
        appels = []

        @garde
        def traiter(self):
            appels.append(1)
            if len(appels) == 1:
                raise RuntimeError("defaut synthetique")
            return True

        with self.assertRaises(RuntimeError):
            traiter(objet)
        self.assertFalse(objet._traitement_en_cours)
        self.assertTrue(traiter(objet))
        self.assertEqual(len(appels), 2)

    def test_second_traitement_retourne_false_et_neffectue_aucune_ecriture(self):
        _, _, charger = charger_fonctions()
        garde, _ = charger(True)
        objet = DoubleDialogue()
        mutations = []

        @garde
        def traiter(self):
            mutations.append("traitement fictif")
            retour = traiter(self)
            self.retour_seconde_execution = retour
            return "OK"

        self.assertEqual(traiter(objet), "OK")
        self.assertIs(objet.retour_seconde_execution, False)
        self.assertEqual(mutations, ["traitement fictif"])
        self.assertFalse(objet._traitement_en_cours)


if __name__ == "__main__":
    unittest.main()
