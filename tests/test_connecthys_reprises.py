# -*- coding: utf-8 -*-
"""Confirmations Connecthys : reprises après interruption, pannes locales,
acceptation incertaine et traitements simultanés.

Transporteur factice (aucun email réel, adresses fictives), base SQLite
fictive. Les tests de la classe ReprisesTests n'utilisent que l'API déjà
présente avant ce correctif (EnvoiEmailFamille, Enregistrer, Lire) : ils
peuvent être rejoués sur une copie du code antérieur (contre-épreuve).
"""
import re
import sqlite3
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402,F401
import GestionDB  # noqa: E402
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_Emails_acceptes as Suivis  # noqa: E402

try:
    from Utils import UTILS_Envoi_email  # noqa: E402
    import Dlg  # noqa: E402
except Exception:  # pragma: no cover - wx indisponible
    UTILS_Envoi_email = None

A, B, C = "a@example.test", "b@example.test", "c@example.test"
CLE = "portail_action_7_reponse"


class _Message(object):
    def __init__(self, adresse):
        self.destinataires = [adresse]


class _Transporteur(object):
    """Double de DLG_Mailer.Dialog. `scenario(adresses)` renvoie
    (acceptées, incertaines) ou lève une exception (interruption)."""
    scenario = None
    instances = []
    pendant_envoi = None

    def __init__(self, parent, categorie="", afficher_confirmation_envoi=True):
        self.adresses = []
        self.listeSucces = []
        self.listeIncertains = []
        _Transporteur.instances.append(self)

    def SetDonnees(self, donnees, modificationAutorisee=True):
        self.adresses = [d["adresse"] for d in donnees]

    def SetPiecesJointes(self, pieces):
        pass

    def ChargerModeleDefaut(self):
        pass

    def ChargerModele(self, IDmodele):
        pass

    def ShowModal(self):
        self.OnBoutonEnvoyer(None)

    def OnBoutonEnvoyer(self, event):
        if _Transporteur.pendant_envoi:
            _Transporteur.pendant_envoi()
        acceptees, incertaines = _Transporteur.scenario(self.adresses, self)
        self.listeSucces = [_Message(a) for a in self.adresses if a in acceptees]
        self.listeIncertains = [_Message(a) for a in self.adresses if a in incertaines]
        self.envoi_complet = len(self.listeSucces) == len(self.adresses)

    def Destroy(self):
        pass


class _Journal(object):
    def __init__(self):
        self.lignes = []

    def EcritLog(self, texte):
        self.lignes.append(texte)


class _CurseurEnPanne(object):
    def __init__(self, curseur, test):
        self._curseur = curseur
        self._test = test

    def execute(self, req, *args):
        if self._test.panne and re.search(self._test.panne, req, re.I):
            raise sqlite3.OperationalError("panne injectée")
        return self._curseur.execute(req, *args)

    def __getattr__(self, nom):
        return getattr(self._curseur, nom)


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        self.base.db.CreationTable("portail_actions", dicoDB=Tables.DB_DATA)
        self.base.inserer("portail_actions", ["IDaction", "IDfamille", "etat"], [(7, 3, "attente"), (8, 3, "attente")])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.panne = None
        classe = GestionDB.DB
        test = self

        def instrumentee(*args, **kwargs):
            db = classe(*args, **kwargs)
            db.cursor = _CurseurEnPanne(db.cursor, test)
            return db
        p = mock.patch.object(GestionDB, "DB", side_effect=instrumentee)
        p.start()
        self.addCleanup(p.stop)

    def lignes(self, req):
        self.base.db.ExecuterReq(req)
        return self.base.db.ResultatReq()

    def suivi_brut(self, cle=CLE):
        return self.lignes("SELECT parametre FROM parametres WHERE categorie='%s' AND nom='%s'" % (Suivis.CATEGORIE, cle))


