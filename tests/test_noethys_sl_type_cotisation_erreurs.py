# -*- coding: utf-8 -*-
"""Type de cotisation : nouvel essai après erreur et pannes SQL injectées.

Les vraies méthodes `Importation` et `OnBoutonOk` du dialogue sont
exécutées sur un hôte sans fenêtre (contrôles simulés) et une base SQLite
fictive : le même fichier peut être rejoué sur une copie isolée d'un code
antérieur pour démontrer le défaut (contre-épreuve).

Pannes injectées au niveau du curseur de GestionDB : ReqInsert, ReqMAJ et
ReqDEL interceptent l'erreur SQL (ReqInsert renvoie None, les deux autres
rien) ; le dialogue ne doit jamais en déduire un succès.
"""
import re
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import wx  # noqa: E402
import _garde_reseau  # noqa: E402,F401
import GestionDB  # noqa: E402
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Dlg import DLG_Saisie_type_cotisation  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402


class _Valeur(object):
    def __init__(self, valeur=u""):
        self.valeur = valeur

    def GetValue(self):
        return self.valeur

    def SetValue(self, valeur):
        self.valeur = valeur


class _Choix(object):
    def __init__(self, selection=0):
        self.selection = selection

    def GetSelection(self):
        return self.selection

    def SetSelection(self, selection):
        self.selection = selection

    Select = SetSelection

    def Enable(self, actif=True):
        pass


class _Unites(object):
    def __init__(self):
        self.donnees = []

    def SetListeDonnees(self, donnees):
        self.donnees = donnees

    def GetListeDonnees(self):
        return self.donnees

    def MAJ(self):
        pass


# Hôte sans fenêtre portant toutes les méthodes du vrai dialogue.
_Hote = type("_Hote", (object,), dict(
    (nom, valeur) for nom, valeur in vars(DLG_Saisie_type_cotisation.Dialog).items()
    if callable(valeur) and nom != "__init__"))


def hote(IDtype_cotisation=None):
    h = _Hote()
    h.parent = None
    h.IDtype_cotisation = IDtype_cotisation
    h.dictUnites = {}
    h.defaut = 0
    h.mode_association_invalide = None
    h.ctrl_nom = _Valeur(u"Adhésion fictive")
    h.ctrl_type = _Choix(1)
    h.ctrl_carte = _Valeur(False)
    h.ctrl_code_comptable = _Valeur(u"")
    h.ctrl_code_produit_local = _Valeur(u"")
    h.ctrl_mode_adhesion = _Choix(0)
    h.ctrl_unites = _Unites()
    h.EndModal = mock.Mock()
    return h


def unite(nom):
    return {"IDunite_cotisation": None, "date_debut": None, "date_fin": None, "defaut": 1, "nom": nom,
            "montant": 12.5, "label_prestation": None, "etat": "MODIF", "duree": "j0-m0-a1"}


