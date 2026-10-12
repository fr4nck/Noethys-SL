# -*- coding: utf-8 -*-
"""Non-régression : backend Mailjet et confirmation utilisateur pour
l'envoi manuel d'Email depuis une demande Connecthys.

Défaut réel reproduit (Windows / Python 3.10) :

    DLG_Saisie_portail_demande.py:OnBoutonEnvoyer
    -> Envoyer(visible=False)
    -> UTILS_Envoi_email.EnvoiEmailFamille(...)
    -> DLG_Mailer.OnBoutonEnvoyer(...) -> DLG_Mailer.Envoyer(...)
    -> messagerie.Connecter() -> UTILS_Envoi_email.Mailjet.Connecter()
    -> ModuleNotFoundError: No module named 'mailjet_rest'
    -> (ancienne implémentation) AttributeError masquant la cause réelle.

La gestion d'erreur Python 3 (préservation du texte d'origine, aucune
seconde exception) est déjà couverte par _FormateErreurMessagerie()
(DLG_Mailer.py) et _TexteUtf8() (UTILS_Envoi_email.py), testées
directement dans tests/test_noethys_sl_mailer_errors.py et
tests/test_noethys_sl_py3_wx_hardening.py -- ce fichier ne reteste PAS ces
helpers eux-mêmes ni leur implémentation interne. Il vérifie le
COMPORTEMENT bout en bout (aucun AttributeError, message préservé, aucun
succès compté) et couvre ce qui est propre à ce lot : la dépendance
mailjet-rest et la confirmation utilisateur pour l'envoi manuel.

Aucun accès réseau réel : tous les tests utilisent des mocks/fakes. Aucun
test ne construit le DLG_Mailer.Dialog ni le DLG_Saisie_portail_demande.
Dialog complets (nombreux contrôles OLV/HTML réels, hors de proportion
pour ce correctif) : le contrat est testé au niveau des méthodes
concernées, comme documenté ci-dessous pour chaque test.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))
REPO_ROOT = Path(__file__).resolve().parents[1]

import wx  # noqa: E402

_APP = wx.App(False)

from Utils import UTILS_Envoi_email  # noqa: E402
from Dlg import DLG_Saisie_portail_demande  # noqa: E402


class MailjetDependanceTests(unittest.TestCase):
    """Mission A : contrat de dépendance mailjet_rest / mailjet-rest."""

    def test_mailjet_rest_est_importable(self):
        """La bibliothèque déclarée dans requirements.txt fournit bien le
        module réellement importé par UTILS_Envoi_email.Mailjet.Connecter()
        (noethys/Utils/UTILS_Envoi_email.py:783)."""
        try:
            from mailjet_rest import Client
        except ModuleNotFoundError as err:
            self.fail(
                "mailjet_rest n'est pas installé dans cet environnement de "
                "test alors que requirements.txt le déclare : %s" % err
            )
        self.assertTrue(callable(Client))

    def test_requirements_txt_declare_mailjet_rest(self):
        contenu = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        lignes = [l.strip() for l in contenu.splitlines() if l.strip()]
        self.assertIn("mailjet-rest", lignes)

    def test_vanilla_noethys_spec_ne_collecte_pas_mailjet_rest_explicitement(self):
        """mailjet_rest est un paquet plat (Client/Config/Errors), sans
        import dynamique (vérifié en lisant ses sources installées) : il
        n'a pas besoin d'un collect_runtime_submodules explicite dans
        packaging/vanilla-noethys.spec, contrairement à reportlab/twisted/
        etc. Ce test fige ce constat -- pas une exigence : si un jour il
        s'avère nécessaire de l'ajouter, ce test doit être mis à jour en
        connaissance de cause, pas par accident."""
        spec = (REPO_ROOT / "packaging" / "vanilla-noethys.spec").read_text(encoding="utf-8")
        self.assertNotIn("mailjet", spec.lower())


class MailjetConnecterEtEnvoyerLotTests(unittest.TestCase):
    """Mission B (comportement, pas implémentation) : Connecter() et
    Envoyer_lot() ne doivent jamais lever d'AttributeError secondaire, et
    doivent préserver le texte de l'erreur d'origine. Utilise la vraie
    classe UTILS_Envoi_email.Mailjet (autonome, sans wx.Dialog) : la
    gestion d'erreur interne (_TexteUtf8) n'est volontairement pas
    ré-inspectée ici, seul le résultat observable compte."""

    def _mailjet(self):
        return UTILS_Envoi_email.Mailjet(
            email_exp="expediteur@example.org", nom_exp="Test",
            parametres="api_key==xxx##api_secret==yyy",
        )

    def test_connecter_sans_mailjet_rest_installe_ne_leve_pas_attributeerror(self):
        """Simule l'absence réelle de la dépendance (ModuleNotFoundError),
        sans désinstaller quoi que ce soit : mailjet_rest est retiré de
        sys.modules le temps du test -- reproduction exacte du défaut
        réel signalé."""
        m = self._mailjet()
        with mock.patch.dict(sys.modules, {"mailjet_rest": None}):
            with self.assertRaises(ModuleNotFoundError) as ctx:
                m.Connecter()
        # La cause réelle doit rester exploitable comme texte, sans lever
        # de seconde exception au moment de la convertir en message (c'est
        # exactement le rôle de _TexteUtf8 / _FormateErreurMessagerie,
        # exercé ici indirectement via le comportement observable).
        try:
            message = UTILS_Envoi_email._TexteUtf8(ctx.exception)
        except AttributeError:
            self.fail("La conversion de l'erreur d'origine a levé une AttributeError (bug reproduit)")
        self.assertIn("mailjet_rest", message)

    def test_connecter_reussit_quand_mailjet_rest_est_present(self):
        """Connexion Mailjet simulée réussie : Client() est construit sans
        appel réseau (le SDK Mailjet ne se connecte pas à la construction),
        aucune exception."""
        m = self._mailjet()
        m.Connecter()
        self.assertIsNotNone(m.connection)

    def test_envoyer_lot_erreur_ne_leve_pas_attributeerror_et_ne_compte_aucun_succes(self):
        """Reproduit noethys/Utils/UTILS_Envoi_email.py Mailjet.Envoyer_lot :
        un échec d'envoi individuel (ex. rejet de l'API Mailjet) ne doit ni
        lever d'AttributeError, ni être compté dans les succès."""
        from Dlg import DLG_Messagebox

        m = self._mailjet()
        message = UTILS_Envoi_email.Message(
            destinataires=["famille@example.org"], sujet="Sujet test", texte_html="<p>Test</p>",
        )
        with mock.patch.object(m, "Envoyer", side_effect=RuntimeError("401 Unauthorized (Mailjet)")):
            with mock.patch.object(DLG_Messagebox.Dialog, "ShowModal", return_value=1):
                with mock.patch.object(DLG_Messagebox.Dialog, "Destroy", return_value=None):
                    try:
                        succes = m.Envoyer_lot(messages=[message], dlg_progress=None, afficher_confirmation_envoi=False)
                    except AttributeError as err:
                        self.fail("Envoyer_lot() a levé une AttributeError (bug reproduit) : %s" % err)
        self.assertEqual(succes, [])