@unittest.skipIf(UTILS_Envoi_email is None, "UTILS_Envoi_email non importable")
class _BaseEnvoi(_Base):
    ADRESSES = [A, B]

    def setUp(self):
        _Base.setUp(self)
        _Transporteur.instances = []
        _Transporteur.pendant_envoi = None
        self.journal = _Journal()
        faux = mock.Mock(Dialog=_Transporteur)
        for p in (mock.patch.dict(sys.modules, {"Dlg.DLG_Mailer": faux}),
                  mock.patch.object(Dlg, "DLG_Mailer", faux, create=True),
                  mock.patch.object(UTILS_Envoi_email, "GetAdresseFamille", side_effect=lambda ID: list(self.ADRESSES))):
            p.start()
            self.addCleanup(p.stop)

    def envoyer(self, acceptees=(), incertaines=(), interruption=None, **kwargs):
        def scenario(adresses, transporteur):
            transporteur.listeSucces = [_Message(a) for a in adresses if a in acceptees]
            if interruption is not None:
                raise interruption
            return set(acceptees), set(incertaines)
        _Transporteur.scenario = staticmethod(scenario)
        return UTILS_Envoi_email.EnvoiEmailFamille(parent=None, IDfamille=3, nomDoc=False, categorie="portail",
                                                   visible=False, log=self.journal,
                                                   CreationPDF=lambda nomDoc="", afficherDoc=True: {"{X}": "y"},
                                                   cle_suivi=CLE, **kwargs)

    def destinataires(self):
        return [a for t in _Transporteur.instances for a in t.adresses]


class ReprisesTests(_BaseEnvoi):
    """API commune à l'ancien et au nouveau code (contre-épreuve)."""

    def test_panne_entre_suppression_et_reinsertion_du_suivi(self):
        Suivis.Enregistrer(CLE, [A])
        avant = self.suivi_brut()
        self.panne = r"INSERT\s+INTO\s+parametres"
        try:
            Suivis.Enregistrer(CLE, [A, B])
        except Exception:
            pass
        self.panne = None
        self.assertEqual(self.suivi_brut(), avant)
        self.assertEqual(Suivis.Lire(CLE), {A})

    def test_toutes_acceptees_puis_demande_non_enregistree_aucun_renvoi(self):
        self.assertTrue(self.envoyer(acceptees={A, B}))
        # La demande n'a pas été enregistrée (arrêt, erreur) : nouveau traitement.
        self.assertTrue(self.envoyer(acceptees={A, B}))
        self.assertEqual(self.destinataires(), [A, B])

    def test_reponse_perdue_apres_transmission_pas_de_relance_aveugle(self):
        self.assertFalse(self.envoyer(acceptees={A}, incertaines={B}))
        self.assertFalse(self.envoyer(acceptees={A, B}))
        self.assertEqual(self.destinataires(), [A, B])  # B jamais renvoyé automatiquement

    def test_interruption_apres_une_acceptation_partielle(self):
        try:
            self.envoyer(acceptees={A}, interruption=RuntimeError("arrêt pendant l'envoi"))
        except RuntimeError:
            pass
        try:
            self.envoyer(acceptees={A, B})
        except RuntimeError:
            pass
        self.assertEqual(self.destinataires().count(A), 1)  # A jamais renvoyé

    def test_suivi_illisible_aucun_envoi(self):
        self.base.inserer("parametres", ["categorie", "nom", "parametre"], [(Suivis.CATEGORIE, CLE, "{corrompu")])
        try:
            resultat = self.envoyer(acceptees={A, B})
        except Exception:
            resultat = None
        self.assertNotEqual(resultat, True)
        self.assertEqual(self.destinataires(), [])
        self.assertEqual(self.suivi_brut(), [("{corrompu",)])

    def test_deux_tentatives_concurrentes(self):
        resultats = []

        def seconde_tentative():
            fil = threading.Thread(target=lambda: resultats.append(self.envoyer(acceptees={A, B})))
            fil.start()
            fil.join(20)
        _Transporteur.pendant_envoi = staticmethod(lambda: (setattr(_Transporteur, "pendant_envoi", None),
                                                            seconde_tentative()))
        self.envoyer(acceptees={A, B})
        self.assertEqual(resultats, [False])
        self.assertEqual(self.destinataires(), [A, B])  # un seul envoi

    def test_reprise_apres_redemarrage(self):
        self.assertFalse(self.envoyer(acceptees={A}))
        self.redirection.__exit__(None, None, None)  # « redémarrage » : nouvelles connexions au même fichier
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.assertTrue(self.envoyer(acceptees={B}))
        self.assertEqual(self.destinataires(), [A, B, B])


