# -*- coding: utf-8 -*-
"""Garde permanente : un lancement de diagnostic du workflow Windows RC10.4 ne
peut créer ni tag ni release.

Le workflow est analysé avec un lecteur YAML minimal (sous-ensemble utilisé
par ce fichier : mappings, listes, scalaires simples ou entre guillemets,
blocs | et >-), sans dépendance externe, et contre-vérifié par PyYAML quand
il est installé. Les conditions `if:` sont évaluées pour chaque scénario de
déclenchement par un évaluateur d'expressions GitHub restreint ; toute
syntaxe inconnue fait échouer le test plutôt que d'être ignorée.
"""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github" / "workflows" / "noethys-sl-rc104-windows.yml"
SCRIPT_PORTABLE = RACINE / "scripts" / "verify_windows_portable_rc104.ps1"
TAG = "noethys-sl-0.1.0-rc.10.4"


# --------------------------------------------------------------------------
# Lecteur YAML minimal
# --------------------------------------------------------------------------

def _scalaire(texte):
    texte = texte.strip()
    if texte.startswith("'") and texte.endswith("'"):
        return texte[1:-1].replace("''", "'")
    if texte.startswith('"') and texte.endswith('"'):
        return texte[1:-1]
    if texte in ("true", "false"):
        return texte == "true"
    if re.fullmatch(r"-?\d+", texte):
        return int(texte)
    return texte


def _sans_commentaire(ligne):
    if ligne.lstrip().startswith("#"):
        return ""
    return ligne


class LecteurYAML(object):
    def __init__(self, texte):
        self.lignes = [l.rstrip("\n") for l in texte.splitlines()]
        self.i = 0

    def _suivante(self):
        while self.i < len(self.lignes) and not _sans_commentaire(self.lignes[self.i]).strip():
            self.i += 1
        if self.i >= len(self.lignes):
            return None, None
        ligne = self.lignes[self.i]
        return len(ligne) - len(ligne.lstrip(" ")), ligne.strip()

    def lire(self):
        indent, contenu = self._suivante()
        return self._bloc(indent)

    def _bloc_texte(self, indent_parent, plie):
        morceaux, indent_bloc = [], None
        while self.i < len(self.lignes):
            ligne = self.lignes[self.i]
            if ligne.strip():
                indent = len(ligne) - len(ligne.lstrip(" "))
                if indent <= indent_parent:
                    break
                indent_bloc = indent if indent_bloc is None else indent_bloc
                morceaux.append(ligne[indent_bloc:])
            else:
                morceaux.append("")
            self.i += 1
        while morceaux and not morceaux[-1]:
            morceaux.pop()
        if not plie:
            return "\n".join(morceaux) + "\n"
        # Repliement YAML : saut de ligne conservé autour des lignes plus indentées.
        texte = morceaux[0] if morceaux else ""
        for precedent, ligne in zip(morceaux, morceaux[1:]):
            separateur = "\n" if (ligne.startswith(" ") or precedent.startswith(" ") or not ligne) else ("" if not precedent else " ")
            texte += separateur + ligne
        return texte

    def _valeur(self, reste, indent):
        if reste in ("|", "|-"):
            return self._bloc_texte(indent, plie=False)
        if reste in (">-", ">"):
            return self._bloc_texte(indent, plie=True)
        if reste == "":
            suivant, contenu = self._suivante()
            if suivant is None or suivant <= indent and not (suivant == indent and contenu.startswith("- ")):
                return None
            return self._bloc(suivant)
        return _scalaire(reste)

    def _bloc(self, indent):
        indent_lu, contenu = self._suivante()
        if contenu is not None and contenu.startswith("- "):
            return self._liste(indent)
        resultat = {}
        while True:
            indent_lu, contenu = self._suivante()
            if contenu is None or indent_lu < indent:
                return resultat
            if indent_lu > indent or contenu.startswith("- "):
                raise ValueError("Indentation inattendue ligne %d : %r" % (self.i + 1, contenu))
            cle, separateur, reste = contenu.partition(":")
            if not separateur:
                raise ValueError("Clé attendue ligne %d : %r" % (self.i + 1, contenu))
            self.i += 1
            resultat[_scalaire(cle)] = self._valeur(reste.strip(), indent)

    def _liste(self, indent):
        resultat = []
        while True:
            indent_lu, contenu = self._suivante()
            if contenu is None or indent_lu < indent or not contenu.startswith("- "):
                return resultat
            element = contenu[2:].strip()
            if ":" in element and not element.startswith(("'", '"')) and re.match(r"^[\w-]+:( |$)", element):
                # Élément mapping : réécrit la ligne sans le tiret, indentation +2.
                self.lignes[self.i] = " " * (indent_lu + 2) + element
                resultat.append(self._bloc(indent_lu + 2))
            else:
                self.i += 1
                resultat.append(_scalaire(element))


def LireWorkflow(texte):
    return LecteurYAML(texte).lire()


# --------------------------------------------------------------------------
# Évaluateur d'expressions GitHub restreint
# --------------------------------------------------------------------------

