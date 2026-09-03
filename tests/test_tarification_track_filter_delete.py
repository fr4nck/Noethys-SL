import ast
import copy
from pathlib import Path
import types
import unittest


SOURCE = Path("noethys/Dlg/DLG_Saisie_tarification.py")


def load_sauvegarde():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Dialog")
    method = next(node for node in dialog.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "Sauvegarde")
    method = ast.fix_missing_locations(method)
    module = ast.Module(body=[method], type_ignores=[])

    class ForbiddenGestionDB:
        @staticmethod
        def DB():
            raise AssertionError("La base ne doit pas être ouverte en mode track_tarif")

    namespace = {"copy": copy, "GestionDB": ForbiddenGestionDB}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["Sauvegarde"]


class Generalites:
    def GetDateDebut(self): return None
    def GetDateFin(self): return None
    def GetDescription(self): return ""
    def GetObservations(self): return ""
    def GetCategories(self): return None
    def GetTVA(self): return None
    def GetCodeComptable(self): return None
    def GetCPL(self): return None
    def GetLabelPrestation(self): return None


class Conditions:
    def GetGroupes(self): return None
    def GetEtiquettes(self): return None
    def GetCotisations(self): return None
    def GetCaisses(self): return None
    def GetFiltres(self): return []
    def GetPeriodes(self): return (None, None)
    def GetListeInitialeFiltres(self):
        return [{"IDfiltre": 41, "IDquestion": 3, "choix": "x", "criteres": "y"}]


class Calcul:
    def GetCodeMethode(self): return "montant_unique"
    def GetTarifsCompatibles(self): return ["EVENEMENT"]
    def GetTypeQuotient(self): return None


class Toolbook:
    def __init__(self):
        self.pages = {"generalites": Generalites(), "conditions": Conditions(), "type": None, "calcul": Calcul()}
    def GetPage(self, name):
        return self.pages.get(name)


class Track:
    def __init__(self):
        self.updated = None
        self.filters = None
    def MAJ(self, values):
        self.updated = values
    def SetFiltres(self, filters):
        self.filters = filters


class TarificationTrackFilterDeleteTest(unittest.TestCase):
    def test_removing_initial_filter_in_track_mode_does_not_touch_database(self):
        sauvegarde = load_sauvegarde()
        track = Track()
        dialog = types.SimpleNamespace(toolbook=Toolbook(), track_tarif=track, IDtarif=None)

        result = sauvegarde(dialog)

        self.assertIsNone(result)
        self.assertIsNotNone(track.updated)
        self.assertEqual(track.filters, [])

    def test_database_filter_deletion_is_guarded_by_non_track_mode(self):
        source = SOURCE.read_text(encoding="utf-8")
        guarded = 'if self.track_tarif == None and self.toolbook.GetPage("conditions") != None :'
        self.assertIn(guarded, source)


if __name__ == "__main__":
    unittest.main()
