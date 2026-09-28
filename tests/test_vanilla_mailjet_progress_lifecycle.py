# -*- coding: utf-8 -*-
"""Non-régression : parcours réel signalé par une recette Windows.

    DLG_Saisie_portail_demande -> EnvoiEmailFamille -> DLG_Mailer
    -> Mailjet.Envoyer_lot() -> Mailjet.Envoyer()

Deux défauts caractérisés mécaniquement (wxPython 4.2.5 / mailjet_rest
réellement installé, aucun accès réseau dans les tests) :

A. Base64Content -- base64.b64encode() renvoie des bytes sous Python 3.
   mailjet_rest transmet le payload directement à json.dumps() (via
   requests) : des bytes non décodés y lèvent
   TypeError("Object of type bytes is not JSON serializable"). Corrigé en
   décodant explicitement en ASCII (noethys/Utils/UTILS_Envoi_email.py,
   Mailjet.Envoyer()).

B. Cycle de vie de la wx.ProgressDialog dans Mailjet.Envoyer_lot() :
   plusieurs phases (préparation du libellé destinataire, construction de
   la ProgressDialog elle-même, ses propres Update()) n'étaient pas
   couvertes par le try/except existant -- une exception y échappait donc
   entièrement, laissant la ProgressDialog ouverte, référencée dans un
   état incohérent. Corrigé en élargissant le try/except à l'intégralité
   du corps par message, et en détruisant systématiquement la
   ProgressDialog (jamais deux fois : _FermerProgressDialog() est
   idempotente) avant tout affichage d'erreur bloquant.

   Un second défaut du même ordre a été trouvé dans l'appelant
   (noethys/Dlg/DLG_Mailer.py, Dialog.Envoyer()) : après le retour de
   Envoyer_lot() (qui détruit déjà systématiquement dlg_progress avant de
   rendre la main), l'appelant tentait un second Destroy() sur le même
   objet, silencieusement avalé par un `except: pass` générique --
   masquant un vrai RuntimeError ("wrapped C/C++ object ... has been
   deleted"). Resserré à `except RuntimeError: pass`, documenté.

C/D. Les libellés de la ProgressDialog reflètent désormais des étapes
   réellement franchies (préparation, pièces jointes si présentes,
   envoi+attente, succès), avec une progression numérique qui avance à
   chaque étape -- plus un seul cran statique par message entier (qui
   laissait la barre figée à 50% pendant toute la durée réelle de l'envoi
   d'un message unique). mailjet_rest exécute l'appel HTTP de façon
   synchrone (self.connection.session.request(..., timeout=...)) : aucun
   évènement wx n'est traité pendant l'attente réseau elle-même, donc
   aucune animation n'est possible à ce moment précis -- caractérisé et
   documenté, pas masqué. mailjet_rest applique déjà un timeout réseau par
   défaut (_DEFAULT_TIMEOUT = 60 secondes, mailjet_rest/types.py),
   transmis à chaque appel HTTP (mailjet_rest/client.py) : non modifié ici
   (non demandé, valeur déjà raisonnable).
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from Utils import UTILS_Envoi_email  # noqa: E402
from Dlg import DLG_Messagebox  # noqa: E402


class FauxProgressDialog:
    """Double de test pour wx.ProgressDialog : compte création, Update(),
    Pulse() et Destroy(), et lève comme le ferait le vrai wx.ProgressDialog
    (RuntimeError) si on l'utilise après destruction -- permet de détecter
    un double Destroy() ou une utilisation après destruction sans jamais
    construire de fenêtre réelle."""

    INSTANCES = []

    def __init__(self, titre="", message="", maximum=1, parent=None):
        self.titre = titre
        self.maximum_construction = maximum
        self.range = maximum
        self.appels_update = []
        self.appels_pulse = []
        self.nb_destroy = 0
        self.detruite = False
        FauxProgressDialog.INSTANCES.append(self)

    def SetSize(self, taille):
        pass

    def CenterOnScreen(self):
        pass

    def SetRange(self, valeur):
        if self.detruite:
            raise RuntimeError("wrapped C/C++ object of type ProgressDialog has been deleted")
        self.range = valeur

    def GetRange(self):
        return self.range

    def Update(self, value, message=""):
        if self.detruite:
            raise RuntimeError("wrapped C/C++ object of type ProgressDialog has been deleted")
        self.appels_update.append((value, message))
        return True, False

    def Pulse(self, message=""):
        if self.detruite:
            raise RuntimeError("wrapped C/C++ object of type ProgressDialog has been deleted")
        self.appels_pulse.append(message)
        return True, False

    def Destroy(self):
        if self.detruite:
            raise RuntimeError("wrapped C/C++ object of type ProgressDialog has been deleted")
        self.detruite = True
        self.nb_destroy += 1


def _NouveauMessage(sujet="Sujet du test", fichiers=None, images=None):
    return UTILS_Envoi_email.Message(
        destinataires=["destinataire@example.org"],
        sujet=sujet,
        texte_html="<p>Texte</p>",
        fichiers=fichiers or [],
        images=images or [],
    )


def _NouveauMailjet():
    return UTILS_Envoi_email.Mailjet(
        email_exp="expediteur@example.org", nom_exp="Test",
        parametres="api_key==xxx##api_secret==yyy",
    )


class Base64ContentTests(unittest.TestCase):
    """Mission A : Mailjet.Envoyer() -- InlinedAttachments/Attachments."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmpdir, ignore_errors=True))

        self.contenu_image = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
        self.chemin_image = os.path.join(self.tmpdir, "image.png")
        with open(self.chemin_image, "wb") as f:
            f.write(self.contenu_image)

        self.contenu_pj = b"%PDF-1.4\n" + bytes(range(256)) * 6
        self.chemin_pj = os.path.join(self.tmpdir, "document.pdf")
        with open(self.chemin_pj, "wb") as f:
            f.write(self.contenu_pj)

    def _envoyer_et_capturer_payload(self, images=None, fichiers=None):
        message = _NouveauMessage(images=images or [], fichiers=fichiers or [])
        m = _NouveauMailjet()

        payload_capture = {}

        class FauxSend:
            def create(self, data=None):
                payload_capture["data"] = data
                # Reproduit exactement ce que fait mailjet_rest/requests en
                # interne : json.dumps() du payload avant l'envoi HTTP.
                json.dumps(data)

                class FauxResultat:
                    status_code = 200

                    def json(self2):
                        return {"Messages": [{"Status": "success"}]}

                return FauxResultat()

        class FauxConnection:
            send = FauxSend()

        m.connection = FauxConnection()
        m.Envoyer(message)
        return payload_capture["data"]

    def test_image_inline_base64content_est_str_sous_python3(self):
        data = self._envoyer_et_capturer_payload(images=[self.chemin_image])
        base64content = data["Messages"][0]["InlinedAttachments"][0]["Base64Content"]
        self.assertIsInstance(base64content, str)

    def test_piece_jointe_base64content_est_str_sous_python3(self):
        data = self._envoyer_et_capturer_payload(fichiers=[self.chemin_pj])
        base64content = data["Messages"][0]["Attachments"][0]["Base64Content"]
        self.assertIsInstance(base64content, str)

    def test_json_dumps_du_payload_reussit_avec_images_et_pieces_jointes(self):
        """Ce test échouerait avec TypeError("Object of type bytes is not
        JSON serializable") avant correctif."""
        try:
            data = self._envoyer_et_capturer_payload(images=[self.chemin_image], fichiers=[self.chemin_pj])
        except TypeError as err:
            self.fail("json.dumps() du payload a échoué (bug reproduit) : %s" % err)
        # json.dumps() doit aussi réussir une seconde fois, indépendamment,
        # sur le payload tel que capturé.
        json.dumps(data)

    def test_decodage_base64_redonne_les_octets_originaux_image(self):
        data = self._envoyer_et_capturer_payload(images=[self.chemin_image])
        base64content = data["Messages"][0]["InlinedAttachments"][0]["Base64Content"]
        self.assertEqual(base64.b64decode(base64content), self.contenu_image)

    def test_decodage_base64_redonne_les_octets_originaux_piece_jointe(self):
        data = self._envoyer_et_capturer_payload(fichiers=[self.chemin_pj])
        base64content = data["Messages"][0]["Attachments"][0]["Base64Content"]
        self.assertEqual(base64.b64decode(base64content), self.contenu_pj)

    def test_aucun_champ_bytes_ne_subsiste_dans_le_payload(self):
        data = self._envoyer_et_capturer_payload(images=[self.chemin_image], fichiers=[self.chemin_pj])

        def _aucun_bytes(valeur):
            if isinstance(valeur, bytes):
                return False
            if isinstance(valeur, dict):
                return all(_aucun_bytes(v) for v in valeur.values())
            if isinstance(valeur, list):
                return all(_aucun_bytes(v) for v in valeur)
            return True

        self.assertTrue(_aucun_bytes(data), "le payload contient encore des bytes non décodés")


