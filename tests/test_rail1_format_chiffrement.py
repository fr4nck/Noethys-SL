# -*- coding: utf-8 -*-
"""X-01 -- désérialisation pickle des fichiers chiffrés « ancien format ».

Cartographie des appels à DecrypterFichier (RC2) :
- RÉSEAU CONNECTHYS : DLG_Saisie_portail_demande.Traitement_pieces (pièces
  des familles). Connecthys chiffre les pièces avec cryptFile2 (SV2) depuis
  leur introduction (2021) ; sans AES côté serveur, la pièce est stockée en
  clair (jamais en pickle). -> ancien format REFUSÉ.
- RÉSEAU NOMADHYS : DLG_Synchronisation.AnalyserFichier (FTP, serveur TCP,
  import manuel). Nomadhys >= 2020 n'émet que du SV2 ; Noethys sous
  Python 3 n'écrit lui-même que du SV2 (CrypterFichier), donc une tablette
  incapable de lire le SV2 ne fonctionne déjà pas avec la RC2 en mode
  chiffré. -> ancien format REFUSÉ.
- RESTAURATION LOCALE : DLG_Restauration (sauvegardes de Noethys Python 2
  possibles). -> ancien format CONSERVÉ (action volontaire de l'utilisateur ;
  durcissement proposé au rail 2).
"""
from __future__ import annotations

import ast
import importlib.util
import os
import pickle
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"


def charger_cryptage():
    spec = importlib.util.spec_from_file_location("rail1_UTILS_Cryptage_fichier",
                                                  str(NOETHYS_DIR / "Utils" / "UTILS_Cryptage_fichier.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def appels_decrypter(chemin):
    arbre = ast.parse((NOETHYS_DIR / chemin).read_text(encoding="utf-8"))
    appels = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", None) == "DecrypterFichier":
            kw = dict((k.arg, getattr(k.value, "value", None)) for k in noeud.keywords)
            appels.append(kw)
    return appels


class FormatChiffrementTests(unittest.TestCase):
    def setUp(self):
        self.c = charger_cryptage()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def chemin(self, nom):
        return os.path.join(self.tmp.name, nom)

    def test_ancien_format_refuse_sans_execution(self):
        marqueur = "RAIL1_PICKLE_%d" % os.getpid()
        os.environ.pop(marqueur, None)

        class Charge(object):
            def __reduce__(self):
                return (exec, ("import os; os.environ[%r] = '1'" % marqueur,))
        with open(self.chemin("piege.crypt"), "wb") as f:
            pickle.dump(Charge(), f)
        try:
            with self.assertRaises(self.c.FormatChiffrementRefuse):
                self.c.DecrypterFichier(self.chemin("piege.crypt"), self.chemin("x"), "mdp", autoriser_ancien_format=False)
            self.assertIsNone(os.environ.get(marqueur))
            self.assertFalse(os.path.exists(self.chemin("x")))
        finally:
            os.environ.pop(marqueur, None)

    def test_sv2_toujours_lu_en_mode_strict(self):
        with zipfile.ZipFile(self.chemin("a.zip"), "w") as z:
            z.writestr("database.dat", b"donnees")
        self.c.CrypterFichier(self.chemin("a.zip"), self.chemin("a.crypt"), "mdp")
        self.c.DecrypterFichier(self.chemin("a.crypt"), self.chemin("b.zip"), "mdp", autoriser_ancien_format=False)
        self.assertTrue(zipfile.is_zipfile(self.chemin("b.zip")))

    def test_restauration_tente_toujours_l_ancien_format(self):
        """Mode par défaut (restauration locale) : un fichier non SV2 est
        toujours confié à l'ancien décodeur (comportement historique), il
        n'est pas refusé d'emblée."""
        with open(self.chemin("ancien.crypt"), "wb") as f:
            f.write(b"pas un pickle")
        with self.assertRaises(Exception) as ctx:
            self.c.DecrypterFichier(self.chemin("ancien.crypt"), self.chemin("x"), "mdp")
        self.assertNotIsInstance(ctx.exception, self.c.FormatChiffrementRefuse)
        self.assertIsInstance(ctx.exception, pickle.UnpicklingError)

    def test_noethys_py3_n_ecrit_que_du_sv2(self):
        """Fondement de la compatibilité Nomadhys : même avec
        ancienne_methode=True, Noethys sous Python 3 produit du SV2."""
        with open(self.chemin("clair"), "wb") as f:
            f.write(b"x")
        self.c.CrypterFichier(self.chemin("clair"), self.chemin("c.crypt"), "mdp", ancienne_methode=True)
        self.assertEqual(open(self.chemin("c.crypt"), "rb").read()[:3], b"SV2")


class CartographieAppelsTests(unittest.TestCase):
    def test_entrees_reseau_en_mode_strict(self):
        for chemin in ("Dlg/DLG_Saisie_portail_demande.py", "Dlg/DLG_Synchronisation.py"):
            with self.subTest(chemin=chemin):
                appels = appels_decrypter(chemin)
                self.assertTrue(appels)
                for kw in appels:
                    self.assertIs(kw.get("autoriser_ancien_format"), False)

    def test_restauration_locale_conserve_l_ancien_format(self):
        appels = appels_decrypter("Dlg/DLG_Restauration.py")
        self.assertEqual(appels, [{}])

    def test_aucun_autre_appelant(self):
        trouves = set()
        for chemin in NOETHYS_DIR.rglob("*.py"):
            texte = chemin.read_text(encoding="utf-8", errors="ignore")
            if "DecrypterFichier(" in texte and chemin.name != "UTILS_Cryptage_fichier.py":
                trouves.add(chemin.relative_to(NOETHYS_DIR).as_posix())
        self.assertEqual(trouves, {"Dlg/DLG_Saisie_portail_demande.py", "Dlg/DLG_Synchronisation.py",
                                   "Dlg/DLG_Restauration.py"})


if __name__ == "__main__":
    unittest.main()
