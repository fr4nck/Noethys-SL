# -*- coding: utf-8 -*-
"""MAIL-FAM-01 -- familles configurées pour l'envoi par email dont le
destinataire mémorisé ne peut plus être résolu.

Les méthodes réelles (DLG_Factures_email.OnBoutonOk, DLG_Rappels_email.
OnBoutonOk, DLG_Saisie_reglement / DLG_Saisie_depot) sont exécutées avec des
doublures (base, impression, dialogues, Mailer) : aucun email n'est envoyé.

Avant correction (commit f8aad6a) : la famille dont l'individu mémorisé
n'existe plus disparaissait du lot sans figurer dans l'avertissement, et les
rappels ignoraient toujours les adresses libres. Ces tests vérifient
désormais qu'aucune famille prévue ne disparaît silencieusement.
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

try:
    import wx  # noqa: F401
    from Dlg import DLG_Factures_email, DLG_Rappels_email
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover
    IMPORT_ERREUR = err


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))


# Individus de la base factice : (IDindividu, mail, travail_mail)
INDIVIDUS = [
    (1, "parent.a@example.org", None),
    (2, "parent.b@example.org", ""),
    (3, "ancien.membre@example.org", None),
]
# Rattachements factices : (IDindividu, IDfamille)
RATTACHEMENTS = [(1, 10), (2, 20)]   # l'individu 3 n'est plus rattaché à la famille 30


class FausseDB(object):
    def __init__(self, *a, **k):
        self._dernier = []

    def ExecuterReq(self, req, *a, **k):
        if "rattachements" in req and "mail" not in req:
            self._dernier = list(RATTACHEMENTS)
        else:
            self._dernier = list(INDIVIDUS)

    def ResultatReq(self):
        return self._dernier

    def Close(self):
        pass


class Capture(object):
    """Mémorise les dialogues et le Mailer ouverts par la méthode testée."""

    def __init__(self, reponse_avertissement=0):
        self.avertissements = []
        self.messages = []
        self.donnees_mailer = None
        self.reponse_avertissement = reponse_avertissement
        capture = self

        class Messagebox(object):
            def __init__(self, *a, **k):
                capture.avertissements.append(k)

            def ShowModal(self):
                return capture.reponse_avertissement

            def Destroy(self):
                pass

        class MessageDialog(object):
            def __init__(self, parent, message, *a, **k):
                capture.messages.append(message)

            def ShowModal(self):
                return wx.ID_YES

            def Destroy(self):
                pass

        class Mailer(object):
            def __init__(self, *a, **k):
                pass

            def SetDonnees(self, donnees, modificationAutorisee=True):
                capture.donnees_mailer = donnees

            def ChargerModeleDefaut(self):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        self.Messagebox = Messagebox
        self.MessageDialog = MessageDialog
        self.Mailer = Mailer

    def adresses_envoyees(self):
        return [d["adresse"] for d in (self.donnees_mailer or [])]

    def familles_signalees(self):
        texte = u"".join(k.get("detail", u"") for k in self.avertissements)
        return texte


def piste(IDfamille, nom, email_factures, ID=None, email=True):
    return types.SimpleNamespace(
        IDfamille=IDfamille, nomsTitulaires=nom, email=email,
        email_factures=email_factures, IDfacture=ID or IDfamille, IDrappel=ID or IDfamille,
        etat=None, numero=str(ID or IDfamille))


class _BaseLot(unittest.TestCase):
    module = None
    attr_liste = None


class _ScenariosCommuns(object):
    def test_famille_avec_destinataire_valide_est_envoyee(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertEqual(c.avertissements, [])

    def test_adresse_libre_est_envoyee(self):
        c = self.executer([piste(10, u"Famille A", ";;libre@example.org")])
        self.assertEqual(c.adresses_envoyees(), ["libre@example.org"])

    def test_individu_sans_adresse_est_signale(self):
        """Comportement historique conservé : individu présent mais adresse
        vide -> la famille figure dans l'avertissement."""
        c = self.executer([piste(10, u"Famille A", "1;perso;"),
                           piste(20, u"Famille B", "2;travail;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertIn(u"Famille B", c.familles_signalees())


class FacturesDestinataireIntrouvableTests(_BaseLot, _ScenariosCommuns):
    module = DLG_Factures_email if IMPORT_ERREUR is None else None
    attr_liste = "ctrl_liste_factures"

    def executer(self, pistes, reponse_avertissement=0):
        return _executer_avec_classe(self, pistes, reponse_avertissement, "UTILS_Facturation", "Facturation")

    def test_individu_supprime_famille_signalee(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;"),
                           piste(40, u"Famille Fantôme", "99;perso;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertIn(u"Famille Fantôme (destinataire configuré introuvable)", c.familles_signalees())

    def test_individu_detache_famille_signalee(self):
        c = self.executer([piste(30, u"Famille C", "3;perso;")], reponse_avertissement=0)
        self.assertEqual(c.adresses_envoyees(), [])
        self.assertIn(u"Famille C (destinataire configuré n'est plus rattaché à la famille)", c.familles_signalees())

    def test_une_adresse_resolue_et_une_introuvable(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;##99;travail;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertIn(u"Famille A (destinataire configuré introuvable)", c.familles_signalees())

    def test_annuler_sur_avertissement_n_ouvre_pas_le_mailer(self):
        c = self.executer([piste(40, u"Famille Fantôme", "99;perso;")], reponse_avertissement=2)
        self.assertIsNone(c.donnees_mailer)


class RappelsDestinataireIntrouvableTests(_BaseLot, _ScenariosCommuns):
    module = DLG_Rappels_email if IMPORT_ERREUR is None else None
    attr_liste = "ctrl_liste_rappels"


    def executer(self, pistes, reponse_avertissement=0):
        return _executer_avec_classe(self, pistes, reponse_avertissement, "UTILS_Rappels", "Facturation")

    def test_individu_supprime_famille_signalee(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;"),
                           piste(40, u"Famille Fantôme", "99;perso;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertIn(u"Famille Fantôme (destinataire configuré introuvable)", c.familles_signalees())

    def test_individu_detache_famille_signalee(self):
        c = self.executer([piste(30, u"Famille C", "3;perso;")], reponse_avertissement=0)
        self.assertEqual(c.adresses_envoyees(), [])
        self.assertIn(u"Famille C (destinataire configuré n'est plus rattaché à la famille)", c.familles_signalees())

    def test_une_adresse_resolue_et_une_introuvable(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;##99;travail;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertIn(u"Famille A (destinataire configuré introuvable)", c.familles_signalees())

    def test_annuler_sur_avertissement_n_ouvre_pas_le_mailer(self):
        c = self.executer([piste(40, u"Famille Fantôme", "99;perso;")], reponse_avertissement=2)
        self.assertIsNone(c.donnees_mailer)


def _executer_avec_classe(test, pistes, reponse_avertissement, nom_module, nom_classe):
    capture = Capture(reponse_avertissement)
    pieces = dict((p.IDfacture, "/tmp/doc_%d.pdf" % p.IDfacture) for p in pistes)
    champs = dict((p.IDfacture, {}) for p in pistes)
    moteur = mock.MagicMock()
    moteur.Impression.return_value = (champs, pieces)
    options = mock.MagicMock()
    options.GetOptions.return_value = {"repertoire_copie": None, "repertoire": None}
    liste = mock.MagicMock()
    liste.GetTracksCoches.return_value = pistes
    self_ = types.SimpleNamespace(ctrl_options=options)
    setattr(self_, test.attr_liste, liste)
    module = test.module
    from Dlg import DLG_Mailer
    module_impression = getattr(module, nom_module)
    with mock.patch.object(module.GestionDB, "DB", FausseDB), \
            mock.patch.object(module_impression, nom_classe, return_value=moteur), \
            mock.patch.object(module.DLG_Messagebox, "Dialog", capture.Messagebox), \
            mock.patch.object(module.wx, "MessageDialog", capture.MessageDialog), \
            mock.patch.object(DLG_Mailer, "Dialog", capture.Mailer), \
            mock.patch.object(module.os, "remove"):
        module.Dialog.OnBoutonOk(self_, None)
    return capture


class ResoudreAdresseConfigureeTests(unittest.TestCase):
    """Fonction commune aux factures, rappels, reçus et avis de dépôt."""

    def setUp(self):
        from Utils import UTILS_Envoi_email
        self.f = UTILS_Envoi_email.ResoudreAdresseConfiguree
        self.d = {1: {"perso": "a@example.org", "travail": None}, 2: {"perso": " b@example.org ", "travail": ""}}

    def test_membre_resolu(self):
        self.assertEqual(self.f("1;perso;", self.d), ("a@example.org", None))

    def test_espaces_retires(self):
        self.assertEqual(self.f("2;perso;", self.d), ("b@example.org", None))

    def test_adresse_libre(self):
        self.assertEqual(self.f(";;libre@example.org", self.d), ("libre@example.org", None))

    def test_individu_introuvable(self):
        self.assertEqual(self.f("99;perso;", self.d), (None, u"destinataire configuré introuvable"))

    def test_individu_non_rattache(self):
        adresse, motif = self.f("1;perso;", self.d, IDfamille=7, rattachements={(1, 8)})
        self.assertIsNone(adresse)
        self.assertIn(u"rattaché", motif)

    def test_rattachement_non_verifie_si_non_fourni(self):
        """Reçu de règlement : le dictionnaire ne contient déjà que les
        membres de la famille."""
        self.assertEqual(self.f("1;perso;", self.d, IDfamille=7), ("a@example.org", None))

    def test_adresse_vide(self):
        self.assertEqual(self.f("1;travail;", self.d), (None, u"adresse email vide"))
        self.assertEqual(self.f("2;travail;", self.d), (None, u"adresse email vide"))

    def test_configuration_illisible(self):
        for valeur in ("", None, "abc", "x;perso;", "1;perso"):
            with self.subTest(valeur=valeur):
                adresse, motif = self.f(valeur, self.d)
                self.assertIsNone(adresse)
                self.assertTrue(motif)


class RecuEtDepotTests(unittest.TestCase):
    """Reçu de règlement et avis de dépôt utilisent la même résolution : un
    destinataire introuvable n'aboutit plus à une adresse vide."""

    def test_recu_utilise_la_resolution_commune(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_reglement.py").read_text(encoding="utf-8")
        self.assertIn("UTILS_Envoi_email.ResoudreAdresseConfiguree(email_recus, dictAdressesIndividus)", source)
        self.assertNotIn('IDindividu, categorie, adresse = email_recus.split(";")', source)
        self.assertIn(u"Le reçu n'a pas été envoyé : %s.", source)

    def test_depot_utilise_la_resolution_commune(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_depot.py").read_text(encoding="utf-8")
        self.assertIn("ResoudreAdresseConfiguree(track.email_depots, dictAdressesIndividus, track.IDfamille, rattachements)", source)
        self.assertNotIn('IDindividu, categorie, adresse = track.email_depots.split(";")', source)

    def test_selection_avis_depot_bloque_les_adresses_inconnues(self):
        """Contrat existant réutilisé : une ligne cochée avec adresse None
        est refusée par DLG_Selection_avis_depots (pas d'envoi silencieux)."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Selection_avis_depots.py").read_text(encoding="utf-8")
        self.assertIn("if track.adresse == None :", source)


if __name__ == "__main__":
    unittest.main()
