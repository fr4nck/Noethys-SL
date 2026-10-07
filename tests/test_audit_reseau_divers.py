# -*- coding: utf-8 -*-
"""Tests de caractérisation de l'audit réseau « divers » (hors emails,
Connecthys/Portail, Nomadhys, GestionDB/MySQL).

Ces tests DÉCRIVENT le comportement actuel de la RC2 (ils passent tant que
l'anomalie documentée est présente). Aucun accès Internet : urlopen,
urlretrieve et requests sont remplacés par des doublures ; seul un appel
vers 127.0.0.1:443 (connexion refusée attendue) est utilisé pour observer la
création du contexte TLS.
"""
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
NOETHYS = RACINE / "noethys"
sys.path.insert(0, str(NOETHYS))

try:
    import wx  # noqa: F401
    WX_OK = True
except Exception:  # pragma: no cover - environnement sans wx
    WX_OK = False

try:
    import requests  # noqa: F401
    REQUESTS_OK = True
except Exception:  # pragma: no cover
    REQUESTS_OK = False

from urllib.error import URLError

from Utils import UTILS_Ephemerides as eph


# ---------------------------------------------------------------------------
# Doublures
# ---------------------------------------------------------------------------
class FauxReponseUrllib(io.BytesIO):
    def __init__(self, contenu=b"", url="https://exemple.gouv.fr/"):
        super().__init__(contenu)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FauxReponseRequests(object):
    def __init__(self, status_code=200, texte="", contenu=None):
        self.status_code = status_code
        self.text = texte
        self.content = contenu if contenu is not None else texte.encode("utf-8")
        self.ok = 200 <= status_code < 400

    def json(self):
        return json.loads(self.text)


class RepTemp(object):
    """Remplace UTILS_Fichiers.GetRepTemp par un dossier jetable."""

    def __enter__(self):
        self.rep = tempfile.mkdtemp(prefix="audit_reseau_")
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.rep, ignore_errors=True)
        return False

    def GetRepTemp(self, fichier=""):
        return os.path.join(self.rep, fichier) if fichier else self.rep


# ---------------------------------------------------------------------------
# 1. UTILS_Ephemerides : frontière réseau du panneau « Aujourd'hui »
# ---------------------------------------------------------------------------
class EphemeridesFrontiere(unittest.TestCase):
    def test_read_url_passe_un_timeout_de_8s_et_un_user_agent(self):
        appels = []

        def faux_urlopen(req, timeout=None):
            appels.append((req, timeout))
            return FauxReponseUrllib(b"{}", url=req.full_url)

        with mock.patch.object(eph, "urlopen", faux_urlopen):
            self.assertEqual(eph.read_url("https://api.open-meteo.com/v1/forecast"), b"{}")
        req, timeout = appels[0]
        self.assertEqual(timeout, 8)
        self.assertEqual(req.get_header("User-agent"), "Noethys-SL Ephemerides/1.0")

    def test_read_url_refuse_http_et_redirection_vers_http(self):
        with self.assertRaises(ValueError):
            eph.read_url("http://api.open-meteo.com/")
        with mock.patch.object(eph, "urlopen",
                               lambda req, timeout=None: FauxReponseUrllib(b"x", url="http://evil.example/")):
            with self.assertRaisesRegex(ValueError, "Redirection"):
                eph.read_url("https://api.open-meteo.com/")

    def test_read_url_borne_la_taille(self):
        with mock.patch.object(eph, "urlopen",
                               lambda req, timeout=None: FauxReponseUrllib(b"a" * 2000001, url=req.full_url)):
            with self.assertRaisesRegex(ValueError, "volumineuse"):
                eph.read_url("https://api.open-meteo.com/")

    def test_geocode_dns_impossible_donne_un_message_explicite(self):
        def dns_ko(req, timeout=None):
            raise URLError("[Errno -2] Name or service not known")

        with mock.patch.object(eph, "urlopen", dns_ko):
            with self.assertRaisesRegex(ValueError, "Localisation impossible pour 35240 Bais"):
                eph.geocode("Bais", "35240")

    def test_geocode_envoie_ville_et_code_postal_a_deux_tiers(self):
        """Donnée transmise : ville + CP de l'organisateur (geo.api.gouv.fr puis Open-Meteo)."""
        urls = []

        def faux_read_url(url, official=False):
            urls.append(url)
            return b"[]" if "geo.api.gouv.fr" in url else b"{}"

        with mock.patch.object(eph, "read_url", faux_read_url):
            with self.assertRaises(ValueError):
                eph.geocode("Bais", "35240")
        self.assertTrue(urls[0].startswith("https://geo.api.gouv.fr/communes?codePostal=35240"))
        self.assertTrue(urls[1].startswith("https://geocoding-api.open-meteo.com/v1/search?name=Bais"))

    def test_reponses_meteo_invalides_levent_des_exceptions_heterogenes(self):
        """aggregate_weather ne lève pas toujours ValueError : seul l'except large de _load les absorbe."""
        with self.assertRaises(AttributeError):
            eph.aggregate_weather([])           # JSON valide mais liste
        with self.assertRaises(ValueError):
            eph.aggregate_weather({"hourly": {"time": ["pas-une-date"]}})
        with self.assertRaises(TypeError):
            eph.aggregate_weather({"hourly": {"time": [12]}})
        with self.assertRaises(ValueError):
            eph.aggregate_weather({})           # réponse vide

    def test_fetch_bulletins_prefecture_n_est_pas_appele_en_production(self):
        sources = [p for p in NOETHYS.rglob("*.py") if p.name != "UTILS_Ephemerides.py"]
        appelants = [str(p) for p in sources if "fetch_bulletins" in p.read_text(encoding="utf-8", errors="replace")]
        self.assertEqual(appelants, [])


