# -*- coding: utf-8 -*-
"""#432 : synchro Connecthys sans contention GIL prolongee sur le thread wx.

- PrioriteUI : le thread de fond se met en pause quand la boucle wx ne traite
  plus ses evenements, sans jamais bloquer definitivement la synchro.
- Upload_data reel sur une base fictive : ouvertures et consommations exportees
  ligne a ligne identiques aux donnees sources (insertion groupee), aucune
  donnee reelle, aucun reseau hors 127.0.0.1.
"""
import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

from Utils import UTILS_Priorite_ui as P  # noqa: E402


class Horloge:
    def __init__(self):
        self.t = 100.0
        self.pendants = []

    def __call__(self):
        return self.t

    def dormir(self, duree):
        self.t += duree

    def poster_occupe(self, rappel):
        self.pendants.append(rappel)  # la boucle wx ne traite rien

    def poster_reactif(self, rappel):
        rappel()


class PrioriteTests(unittest.TestCase):
    def nouvelle(self, poster):
        self.h = Horloge()
        return P.PrioriteUI(poster=poster, horloge=self.h, dormir=self.h.dormir)

    def test_sans_boucle_wx_aucun_effet(self):
        with mock.patch.object(P, "_poster_wx", return_value=None):
            p = P.PrioriteUI()
        self.assertFalse(p.actif)
        p.ceder()
        session = object()
        self.assertIs(P.session_cooperative(session, p), session)

    def test_interface_reactive_jamais_de_pause(self):
        h = Horloge()
        p = P.PrioriteUI(poster=h.poster_reactif, horloge=h, dormir=h.dormir)
        for _ in range(1000):
            p.ceder()
            h.t += 0.001
        self.assertEqual(p.pauses, 0)

    def test_un_seul_ping_en_attente(self):
        p = self.nouvelle(None)
        p._poster = self.h.poster_occupe
        for _ in range(5):
            p.ceder()
            self.h.t += 0.01
        self.assertEqual(len(self.h.pendants), 1)

    def test_pause_jusqua_traitement_du_ping(self):
        p = self.nouvelle(None)
        h = self.h

        def dormir(duree):
            h.t += duree
            if h.t >= 100.3 and h.pendants:
                h.pendants.pop()()  # la boucle wx redevient disponible

        p._poster, p._dormir = h.poster_occupe, dormir
        p.ceder()                 # ping envoye a t=100
        h.t = 100.06              # 60 ms sans traitement : interface occupee
        p.ceder()
        self.assertEqual(p.pauses, 1)
        self.assertAlmostEqual(h.t, 100.3, places=2)
        self.assertIsNone(p._ping)

    def test_pause_plafonnee_puis_tranche_de_progression(self):
        p = self.nouvelle(None)
        p._poster = self.h.poster_occupe
        p.ceder()
        self.h.t += 0.06
        p.ceder()
        self.assertEqual(p.pauses, 1)
        self.assertAlmostEqual(p.duree_pauses, P.PAUSE_MAX_S, places=2)
        fin_tranche = self.h.t + P.TRANCHE_MIN_S
        while self.h.t < fin_tranche - 0.01:
            p.ceder()
            self.h.t += 0.01
        self.assertEqual(p.pauses, 1)  # la synchro progresse pendant la tranche
        self.h.t = fin_tranche + 0.01
        p.ceder()
        self.assertEqual(p.pauses, 2)

    def test_poster_en_erreur_desactive(self):
        def poster(_):
            raise RuntimeError("application fermee")

        p = self.nouvelle(poster)
        p.ceder()
        self.assertFalse(p.actif)
        self.assertIsNone(p._ping)

    def test_session_cooperative_cede_avant_chaque_ajout(self):
        appels = []

        class Session:
            def add(self, instance, _warn=True):
                appels.append(("add", instance, _warn))
                return "ok"

        p = self.nouvelle(lambda r: appels.append("ping"))
        s = P.session_cooperative(Session(), p)
        self.assertEqual(s.add("objet", _warn=False), "ok")
        self.assertEqual(appels, ["ping", ("add", "objet", False)])

    def test_flush_par_tranches_et_lots(self):
        evenements = []

        class Session:
            def add(self, instance):
                evenements.append("add")

            def flush(self):
                evenements.append("flush")

            def bulk_save_objects(self, objets):
                evenements.append(("lot", len(objets)))

        p = self.nouvelle(lambda r: r())
        s = P.session_cooperative(Session(), p, taille_flush=3)
        for i in range(7):
            s.add(i)
        self.assertEqual(evenements.count("flush"), 2)
        self.assertEqual(evenements[3], "flush")
        evenements.clear()
        P.enregistrer_par_lots(s, list(range(5)), p, taille=2)
        self.assertEqual(evenements, [("lot", 2), ("lot", 2), ("lot", 1)])