class ProgressDialogLifecycleTests(unittest.TestCase):
    """Mission B : cycle de vie de dlg_progress dans Envoyer_lot()."""

    def setUp(self):
        FauxProgressDialog.INSTANCES = []
        self.m = _NouveauMailjet()

    def test_creation_update_destroy_sont_bien_comptes_sur_envoi_reussi(self):
        fausse = FauxProgressDialog(maximum=1)
        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            succes = self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(succes, [message])
        self.assertGreaterEqual(len(fausse.appels_update), 3, "au moins préparation/envoi/succès attendus")
        self.assertEqual(fausse.nb_destroy, 1)
        self.assertTrue(fausse.detruite)

    def test_jamais_de_double_destroy_sur_envoi_reussi(self):
        fausse = FauxProgressDialog(maximum=1)
        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)
        self.assertEqual(fausse.nb_destroy, 1)
        # Un second appel réel à Destroy() lèverait RuntimeError (simulé
        # par FauxProgressDialog) : le code ne doit jamais le déclencher.

    def test_destruction_sur_exception_du_faux_client_mailjet(self):
        fausse = FauxProgressDialog(maximum=1)
        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", side_effect=RuntimeError("401 Unauthorized (Mailjet)")):
            with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", return_value=1):
                with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                    succes = self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(succes, [])
        self.assertEqual(fausse.nb_destroy, 1)
        self.assertTrue(fausse.detruite)

    def test_destruction_sur_exception_de_preparation_avant_tout_update(self):
        """L'exception survient avant même le premier Update() (ex. une
        erreur lors de la construction du libellé destinataire) : doit
        malgré tout détruire proprement dlg_progress."""
        fausse = FauxProgressDialog(maximum=1)

        class MessageCasse:
            sujet = "Sujet"
            images = []
            fichiers = []

            def GetLabelDestinataires(self):
                raise ValueError("destinataire invalide")

        with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", return_value=1):
            with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                succes = self.m.Envoyer_lot(messages=[MessageCasse()], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(succes, [])
        self.assertEqual(fausse.nb_destroy, 1)
        self.assertEqual(fausse.appels_update, [], "aucun Update() n'a pu avoir lieu avant l'exception")

    def test_destruction_sur_exception_de_payload_dans_envoyer(self):
        """Reproduit une exception survenant DANS Envoyer() lui-même
        (préparation du payload/encodage), pas seulement une erreur réseau
        générique."""
        fausse = FauxProgressDialog(maximum=1)
        message = _NouveauMessage(images=["/chemin/inexistant.png"])
        self.m.connection = mock.Mock()

        with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", return_value=1):
            with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                succes = self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(succes, [])
        self.assertEqual(fausse.nb_destroy, 1)

    def test_dlg_progress_recreee_apres_reessayer_reste_propre(self):
        """reponse == 0 ("Réessayer") : dlg_progress doit être recréée
        proprement (une nouvelle instance), sans jamais réutiliser ni
        redétruire l'ancienne."""
        fausse_initiale = FauxProgressDialog(maximum=1)
        message = _NouveauMessage()

        appels_envoyer = {"n": 0}

        def _envoyer(msg):
            appels_envoyer["n"] += 1
            if appels_envoyer["n"] == 1:
                raise RuntimeError("Erreur temporaire")
            return "success"

        with mock.patch.object(UTILS_Envoi_email.wx, "ProgressDialog", FauxProgressDialog):
            with mock.patch.object(self.m, "Envoyer", side_effect=_envoyer):
                with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", return_value=0):  # "Réessayer"
                    with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                        succes = self.m.Envoyer_lot(
                            messages=[message], dlg_progress=fausse_initiale, afficher_confirmation_envoi=False,
                        )

        self.assertEqual(succes, [message])
        # L'instance initiale a bien été détruite une seule fois, et une
        # nouvelle instance a été créée pour la retentative.
        self.assertEqual(fausse_initiale.nb_destroy, 1)
        self.assertGreaterEqual(len(FauxProgressDialog.INSTANCES), 2)
        nouvelle = FauxProgressDialog.INSTANCES[-1]
        self.assertIsNot(nouvelle, fausse_initiale)
        self.assertEqual(nouvelle.nb_destroy, 1, "la nouvelle instance doit elle aussi être détruite en fin d'envoi")

    def test_dlg_progress_absente_est_creee_puis_detruite(self):
        """dlg_progress=None : Envoyer_lot() doit la créer elle-même puis
        la détruire -- vérifié en patchant wx.ProgressDialog."""
        message = _NouveauMessage()
        with mock.patch.object(UTILS_Envoi_email.wx, "ProgressDialog", FauxProgressDialog):
            with mock.patch.object(self.m, "Envoyer", return_value="success"):
                self.m.Envoyer_lot(messages=[message], dlg_progress=None, afficher_confirmation_envoi=False)

        self.assertEqual(len(FauxProgressDialog.INSTANCES), 1)
        self.assertEqual(FauxProgressDialog.INSTANCES[0].nb_destroy, 1)

    def test_dlg_progress_fournie_par_lappelant_est_recalee_sur_le_bon_maximum(self):
        """DLG_Mailer.Envoyer() construit dlg_progress avec
        maximum=len(messages)+1 avant d'appeler Envoyer_lot() -- trop petit
        pour le nouveau schéma par étapes : doit être réalignée via
        SetRange(), jamais reconstruite depuis zéro."""
        fausse = FauxProgressDialog(maximum=2)  # ancien schéma : len([message])+1
        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(fausse.range, 1 * 4 + 1)
        self.assertEqual(len(FauxProgressDialog.INSTANCES), 1, "la ProgressDialog fournie ne doit pas être reconstruite")


class LibellesProgressionTests(unittest.TestCase):
    """Mission C : contenu des libellés affichés."""

    def setUp(self):
        FauxProgressDialog.INSTANCES = []
        self.m = _NouveauMailjet()

    def _envoyer(self, message, images=None, fichiers=None):
        fausse = FauxProgressDialog(maximum=1)
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)
        return fausse

    def test_libelle_contient_le_destinataire(self):
        message = _NouveauMessage()
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("destinataire@example.org", textes)

    def test_libelle_contient_le_sujet_tronque_a_80_caracteres(self):
        sujet_long = "S" * 200
        message = _NouveauMessage(sujet=sujet_long)
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("S" * 80 + "...", textes)
        self.assertNotIn("S" * 81, textes)

    def test_libelle_sans_pieces_jointes_ne_mentionne_pas_de_piece_jointe(self):
        message = _NouveauMessage()
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertNotIn("pièce jointe", textes)
        self.assertNotIn("pièces jointes", textes)

    def test_libelle_avec_une_piece_jointe_indique_le_nombre_et_la_taille(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chemin = os.path.join(tmpdir, "doc.pdf")
            with open(chemin, "wb") as f:
                f.write(b"x" * (184 * 1024))
            message = _NouveauMessage(fichiers=[chemin])
            fausse = self._envoyer(message)

        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("1 pièce jointe", textes)
        self.assertIn("184 Ko", textes)

    def test_libelle_avec_plusieurs_pieces_jointes_indique_le_nombre_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chemins = []
            for i in range(2):
                chemin = os.path.join(tmpdir, "doc%d.pdf" % i)
                with open(chemin, "wb") as f:
                    f.write(b"x" * 1024)
                chemins.append(chemin)
            message = _NouveauMessage(fichiers=chemins)
            fausse = self._envoyer(message)

        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("2 pièces jointes", textes)

    def test_libelle_mentionne_envoi_via_mailjet_avant_lappel_bloquant(self):
        message = _NouveauMessage()
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("Mailjet", textes)
        self.assertIn("attente de la réponse", textes)

    def test_libelle_final_indique_le_succes(self):
        message = _NouveauMessage()
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update)
        self.assertIn("succès", textes)

    def test_aucun_secret_naparait_jamais_dans_les_libelles(self):
        message = _NouveauMessage()
        fausse = self._envoyer(message)
        textes = "\n".join(m for _v, m in fausse.appels_update).lower()
        for motif_interdit in ("xxx", "yyy", "api_key", "api_secret", "mot de passe", "password"):
            self.assertNotIn(motif_interdit, textes)

    def test_erreur_ferme_dabord_la_progressdialog_avant_le_dialogue_derreur(self):
        message = _NouveauMessage()
        fausse = FauxProgressDialog(maximum=1)
        ordre = []

        def _envoyer(msg):
            raise RuntimeError("échec simulé")

        def _show_modal_erreur(self_dlg):
            ordre.append(("erreur_affichee", fausse.detruite))
            return 1  # "Arrêter" (un seul message)

        with mock.patch.object(self.m, "Envoyer", side_effect=_envoyer):
            with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", _show_modal_erreur):
                with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                    self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(ordre, [("erreur_affichee", True)], "la ProgressDialog doit déjà être détruite quand le dialogue d'erreur s'affiche")


