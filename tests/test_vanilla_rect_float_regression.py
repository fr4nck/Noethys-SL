# -*- coding: utf-8 -*-
"""Non-regression : crash reel constate au demarrage du portable Windows
construit par la CI (executable "Construire la Vanilla Windows"), alors
meme que tests automatises et CI etaient verts.

Trace reelle (OnInit -> OuvrirDernierFichier -> OuvrirFichier ->
AfficherServeurConnecthys -> CTRL_Portail_serveur.MAJ_bouton ->
CTRL_TaskBarIcon.Connecthys -> AjouteTexteImage) :

    TypeError: Rect(): arguments did not match any overloaded call:
      ... argument has unexpected type 'float'

Cause : "hauteurRond / 2.0" est une division reelle, toujours un float
en Python (2 et 3), directement injecte dans wx.Rect(...) sans caster en
int. wx.Rect (Phoenix) rejette les arguments float -- wx Classic les
acceptait silencieusement. Confirme independant de la PR Convention :
aucun commit de cette PR ne touche Noethys.py, CTRL_Portail_serveur.py
ni CTRL_TaskBarIcon.py (verifiable via git log).

Ratissage (doctrine de sweep systematique) : la meme fonction "rond
rouge avec texte" (badge/compteur) est dupliquee dans 5 fichiers.
CTRL_Commande_repas.py castait deja correctement en int (faux positif,
exclu) ; CTRL_TaskBarIcon.py, DLG_Envoi_sms.py, DLG_Ouvertures.py et
DLG_Selection_mails.py partageaient le meme defaut confirme, corrige ici
dans un lot homogene. Ce test exerce directement les 4 fonctions
corrigees avec les memes types d'arguments que l'appel reel qui a
crashe : sans caster en int, n'importe quel appel a "hauteurRond/2.0"
etant systematiquement un float, le crash etait deterministe, pas un
cas limite.
"""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from Ctrl import CTRL_TaskBarIcon  # noqa: E402
from Dlg import DLG_Envoi_sms  # noqa: E402
from Dlg import DLG_Ouvertures  # noqa: E402
from Dlg import DLG_Selection_mails  # noqa: E402
from Utils import UTILS_Portail_synchro  # noqa: E402


class BadgeRondRougeAvecTexteNeLevePasTests(unittest.TestCase):
    """ Chacune de ces fonctions dessine un petit rond rouge avec un texte
    (compteur/badge) sur un bitmap. Aucune ne doit lever de TypeError,
    quel que soit le texte/padding fourni -- c'est exactement le chemin
    de code exécuté au démarrage réel (icône de la barre des tâches). """

    def test_task_bar_icon_ajoute_texte_image_reproduit_l_appel_reel_du_crash(self):
        """ Reproduit exactement Connecthys(nbre=1) : texte="1",
        taille_police=6, l'appel qui a fait planter OnInit. """
        icone = CTRL_TaskBarIcon.CustomTaskBarIcon.__new__(CTRL_TaskBarIcon.CustomTaskBarIcon)
        image = wx.Bitmap(16, 16)
        bmp = icone.AjouteTexteImage(image, "1", taille_police=6)
        self.assertIsInstance(bmp, wx.Bitmap)

    def test_task_bar_icon_avec_plusieurs_chiffres_et_paddings(self):
        icone = CTRL_TaskBarIcon.CustomTaskBarIcon.__new__(CTRL_TaskBarIcon.CustomTaskBarIcon)
        for texte, padding in (("1", 0), ("12", 1), ("999", 2), ("", 0)):
            image = wx.Bitmap(16, 16)
            bmp = icone.AjouteTexteImage(image, texte, padding=padding, taille_police=6)
            self.assertIsInstance(bmp, wx.Bitmap)

    def test_envoi_sms_ajoute_texte_image(self):
        image = wx.Bitmap(16, 16)
        bmp = DLG_Envoi_sms.AjouteTexteImage(image, "12", taille_police=8)
        self.assertIsInstance(bmp, wx.Bitmap)

    def test_selection_mails_ajoute_texte_image(self):
        image = wx.Bitmap(16, 16)
        bmp = DLG_Selection_mails.AjouteTexteImage(image, "3", taille_police=8)
        self.assertIsInstance(bmp, wx.Bitmap)

    def test_ouvertures_get_image_evenement(self):
        # GetImageEvement n'utilise aucun attribut de self : un objet non
        # initialisé (contournant le __init__ du renderer de grille, hors
        # sujet ici) suffit pour exercer le même code que l'écran réel.
        renderer = DLG_Ouvertures.CaseOuvertureRenderer.__new__(DLG_Ouvertures.CaseOuvertureRenderer)
        bmp = renderer.GetImageEvement(texte="5", taille=(16, 16))
        self.assertIsInstance(bmp, wx.Bitmap)

    def test_pulse_gauge_transmet_un_entier_a_setgauge(self):
        """ Meme famille, revelee non pas au demarrage mais en aval : lors
        du premier test reel de l'executable corrige, l'appli s'ouvrait
        desormais (fenetre principale visible), mais le thread de
        synchronisation du portail imprimait en boucle sur stderr
        "Gauge.SetValue(): argument 1 has unexpected type 'float'" --
        "100 * self.num_etape / self.nbre_etapes" est une division reelle,
        donc toujours un float en Python 3, transmise telle quelle a
        CTRL_Portail_serveur.SetGauge -> wx.CallAfter(self.gauge.SetValue,
        valeur), que wx.Gauge (Phoenix) refuse. Corrige en castant en int
        avant transmission. """
        class FauxLog:
            def __init__(self):
                self.dernieres_valeurs = []

            def SetGauge(self, valeur=0):
                self.dernieres_valeurs.append(valeur)

            def EcritLog(self, message=""):
                pass

        faux_log = FauxLog()
        synchro = UTILS_Portail_synchro.Synchro(dict_parametres={"accept_all_cert": False}, log=faux_log)
        synchro.nbre_etapes = 25
        for etape in (1, 2, 3, 24, 25):
            synchro.Pulse_gauge(etape)
        for valeur in faux_log.dernieres_valeurs:
            self.assertIsInstance(valeur, int, "SetGauge doit toujours recevoir un int, jamais un float : %r" % (valeur,))

    def test_commande_repas_deja_correct_reste_correct(self):
        """ Non-régression du "bon" cas (faux positif du ratissage,
        déjà correctement casté en int) : doit rester fonctionnel. """
        import sys as _sys
        if str(NOETHYS_DIR) not in _sys.path:
            _sys.path.insert(0, str(NOETHYS_DIR))
        from Ctrl import CTRL_Commande_repas
        source = (NOETHYS_DIR / "Ctrl" / "CTRL_Commande_repas.py").read_text(encoding="utf-8")
        self.assertIn("largeurRond = int(largeurTexte + padding * 2 + hauteurRond / 2.0)", source)


if __name__ == "__main__":
    unittest.main()
