# -*- coding: utf-8 -*-
"""Non-regression : robustesse du client de synchronisation Connecthys.

Recette réelle : le panneau restait sur "Client de synchronisation
prêt" avec des demandes non traitées, sans que l'utilisateur puisse
relancer une synchronisation. Cause confirmée par audit (aucune
supposition) : une exception non gérée au milieu de
Synchro_totale()/Download_data()/Upload_data() faisait mourir le thread
de synchronisation ET laissait synchro_en_cours à True pour toujours --
plus aucune synchro, automatique ou manuelle, n'était alors possible
sans redémarrer Noethys, sans aucun diagnostic pour l'utilisateur.

Ne change ni le protocole, ni le schéma, ni le serveur Connecthys, ni
les données métier exportées : uniquement la gestion des erreurs et la
journalisation côté client, à l'endroit précis où le défaut a été
identifié.
"""
from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

from Ctrl import CTRL_Portail_serveur  # noqa: E402
from Utils import UTILS_Portail_synchro  # noqa: E402


class FauxLog:
    """ Double du panneau Connecthys (CTRL_Portail_serveur.Panel) :
    fournit exactement ce que Synchro_totale()/EffectuerCycle()
    utilisent, sans wx ni base de données. """

    def __init__(self):
        self.last_synchro = datetime.datetime.now()
        self.synchro_ouverture = False
        self.delai = 999999  # jamais de synchro automatique déclenchée pendant le test
        self.images = []
        self.logs = []
        self.nbre_maj_bouton = 0

    def SetImage(self, nom):
        self.images.append(nom)

    def EcritLog(self, message=""):
        self.logs.append(message)

    def SetGauge(self, valeur=0):
        pass

    def MAJ_bouton(self):
        self.nbre_maj_bouton += 1


def _synchro(**resultats):
    """ Instance Synchro réelle, dont Download_data/Update_application/
    Upload_data sont remplacées (le protocole/les données métier ne sont
    jamais exercés ici, seule la robustesse de l'orchestration l'est). """
    log = FauxLog()
    synchro = UTILS_Portail_synchro.Synchro(
        dict_parametres={"accept_all_cert": False, "client_rechercher_updates": False},
        log=log,
    )
    for nom, valeur in resultats.items():
        setattr(synchro, nom, valeur)
    return synchro, log


class SynchroTotaleRobustesseTests(unittest.TestCase):
    def test_synchro_reussie(self):
        synchro, log = _synchro(
            Download_data=lambda full_synchro=False: True,
            Upload_data=lambda full_synchro=False: True,
        )
        resultat = synchro.Synchro_totale()
        self.assertTrue(resultat)
        self.assertIn(u"Client de synchronisation prêt", log.logs)
        self.assertFalse(any(u"incomplète" in m for m in log.logs))

    def test_download_data_retourne_false(self):
        synchro, log = _synchro(
            Download_data=lambda full_synchro=False: False,
            Upload_data=lambda full_synchro=False: True,
        )
        resultat = synchro.Synchro_totale()
        self.assertFalse(resultat)
        self.assertTrue(any(u"incomplète" in m for m in log.logs))
        self.assertIn(u"Client de synchronisation prêt", log.logs)

    def test_upload_data_retourne_false(self):
        synchro, log = _synchro(
            Download_data=lambda full_synchro=False: True,
            Upload_data=lambda full_synchro=False: False,
        )
        resultat = synchro.Synchro_totale()
        self.assertFalse(resultat)
        self.assertTrue(any(u"incomplète" in m for m in log.logs))
        self.assertIn(u"Client de synchronisation prêt", log.logs)

    def test_exception_pendant_download_data_ne_remonte_pas(self):
        def leve_erreur(full_synchro=False):
            raise RuntimeError("panne réseau simulée")

        synchro, log = _synchro(
            Download_data=leve_erreur,
            Upload_data=lambda full_synchro=False: True,
        )
        resultat = synchro.Synchro_totale()  # ne doit jamais lever
        self.assertFalse(resultat)
        self.assertTrue(any(u"Échec du téléchargement" in m and "panne réseau simulée" in m for m in log.logs))
        self.assertIn(u"Client de synchronisation prêt", log.logs)

    def test_exception_pendant_upload_data_ne_remonte_pas(self):
        def leve_erreur(full_synchro=False):
            raise RuntimeError("erreur FTP simulée")

        synchro, log = _synchro(
            Download_data=lambda full_synchro=False: True,
            Upload_data=leve_erreur,
        )
        resultat = synchro.Synchro_totale()  # ne doit jamais lever
        self.assertFalse(resultat)
        self.assertTrue(any(u"Échec de l'envoi des données" in m and "erreur FTP simulée" in m for m in log.logs))
        self.assertIn(u"Client de synchronisation prêt", log.logs)