class ProgressionReelleTests(unittest.TestCase):
    """Mission D : progression par étapes réelles, pas de pourcentage figé
    pendant toute la durée réelle de l'envoi d'un message unique."""

    def setUp(self):
        FauxProgressDialog.INSTANCES = []
        self.m = _NouveauMailjet()

    def test_un_seul_message_avance_sur_plusieurs_valeurs_distinctes(self):
        """Défaut caractérisé : avec l'ancien schéma (maximum=len(messages)+1,
        un seul Update() avant l'envoi), un seul message produisait une
        unique valeur numérique, statique pendant toute la phase réelle
        d'envoi. Le nouveau schéma doit produire plusieurs valeurs
        distinctes et croissantes."""
        fausse = FauxProgressDialog(maximum=1)
        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        valeurs = [v for v, _m in fausse.appels_update]
        self.assertGreater(len(set(valeurs)), 2, "valeurs observées : %r" % (valeurs,))
        self.assertEqual(valeurs, sorted(valeurs), "la progression doit être strictement croissante")

    def test_valeur_juste_avant_lappel_bloquant_nest_pas_la_valeur_finale(self):
        """La valeur affichée juste avant l'appel réseau (bloquant) ne doit
        pas déjà être la valeur de fin : sinon la barre annoncerait un
        travail terminé qui ne l'est pas encore."""
        fausse = FauxProgressDialog(maximum=1)
        valeur_avant_envoi = {}

        def _envoyer(msg):
            valeur_avant_envoi["v"] = fausse.appels_update[-1][0]
            return "success"

        message = _NouveauMessage()
        with mock.patch.object(self.m, "Envoyer", side_effect=_envoyer):
            self.m.Envoyer_lot(messages=[message], dlg_progress=fausse, afficher_confirmation_envoi=False)

        valeur_finale = fausse.appels_update[-1][0]
        self.assertLess(valeur_avant_envoi["v"], valeur_finale)

    def test_maximum_reflete_les_etapes_reelles_pas_le_nombre_de_messages(self):
        messages = [_NouveauMessage(), _NouveauMessage()]
        fausse = FauxProgressDialog(maximum=1)
        with mock.patch.object(self.m, "Envoyer", return_value="success"):
            self.m.Envoyer_lot(messages=messages, dlg_progress=fausse, afficher_confirmation_envoi=False)

        self.assertEqual(fausse.range, len(messages) * 4 + 1)


if __name__ == "__main__":
    unittest.main()