class SuiviEtFinalisationTests(_BaseEnvoi):
    def test_enregistrer_echec_sql_leve_et_conserve(self):
        Suivis.Enregistrer(CLE, [A])
        self.panne = r"INSERT\s+INTO\s+parametres"
        with self.assertRaises(sqlite3.OperationalError):
            Suivis.Enregistrer(CLE, [A, B])
        self.panne = None
        self.assertEqual(Suivis.Lire(CLE), {A})

    def test_document_modifie_nouvel_envoi_legitime(self):
        self.assertFalse(self.envoyer(acceptees={A}, empreinte="v1"))
        self.assertTrue(self.envoyer(acceptees={B}, empreinte="v1"))
        self.assertEqual(self.destinataires(), [A, B, B])
        self.assertTrue(self.envoyer(acceptees={A, B}, empreinte="v2"))  # réédition volontaire
        self.assertEqual(self.destinataires(), [A, B, B, A, B])
        self.assertEqual(Suivis.LireSuivi(CLE).empreinte, "v2")

    def test_echec_d_ecriture_du_suivi_diagnostic_sans_faux_succes(self):
        self.panne = r"INSERT\s+INTO\s+parametres"
        self.assertFalse(self.envoyer(acceptees={A}))
        self.panne = None
        self.assertTrue(any(u"Ne relancez pas" in l and A in l for l in self.journal.lignes))

    def test_incertitude_journalisee_et_conservee(self):
        self.assertFalse(self.envoyer(acceptees={A}, incertaines={B}))
        suivi = Suivis.LireSuivi(CLE)
        self.assertEqual((suivi.acceptees, suivi.incertaines, suivi.complet), ({A}, {B}, False))
        self.assertFalse(self.envoyer(acceptees={A, B}))
        self.assertTrue(any(u"Aucune relance automatique" in l for l in self.journal.lignes))

    def test_interruption_marque_les_adresses_non_confirmees_incertaines(self):
        self.assertFalse(self.envoyer(acceptees={A}, interruption=RuntimeError("arrêt")))
        suivi = Suivis.LireSuivi(CLE)
        self.assertEqual((suivi.acceptees, suivi.incertaines), ({A}, {B}))

    def test_reservation_refuse_un_second_traitement(self):
        with Suivis.Reserver(CLE):
            self.assertFalse(self.envoyer(acceptees={A, B}))
        self.assertEqual(self.destinataires(), [])
        self.assertTrue(self.envoyer(acceptees={A, B}))  # réservation libérée

    def test_finalisation_atomique_avec_la_demande(self):
        self.assertTrue(self.envoyer(acceptees={A, B}))  # suivi complet (action 7, réponse)
        Suivis.Enregistrer("portail_action_7_recu", Suivis.Suivi([A], [], None, False))  # partiel
        Suivis.Enregistrer("portail_action_8_reponse", Suivis.Suivi([A, B], [], None, True))  # autre demande
        from Dlg import DLG_Saisie_portail_demande as Demande
        hote = SimpleNamespace(track=SimpleNamespace(IDaction=7, email_date=None))
        # Panne de l'écriture de la demande : rien n'est effacé.
        self.panne = r"UPDATE\s+portail_actions"
        with mock.patch.object(Demande.wx, "MessageDialog") as message:
            self.assertFalse(Demande.Dialog.EnregistrerDemande(hote, "validation", u"Réponse", None))
        message.return_value.ShowModal.assert_called_once_with()
        self.panne = None
        self.assertTrue(self.suivi_brut())
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"), [("attente",)])
        # Enregistrement réussi : seuls les suivis complets de cette demande disparaissent.
        self.assertTrue(Demande.Dialog.EnregistrerDemande(hote, "validation", u"Réponse", None))
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"), [("validation",)])
        self.assertEqual(self.suivi_brut(), [])
        self.assertEqual(Suivis.Lire("portail_action_7_recu"), {A})
        self.assertTrue(Suivis.LireSuivi("portail_action_8_reponse").complet)

    def test_demande_en_attente_conserve_le_suivi(self):
        self.assertTrue(self.envoyer(acceptees={A, B}))
        from Dlg import DLG_Saisie_portail_demande as Demande
        hote = SimpleNamespace(track=SimpleNamespace(IDaction=7, email_date=None))
        self.assertTrue(Demande.Dialog.EnregistrerDemande(hote, "attente", None, None))
        self.assertTrue(Suivis.LireSuivi(CLE).complet)


class CompatibiliteConnecthysTests(unittest.TestCase):
    def test_categorie_privee_et_etats_inchanges(self):
        synchro = (RACINE / "noethys" / "Utils" / "UTILS_Portail_synchro.py").read_text(encoding="utf-8")
        self.assertNotIn(Suivis.CATEGORIE, synchro)
        source = (RACINE / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")
        self.assertIn('UPDATE portail_actions SET etat=?, reponse=?, traitement_date=?, email_date=? WHERE IDaction=?',
                      source)
        etats = set(re.findall(r'SetEtat\(etat="(\w+)"', source))
        self.assertTrue(etats <= {"valide", "attente", "refus"}, etats)


if __name__ == "__main__":
    unittest.main()
