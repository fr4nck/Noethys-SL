# -*- coding: utf-8 -*-
"""MAIL-FAM-01 -- familles configurées pour l'envoi par email dont le
destinataire mémorisé ne peut plus être résolu.

Les méthodes réelles (DLG_Factures_email.OnBoutonOk, DLG_Rappels_email.
OnBoutonOk, DLG_Saisie_reglement / DLG_Saisie_depot) sont exécutées avec des
doublures (base, impression, dialogues, Mailer) : aucun email n'est envoyé.

CARACTÉRISATION (avant correction) : la famille dont l'individu mémorisé
n'existe plus disparaît du lot sans figurer dans l'avertissement.
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

    def test_caracterisation_individu_supprime_famille_disparait_silencieusement(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;"),
                           piste(40, u"Famille Fantôme", "99;perso;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertNotIn(u"Famille Fantôme", c.familles_signalees())


class RappelsDestinataireIntrouvableTests(_BaseLot, _ScenariosCommuns):
    module = DLG_Rappels_email if IMPORT_ERREUR is None else None
    attr_liste = "ctrl_liste_rappels"

    def test_adresse_libre_est_envoyee(self):
        """CARACTÉRISATION : contrairement aux factures, les rappels ignorent
        l'adresse libre (pas de branche else) : la famille est écartée sans
        avertissement."""
        c = self.executer([piste(10, u"Famille A", ";;libre@example.org")])
        self.assertEqual(c.adresses_envoyees(), [])
        self.assertEqual(c.avertissements, [])

    def executer(self, pistes, reponse_avertissement=0):
        return _executer_avec_classe(self, pistes, reponse_avertissement, "UTILS_Rappels", "Facturation")

    def test_caracterisation_individu_supprime_famille_disparait_silencieusement(self):
        c = self.executer([piste(10, u"Famille A", "1;perso;"),
                           piste(40, u"Famille Fantôme", "99;perso;")])
        self.assertEqual(c.adresses_envoyees(), ["parent.a@example.org"])
        self.assertNotIn(u"Famille Fantôme", c.familles_signalees())


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


class RecuEtDepotSourceTests(unittest.TestCase):
    """Reçu de règlement et avis de dépôt : lorsque l'individu mémorisé est
    introuvable, l'adresse retenue est le 3e champ de la configuration, qui
    vaut "" pour un membre de la famille (DLG_Selection_email.GetValeur)."""

    def test_caracterisation_recu_adresse_vide_non_detectee(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_reglement.py").read_text(encoding="utf-8")
        self.assertIn('IDindividu, categorie, adresse = email_recus.split(";")', source)
        self.assertIn("if adresse == None :", source)

    def test_caracterisation_depot_adresse_vide_non_detectee(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_depot.py").read_text(encoding="utf-8")
        self.assertIn('IDindividu, categorie, adresse = track.email_depots.split(";")', source)

    def test_configuration_membre_memorise_une_adresse_vide(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Selection_email.py").read_text(encoding="utf-8")
        self.assertIn('IDindividu, categorie = self.ctrl_membre.GetAdresse()\n            adresse = ""', source)


if __name__ == "__main__":
    unittest.main()
