# -*- coding: utf-8 -*-
"""EMAIL-10 -- traitement automatique d'une demande Connecthys de reçu de
règlement par email.

Contrat établi depuis le code (Noethys RC2 + Connecthys) :
- Traitement.Traiter() renvoie un dict local {"etat", "reponse"} ou False ;
  il n'est JAMAIS transmis tel quel à Connecthys ;
- etat=True -> la demande passe à "validation" avec la réponse affichée à la
  famille ; False -> elle reste "attente" ;
- Connecthys ne reçoit etat/reponse qu'au syncup suivant (UPDATE de
  portail_actions par ref_unique : application/importation.py).
Traitement_factures renvoie déjà False quand l'email échoue : le reçu suit
désormais le même contrat (aucun nouvel état, aucun changement de format).
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
    from Dlg import DLG_Saisie_portail_demande, DLG_Impression_recu
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover
    IMPORT_ERREUR = err


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))


class TraitementRecuEmailTests(unittest.TestCase):
    def executer(self, resultat_email):
        impression = mock.MagicMock()
        logs = []
        traitement = types.SimpleNamespace(
            mode="automatique", parent=None,
            dict_parametres={"IDreglement": "12", "methode_envoi": "email"},
            track=types.SimpleNamespace(IDfamille=3),
            EcritLog=lambda message="", log_jumeau=None: logs.append(message))
        module = DLG_Saisie_portail_demande
        with mock.patch.object(DLG_Impression_recu, "Dialog", return_value=impression), \
                mock.patch.object(module.UTILS_Envoi_email, "EnvoiEmailFamille", return_value=resultat_email):
            resultat = module.Traitement.Traitement_recus(traitement)
        return resultat, impression, logs

    def test_email_accepte_demande_validee(self):
        resultat, impression, logs = self.executer(True)
        self.assertEqual(resultat, {"etat": True, "reponse": u"Reçu de règlement envoyé par Email."})
        impression.Sauvegarder.assert_called_once_with(demander=False)

    def test_email_en_echec_demande_reste_en_attente(self):
        resultat, impression, logs = self.executer(False)
        self.assertIs(resultat, False)
        impression.Sauvegarder.assert_not_called()
        impression.Destroy.assert_called_once_with()
        self.assertIn(u"Le reçu de règlement n'a pas été envoyé par Email.", logs)

    def test_valeurs_de_retour_identiques_a_celles_des_factures(self):
        """Seules des valeurs déjà produites par Traiter() sont utilisées."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")
        self.assertIn(u'self.EcritLog(_(u"La facture n\'a pas été envoyée par Email."))\n                    return False', source)


if __name__ == "__main__":
    unittest.main()