class ConfirmationEnvoiManuelTests(unittest.TestCase):
    """Mission C : DLG_Saisie_portail_demande.Dialog.Envoyer() -- appelé
    par OnBoutonEnvoyer(visible=False, bouton "Envoyer") et par
    OnBoutonEditeur(visible=True, bouton "Editeur d'Emails").

    DLG_Saisie_portail_demande.Dialog est un wx.Dialog complet (nombreux
    contrôles réels, requêtes DB) : hors de proportion à construire pour
    ce correctif ciblé. On appelle donc la méthode non liée
    (Dialog.Envoyer) sur un wx.Frame minimal ne portant que les attributs
    effectivement lus par cette méthode -- UTILS_Envoi_email.EnvoiEmail
    Famille est mocké (aucun accès réseau, aucune construction de
    DLG_Mailer)."""

    def _construire_fausse_dialog(self):
        frame = wx.Frame(None)
        self.addCleanup(frame.Destroy)
        frame.ctrl_reponse = types.SimpleNamespace(GetValue=lambda: "Réponse de test")
        frame.ctrl_modele_email = types.SimpleNamespace(GetID=lambda: 42)
        frame.track = types.SimpleNamespace(categorie="autre", IDfamille=1, email_date=None)
        frame.categorie_email = "reponse_demande"
        frame.CreationPDF = lambda **kwds: {}
        frame.MAJ_email_date = lambda: None
        return frame

    def test_clic_manuel_succes_affiche_une_confirmation_et_memorise_email_date(self):
        frame = self._construire_fausse_dialog()
        with mock.patch.object(DLG_Saisie_portail_demande.UTILS_Envoi_email, "EnvoiEmailFamille", return_value=True):
            with mock.patch.object(wx.MessageDialog, "ShowModal", return_value=wx.ID_OK) as show_modal:
                resultat = DLG_Saisie_portail_demande.Dialog.Envoyer(frame, visible=False)

        self.assertTrue(resultat)
        self.assertTrue(show_modal.called, "Aucune confirmation affichée pour un clic manuel réussi")
        self.assertIsNotNone(frame.track.email_date)

    def test_clic_manuel_echec_affiche_lechec_et_ne_memorise_pas_email_date(self):
        frame = self._construire_fausse_dialog()
        with mock.patch.object(DLG_Saisie_portail_demande.UTILS_Envoi_email, "EnvoiEmailFamille", return_value=False):
            with mock.patch.object(wx.MessageDialog, "ShowModal", return_value=wx.ID_OK) as show_modal:
                resultat = DLG_Saisie_portail_demande.Dialog.Envoyer(frame, visible=False)

        self.assertFalse(resultat)
        self.assertTrue(show_modal.called, "Aucune confirmation d'échec affichée pour un clic manuel en échec")
        self.assertIsNone(frame.track.email_date, "email_date ne doit pas être mémorisée après un échec")

    def test_editeur_visible_ne_double_pas_la_confirmation_de_dlg_mailer(self):
        """visible=True (bouton "Editeur d'Emails") : DLG_Mailer affiche
        déjà sa propre confirmation (afficher_confirmation_envoi=True) --
        Dialog.Envoyer() ne doit pas en ajouter une seconde."""
        frame = self._construire_fausse_dialog()
        with mock.patch.object(DLG_Saisie_portail_demande.UTILS_Envoi_email, "EnvoiEmailFamille", return_value=True):
            with mock.patch.object(wx.MessageDialog, "ShowModal", return_value=wx.ID_OK) as show_modal:
                resultat = DLG_Saisie_portail_demande.Dialog.Envoyer(frame, visible=True)

        self.assertTrue(resultat)
        self.assertFalse(show_modal.called, "Une confirmation a été ajoutée en double pour le parcours éditeur visible")
        self.assertIsNotNone(frame.track.email_date)

    def test_parcours_automatique_ne_passe_jamais_par_dialog_envoyer(self):
        """Caractérise structurellement l'hypothèse de la mission : le
        parcours automatique (classe Traitement, méthode
        Traitement_recus, qui appelle UTILS_Envoi_email.EnvoiEmailFamille
        directement) n'appelle jamais self.Envoyer(...) -- donc jamais la
        confirmation ajoutée dans Dialog.Envoyer(). Aucune popup de succès
        n'est donc forcée sur ce chemin, par construction."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")
        debut = source.index("class Traitement():")
        fin_marqueur = source.find("\nclass ", debut + 1)
        bloc_traitement = source[debut: fin_marqueur if fin_marqueur != -1 else len(source)]

        self.assertIn("EnvoiEmailFamille", bloc_traitement)
        self.assertNotIn("self.Envoyer(", bloc_traitement)


if __name__ == "__main__":
    unittest.main()
