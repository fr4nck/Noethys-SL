#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrat de repli pour une colonne personnalisée obsolète.

``dictParametres["colonnes"]`` provient d'un modèle d'impression enregistré
par l'utilisateur (fichier de préférences). Rien ne garantit qu'un
``donnee_code`` sauvegardé reste reconnu si la liste des données proposées
évolue (ex : champ renommé ou retiré dans une version ultérieure). Avant
correctif, un ``donnee_code`` inconnu provoquait un ``UnboundLocalError``
sur ``donnee`` car aucune branche du ``try`` ne l'initialisait et que la
lecture fautive se trouvait hors du ``except``. Ce test isole la boucle
réelle de ``Impression`` (sans dépendre de wx/reportlab) pour vérifier que
les codes connus restent inchangés et qu'un code inconnu ne casse plus
l'impression.
"""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Impression_conso.py"


def load_colonne_perso_loop():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

    impression = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "Impression":
            impression = node
            break
    if impression is None:
        raise AssertionError("Méthode Impression absente de DLG_Impression_conso.py")

    loop = None
    for node in ast.walk(impression):
        if (
            isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and node.target.id == "dictColonnePerso"
            and any(
                isinstance(inner, ast.Name) and inner.id == "type_donnee"
                for inner in ast.walk(node)
            )
        ):
            loop = node
            break
    if loop is None:
        raise AssertionError("Boucle 'for dictColonnePerso' (avec type_donnee) absente de Impression")

    args = ast.arguments(
        posonlyargs=[],
        args=[
            ast.arg(arg=name, annotation=None)
            for name in (
                "dictParametres",
                "IDindividu",
                "dictIndividus",
                "dictInfosIndividus",
                "dictInfosFamilles",
                "ligne",
                "six",
                "code39",
                "Paragraph",
                "styleNormal",
            )
        ],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )
    func = ast.FunctionDef(
        name="run_colonne_perso_loop",
        args=args,
        body=[loop, ast.Return(value=ast.Name(id="ligne", ctx=ast.Load()))],
        decorator_list=[],
        returns=None,
    )
    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["run_colonne_perso_loop"]


class _Six:
    @staticmethod
    def text_type(value):
        return str(value)


class _Paragraph:
    def __init__(self, texte, style):
        self.texte = texte
        self.style = style

    def __eq__(self, other):
        return isinstance(other, _Paragraph) and self.texte == other.texte


class ImpressionColonnePersoContractTests(unittest.TestCase):
    def setUp(self):
        self.run = load_colonne_perso_loop()
        self.dictIndividus = {1: {"IDfamille": 10}}
        self.dictInfosIndividus = {1: {"INDIVIDU_SEXE": "M"}}
        self.dictInfosFamilles = {10: {"FAMILLE_NOM": "Dupont"}}

    def _run(self, donnee_code):
        dictParametres = {"colonnes": [{"donnee_code": donnee_code}]}
        return self.run(
            dictParametres,
            1,
            self.dictIndividus,
            self.dictInfosIndividus,
            self.dictInfosFamilles,
            [],
            _Six,
            None,
            _Paragraph,
            "styleNormal",
        )

    def test_known_donnee_code_is_unaffected(self):
        ligne = self._run("genre")
        self.assertEqual(ligne, [_Paragraph("M", "styleNormal")])

    def test_none_donnee_code_yields_blank_cell(self):
        ligne = self._run(None)
        self.assertEqual(ligne, [_Paragraph("", "styleNormal")])

    def test_unknown_donnee_code_no_longer_raises_unbound_local_error(self):
        # Ancien contrat : un donnee_code périmé (issu d'un modèle d'impression
        # enregistré avant un renommage/suppression de champ) faisait planter
        # l'impression avec un UnboundLocalError sur 'donnee'.
        ligne = self._run("champ_supprime_dans_une_version_anterieure")
        self.assertEqual(ligne, [_Paragraph("", "styleNormal")])


if __name__ == "__main__":
    unittest.main()
