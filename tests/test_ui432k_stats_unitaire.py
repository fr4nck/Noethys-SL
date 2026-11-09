# -*- coding: utf-8 -*-
"""UI-432K : calcul simple hors wx, sans base ni reseau de production."""
import ast
import sys
import threading
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import _garde_reseau  # noqa: E402,F401
from Utils import UTILS_Stats_unitaire, UTILS_Etapes_ui  # noqa: E402


def objet_compatible():
    def maj(self, DB=None, dictParametres=None):
        self.texte = "nouveau: " + str(dictParametres["periode"])
        DB.ExecuterReq("SQL fictif")
    classe = type("Texte_nombre_individus", (), {
        "__module__": "Utils.UTILS_Stats_individus", "MAJ": maj})
    objet = classe()
    objet.texte = "ancien"
    objet.dictParametres = {}
    objet.visible = True
    return objet


class CalculUnitaireTests(unittest.TestCase):
    def test_refuse_graphe_non_qualifie(self):
        graphe = type("Graphe_repartition_ages", (), {
            "__module__": "Utils.UTILS_Stats_individus"})()
        self.assertFalse(UTILS_Stats_unitaire.est_compatible(graphe))
        with self.assertRaises(ValueError):
            UTILS_Stats_unitaire.preparer(graphe, {}, "FICTIVE")

    def test_snapshot_connexion_propre_et_application_differee(self):
        objet = objet_compatible()
        params = {"periode": 2026}
        db = mock.Mock()
        threads = []
        db.ExecuterReq.side_effect = lambda *_: threads.append(
            threading.current_thread().name)
        with mock.patch.object(UTILS_Stats_unitaire.GestionDB, "DB",
                               return_value=db) as ouverture:
            commande = UTILS_Stats_unitaire.preparer(objet, params, "FICTIVE")
            params["periode"] = 1998
            resultats = []
            fil = threading.Thread(
                target=lambda: resultats.append(commande()), name="Calcul-Fictif")
            fil.start()
            fil.join(timeout=5)
        self.assertFalse(fil.is_alive())
        ouverture.assert_called_once_with(
            nomFichier="FICTIVE", suffixe=None, pooling=False)
        self.assertEqual(threads, ["Calcul-Fictif"])
        self.assertEqual(objet.texte, "ancien")
        self.assertEqual(resultats, [{"texte": "nouveau: 2026"}])
        UTILS_Stats_unitaire.appliquer(objet, resultats[0])
        self.assertEqual(objet.texte, "nouveau: 2026")
        db.Close.assert_called_once_with()

    def test_erreur_sql_ne_mutile_pas_instance_visible(self):
        objet = objet_compatible()
        db = mock.Mock()
        db.ExecuterReq.side_effect = RuntimeError("SQL fictif refuse")
        with mock.patch.object(UTILS_Stats_unitaire.GestionDB, "DB",
                               return_value=db):
            commande = UTILS_Stats_unitaire.preparer(
                objet, {"periode": 2026}, "FICTIVE")
            with self.assertRaisesRegex(RuntimeError, "SQL fictif refuse"):
                commande()
        self.assertEqual(objet.texte, "ancien")
        db.Close.assert_called_once()

    def test_rejette_attributs_rendus_non_qualifies(self):
        obj = objet_compatible()
        with self.assertRaises(ValueError):
            UTILS_Stats_unitaire.appliquer(obj, {"bitmap": object()})
        self.assertEqual(obj.texte, "ancien")

    def test_source_db_explicite(self):
        with self.assertRaises(ValueError):
            UTILS_Stats_unitaire.preparer(
                objet_compatible(), {"periode": 2026}, None)

    def test_worker_fin_et_exception_passent_par_la_file(self):
        job = UTILS_Etapes_ui.TravailFond(lambda: "calcule")
        job.demarrer()
        job.thread.join(timeout=3)
        self.assertFalse(job.thread.is_alive())
        self.assertEqual(job.resultats.get_nowait(), ("ok", "calcule"))
        with self.assertRaises(RuntimeError):
            job.demarrer()
        def erreur():
            raise RuntimeError("echec fictif")
        job_erreur = UTILS_Etapes_ui.TravailFond(erreur)
        job_erreur.demarrer()
        job_erreur.thread.join(timeout=3)
        etat, details = job_erreur.resultats.get_nowait()
        self.assertEqual(etat, "erreur")
        self.assertIsInstance(details[1], RuntimeError)

    def test_liste_blanche_aucun_appel_wx_ou_matplotlib_dans_maj(self):
        # Controle de non-regression statique : si MAJ gagne un acces GUI,
        # il faut desactiver son worker avant de modifier la liste blanche.
        for nom_module, nom_classe in UTILS_Stats_unitaire._CLASSES:
            chemin = ROOT / "noethys" / "Utils" / (
                nom_module.rsplit(".", 1)[1] + ".py")
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
            classe = next(n for n in arbre.body
                          if isinstance(n, ast.ClassDef) and n.name == nom_classe)
            maj = next(n for n in classe.body
                       if isinstance(n, ast.FunctionDef) and n.name == "MAJ")
            for node in ast.walk(maj):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertNotIn(node.value.id, ("wx", "matplotlib"),
                                     (nom_classe, node.lineno))


if __name__ == "__main__":
    unittest.main()
