# -*- coding: utf-8 -*-
"""Confirmations Connecthys envoyées à plusieurs adresses : sémantique
uniforme (SMTP comme Mailjet) et aucun renvoi aux adresses déjà acceptées.

Compatibilité avec le Connecthys d'origine : aucun nouvel état de demande,
aucune réponse modifiée, aucun paramètre de la catégorie `portail` ;
l'information locale tient dans une catégorie dédiée de `parametres`, que
la synchronisation ne lit pas. Base SQLite fictive, aucun email envoyé.
"""
import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402,F401
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Utils import UTILS_Emails_acceptes as Acceptes  # noqa: E402

try:
    from Utils import UTILS_Envoi_email  # noqa: E402
    import Dlg  # noqa: E402
except Exception:  # pragma: no cover - wx indisponible
    UTILS_Envoi_email = None


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()  # la fixture crée déjà la table native `parametres`
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def lignes(self, categorie):
        self.base.db.ExecuterReq("SELECT nom, parametre FROM parametres WHERE categorie='%s';" % categorie)
        return self.base.db.ResultatReq()


class MemoireAdressesTests(_Base):
    def test_lecture_enregistrement_effacement(self):
        cle = Acceptes.CleDemande(42, "recu")
        self.assertEqual(cle, "portail_action_42_recu")
        self.assertEqual(Acceptes.Lire(cle), set())
        Acceptes.Enregistrer(cle, ["A@Example.test ", "b@example.test"])
        Acceptes.Enregistrer(cle, ["a@example.test", "b@example.test"])  # une seule ligne par clé
        self.assertEqual(Acceptes.Lire(cle), {"a@example.test", "b@example.test"})
        Acceptes.Enregistrer(cle, Acceptes.Suivi(["a@example.test"], ["c@example.test"], "e1", False))
        suivi = Acceptes.LireSuivi(cle)
        self.assertEqual((suivi.acceptees, suivi.incertaines, suivi.empreinte, suivi.complet),
                         ({"a@example.test"}, {"c@example.test"}, "e1", False))
        Acceptes.Enregistrer(cle, ["a@example.test", "b@example.test"])
        self.assertEqual(Acceptes.Lire(cle), {"a@example.test", "b@example.test"})
        self.assertEqual(len(self.lignes(Acceptes.CATEGORIE)), 1)
        Acceptes.Effacer(cle)
        self.assertEqual(Acceptes.Lire(cle), set())

    def test_cle_invalide_refusee_avant_toute_requete(self):
        for cle in ("x'; DROP TABLE parametres; --", "", None, "A" * 3):
            with self.subTest(cle=cle), self.assertRaises(ValueError):
                Acceptes.Lire(cle)
        with self.assertRaises(ValueError):
            Acceptes.CleDemande(42, "re'cu")

    def test_valeur_corrompue_jamais_lue_comme_vide(self):
        self.base.inserer("parametres", ["categorie", "nom", "parametre"],
                          [(Acceptes.CATEGORIE, "portail_action_1_recu", "{pas du json")])
        with self.assertRaises(Acceptes.SuiviIllisible):
            Acceptes.Lire("portail_action_1_recu")

    def test_categorie_jamais_synchronisee_avec_connecthys(self):
        self.assertNotEqual(Acceptes.CATEGORIE, "portail")
        synchro = (RACINE / "noethys" / "Utils" / "UTILS_Portail_synchro.py").read_text(encoding="utf-8")
        self.assertNotIn(Acceptes.CATEGORIE, synchro)
        self.assertNotIn("UTILS_Emails_acceptes", synchro)


class _FauxMessage(object):
    def __init__(self, adresse):
        self.destinataires = [adresse]


class _FauxMailer(object):
    """Double de DLG_Mailer.Dialog : accepte les adresses de `acceptees`."""
    acceptees = set()
    instances = []

    def __init__(self, parent, categorie="", afficher_confirmation_envoi=True):
        self.adresses = []
        self.listeSucces = []
        self.envoi_complet = False
        _FauxMailer.instances.append(self)

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
        self.listeSucces = [_FauxMessage(a) for a in self.adresses if a in _FauxMailer.acceptees]
        self.envoi_complet = len(self.listeSucces) == len(self.adresses)

    def Destroy(self):
        pass


class _Journal(object):
    def __init__(self):
        self.lignes = []

    def EcritLog(self, texte):
        self.lignes.append(texte)