@unittest.skipUnless(WX_OK, "wxPython absent")
class EphemeridesChargement(unittest.TestCase):
    """CTRL_Ephemeride._load appelé hors wx avec une fausse instance."""

    def _charger(self, saved, organisateur):
        from Ctrl import CTRL_Ephemeride as ui

        class FausseDB(object):
            def __init__(self, *a, **k):
                self.n = 0

            def ExecuterReq(self, req):
                self.req = req
                return True

            def ResultatReq(self):
                return [organisateur] if "organisateur" in self.req else []

            def Close(self):
                pass

        urls = []

        def faux_read_url(url, official=False):
            urls.append(url)
            if "geo.api.gouv.fr" in url:
                return json.dumps([{"nom": organisateur[1], "centre": {"coordinates": [-1.29, 48.0]}}]).encode()
            return json.dumps({"hourly": {"time": []}}).encode()

        faux = mock.Mock()
        faux._alive = True
        publie = []
        with mock.patch.object(ui.GestionDB, "DB", FausseDB), \
                mock.patch.object(ui.data, "read_url", faux_read_url), \
                mock.patch.object(ui.wx, "CallAfter", lambda f, *a: publie.append(a)):
            ui.CTRL._load(faux, 1, saved, True, "base.dat", ui.data.normalize_dashboard_layout())
        return urls, publie[0][1]

    def test_parametres_memorises_masquent_la_nouvelle_adresse_de_l_organisateur(self):
        """NET-09 : après un premier affichage, la ville/CP/GPS mémorisés priment sur la base."""
        saved = {"settings": {"city": "Brest", "postcode": "29200", "latitude": "48.39", "longitude": "-4.48",
                              "zone": "", "agenda": "", "territories": "", "events": []}}
        urls, result = self._charger(saved, ("35240", "Bais", None))
        self.assertEqual(result["settings"]["city"], "Brest")
        self.assertEqual(result["settings"]["postcode"], "29200")
        self.assertTrue(any("latitude=48.39" in u for u in urls), urls)
        self.assertFalse(any("geo.api.gouv.fr" in u for u in urls))

    def test_meteo_vide_est_signalee_sans_crash(self):
        urls, result = self._charger({}, ("35240", "Bais", None))
        self.assertTrue(result["weather_error"].startswith("Météo indisponible"))
        self.assertEqual(result["rows"], [])