_JETONS = re.compile(r"\s*(?:(\|\||&&|==|!=|!|\(|\)|,)|('(?:[^']|'')*')|([A-Za-z_][\w.\-]*))")


def _jetons(expression):
    position, jetons = 0, []
    expression = expression.strip()
    while position < len(expression):
        trouve = _JETONS.match(expression, position)
        if not trouve or trouve.end() == position:
            raise ValueError("Syntaxe non prise en charge : %r" % expression[position:])
        operateur, chaine, nom = trouve.groups()
        jetons.append(("op", operateur) if operateur else ("str", chaine[1:-1].replace("''", "'")) if chaine else ("nom", nom))
        position = trouve.end()
    return jetons


def Evaluer(expression, contexte):
    jetons, pos = _jetons(expression), [0]

    def courant():
        return jetons[pos[0]] if pos[0] < len(jetons) else (None, None)

    def avancer():
        if pos[0] >= len(jetons):
            raise ValueError("Expression incomplète : %r" % expression)
        pos[0] += 1
        return jetons[pos[0] - 1]

    def valeur_nom(nom):
        if nom in ("true", "false"):
            return nom == "true"
        objet = contexte
        for partie in nom.split("."):
            objet = objet.get(partie) if isinstance(objet, dict) else None
        return objet

    def primaire():
        genre, valeur = avancer()
        if (genre, valeur) == ("op", "("):
            resultat = ou()
            if avancer() != ("op", ")"):
                raise ValueError("Parenthèse fermante attendue")
            return resultat
        if (genre, valeur) == ("op", "!"):
            return not primaire()
        if genre == "str":
            return valeur
        if genre == "nom" and courant() == ("op", "("):
            if valeur != "contains":
                raise ValueError("Fonction non prise en charge : %s" % valeur)
            avancer()
            a = ou()
            if avancer() != ("op", ","):
                raise ValueError("Virgule attendue")
            b = ou()
            if avancer() != ("op", ")"):
                raise ValueError("Parenthèse fermante attendue")
            return a is not None and b is not None and str(b).lower() in str(a).lower()
        if genre == "nom":
            return valeur_nom(valeur)
        raise ValueError("Jeton inattendu : %r" % (valeur,))

    def comparaison():
        gauche = primaire()
        while courant() in (("op", "=="), ("op", "!=")):
            operateur = avancer()[1]
            droite = primaire()
            gauche = (gauche == droite) if operateur == "==" else (gauche != droite)
        return gauche

    def et():
        resultat = comparaison()
        while courant() == ("op", "&&"):
            avancer()
            droite = comparaison()
            resultat = bool(resultat) and bool(droite)
        return resultat

    def ou():
        resultat = et()
        while courant() == ("op", "||"):
            avancer()
            droite = et()
            resultat = bool(resultat) or bool(droite)
        return resultat

    resultat = ou()
    if pos[0] != len(jetons):
        raise ValueError("Expression non consommée : %r" % expression)
    return bool(resultat)


def Contexte(evenement, ref="refs/heads/wx", publier=None, message=""):
    inputs = {} if publier is None else {"publier": publier}
    return {"github": {"event_name": evenement, "ref": ref,
                       "event": {"head_commit": {"message": message}, "inputs": inputs}},
            "inputs": inputs}


SCENARIOS_SANS_PUBLICATION = {
    "lancement manuel de diagnostic (publier par défaut)": Contexte("workflow_dispatch", publier=False),
    "lancement manuel sans valeur publier": Contexte("workflow_dispatch"),
    "publier=true hors wx": Contexte("workflow_dispatch", ref="refs/heads/main", publier=True),
    "publier=true sur une étiquette": Contexte("workflow_dispatch", ref="refs/tags/x", publier=True),
    "push candidat": Contexte("push", message="build [candidate rc104]"),
    "push avec ancien marqueur de publication": Contexte("push", message="release [publish rc9]"),
    "push avec ancien marqueur RC8.1": Contexte("push", message="[publish rc81]"),
    "push sans marqueur": Contexte("push", message="docs"),
    "publier='true' en texte": Contexte("workflow_dispatch", publier="true"),
}


