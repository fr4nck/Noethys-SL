# -*- coding: utf-8 -*-
"""Publication ponctuelle : uniquement les assets du candidat RC10.3 qualifié."""
from pathlib import Path
import unittest
from tests.test_noethys_sl_workflow_publication_rc103 import LireWorkflow, Evaluer, Contexte

RACINE = Path(__file__).resolve().parents[1]
SHA = "f4b19f7de9e0aec6dc0901214c6807b8bbc9ec90"


class PublicationExacteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = LireWorkflow((RACINE / ".github/workflows/noethys-sl-rc103-publish-verified.yml").read_text(encoding="utf-8"))
        cls.job = cls.workflow["jobs"]["publier"]

    def test_sha_et_runs_exacts(self):
        self.assertEqual(self.job["env"]["BUILD_SHA"], SHA)
        self.assertEqual(self.job["env"]["BUILD_RUN"], "40871040969")
        self.assertEqual(self.job["env"]["FAST_RUN"], "40873002081")
        self.assertEqual(self.job["env"]["QUALIFICATION_SHA"], "7f48148df568acb243063aa2427707cd292669d1")
        recuperer = next(s for s in self.job["steps"] if s.get("uses", "").startswith("actions/download-artifact@")
                         and s["with"]["name"].startswith("Noethys-SL"))
        self.assertEqual(str(recuperer["with"]["run-id"]), self.job["env"]["BUILD_RUN"])
        self.assertEqual(recuperer["with"]["name"], "Noethys-SL-0.1.0-rc.10.3-Windows-candidat")
        controles = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertIn('test "$etat" = "success"', controles)
        self.assertIn('"$BUILD_RUN:$BUILD_SHA" "$FAST_RUN:$QUALIFICATION_SHA"', controles)
        self.assertIn('test "$source" = "$attendu"', controles)

    def test_autorisation_exacte_et_refus_des_autres_evenements(self):
        message = "release: publier RC10.3 validee f4b19f7d"
        for event, ref, msg, resultat in (
            ("push", "refs/heads/wx", message, True),
            ("push", "refs/heads/main", message, False),
            ("push", "refs/heads/wx", "docs", False),
            ("workflow_dispatch", "refs/heads/wx", message, False),
            ("pull_request", "refs/heads/wx", message, False),
        ):
            contexte = Contexte(event, ref=ref, message=msg)
            contexte["github"]["repository"] = "fr4nck/Noethys-SL"
            self.assertEqual(Evaluer(self.job["if"], contexte), resultat)

    def test_empreintes_et_refus_de_remplacer_tag_ou_release(self):
        texte = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertIn("sha256sum -c SHA256SUMS.txt", texte)
        self.assertIn("git/ref/tags/$TAG", texte)
        self.assertIn('gh release view "$TAG"', texte)
        self.assertNotIn("--clobber", texte)
        self.assertNotIn("--force", texte)
        self.assertIn('--target "$BUILD_SHA"', texte)
        self.assertIn("--prerelease", texte)

    def test_permissions_et_declencheur_limites(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.job["permissions"], {"actions": "read", "contents": "write"})
        self.assertEqual(self.workflow["on"]["push"]["branches"], ["wx"])
        self.assertEqual(self.job["env"]["TAG"], "noethys-sl-0.1.0-rc.10.3")

    def test_contenu_du_binaire_exige_alsh_et_attente_sans_execution(self):
        texte = next(s['run'] for s in self.job['steps'] if 'CArchiveReader' in s.get('run', ''))
        for module in ('Dlg.DLG_Frequentation_collectivites', 'Utils.UTILS_Attente',
                       'Utils.UTILS_Frequentation_collectivites_db', 'xlsxwriter.workbook'):
            self.assertIn(module, texte)
        self.assertIn('z.testzip() is None', texte)
        code = texte.split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        compile(code, '<verification-binaire>', 'exec')
        self.assertNotIn('subprocess', code)

    def test_attestation_lie_requalification_et_source_exact(self):
        recuperer = next(s for s in self.job['steps'] if s.get('with', {}).get('name') == 'RC10.3-qualification-f4b19f7d')
        self.assertEqual(str(recuperer['with']['run-id']), self.job['env']['FAST_RUN'])
        texte = next(s['run'] for s in self.job['steps'] if 'preuve[\'source_sha\']' in s.get('run', ''))
        self.assertIn("preuve['source_sha'] == os.environ['BUILD_SHA']", texte)
        self.assertIn("preuve['workflow_sha'] == os.environ['QUALIFICATION_SHA']", texte)
        self.assertIn("preuve['fast_workflow_sha256']", texte)
        self.assertIn("preuve['resultat'] == 'success'", texte)


if __name__ == "__main__":
    unittest.main()