class _CurseurEnPanne(object):
    """Curseur qui lève une erreur SQL sur les requêtes visées."""

    def __init__(self, curseur, motif, journal):
        self._curseur = curseur
        self._motif = motif
        self._journal = journal

    def execute(self, req, *args):
        self._journal.append(" ".join(req.split()))
        if self._motif is not None and re.search(self._motif, req, re.I | re.S):
            raise sqlite3.OperationalError("panne injectée")
        return self._curseur.execute(req, *args)

    def __getattr__(self, nom):
        return getattr(self._curseur, nom)


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.addCleanup(self.base.fermer)
        for table in ("types_cotisations", "unites_cotisations", "cotisations"):
            self.base.db.CreationTable(table, dicoDB=Tables.DB_DATA)
        # Données financières témoins : elles ne doivent jamais changer.
        self.base.inserer("cotisations", ["IDcotisation", "IDtype_cotisation", "IDunite_cotisation", "IDindividu"],
                          [(1, 1, 1, 100)])
        self.base.inserer("prestations", ["IDprestation", "label", "montant", "IDfamille"],
                          [(1, u"Adhésion fictive", 12.5, 1)])
        self.base.inserer("parametres", ["categorie", "nom", "parametre"],
                          [(A.CATEGORIE_MODE_ASSOCIATION, "type_2", "participations")])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.messages = []
        for cible, valeur in ((wx, "MessageDialog"), (wx, "CallAfter")):
            p = mock.patch.object(cible, valeur, side_effect=self._message if valeur == "MessageDialog" else None)
            p.start()
            self.addCleanup(p.stop)
        self.requetes = []
        self.panne = None
        classe_redirigee = GestionDB.DB
        test = self

        def db_instrumentee(*args, **kwargs):
            db = classe_redirigee(*args, **kwargs)
            db.cursor = _CurseurEnPanne(db.cursor, test.panne, test.requetes)
            return db
        p = mock.patch.object(GestionDB, "DB", side_effect=db_instrumentee)
        p.start()
        self.addCleanup(p.stop)
        self.temoin_financier = self.financier()

    def _message(self, parent, texte, *args, **kwargs):
        self.messages.append(texte)
        return mock.Mock()

    def tearDown(self):
        self.assertEqual(self.financier(), self.temoin_financier, "cotisations ou prestations modifiées")

    def lignes(self, req):
        self.base.db.ExecuterReq(req)
        return self.base.db.ResultatReq()

    def financier(self):
        return (self.lignes("SELECT * FROM cotisations ORDER BY IDcotisation"),
                self.lignes("SELECT * FROM prestations ORDER BY IDprestation"))

    def parametres(self, nom):
        return sorted(r[0] for r in self.lignes(
            "SELECT parametre FROM parametres WHERE categorie='%s' AND nom='%s'" % (A.CATEGORIE_MODE_ASSOCIATION, nom)))

    def type_existant(self, unites=((1, u"Ancienne"), (2, u"Conservée")), modes=()):
        self.base.inserer("types_cotisations", ["IDtype_cotisation", "nom", "type", "carte", "defaut"],
                          [(1, u"Adhésion fictive", "individu", 0, 0)])
        self.base.inserer("unites_cotisations", ["IDunite_cotisation", "IDtype_cotisation", "nom", "defaut", "duree",
                                                 "montant"],
                          [(ID, 1, nom, 1 if ID == 2 else 0, "j0-m0-a1", 12.5) for ID, nom in unites])
        if modes:
            self.base.inserer("parametres", ["categorie", "nom", "parametre"],
                              [(A.CATEGORIE_MODE_ASSOCIATION, "type_1", m) for m in modes])
        h = hote(1)
        h.Importation()
        return h

    def ok(self, h):
        """Clic sur OK : vrai seulement si la fenêtre se ferme sur ID_OK."""
        h.EndModal.reset_mock()
        h.OnBoutonOk(None)
        if h.EndModal.called:
            h.EndModal.assert_called_once_with(wx.ID_OK)
            return True
        return False

    def requetes_sur(self, motif):
        return [r for r in self.requetes if re.search(motif, r, re.I)]


class NouvelEssaiTests(_Base):
    def test_erreur_du_mode_apres_insertion_puis_second_ok_sans_doublon(self):
        h = hote()
        h.ctrl_unites.SetListeDonnees([unite(u"Annuelle")])
        with mock.patch.object(A, "EnregistrerModeAssociation", side_effect=RuntimeError("base verrouillée")):
            self.assertFalse(self.ok(h))
        self.assertTrue(self.messages)
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT nom, montant FROM unites_cotisations"), [(u"Annuelle", 12.5)])
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM types_cotisations")[0][0], 1)
        self.assertEqual(A.LireModeAssociation(h.IDtype_cotisation), A.MODE_ASSOCIATION_INSCRIPTIONS)

    def test_suppression_puis_nouvel_essai_non_rejouee(self):
        h = self.type_existant()
        next(u for u in h.ctrl_unites.GetListeDonnees() if u["IDunite_cotisation"] == 1)["etat"] = "SUPPR"
        with mock.patch.object(A, "EnregistrerModeAssociation", side_effect=RuntimeError("base verrouillée")):
            self.assertFalse(self.ok(h))
        self.assertTrue(self.ok(h))
        self.assertEqual(len(self.requetes_sur(r"^DELETE FROM unites_cotisations")), 1)
        self.assertEqual(self.lignes("SELECT IDunite_cotisation FROM unites_cotisations"), [(2,)])

    def test_ouverture_d_un_type_dont_le_mode_est_en_double(self):
        h = self.type_existant(modes=("inscriptions", "participations"))
        self.assertIsNotNone(h.mode_association_invalide)
        self.assertEqual([u["nom"] for u in h.ctrl_unites.GetListeDonnees()], [u"Ancienne", u"Conservée"])
        h.ctrl_mode_adhesion.SetSelection(1)
        self.assertTrue(self.ok(h))
        self.assertEqual(self.parametres("type_1"), ["participations"])
        self.assertEqual(self.parametres("type_2"), ["participations"])