@unittest.skipIf(UTILS_Envoi_email is None, "UTILS_Envoi_email non importable")
class ConfirmationPartielleTests(_Base):
    ADRESSES = ["a@example.test", "b@example.test"]

    def setUp(self):
        _Base.setUp(self)
        _FauxMailer.instances = []
        self.journal = _Journal()
        faux_module = mock.Mock(Dialog=_FauxMailer)
        for patch in (mock.patch.dict(sys.modules, {"Dlg.DLG_Mailer": faux_module}),
                      mock.patch.object(Dlg, "DLG_Mailer", faux_module, create=True),
                      mock.patch.object(UTILS_Envoi_email, "GetAdresseFamille", return_value=list(self.ADRESSES))):
            patch.start()
            self.addCleanup(patch.stop)

    def envoyer(self, acceptees, visible=False, cle="portail_action_7_reponse", pdf=None):
        _FauxMailer.acceptees = set(acceptees)
        creation = pdf or (lambda nomDoc="", afficherDoc=True: {"{X}": "y"})
        return UTILS_Envoi_email.EnvoiEmailFamille(parent=None, IDfamille=3, nomDoc=False, categorie="portail",
                                                   visible=visible, log=self.journal, CreationPDF=creation,
                                                   cle_suivi=cle)

    def test_envoi_partiel_non_valide_puis_renvoi_aux_seules_adresses_restantes(self):
        self.assertFalse(self.envoyer({"a@example.test"}))
        self.assertEqual(Acceptes.Lire("portail_action_7_reponse"), {"a@example.test"})
        # Nouvel essai : seule b reçoit le message ; la confirmation devient
        # complète, son suivi est conservé jusqu'à l'enregistrement de la demande.
        self.assertTrue(self.envoyer({"b@example.test"}))
        self.assertEqual(_FauxMailer.instances[-1].adresses, ["b@example.test"])
        self.assertTrue(Acceptes.LireSuivi("portail_action_7_reponse").complet)
        self.assertTrue(any("non encore acceptées (1 sur 2)" in l for l in self.journal.lignes))

    def test_toutes_deja_acceptees_aucun_renvoi(self):
        Acceptes.Enregistrer("portail_action_7_reponse", self.ADRESSES)
        pdf = mock.Mock(return_value={"{X}": "y"})
        self.assertTrue(self.envoyer(set(), pdf=pdf))
        self.assertEqual(_FauxMailer.instances, [])  # aucun message préparé ni envoyé
        pdf.assert_not_called()
        self.assertTrue(Acceptes.LireSuivi("portail_action_7_reponse").complet)

    def test_aucun_succes_rien_memorise(self):
        self.assertFalse(self.envoyer(set()))
        self.assertEqual(self.lignes(Acceptes.CATEGORIE), [])

    def test_envoi_complet_du_premier_coup_memorise_comme_complet(self):
        self.assertTrue(self.envoyer(set(self.ADRESSES)))
        suivi = Acceptes.LireSuivi("portail_action_7_reponse")
        self.assertEqual((suivi.complet, suivi.acceptees), (True, set(self.ADRESSES)))

    def test_editeur_affiche_sans_filtrage_ni_memoire(self):
        Acceptes.Enregistrer("portail_action_7_reponse", ["a@example.test"])
        self.assertFalse(self.envoyer({"a@example.test"}, visible=True))
        self.assertEqual(_FauxMailer.instances[-1].adresses, self.ADRESSES)
        self.assertEqual(Acceptes.Lire("portail_action_7_reponse"), {"a@example.test"})

    def test_sans_cle_partiel_refuse_comme_avant_pour_tous_les_moteurs(self):
        self.assertFalse(self.envoyer({"a@example.test"}, cle=None))
        self.assertEqual(self.lignes(Acceptes.CATEGORIE), [])

    def test_dialogue_sans_indicateur_meme_critere_complet(self):
        class SansIndicateur(_FauxMailer):
            def OnBoutonEnvoyer(self, event):
                self.listeSucces = [_FauxMessage(a) for a in self.adresses if a in _FauxMailer.acceptees]
                del self.envoi_complet
        faux_module = mock.Mock(Dialog=SansIndicateur)
        with mock.patch.dict(sys.modules, {"Dlg.DLG_Mailer": faux_module}), \
                mock.patch.object(Dlg, "DLG_Mailer", faux_module, create=True):
            self.assertFalse(self.envoyer({"a@example.test"}, cle=None))
            self.assertTrue(self.envoyer(set(self.ADRESSES), cle=None))
            self.assertFalse(self.envoyer(set(), cle=None))

    def test_cle_absente_pour_une_demande_sans_identifiant(self):
        self.assertIsNone(UTILS_Envoi_email.CleSuiviDemande(None, "reponse"))
        self.assertEqual(UTILS_Envoi_email.CleSuiviDemande(12, "facture"), "portail_action_12_facture")


class CompatibiliteConnecthysTests(unittest.TestCase):
    """Le traitement des demandes garde ses états, réponses et contrats d'origine."""

    @classmethod
    def setUpClass(cls):
        cls.source = (RACINE / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")

    def test_appels_suivis_par_demande_et_document(self):
        for document in ("reponse", "recu", "facture"):
            self.assertIn('CleSuiviDemande(getattr(self.track, "IDaction", None), "%s")' % document, self.source)

    def test_etats_et_reponses_inchanges(self):
        self.assertIn('self.SetEtat(etat="valide", traitement_date=datetime.date.today())', self.source)
        for reponse in ("Facture envoyée par Email.", "Reçu de règlement envoyé par Email."):
            self.assertIn(reponse, self.source)
        self.assertIn("if resultat == True :\n            self.track.email_date = datetime.date.today()", self.source)
        etats = set(__import__("re").findall(r'SetEtat\(etat="(\w+)"', self.source))
        self.assertTrue(etats <= {"valide", "attente", "refus"}, etats)

    def test_signature_historique_de_envoi_email_famille_conservee(self):
        arbre = ast.parse((RACINE / "noethys" / "Utils" / "UTILS_Envoi_email.py").read_text(encoding="utf-8"))
        fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "EnvoiEmailFamille")
        noms = [a.arg for a in fonction.args.args]
        self.assertEqual(noms[:9], ["parent", "IDfamille", "nomDoc", "categorie", "listeAdresses", "visible", "log",
                                    "CreationPDF", "IDmodele"])
        self.assertEqual(noms[9:], ["cle_suivi", "empreinte"])


if __name__ == "__main__":
    unittest.main()
