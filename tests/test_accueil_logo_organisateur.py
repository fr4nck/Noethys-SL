# -*- coding: utf-8 -*-
"""Logo de l'organisateur sur l'accueil : transparence conservée, aucun accès
à la base avant l'ouverture d'un fichier.

Repris de fix/vanilla-no-black (32974d49, 349132b7, c92a5c9e) et adapté au fond
d'accueil adaptatif de main. Images en mémoire uniquement ; aucune fenêtre
n'est créée ni affichée.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import wx  # noqa: E402

_APP = wx.GetApp() or wx.App(False)

from Ctrl import CTRL_Accueil  # noqa: E402
from Utils import UTILS_Organisateur  # noqa: E402

NOETHYS = Path(__file__).resolve().parents[1] / "noethys" / "Noethys.py"


def _image_opaque(largeur, hauteur, couleur=(200, 0, 0), alpha=True):
    img = wx.Image(largeur, hauteur)
    img.SetRGB(wx.Rect(0, 0, largeur, hauteur), *couleur)
    if alpha:
        img.InitAlpha()
        img.SetAlpha(bytes(bytearray([255] * (largeur * hauteur))))
    return img


class RecadrageLogoTests(unittest.TestCase):
    def test_logo_transparent_sans_fond_blanc_cuit(self):
        img = UTILS_Organisateur.RecadreImg(_image_opaque(200, 100), (80, 80), fondBlanc=False)
        self.assertEqual(tuple(img.GetSize()), (80, 80))
        self.assertTrue(img.HasAlpha())
        # Bandes hors logo (ratio conservé : 80x40 centré) : transparentes
        self.assertEqual(img.GetAlpha(0, 0), 0)
        self.assertEqual(img.GetAlpha(40, 10), 0)
        # Logo : opaque, couleur intacte
        self.assertEqual(img.GetAlpha(40, 40), 255)
        self.assertEqual((img.GetRed(40, 40), img.GetGreen(40, 40), img.GetBlue(40, 40)), (200, 0, 0))

    def test_documents_gardent_le_fond_blanc_par_defaut(self):
        img = UTILS_Organisateur.RecadreImg(_image_opaque(200, 100), (80, 80))
        self.assertEqual(tuple(img.GetSize()), (80, 80))
        self.assertEqual((img.GetRed(0, 0), img.GetGreen(0, 0), img.GetBlue(0, 0)), (255, 255, 255))

    def test_logo_sans_canal_alpha_garde_le_fond_blanc(self):
        img = UTILS_Organisateur.RecadreImg(_image_opaque(200, 100, alpha=False), (80, 80), fondBlanc=False)
        self.assertEqual((img.GetRed(0, 0), img.GetGreen(0, 0), img.GetBlue(0, 0)), (255, 255, 255))

    def test_petit_logo_non_agrandi(self):
        img = UTILS_Organisateur.RecadreImg(_image_opaque(30, 20), (80, 80), fondBlanc=False)
        self.assertEqual(img.GetAlpha(24, 29), 0)    # juste avant le logo (x 25..54)
        self.assertEqual(img.GetAlpha(25, 30), 255)  # premier pixel du logo
        self.assertEqual(img.GetAlpha(54, 49), 255)  # dernier pixel du logo
        self.assertEqual(img.GetAlpha(55, 50), 0)

    def test_get_donnees_transmet_le_choix_du_fond(self):
        import io
        tampon = io.BytesIO()
        source = _image_opaque(60, 30)
        source.SetAlpha(0, 0, 0)  # un logo transparent : le PNG garde son canal alpha
        source.SaveFile(tampon, wx.BITMAP_TYPE_PNG)
        ligne = [(u"Organisateur fictif", None, None, None, None, None, None, None, None, None, None,
                  tampon.getvalue(), None)]
        faux_db = mock.MagicMock()
        faux_db.ResultatReq.return_value = ligne
        with mock.patch.object(UTILS_Organisateur.GestionDB, "DB", return_value=faux_db):
            logo = UTILS_Organisateur.GetDonnees(tailleLogo=(80, 80), fondLogoBlanc=False)["logo"]
        self.assertTrue(logo.IsOk())
        self.assertEqual(logo.ConvertToImage().GetAlpha(0, 0), 0)


class PositionLogoTests(unittest.TestCase):
    def test_coin_superieur_droit(self):
        self.assertEqual(CTRL_Accueil.PositionLogoAccueil((1000, 700), (80, 40)), (900, 20))

    def test_zone_trop_petite_ou_logo_vide(self):
        self.assertIsNone(CTRL_Accueil.PositionLogoAccueil((100, 700), (80, 40)))
        self.assertIsNone(CTRL_Accueil.PositionLogoAccueil((1000, 60), (80, 40)))
        self.assertIsNone(CTRL_Accueil.PositionLogoAccueil((1000, 700), (0, 0)))


class _FauxPanel(object):
    def __init__(self):
        self.logo_organisateur = "ancien"
        self.rafraichi = 0

    def Refresh(self):
        self.rafraichi += 1


class MajAccueilTests(unittest.TestCase):
    def test_fichier_ferme_aucun_acces_base_et_logo_retire(self):
        panel = _FauxPanel()
        with mock.patch.object(UTILS_Organisateur, "GetDonnees") as get_donnees:
            CTRL_Accueil.Panel.MAJ(panel, fichier_ouvert=False)
        get_donnees.assert_not_called()
        self.assertIsNone(panel.logo_organisateur)
        self.assertEqual(panel.rafraichi, 1)

    def test_fichier_ouvert_charge_le_logo_transparent(self):
        panel = _FauxPanel()
        bitmap = wx.Bitmap(_image_opaque(10, 10))
        with mock.patch.object(UTILS_Organisateur, "GetDonnees", return_value={"logo": bitmap}) as get_donnees:
            CTRL_Accueil.Panel.MAJ(panel, fichier_ouvert=True)
        get_donnees.assert_called_once_with(tailleLogo=CTRL_Accueil.TAILLE_LOGO_ACCUEIL, fondLogoBlanc=False)
        self.assertIs(panel.logo_organisateur, bitmap)

    def test_erreur_de_lecture_conserve_l_accueil(self):
        panel = _FauxPanel()
        with mock.patch.object(UTILS_Organisateur, "GetDonnees", side_effect=RuntimeError("base")):
            CTRL_Accueil.Panel.MAJ(panel, fichier_ouvert=True)
        self.assertIsNone(panel.logo_organisateur)

    def test_fenetre_principale_actualise_a_l_ouverture_et_a_la_fermeture(self):
        source = NOETHYS.read_text(encoding="utf-8")
        self.assertIn('self.ctrl_accueil.MAJ(fichier_ouvert=self.userConfig["nomFichier"] != "")', source)
        self.assertIn("self.ctrl_accueil.MAJ(fichier_ouvert=False)", source)


if __name__ == "__main__":
    unittest.main()