class LecteurTests(unittest.TestCase):
    def test_bloc_plie_conserve_un_seul_retour_entre_paragraphes(self):
        self.assertEqual(LireWorkflow("run: >-\n  commande\n\n  # commentaire\n")["run"], "commande\n# commentaire")

    def test_lecteur_conforme_a_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML absent : contre-vérification locale uniquement")
        texte = WORKFLOW.read_text(encoding="utf-8")
        reference = yaml.safe_load(texte)
        reference["on"] = reference.pop(True)  # YAML 1.1 : « on » devient True
        self.assertEqual(LireWorkflow(texte), reference)

    def test_evaluateur_refuse_une_syntaxe_inconnue(self):
        for expression in ("startsWith(github.ref, 'x')", "github.ref > 'a'", "github.ref == 'x' ||"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Evaluer(expression, Contexte("push"))


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texte = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = LireWorkflow(cls.texte)
        cls.jobs = cls.workflow["jobs"]

    def jobs_publiant(self):
        return [nom for nom, job in self.jobs.items()
                if any(re.search(r"gh\s+release\s+create|git\s+tag|git\s+push|gh\s+api\s+.*-X\s*(POST|PUT|PATCH)",
                                 str(etape.get("run", ""))) for etape in job.get("steps", []))]

    def test_entree_publier_explicite_et_fausse_par_defaut(self):
        entree = self.workflow["on"]["workflow_dispatch"]["inputs"]["publier"]
        self.assertEqual((entree["type"], entree["default"]), ("boolean", False))

    def test_permissions_ecriture_reservees_au_job_de_publication(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        for nom, job in self.jobs.items():
            permissions = job.get("permissions")
            self.assertIsNotNone(permissions, "permissions explicites requises pour %s" % nom)
            ecritures = {cle for cle, valeur in permissions.items() if valeur == "write"}
            if nom == "publish":
                self.assertEqual(permissions, {"contents": "write"})
            else:
                self.assertEqual(ecritures, set(), "%s ne doit rien écrire" % nom)

    def test_seul_le_job_publish_cree_tag_ou_release(self):
        self.assertEqual(self.jobs_publiant(), ["publish"])
        build = str(self.jobs["build"])
        for interdit in ("GH_TOKEN", "github.token", "secrets.", "gh release", "gh api"):
            self.assertNotIn(interdit, build)

    def test_publication_apres_toutes_les_barrieres(self):
        self.assertEqual(self.jobs["publish"]["needs"], "build")
        for etape in self.jobs["publish"]["steps"]:
            self.assertNotIn("if", etape, "aucune condition d'étape ne doit contourner la condition du job")
        run = "\n".join(str(e.get("run", "")) for e in self.jobs["publish"]["steps"])
        self.assertLess(run.index("git/ref/tags/$tag"), run.index("gh release create"))
        self.assertIn("SHA256SUMS.txt", run)
        self.assertIn("-ne 'wx'", run)

    def test_aucun_scenario_de_diagnostic_ne_publie(self):
        condition = self.jobs["publish"]["if"]
        for nom, contexte in SCENARIOS_SANS_PUBLICATION.items():
            with self.subTest(scenario=nom):
                self.assertFalse(Evaluer(condition, contexte))

    def test_publication_seulement_sur_autorisation_explicite_depuis_wx(self):
        self.assertTrue(Evaluer(self.jobs["publish"]["if"], Contexte("workflow_dispatch", publier=True)))

    def test_build_de_diagnostic_disponible_sans_publication(self):
        condition = self.jobs["build"]["if"]
        self.assertTrue(Evaluer(condition, Contexte("workflow_dispatch", publier=False)))
        self.assertTrue(Evaluer(condition, Contexte("push", message="x [candidate rc104]")))
        self.assertFalse(Evaluer(condition, Contexte("push", message="[publish rc104]")))
        self.assertFalse(Evaluer(condition, Contexte("push", message="docs")))

    def test_pythonpath_sous_processus_aligne_sur_ci_rapide(self):
        """Les sous-processus CE-4/CE-5 doivent retrouver la garde reseau."""
        rapide = LireWorkflow(
            (RACINE / ".github" / "workflows" / "noethys-sl-fast.yml")
            .read_text(encoding="utf-8")
        )
        attendu = rapide["jobs"]["tests-windows"]["env"]["PYTHONPATH"]
        obtenu = self.jobs["build"].get("env", {}).get("PYTHONPATH")
        self.assertEqual(obtenu, attendu)
        self.assertIn(r"\noethys", obtenu)
        self.assertIn(r"\tests", obtenu)

    def test_declencheurs_limites(self):
        self.assertEqual(set(self.workflow["on"]), {"workflow_dispatch", "push"})
        self.assertEqual(self.workflow["on"]["push"]["branches"], ["wx"])


class DiagnosticDemarrageWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = LireWorkflow(WORKFLOW.read_text(encoding="utf-8"))
        self.etapes = {e.get("name"): e for e in self.workflow["jobs"]["build"]["steps"]}

    def test_smoke_installable_exige_la_fin_d_initialisation(self):
        run = self.etapes["Vérifier le démarrage sur runner Windows isolé"]["run"]
        self.assertIn("NOETHYS_DIAGNOSTIC_DEMARRAGE", run)
        self.assertIn("ETAPE oninit_fin", run)
        self.assertNotIn("Start-Sleep -Seconds 12", run)

    def test_diagnostics_publies_meme_en_echec(self):
        etape = self.etapes["Conserver les diagnostics de démarrage (même en échec)"]
        self.assertEqual(etape["if"], "always()")
        self.assertIn("diagnostics-demarrage", etape["with"]["path"])

    def test_script_portable_instrumente_et_surveille_le_vrai_profil(self):
        script = SCRIPT_PORTABLE.read_text(encoding="utf-8")
        for attendu in ("NOETHYS_DIAGNOSTIC_DEMARRAGE", "GetFolderPath('ApplicationData')",
                        "GetFolderPath('CommonApplicationData')", "FenetresProcessus", "diagnostics-demarrage"):
            self.assertIn(attendu, script)


if __name__ == "__main__":
    unittest.main()