class ContratSourceTests(unittest.TestCase):
    def test_upload_data_groupe_et_cede(self):
        source = (ROOT / "noethys" / "Utils" / "UTILS_Portail_synchro.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        upload = next(n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == "Upload_data")
        texte = ast.get_source_segment(source, upload)
        self.assertIn("session_cooperative(Session(), priorite)", texte)
        self.assertIn("enregistrer_par_lots(session, ouvertures, priorite)", texte)
        self.assertIn("enregistrer_par_lots(session, consommations, priorite)", texte)
        self.assertNotIn("models.Ouverture(date=date, IDunite=IDunite, IDgroupe=IDgroupe))\n                session.add", texte)


class UploadReelTests(unittest.TestCase):
    def test_export_identique_aux_sources_sur_base_fictive(self):
        try:
            import sqlalchemy  # noqa: F401
            import wx  # noqa: F401
        except Exception:
            self.skipTest("sqlalchemy ou wx indisponible")
        code = ("import json, sys; sys.argv=['b']; import ui432_bench_upload as b; "
                "r = b.executer(30, False, 50); print('UI432_UPLOAD ' + json.dumps(r))")
        p = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=300, env={**os.environ, "PYTHONPATH": os.pathsep.join(
                               [str(ROOT / "tools"), str(ROOT / "noethys"), str(ROOT / "tests"), str(ROOT)])})
        ligne = next((l for l in p.stdout.splitlines() if l.startswith("UI432_UPLOAD ")), None)
        self.assertIsNotNone(ligne, p.stdout[-3000:] + p.stderr[-3000:])
        import json
        r = json.loads(ligne.split(" ", 1)[1])
        self.assertIs(r["upload"]["retour"], True, r["upload"])
        self.assertTrue(r["export"]["conforme_source"])
        self.assertEqual(r["export"]["lignes"]["portail_consommations"], r["volumes"]["consommations"])
        self.assertEqual(r["export"]["lignes"]["portail_ouvertures"], r["volumes"]["ouvertures"])
        self.assertEqual(r["export"]["lignes"]["portail_users"], 30)



def lancer_banc(familles, appels, extra=()):
    import json
    code = ("import json, sys; sys.argv=['b']; import ui432_bench_upload as b; "
            "r = b.executer(%d, False, %d, None, %s, %r); print('UI432_UPLOAD ' + json.dumps(r))"
            % (familles, appels, "--sans-priorite" not in extra, "wx" if "--wx" in extra else "simulee"))
    p = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900, env={**os.environ, "PYTHONPATH": os.pathsep.join(
                           [str(ROOT / "tools"), str(ROOT / "noethys"), str(ROOT / "tests"), str(ROOT)])})
    ligne = next((l for l in p.stdout.splitlines() if l.startswith("UI432_UPLOAD ")), None)
    if ligne is None:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    return json.loads(ligne.split(" ", 1)[1])


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "vraie boucle wx : runner Windows isole uniquement")
class BoucleWxReelleTests(unittest.TestCase):
    """Meme Upload_data, meme traitement wx de reference, vraie boucle wx :
    priorite desactivee (comportement anterieur) puis active."""

    def test_traitement_wx_pendant_la_synchro_avant_apres(self):
        avant = lancer_banc(400, 100000, ("--wx", "--sans-priorite"))
        apres = lancer_banc(400, 100000, ("--wx",))
        for r in (avant, apres):
            self.assertIs(r["upload"]["retour"], True, r["upload"])
            self.assertTrue(r["export"]["conforme_source"])
        ref = apres["tick_reference_ms"]["median"]
        print("UI432_BOUCLE_WX avant=%s apres=%s reference_ms=%s pauses=%s upload_s=%s/%s" % (
            avant["tick_pendant_ms"], apres["tick_pendant_ms"], ref, apres["priorite_ui"],
            avant["upload"]["duree_s"], apres["upload"]["duree_s"]), flush=True)
        self.assertGreater(apres["priorite_ui"]["pauses"], 0)
        self.assertLess(apres["tick_pendant_ms"]["p95"], avant["tick_pendant_ms"]["p95"])
        self.assertLess(apres["tick_pendant_ms"]["max"], avant["tick_pendant_ms"]["max"])


if __name__ == "__main__":
    unittest.main()