class ContexteTLSGlobal(unittest.TestCase):
    """NET-01 : le monkeypatch Connecthys de ssl._create_default_https_context
    (UTILS_Portail_synchro.Synchro.__init__, accept_all_cert=True) s'applique
    aux appels urllib des autres modules."""

    SCRIPT = textwrap.dedent("""
        import sys, ssl
        sys.path.insert(0, %(noethys)r)
        from Utils import UTILS_Ephemerides as eph
        from urllib.request import urlopen
        avant = %(avant)s
        if avant:
            try:
                urlopen("https://127.0.0.1/", timeout=2)
            except Exception:
                pass
        compteur = []
        def non_verifie(*a, **k):
            compteur.append(1)
            return ssl._create_unverified_context(*a, **k)
        ssl._create_default_https_context = non_verifie   # comme UTILS_Portail_synchro.py:102
        try:
            eph.read_url("https://127.0.0.1/")
        except Exception:
            pass
        print(len(compteur))
    """)

    def _lancer(self, executable, avant):
        script = self.SCRIPT % {"noethys": str(NOETHYS), "avant": "True" if avant else "False"}
        sortie = subprocess.run([executable, "-c", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        return int(sortie.stdout.strip().splitlines()[-1])

    def test_patch_avant_le_premier_urlopen_neutralise_tls_pour_ephemerides(self):
        self.assertGreaterEqual(self._lancer(sys.executable, avant=False), 1)

    @unittest.skipUnless(shutil.which("python3.11") or shutil.which("python3.10"),
                         "Python 3.10/3.11 (version du build Windows) absent")
    def test_python_3_10_3_11_patch_tardif_neutralise_aussi_tls(self):
        exe = shutil.which("python3.10") or shutil.which("python3.11")
        self.assertGreaterEqual(self._lancer(exe, avant=True), 1)


# ---------------------------------------------------------------------------
# 2. Validation XSD PES / SEPA (téléchargement http:// non vérifié)
# ---------------------------------------------------------------------------
class ValidationXSD(unittest.TestCase):
    def test_pes_echec_telechargement_vaut_validation_reussie(self):
        from Utils import UTILS_Pes
        appels = []

        def ko(url, dest, *a, **k):
            appels.append((url, a, k))
            raise URLError("timed out")

        with RepTemp() as rt, mock.patch.object(UTILS_Pes, "urlretrieve", ko), \
                mock.patch.object(UTILS_Pes.UTILS_Fichiers, "GetRepTemp", rt.GetRepTemp):
            self.assertIs(UTILS_Pes.ValidationXSD(b"<PES_Aller>invalide</PES_Aller>"), True)
        self.assertEqual(appels[0][0], "http://www.noethys.com/fichiers/pes/schemas_pes.zip")
        self.assertEqual(appels[0][1:], ((), {}))   # ni timeout, ni hook, ni empreinte

    def test_sepa_echec_telechargement_vaut_validation_reussie(self):
        from Utils import UTILS_Prelevements
        with RepTemp() as rt, \
                mock.patch.object(UTILS_Prelevements, "urlretrieve", mock.Mock(side_effect=URLError("refused"))) as ur, \
                mock.patch.object(UTILS_Prelevements.UTILS_Fichiers, "GetRepTemp", rt.GetRepTemp):
            self.assertIs(UTILS_Prelevements.ValidationXSD(b"<x/>", {"version_sepa": "2019"}), True)
        self.assertEqual(ur.call_args.args[0], "http://www.noethys.com/fichiers/sepa/schema_sepa.zip")

    def test_sepa_zip_corrompu_vaut_validation_reussie(self):
        from Utils import UTILS_Prelevements

        def corrompu(url, dest, *a, **k):
            with open(dest, "wb") as f:
                f.write(b"<html>502 Bad Gateway</html>")

        with RepTemp() as rt, mock.patch.object(UTILS_Prelevements, "urlretrieve", corrompu), \
                mock.patch.object(UTILS_Prelevements.UTILS_Fichiers, "GetRepTemp", rt.GetRepTemp):
            self.assertIs(UTILS_Prelevements.ValidationXSD(b"<x/>", {"version_sepa": "2019"}), True)

    def test_sepa_version_inconnue_vaut_validation_reussie(self):
        from Utils import UTILS_Prelevements

        def zip_ok(url, dest, *a, **k):
            with zipfile.ZipFile(dest, "w") as z:
                z.writestr("pain.008.001.02.xsd", "<x/>")

        with RepTemp() as rt, mock.patch.object(UTILS_Prelevements, "urlretrieve", zip_ok), \
                mock.patch.object(UTILS_Prelevements.UTILS_Fichiers, "GetRepTemp", rt.GetRepTemp):
            self.assertIs(UTILS_Prelevements.ValidationXSD(b"<x/>", {"version_sepa": "2030"}), True)

    def test_sepa_le_schema_distant_decide_seul_de_la_validite(self):
        """Un XSD permissif servi par le serveur (ou un MITM sur http://) valide n'importe quel fichier."""
        from Utils import UTILS_Prelevements
        permissif = ('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
                     '<xs:element name="Document"/></xs:schema>')

        def zip_permissif(url, dest, *a, **k):
            with zipfile.ZipFile(dest, "w") as z:
                z.writestr("pain.008.001.08.xsd", permissif)

        with RepTemp() as rt, mock.patch.object(UTILS_Prelevements, "urlretrieve", zip_permissif), \
                mock.patch.object(UTILS_Prelevements.UTILS_Fichiers, "GetRepTemp", rt.GetRepTemp):
            self.assertIs(UTILS_Prelevements.ValidationXSD(
                b"<Document><IBAN>pas un IBAN</IBAN></Document>", {"version_sepa": "2019"}), True)


# ---------------------------------------------------------------------------
# 3. Envoi de SMS par API HTTP (Mailjet / OVH / Brevo)
# ---------------------------------------------------------------------------
@unittest.skipUnless(WX_OK and REQUESTS_OK, "wxPython ou requests absent")
class EnvoiSMS(unittest.TestCase):
    def _envoyer(self, plateforme, faux_get=None, faux_post=None, choix_erreur=1):
        from Dlg import DLG_Envoi_sms as sms
        journal = []

        class FauxMessage(object):
            def __init__(self, parent, message, *a, **k):
                self.message = message

            def ShowModal(self):
                journal.append(("message", self.message))
                return sms.wx.ID_YES

            def Destroy(self):
                pass

        class FauxMessagebox(object):
            def __init__(self, *a, **k):
                self.k = k

            def ShowModal(self):
                journal.append(("erreur", self.k.get("detail")))
                return choix_erreur

            def Destroy(self):
                pass

        def trace(nom, f):
            def appel(*a, **k):
                journal.append((nom, a, k))
                return f(*a, **k)
            return appel

        faux = mock.Mock()
        faux.dictDonnees = {
            "plateforme": plateforme, "message": "Bonjour", "objet": "Test",
            "liste_telephones": ["06.00.00.00.01", "06.00.00.00.02"],
            "token_sms_mailjet": "XXXX", "sender_sms_mailjet": "PMSL",
            "ovh_nom_compte": "sms-xx", "ovh_identifiant": "u", "ovh_mot_passe": "XXXX", "ovh_nom_exp": "PMSL",
            "token_sms_brevo": "XXXX", "sender_sms_brevo": "PMSL",
        }
        patches = [mock.patch.object(sms.wx, "MessageDialog", FauxMessage),
                   mock.patch.object(sms.DLG_Messagebox, "Dialog", FauxMessagebox)]
        if faux_get:
            patches.append(mock.patch.object(sms.requests, "get", trace("get", faux_get)))
        if faux_post:
            patches.append(mock.patch.object(sms.requests, "post", trace("post", faux_post)))
        for p in patches:
            p.start()
        try:
            resultat = sms.Dialog.Envoyer(faux)
            erreur = None
        except Exception as exc:
            resultat, erreur = None, exc
        finally:
            for p in reversed(patches):
                p.stop()
        return resultat, erreur, journal

    def test_ovh_annonce_envoi_termine_avant_le_premier_appel_http(self):
        ok = lambda *a, **k: FauxReponseRequests(200, json.dumps({"status": 100}))
        resultat, erreur, journal = self._envoyer("ovh", faux_get=ok)
        self.assertIsNone(erreur)
        etapes = [e[0] if e[0] != "message" else e[1] for e in journal]
        premier_http = etapes.index("get")
        self.assertIn("Envoi des SMS terminé.", etapes[:premier_http])
        self.assertEqual(etapes.count("Envoi des SMS terminé."), 2)

    def test_ovh_mot_de_passe_en_query_string_et_aucun_timeout(self):
        ok = lambda *a, **k: FauxReponseRequests(200, json.dumps({"status": 100}))
        _, _, journal = self._envoyer("ovh", faux_get=ok)
        appel = [e for e in journal if e[0] == "get"][0]
        self.assertIn("password", appel[2]["params"])
        self.assertNotIn("timeout", appel[2])

    def test_mailjet_erreur_reseau_non_capturee_apres_envois_partiels(self):
        compteur = []

        def post(*a, **k):
            compteur.append(1)
            if len(compteur) == 2:
                raise sms_requests().exceptions.ConnectionError("reset")
            return FauxReponseRequests(200, "{}")

        def sms_requests():
            import requests
            return requests

        resultat, erreur, journal = self._envoyer("mailjet", faux_post=post)
        self.assertIsInstance(erreur, sms_requests().exceptions.ConnectionError)
        self.assertEqual(len(compteur), 2)       # 1er SMS parti, aucun état mémorisé
        self.assertNotIn("timeout", [e for e in journal if e[0] == "post"][0][2])

    def test_mailjet_echecs_puis_continuer_affiche_quand_meme_termine(self):
        ko = lambda *a, **k: FauxReponseRequests(401, json.dumps({"ErrorCode": "x", "ErrorMessage": "token"}))
        resultat, erreur, journal = self._envoyer("mailjet", faux_post=ko, choix_erreur=0)
        self.assertIsNone(erreur)
        self.assertIs(resultat, True)
        self.assertIn(("message", "Envoi des SMS terminé."), journal)

    def test_brevo_reponse_5xx_non_json_leve_une_exception(self):
        ko = lambda *a, **k: FauxReponseRequests(502, "<html>Bad Gateway</html>")
        _, erreur, _ = self._envoyer("brevo", faux_post=ko)
        self.assertIsInstance(erreur, ValueError)   # JSONDecodeError

    def test_mailjet_reponse_erreur_non_json_leve_une_exception(self):
        ko = lambda *a, **k: FauxReponseRequests(503, "Service Unavailable")
        _, erreur, _ = self._envoyer("mailjet", faux_post=ko)
        self.assertIsInstance(erreur, ValueError)


# ---------------------------------------------------------------------------
# 4. Contrôle référentiel (requests sans timeout, tri qui plante)
# ---------------------------------------------------------------------------
@unittest.skipUnless(WX_OK and REQUESTS_OK, "wxPython ou requests absent")
class ControleReferentiel(unittest.TestCase):
    # Deux homonymes distincts, même pertinence (adresses symétriquement différentes)
    XML = (b'<r xmlns:a="urn:x">'
           b'<i><a:nomOfficiel>DURAND</a:nomOfficiel><a:prenomUsuel>LEA</a:prenomUsuel><a:voieNumero>1 rue B</a:voieNumero></i>'
           b'<i><a:nomOfficiel>DURAND</a:nomOfficiel><a:prenomUsuel>LEA</a:prenomUsuel><a:voieNumero>1 rue D</a:voieNumero></i>'
           b'</r>')

    def _rechercher(self, reponse):
        from Dlg import DLG_Controle_referentiel as ref
        faux = mock.Mock()
        faux.ctrl_nom.GetValue.return_value = "Durand"
        faux.ctrl_prenom.GetValue.return_value = "Léa"
        faux.ctrl_adresse.GetValue.return_value = "1 rue A"
        appels = []

        def get(url, *a, **k):
            appels.append((url, k))
            if isinstance(reponse, Exception):
                raise reponse
            return reponse

        with mock.patch.object(ref.UTILS_Customize, "GetValeur", return_value="https://referentiel.invalid/api"), \
                mock.patch.object(ref.requests, "get", get):
            try:
                ref.Dialog.Rechercher(faux)
                return None, appels, faux
            except Exception as exc:
                return exc, appels, faux

    def test_deux_resultats_de_meme_pertinence_font_planter_le_tri(self):
        erreur, appels, _ = self._rechercher(FauxReponseRequests(200, contenu=self.XML))
        self.assertIsInstance(erreur, TypeError)
        url, kwargs = appels[0]
        self.assertEqual(url, "https://referentiel.invalid/api/Durand* Léa*")   # nom/prénom dans l'URL
        self.assertNotIn("timeout", kwargs)

    def test_xml_invalide_non_capture(self):
        from xml.etree.ElementTree import ParseError
        erreur, _, _ = self._rechercher(FauxReponseRequests(200, contenu=b"<html>maintenance"))
        self.assertIsInstance(erreur, ParseError)

    def test_erreur_reseau_affichee(self):
        erreur, _, faux = self._rechercher(OSError("Name or service not known"))
        self.assertIsNone(erreur)
        faux.ctrl_resultats.SetTexte.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Modules historiques : Google sans clé, data.gouv, noethys.com
# ---------------------------------------------------------------------------
class ModulesHistoriques(unittest.TestCase):
    def test_gps_google_http_sans_cle_retourne_none(self):
        from Utils import UTILS_Gps
        urls = []

        def faux(url, timeout=None):
            urls.append((url, timeout))
            return io.BytesIO(json.dumps({"results": [], "status": "REQUEST_DENIED",
                                          "error_message": "You must use an API key"}).encode())

        with mock.patch.object(UTILS_Gps, "urlopen", faux):
            self.assertIsNone(UTILS_Gps.GPS(numero="3", rue="rue des Lilas", cp="35240", ville="Bais", pays="France"))
        url, timeout = urls[0]
        self.assertTrue(url.startswith("http://maps.google.com/maps/api/geocode/json?address=3%20,rue%20des%20Lilas"))
        self.assertEqual(timeout, 5)

    def test_distances_google_http_envoie_les_villes_et_echoue_silencieusement(self):
        from Utils import UTILS_Distances_villes as dist
        urls = []

        def faux(url, timeout=None):
            urls.append(url)
            return io.BytesIO(b'{"status": "REQUEST_DENIED", "rows": []}')

        with mock.patch.object(dist, "urlopen", faux):
            self.assertEqual(dist.GetDistances(("35240", "Bais"), [("35500", "Vitré")]), {})
        self.assertTrue(urls[0].startswith("http://maps.googleapis.com/maps/api/distancematrix/json?origins=35240%20Bais"))

    def test_vacances_data_gouv_erreur_reseau_silencieuse(self):
        from Utils import UTILS_Vacances
        with mock.patch.object(UTILS_Vacances, "urlopen", mock.Mock(side_effect=URLError("timed out"))):
            self.assertEqual(UTILS_Vacances.Calendrier(zone="B").GetVacances(), [])

    def test_vacances_data_gouv_json_objet_fait_planter(self):
        from Utils import UTILS_Vacances
        with mock.patch.object(UTILS_Vacances, "urlopen",
                               lambda url, timeout=None: io.BytesIO(b'{"error": "rate limited"}')):
            with self.assertRaises(TypeError):
                UTILS_Vacances.Calendrier(zone="B").GetVacances()

    @unittest.skipUnless(WX_OK, "wxPython absent")
    def test_enregistrement_code_licence_dans_l_url_sans_encodage(self):
        from Dlg import DLG_Enregistrement as enr
        urls = []

        def faux(url, timeout=None):
            urls.append(url)
            return io.BytesIO(b"codepasok")

        with mock.patch.object(enr, "urlopen", faux):
            self.assertIs(enr.GetValidite(None, None), False)
            enr.GetValidite("id&x=1", "AB#CD")
        self.assertEqual(urls[0], "https://www.noethys.com/aide/html/testcode.php?identifiant=None&code=None")
        self.assertIn("identifiant=id&x=1&code=AB#CD", urls[1])


# ---------------------------------------------------------------------------
# 6. Mise à jour et ouverture d'URL
# ---------------------------------------------------------------------------
class MiseAJourEtNavigateur(unittest.TestCase):
    def _fonction(self, fichier, nom):
        arbre = ast.parse((NOETHYS / fichier).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef) and noeud.name == nom:
                return noeud
        raise AssertionError(nom)

    def test_recherche_maj_au_demarrage_court_circuitee(self):
        corps = self._fonction("Noethys.py", "RechercheMAJinternet").body
        self.assertIsInstance(corps[0], ast.Return)
        self.assertIs(corps[0].value.value, False)

    def test_on_outils_updater_ouvre_le_navigateur_puis_retourne(self):
        corps = self._fonction("Noethys.py", "On_outils_updater").body
        self.assertIn("LaunchDefaultBrowser", ast.dump(corps[0]))
        self.assertIsInstance(corps[1], ast.Return)

    @unittest.skipUnless(WX_OK, "wxPython absent")
    def test_page_recherche_n_effectue_aucun_telechargement(self):
        from Dlg import DLG_Updater as upd
        faux = mock.Mock()
        interdit = mock.Mock(side_effect=AssertionError("réseau interdit"))
        with mock.patch.object(upd.wx, "LaunchDefaultBrowser") as nav, \
                mock.patch.object(upd, "urlopen", interdit), mock.patch.object(upd, "urlretrieve", interdit):
            upd.Page_recherche.Recherche(faux)
        nav.assert_called_once_with("https://github.com/fr4nck/Noethys/releases")
        interdit.assert_not_called()

    def test_lance_fichier_externe_linux_tronque_les_url_a_esperluette(self):
        import FonctionsPerso
        commandes = []
        url = "https://www.noethys.com/index.php?option=com_content&view=article&id=118&Itemid=45"
        with mock.patch.object(FonctionsPerso.sys, "platform", "linux"), \
                mock.patch.object(FonctionsPerso.os, "system", commandes.append):
            FonctionsPerso.LanceFichierExterne(url)
        self.assertEqual(commandes, ["xdg-open " + url])
        # Interprétation réelle par /bin/sh, xdg-open remplacé par printf (inoffensif)
        commande = commandes[0].replace("xdg-open ", "printf '%s\\n' ", 1) + "; wait"
        sortie = subprocess.run(["/bin/sh", "-c", commande], capture_output=True, text=True, timeout=10)
        self.assertEqual(sortie.stdout.strip(), "https://www.noethys.com/index.php?option=com_content")

    def test_lance_fichier_externe_windows_remplace_les_slash_des_url(self):
        import FonctionsPerso
        ouverts = []
        with mock.patch.object(FonctionsPerso.sys, "platform", "win32"), \
                mock.patch.object(FonctionsPerso.os, "startfile", ouverts.append, create=True):
            FonctionsPerso.LanceFichierExterne("https://noethys.com/public/a.pdf")
        self.assertEqual(ouverts, ["https:\\\\noethys.com\\public\\a.pdf"])


if __name__ == "__main__":
    unittest.main()