class PannesSQLTests(_Base):
    def test_panne_a_la_suppression_des_doublons(self):
        h = self.type_existant(modes=("inscriptions", "participations"))
        h.ctrl_mode_adhesion.SetSelection(1)
        h.ctrl_nom.SetValue(u"Nom modifié")
        self.panne = r"DELETE\s+FROM\s+parametres"
        self.assertFalse(self.ok(h))
        self.assertTrue(self.messages)
        self.assertEqual(self.parametres("type_1"), ["inscriptions", "participations"])
        self.assertEqual(self.parametres("type_2"), ["participations"])
        with self.assertRaises(A.ConfigurationAdhesionInvalide):
            A.LireModeAssociation(1)
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.parametres("type_1"), ["participations"])
        self.assertEqual(self.lignes("SELECT nom FROM types_cotisations"), [(u"Nom modifié",)])

    def test_panne_apres_suppression_avant_le_mode_choisi(self):
        h = self.type_existant(modes=("inscriptions", "participations"))
        h.ctrl_mode_adhesion.SetSelection(1)
        self.panne = r"INSERT\s+INTO\s+parametres|UPDATE\s+parametres"
        self.assertFalse(self.ok(h))
        self.assertTrue(self.messages)
        # Jamais un mode arbitraire devenu valide en silence.
        self.assertEqual(self.parametres("type_1"), ["inscriptions", "participations"])
        with self.assertRaises(A.ConfigurationAdhesionInvalide):
            A.LireModeAssociation(1)
        self.assertEqual(self.parametres("type_2"), ["participations"])
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.parametres("type_1"), ["participations"])

    def test_insertion_d_unite_refusee_par_la_base(self):
        h = hote()
        h.ctrl_unites.SetListeDonnees([unite(u"Annuelle")])
        self.panne = r"INSERT\s+INTO\s+unites_cotisations"
        self.assertFalse(self.ok(h))
        self.assertTrue(self.messages)
        donnee = h.ctrl_unites.GetListeDonnees()[0]
        self.assertEqual((donnee["IDunite_cotisation"], donnee["etat"]), (None, "MODIF"))
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 0)
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT nom FROM unites_cotisations"), [(u"Annuelle",)])
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM types_cotisations")[0][0], 1)

    def test_modification_d_unite_refusee_par_la_base(self):
        h = self.type_existant()
        donnee = next(u for u in h.ctrl_unites.GetListeDonnees() if u["IDunite_cotisation"] == 2)
        donnee.update(montant=20.0, etat="MODIF")
        self.panne = r"UPDATE\s+unites_cotisations"
        self.assertFalse(self.ok(h))
        self.assertEqual(donnee["etat"], "MODIF")
        self.assertEqual(self.lignes("SELECT montant FROM unites_cotisations WHERE IDunite_cotisation=2"), [(12.5,)])
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT montant FROM unites_cotisations WHERE IDunite_cotisation=2"), [(20.0,)])

    def test_suppression_d_unite_refusee_par_la_base(self):
        h = self.type_existant()
        donnee = next(u for u in h.ctrl_unites.GetListeDonnees() if u["IDunite_cotisation"] == 1)
        donnee["etat"] = "SUPPR"
        self.panne = r"DELETE\s+FROM\s+unites_cotisations"
        self.assertFalse(self.ok(h))
        self.assertEqual((donnee["IDunite_cotisation"], donnee["etat"]), (1, "SUPPR"))
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 2)
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT IDunite_cotisation FROM unites_cotisations"), [(2,)])

    def test_creation_du_type_refusee_par_la_base(self):
        h = hote()
        h.ctrl_unites.SetListeDonnees([unite(u"Annuelle")])
        self.panne = r"INSERT\s+INTO\s+types_cotisations"
        self.assertFalse(self.ok(h))
        self.assertIsNone(h.IDtype_cotisation)
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 0)
        self.panne = None
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT IDtype_cotisation FROM unites_cotisations"),
                         [(h.IDtype_cotisation,)])


if __name__ == "__main__":
    unittest.main()