class ServeurEffectuerCycleTests(unittest.TestCase):
    def _serveur_pret_a_synchroniser(self, parent):
        serveur = CTRL_Portail_serveur.Serveur(parent)
        serveur.start_synchro = True
        serveur.synchro_en_cours = False
        return serveur

    def test_synchro_en_cours_remis_a_false_apres_succes(self):
        parent = FauxLog()
        serveur = self._serveur_pret_a_synchroniser(parent)
        with mock.patch.object(CTRL_Portail_serveur.UTILS_Portail_synchro, "Synchro") as FauxSynchroClasse:
            FauxSynchroClasse.return_value.Synchro_totale.return_value = True
            serveur.EffectuerCycle()
        self.assertFalse(serveur.synchro_en_cours)
        self.assertEqual(parent.images[-1], "on")
        self.assertEqual(parent.nbre_maj_bouton, 1)

    def test_synchro_en_cours_remis_a_false_meme_apres_exception(self):
        """ Le coeur du défaut confirmé : même si Synchro_totale() lève
        (cas extrême, en plus de la protection ajoutée dans
        Synchro_totale elle-même), synchro_en_cours doit redevenir False
        -- sinon plus aucune synchro n'est jamais possible. """
        parent = FauxLog()
        serveur = self._serveur_pret_a_synchroniser(parent)
        with mock.patch.object(CTRL_Portail_serveur.UTILS_Portail_synchro, "Synchro") as FauxSynchroClasse:
            FauxSynchroClasse.return_value.Synchro_totale.side_effect = RuntimeError("crash simulé")
            with self.assertRaises(RuntimeError):
                serveur.EffectuerCycle()
        self.assertFalse(serveur.synchro_en_cours)
        self.assertEqual(parent.images[-1], "on")
        self.assertEqual(parent.nbre_maj_bouton, 1)

    def test_run_journalise_et_ne_meurt_pas_sur_exception(self):
        """ Le run() réel (pas EffectuerCycle() directement) capture
        l'exception, la journalise, et ne la laisse jamais tuer le
        thread. On force une seule itération en mettant keepGoing à
        False après le premier passage. """
        parent = FauxLog()
        serveur = self._serveur_pret_a_synchroniser(parent)
        serveur.keepGoing = True
        serveur.active = True

        appels = {"n": 0}
        original_sleep = CTRL_Portail_serveur.time.sleep

        def faux_sleep(secondes):
            appels["n"] += 1
            serveur.keepGoing = False  # une seule itération de la boucle

        with mock.patch.object(CTRL_Portail_serveur.UTILS_Portail_synchro, "Synchro") as FauxSynchroClasse, \
             mock.patch.object(CTRL_Portail_serveur.time, "sleep", side_effect=faux_sleep):
            FauxSynchroClasse.return_value.Synchro_totale.side_effect = RuntimeError("crash simulé")
            serveur.run()  # ne doit pas lever

        self.assertFalse(serveur.synchro_en_cours)
        self.assertTrue(any("crash simulé" in m for m in parent.logs))

    def test_peut_relancer_une_synchro_apres_un_echec(self):
        parent = FauxLog()
        serveur = self._serveur_pret_a_synchroniser(parent)

        with mock.patch.object(CTRL_Portail_serveur.UTILS_Portail_synchro, "Synchro") as FauxSynchroClasse:
            FauxSynchroClasse.return_value.Synchro_totale.side_effect = RuntimeError("premier échec")
            with self.assertRaises(RuntimeError):
                serveur.EffectuerCycle()
        self.assertFalse(serveur.synchro_en_cours)

        # Un nouveau déclenchement (ex. bouton "Synchroniser maintenant")
        # doit réellement pouvoir relancer une synchro après l'échec.
        serveur.Start_synchro()
        self.assertTrue(serveur.start_synchro)
        with mock.patch.object(CTRL_Portail_serveur.UTILS_Portail_synchro, "Synchro") as FauxSynchroClasse2:
            FauxSynchroClasse2.return_value.Synchro_totale.return_value = True
            serveur.EffectuerCycle()
        FauxSynchroClasse2.return_value.Synchro_totale.assert_called_once()
        self.assertFalse(serveur.synchro_en_cours)

    def test_impossible_de_lancer_deux_synchros_simultanement(self):
        parent = FauxLog()
        serveur = CTRL_Portail_serveur.Serveur(parent)
        serveur.synchro_en_cours = True
        serveur.start_synchro = False

        serveur.Start_synchro()  # bouton "Synchroniser maintenant"

        self.assertFalse(serveur.start_synchro, "une synchro déjà en cours ne doit pas en déclencher une seconde")


