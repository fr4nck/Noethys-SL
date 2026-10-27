# -*- coding: utf-8 -*-
"""Lanceur de recette UI-432G (#432) : verdicts sur journaux synthetiques.

Aucun test ne lance Noethys, n'accede a une base ou a Connecthys : le mode
-Analyser ne lit que le dossier synthetique fourni, et les refus sont obtenus
sur des depots git temporaires avant toute recherche de Python.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANCEUR = ROOT / "tools" / "ui432g_recette.ps1"
COQUILLES = [c for c in ("powershell.exe", "pwsh") if sys.platform == "win32" and shutil.which(c)]

REUSSIE, REFUS, NON_RESPECTEE, A_REVOIR, NON_CONCLUANTE = 0, 2, 10, 11, 12
SECRET_URL = "URL syncdown = https://portail.exemple.invalid/syncdown/20261027424242"
DONNEE_FAMILLE = "Famille DUPONTEL Jeanne jeanne.dupontel@exemple.invalid"


def diag(**champs):
    return "NOETHYS_UI_DIAG " + " ".join("%s=%s" % (k, champs[k]) for k in sorted(champs))


ETAT = diag(evenement="etat", fenetre="principale", wx_maximise="True", iconise="False",
            largeur=1920, hauteur=1040, win32_maximise="True", win32_iconise="False",
            premier_plan="True")


def synchro(duree="12.5", pendant=()):
    """Sequence reelle de stdout : URL syncdown ... Temps upload_data."""
    return [SECRET_URL, "URL syncup = https://portail.exemple.invalid/syncup/20261027424242"] + \
        list(pendant) + ["Temps upload_data =  %s" % duree]


@unittest.skipUnless(COQUILLES, "PowerShell indisponible (Windows uniquement)")
class AnalyseSynthetiqueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ui432g-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def dossier(self, sortie, erreurs=(), execution=("etat=termine", "code_sortie=0", "duree_s=600")):
        d = Path(tempfile.mkdtemp(dir=self.tmp))
        if sortie is not None:
            (d / "stdout-COMPLET-NE-PAS-DIFFUSER.log").write_text("\n".join(sortie) + "\n", encoding="utf-8")
        (d / "stderr-COMPLET-NE-PAS-DIFFUSER.log").write_text("\n".join(erreurs) + "\n", encoding="utf-8")
        (d / "meta-anonyme.txt").write_text(
            "head=0123456789abcdef\npython=3.11.9\nwx=4.2.5 msw (phoenix) wxWidgets 3.2.7\n"
            "sqlalchemy=2.0.52\ndateutil=2.9.0.post0\ndebut=27/10/2026 09:00\n"
            "profil_config=inchange\nprofil_customize=inchange\n", encoding="utf-8")
        if execution is not None:
            (d / "execution.txt").write_text("\n".join(execution) + "\n", encoding="utf-8")
        return d

    def analyser(self, d, *options):
        resultats = []
        for coquille in COQUILLES:
            p = subprocess.run([coquille, "-NoProfile", "-NonInteractive", "-File", str(LANCEUR),
                                "-Analyser", str(d), "-Depot", str(Path(self.tmp) / "inexistant"),
                                "-Python", str(Path(self.tmp) / "inexistant.exe")] + list(options),
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=120)
            extrait = (d / "extrait-anonymise-UI432G.txt").read_text(encoding="utf-8-sig")
            resultats.append((coquille, p.returncode, extrait, p.stdout + p.stderr))
        return resultats

    def verifier(self, d, code, verdict, *options, contient=()):
        for coquille, retour, extrait, console in self.analyser(d, *options):
            with self.subTest(coquille=coquille):
                self.assertEqual(retour, code, console)
                self.assertIn("VERDICT : " + verdict + "\n", extrait)
                for texte in contient:
                    self.assertIn(texte, extrait)
                for interdit in ("https", "syncdown/", "424242", "DUPONTEL", "Jeanne", "@", "C:\\", "Ordi"):
                    self.assertNotIn(interdit, extrait)
        return extrait

    # 1. Synchronisation normale sans gel
    def test_synchro_normale_reussie(self):
        d = self.dossier([ETAT, DONNEE_FAMILLE, diag(evenement="retard_boucle", fenetre="principale", retard_ms=310)]
                         + synchro("12.5", [diag(evenement="retard_boucle", fenetre="principale", retard_ms=820)]))
        extrait = self.verifier(d, REUSSIE, "REUSSIE", contient=(
            "Synchronisations : 1 terminee(s) [upload_data s : 12.5] sur 1 commencee(s)",
            "MARQUEUR synchro_debut", "MARQUEUR synchro_terminee upload_data_s=12.5",
            "evenement=retard_boucle fenetre=principale retard_ms=820"))
        self.assertIn("Gel max : 820 ms", extrait)

    # 2. Session normale sans synchronisation : jamais un succes
    def test_session_sans_synchro_non_concluante(self):
        d = self.dossier([ETAT, diag(evenement="retard_boucle", fenetre="principale", retard_ms=300)])
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("aucune synchronisation observee",))

    def test_synchro_commencee_sans_fin_non_concluante(self):
        d = self.dossier([ETAT, SECRET_URL, "Erreur dans le traitement du fichier : False"])
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE",
                      contient=("1 synchronisation(s) commencee(s) mais aucune terminee",))

    # 3. Gel >= 5 s, pendant puis hors synchronisation, et seuil exact
    def test_gel_pendant_synchro_non_respectee(self):
        d = self.dossier([ETAT] + synchro("30.1", [
            diag(evenement="retard_boucle", fenetre="principale", retard_ms=21297),
            diag(evenement="blocage_thread", fenetre="principale", duree_ms=6000,
                 point="GestionDB.py:ExecuterReq:280", point_synchro="UTILS_Portail_synchro.py:Upload_data:900",
                 veille_retard_ms=0, ne_repond_pas="False", fantome="False")]))
        self.verifier(d, NON_RESPECTEE, "NON RESPECTEE", contient=(
            "gels >= 5000 ms : 2 (pendant synchro : 2, hors synchro : 0)",
            "gel 21297 ms (retard_boucle, pendant_synchro",
            "point=GestionDB.py:ExecuterReq:280"))

    def test_gel_hors_synchro_signale_comme_tel(self):
        d = self.dossier([ETAT] + synchro() + [
            diag(evenement="operation", fenetre="principale", operation="reservations.initialisation_grille",
                 duree_ms=9000, sans_evenements_ms=8700, erreur_type="aucune", maximise="True")])
        self.verifier(d, NON_RESPECTEE, "NON RESPECTEE", contient=("hors synchro : 1", "voir #434"))

    def test_seuil_exact_5000_ms(self):
        sous = self.dossier([ETAT] + synchro(pendant=[diag(evenement="retard_boucle", fenetre="principale", retard_ms=4999)]))
        self.verifier(sous, REUSSIE, "REUSSIE")
        egal = self.dossier([ETAT] + synchro(pendant=[diag(evenement="retard_boucle", fenetre="principale", retard_ms=5000)]))
        self.verifier(egal, NON_RESPECTEE, "NON RESPECTEE")

    # 4. Fenetre "ne repond pas" sans gel mesure >= 5 s
    def test_ne_repond_pas_non_respectee(self):
        d = self.dossier([ETAT] + synchro(pendant=[
            diag(evenement="blocage_thread", fenetre="principale", duree_ms=3000, point="hors_noethys",
                 point_synchro="aucune", veille_retard_ms=0, ne_repond_pas="True", fantome="True")]))
        self.verifier(d, NON_RESPECTEE, "NON RESPECTEE", contient=("ne_repond_pas=True : 1 ; fantome=True : 1",))

    # 5. Iconisation non expliquee, puis declaree volontaire
    def test_iconisation_a_revoir_puis_declaree(self):
        sortie = [ETAT] + synchro() + [
            diag(evenement="iconisation", fenetre="principale", iconise="True"),
            diag(evenement="etat", fenetre="principale", wx_maximise="True", iconise="True", largeur=160,
                 hauteur=28, win32_maximise="False", win32_iconise="True", premier_plan="False")]
        d = self.dossier(sortie)
        self.verifier(d, A_REVOIR, "A REVOIR", contient=("-IconisationVolontaire",))
        self.verifier(d, REUSSIE, "REUSSIE", "-IconisationVolontaire",
                      contient=("declaree volontaire par l'utilisateur",))

    def test_gel_prime_sur_iconisation_declaree(self):
        d = self.dossier([ETAT] + synchro(pendant=[
            diag(evenement="retard_boucle", fenetre="principale", retard_ms=22250),
            diag(evenement="iconisation", fenetre="principale", iconise="True")]))
        self.verifier(d, NON_RESPECTEE, "NON RESPECTEE", "-IconisationVolontaire")

    # 6. Arret anormal
    def test_arret_anormal_non_concluant(self):
        d = self.dossier([ETAT] + synchro(),
                         erreurs=["Windows fatal exception: access violation", "", "Current thread 0x0001:"],
                         execution=("etat=termine", "code_sortie=-1073741819", "duree_s=600"))
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=(
            "sortie anormale de Noethys : code -1073741819 (0xC0000005)", "erreur fatale Python/Windows"))

    # 7. Journal incomplet
    def test_lancement_interrompu(self):
        d = self.dossier([ETAT] + synchro(), execution=("etat=en_cours",))
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("lancement interrompu",))

    def test_sans_fichier_execution(self):
        d = self.dossier([ETAT] + synchro(), execution=None)
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("lancement interrompu",))

    def test_journal_absent(self):
        d = self.dossier(None)
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("journal stdout absent",))

    def test_diagnostic_inactif(self):
        d = self.dossier(synchro())
        self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("aucun evenement de diagnostic",))

    # 8. Valeur inattendue ou potentiellement sensible : masquee, jamais copiee
    def test_valeurs_hors_schema_masquees(self):
        d = self.dossier([ETAT, DONNEE_FAMILLE,
                          "NOETHYS_UI_DIAG evenement=operation fenetre=principale operation=Jeanne.DUPONTEL@exemple duree_ms=12",
                          "NOETHYS_UI_DIAG evenement=etat fenetre=principale nom=DUPONTEL iconise=true",
                          "NOETHYS_UI_DIAG Jeanne DUPONTEL",
                          "NOETHYS_UI_DIAG evenement=retard_boucle fenetre=principale retard_ms=300" + SECRET_URL]
                         + synchro())
        extrait = self.verifier(d, NON_CONCLUANTE, "NON CONCLUANTE", contient=("valeur(s) hors schema masquee(s)",))
        self.assertIn("evenement=operation fenetre=principale duree_ms=12 masque=1", extrait)
        self.assertIn("evenement=etat fenetre=principale masque=2", extrait)
        self.assertNotIn("iconise=true", extrait)
        # Le marqueur colle a une ligne de diagnostic compte toujours.
        self.assertIn("sur 2 commencee(s)", extrait)

    # 9. Plusieurs synchronisations dans une meme session
    def test_plusieurs_synchros(self):
        d = self.dossier([ETAT] + synchro("11.2") + [diag(evenement="retard_boucle", fenetre="principale", retard_ms=400)]
                         + synchro("9.8") + synchro("10.0"))
        self.verifier(d, REUSSIE, "REUSSIE", contient=(
            "Synchronisations : 3 terminee(s) [upload_data s : 11.2, 9.8, 10.0] sur 3 commencee(s)",))

    def test_dossier_inexistant_refuse(self):
        for coquille in COQUILLES:
            with self.subTest(coquille=coquille):
                p = subprocess.run([coquille, "-NoProfile", "-NonInteractive", "-File", str(LANCEUR),
                                    "-Analyser", str(Path(self.tmp) / "absent")],
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, REFUS, p.stdout + p.stderr)


@unittest.skipUnless(COQUILLES and shutil.which("git"), "PowerShell ou git indisponible")
class RefusAvantLancementTests(unittest.TestCase):
    """Refus obtenus avant la recherche de Python : rien n'est lance."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ui432g-depot-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def depot(self, branche):
        d = self.tmp / branche
        (d / "noethys").mkdir(parents=True)
        (d / "noethys" / "Noethys.py").write_text("raise SystemExit('ne doit jamais etre lance')\n")
        git = ["git", "-c", "user.name=test", "-c", "user.email=test@test.invalid", "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["init", "-q", "-b", branche, str(d)], check=True)
        subprocess.run(git + ["-C", str(d), "add", "-A"], check=True)
        subprocess.run(git + ["-C", str(d), "commit", "-q", "-m", "fictif"], check=True)
        return d

    def lancer(self, depot):
        for coquille in COQUILLES:
            p = subprocess.run([coquille, "-NoProfile", "-NonInteractive", "-File", str(LANCEUR),
                                "-VerifierSeulement", "-Depot", str(depot),
                                "-Python", str(self.tmp / "inexistant.exe")],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            yield coquille, p.returncode, p.stdout + p.stderr

    def test_depot_absent(self):
        for coquille, code, sortie in self.lancer(self.tmp / "vide"):
            with self.subTest(coquille=coquille):
                self.assertEqual(code, REFUS, sortie)
                self.assertIn("depot Noethys introuvable", sortie)

    def test_mauvaise_branche(self):
        for coquille, code, sortie in self.lancer(self.depot("main")):
            with self.subTest(coquille=coquille):
                self.assertEqual(code, REFUS, sortie)
                self.assertIn("branche active 'main'", sortie)

    def test_correctif_absent(self):
        for coquille, code, sortie in self.lancer(self.depot("wx")):
            with self.subTest(coquille=coquille):
                self.assertEqual(code, REFUS, sortie)
                self.assertIn("correctif UI-432G", sortie)

    def test_modification_locale_conservee(self):
        d = self.depot("wx")
        fichier = d / "noethys" / "Noethys.py"
        fichier.write_text("# modification locale\n")
        for coquille, code, sortie in self.lancer(d):
            with self.subTest(coquille=coquille):
                self.assertEqual(code, REFUS, sortie)
        self.assertEqual(fichier.read_text(), "# modification locale\n")


class ContratSourceLanceurTests(unittest.TestCase):
    def setUp(self):
        self.texte = LANCEUR.read_text(encoding="utf-8")

    def test_ascii_pour_powershell_5(self):
        # Windows PowerShell 5.1 lit un .ps1 sans BOM en ANSI.
        self.assertTrue(all(ord(c) < 128 for c in self.texte))

    def test_aucune_commande_destructive_ni_politique(self):
        self.assertNotRegex(self.texte, r"(?i)Set-ExecutionPolicy")
        self.assertNotRegex(self.texte, r"&\s*git\s+(pull|checkout|switch|reset|stash|clean|commit|push|merge\s)")
        self.assertNotRegex(self.texte, r"(?i)Remove-Item\s+(?!\"Env:)")

    def test_ordre_analyse_verification_lancement(self):
        analyse = self.texte.index("if ($Analyser) {")
        depot = self.texte.index("# 1. Depot")
        verifier = self.texte.index("if ($VerifierSeulement) {")
        lancement = self.texte.index("Start-Process")
        self.assertLess(analyse, depot)
        self.assertLess(verifier, lancement)
        self.assertLess(self.texte.index("# Aucune autre instance"), verifier)

    def test_diagnostic_limite_au_processus(self):
        bloc = self.texte[self.texte.index("$sauve = @{"):self.texte.index("$fin = Get-Date")]
        self.assertIn('$env:NOETHYS_SL_UI_DIAG = "1"', bloc)
        self.assertRegex(bloc, r"finally \{\s*foreach \(\$k in \$sauve\.Keys\)")

    def test_jamais_de_succes_par_defaut(self):
        self.assertNotIn("CRITERES RESPECTES", self.texte)
        self.assertIn('$verdict = "REUSSIE"; $code = $CodeReussie }', self.texte)
        self.assertTrue(re.search(r"\$synchros\.Count -eq 0", self.texte))


if __name__ == "__main__":
    unittest.main()