class VersionEnvoyeeAConnecthysTests(unittest.TestCase):
    """ Update_application() construit son URL avec
    int(FonctionsPerso.GetVersionLogiciel().replace(".", "")) -- le
    protocole Connecthys exige un entier (voir l'audit ayant motivé
    Identite.py, séparant la version publique Noethys SL de la version de
    compatibilité interne). Ce test vérifie explicitement que
    l'introduction de l'identité publique n'a pas fait dériver la valeur
    réellement envoyée au serveur : elle doit rester celle de
    GetVersionLogiciel(), jamais Identite.PRODUCT_VERSION. """

    def test_update_application_envoie_la_version_interne_numerique(self):
        import FonctionsPerso
        import Identite

        version_interne = FonctionsPerso.GetVersionLogiciel()
        # Garde-fou : si Versions.txt venait à contenir un suffixe non
        # numérique, ce test doit échouer ici plutôt que de masquer un
        # ValueError plus loin dans Update_application().
        self.assertRegex(version_interne, r"^\d+(\.\d+)*$")
        self.assertNotEqual(version_interne, Identite.PRODUCT_VERSION)

        log = FauxLog()
        synchro = UTILS_Portail_synchro.Synchro(
            dict_parametres={
                "accept_all_cert": False,
                "client_rechercher_updates": False,
                "serveur_type": 0,
                "url_connecthys": "https://connecthys.example.org/",
                "secret_key": "abc123",
            },
            log=log,
        )

        urls_captees = []

        class FauxReponse:
            def read(self):
                return b'{"resultat": false}'

        def faux_urlopen(req):
            urls_captees.append(req.get_full_url())
            return FauxReponse()

        with mock.patch.object(UTILS_Portail_synchro, "urlopen", faux_urlopen):
            resultat = synchro.Update_application()

        self.assertTrue(resultat)
        self.assertEqual(len(urls_captees), 1)
        url_envoyee = urls_captees[0]

        version_envoyee = int(version_interne.replace(".", ""))
        self.assertIn("/update/", url_envoyee)
        self.assertIn("/%d/" % version_envoyee, url_envoyee)

        # Preuve négative explicite : la version publique (Noethys SL,
        # forme "0.1.0-rc.1" ou son affichage "0.1.0 RC1") ne doit jamais
        # apparaître, sous aucune forme, dans l'URL envoyée au serveur.
        self.assertNotIn("0.1.0", url_envoyee)
        self.assertNotIn("rc", url_envoyee.lower())


if __name__ == "__main__":
    unittest.main()
