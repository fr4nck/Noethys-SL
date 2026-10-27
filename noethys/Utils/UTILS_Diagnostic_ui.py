# -*- coding: utf-8 -*-
"""Diagnostic UI optionnel et anonymise pour les traitements Connecthys.

Active seulement par NOETHYS_SL_UI_DIAG=1. Ne journalise jamais de noms,
d'identifiants de familles, d'emails, de messages ou de montants.
Les evenements wx sont observes sur le thread UI. Une veille facultative ne
consulte que les piles Python, jamais un widget ou une donnee metier.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from contextlib import contextmanager

ENVIRONNEMENT = "NOETHYS_SL_UI_DIAG"
PERIODE_MS = 250
PERIODE_VEILLE_S = 0.5
# Threads de synchronisation Connecthys dont la position est utile pendant un
# gel : un appel C qui conserve le GIL y bloquerait aussi le thread wx.
THREADS_SYNCHRO = ("Noethys-Connecthys-synchro", "Noethys-Connecthys-manuel")
OPERATIONS = frozenset((
    "demande.traitement",
    "demande.enregistrement",
    "demande.actualisation",
    "reservations.initialisation_grille",
    "reservations.calcul",
    "reservations.sauvegarde",
))

ETAPES_GRILLE = frozenset((
    "grille.activites",
    "grille.individus",
    "grille.groupes",
    "grille.comptes_payeurs",
    "grille.quotients",
    "grille.aides",
    "grille.etiquettes",
    "grille.deductions",
    "grille.prestations",
    "grille.forfaits",
    "grille.transports",
    "grille.ouvertures",
    "grille.unites",
    "grille.raccourcis",
    "grille.vacances",
    "grille.feries",
    "grille.remplissage",
    "grille.inscriptions",
    "grille.infos_individus",
    "grille.memos",
    "grille.calcul_remplissage",
    "grille.affichage",
    "grille.finalisation",
    "grille.erreur",
    "grille.inconnue",
))


def tracer_etape_grille(etape, duree_ms, sortie=None):
    """Duree d'une etape wx, nom fixe et aucune donnee metier."""
    if os.environ.get(ENVIRONNEMENT) != "1":
        return
    etape = etape if isinstance(etape, str) and etape in ETAPES_GRILLE else "grille.inconnue"
    try:
        evenement = {"evenement": "etape", "etape": etape,
                     "duree_ms": max(0, int(duree_ms))}
        if sortie is None:
            print("NOETHYS_UI_DIAG " + " ".join(
                "%s=%s" % (cle, evenement[cle]) for cle in sorted(evenement)
            ), flush=True)
        else:
            sortie(evenement)
    except Exception:
        # Le diagnostic ne doit jamais interrompre la saisie.
        pass


class Diagnostic:
    """Observer l'ecart entre les battements wx, jamais les donnees metier."""

    def __init__(self, fenetre, *, actif=None, clock=None, sortie=None, wx_module=None,
                 role=None):
        self.actif = (os.environ.get(ENVIRONNEMENT) == "1" if actif is None
                      else bool(actif))
        self.fenetre = fenetre
        self.role = role if role in ("principale", "demande") else None
        self._etat_precedent = None
        self.clock = clock or time.monotonic
        self.sortie = sortie
        self._dernier_battement = None
        self._timer = None
        self._wx = wx_module
        self._veille_stop = None
        self._hwnd = None
        surveiller = (self.role == "principale" and sys.platform == "win32"
                      and wx_module is None and clock is None)
        if not self.actif:
            return
        if self._wx is None:
            import wx
            self._wx = wx
        self._dernier_battement = self.clock()
        # Timer sans proprietaire : un wx.Timer(fenetre) non arrete continuait
        # d'adresser ses evenements a la fenetre detruite (0xC0000005 a la
        # sortie, campagne #432). Le battement verifie lui-meme la fenetre.
        self._timer = self._wx.Timer()
        self._timer.Bind(self._wx.EVT_TIMER, self._on_battement)
        fenetre.Bind(self._wx.EVT_ACTIVATE, self._on_activation)
        fenetre.Bind(self._wx.EVT_MAXIMIZE, self._on_maximisation)
        fenetre.Bind(self._wx.EVT_SIZE, self._on_taille)
        fenetre.Bind(self._wx.EVT_ICONIZE, self._on_iconisation)
        fenetre.Bind(self._wx.EVT_WINDOW_DESTROY, self._on_destruction)
        self._timer.Start(PERIODE_MS)
        if surveiller:
            # Lu une fois sur le thread wx : la veille n'interroge que Win32.
            self._hwnd = fenetre.GetHandle()
            self._veille_stop = threading.Event()
            ident = threading.get_ident()
            self._veille_thread = threading.Thread(
                target=self._surveiller_blocages, args=(ident,),
                name="Noethys-UI-diagnostic", daemon=True)
            self._veille_thread.start()

    def _emettre(self, type_evenement, **champs):
        """Le schema est ferme: seuls des champs techniques sont admis."""
        valides = {
            "operation", "duree_ms", "sans_evenements_ms", "erreur_type",
            "retard_ms", "actif", "maximise", "largeur", "hauteur", "iconise",
            "wx_maximise", "win32_maximise", "win32_iconise", "premier_plan",
            "point", "point_synchro", "veille_retard_ms", "ne_repond_pas", "fantome",
        }
        evenement = {"evenement": type_evenement}
        if self.role is not None:
            evenement["fenetre"] = self.role
        evenement.update({cle: valeur for cle, valeur in champs.items() if cle in valides})
        try:
            if self.sortie is None:
                print("NOETHYS_UI_DIAG " + " ".join(
                    "%s=%s" % (cle, evenement[cle]) for cle in sorted(evenement)
                ))
            else:
                self.sortie(evenement)
        except Exception:
            # Un probleme de diagnostic ne doit jamais interrompre l'activite.
            pass

    def _point_thread(self, ident):
        """Nom fixe du fichier / fonction / ligne ; jamais de valeur de pile."""
        try:
            cadre = sys._current_frames().get(ident)
            racine = os.path.normcase(os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir)))
            for _ in range(64):
                if cadre is None:
                    break
                chemin_source = os.path.abspath(cadre.f_code.co_filename)
                chemin = os.path.normcase(chemin_source)
                try:
                    local = os.path.commonpath((racine, chemin)) == racine
                except ValueError:
                    local = False
                if local:
                    # normcase() minuscule les chemins sous Windows : conserver
                    # la casse du fichier d'origine dans la trace anonymisee.
                    fichier = os.path.basename(chemin_source)
                    fonction = cadre.f_code.co_name
                    if (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,70}\.py", fichier)
                            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,70}", fonction)):
                        return "%s:%s:%d" % (fichier, fonction, int(cadre.f_lineno))
                cadre = cadre.f_back
        except Exception:
            pass
        return "hors_noethys"

    def _point_synchro(self):
        """Position du thread de synchro Connecthys actif, sinon 'aucune'."""
        try:
            for thread in threading.enumerate():
                if thread.name in THREADS_SYNCHRO and thread.is_alive():
                    return self._point_thread(thread.ident)
        except Exception:
            pass
        return "aucune"

    def _etat_fenetre_bloquee(self):
        """Windows remplace une fenetre qui ne traite plus ses messages
        (> 5 s) par une fenetre fantome ; une action sur ce fantome (reduire,
        bouton de barre des taches) s'applique ensuite a la vraie fenetre.
        Lecture Win32 seule, booleens uniquement, jamais de titre."""
        if self._hwnd is None or sys.platform != "win32":
            return {}
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.IsHungAppWindow.argtypes = [wintypes.HWND]
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            classe = ctypes.create_unicode_buffer(32)
            premier_plan = user32.GetForegroundWindow()
            if premier_plan:
                user32.GetClassNameW(premier_plan, classe, 32)
            return dict(ne_repond_pas=bool(user32.IsHungAppWindow(self._hwnd)),
                        fantome=classe.value == "Ghost")
        except Exception:
            return {}

    def _surveiller_blocages(self, ident):
        """Lecture des seules frames Python, hors wx et hors transactions SQL."""
        prochaine = 0.0
        attendu = self.clock() + PERIODE_VEILLE_S
        while not self._veille_stop.wait(PERIODE_VEILLE_S):
            prochaine = self._cycle_veille(ident, self.clock(), attendu, prochaine)
            attendu = self.clock() + PERIODE_VEILLE_S

    def _cycle_veille(self, ident, maintenant, attendu, prochaine):
        """Un passage de la veille. Un reveil tres tardif de ce thread signale
        que le GIL (ou le processus) etait monopolise : le gel ne vient alors
        pas forcement du code execute par le thread wx."""
        try:
            veille_retard = max(0.0, maintenant - attendu)
            if veille_retard >= 1.0:
                self._emettre("veille_retardee",
                              veille_retard_ms=int(veille_retard * 1000),
                              point_synchro=self._point_synchro())
            retard = maintenant - self._dernier_battement
            if retard < 1.5:
                return 0.0
            if maintenant < prochaine:
                return prochaine
            self._emettre("blocage_thread", duree_ms=int(retard * 1000),
                          point=self._point_thread(ident),
                          point_synchro=self._point_synchro(),
                          veille_retard_ms=int(veille_retard * 1000),
                          **self._etat_fenetre_bloquee())
            return maintenant + 5.0
        except Exception:
            return prochaine

    def _fenetre_vivante(self):
        try:
            return bool(self.fenetre)
        except Exception:
            return False

    def _arreter(self):
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None
        if self._veille_stop is not None:
            self._veille_stop.set()

    def _on_battement(self, event):
        if not self._fenetre_vivante():
            self._arreter()
            return
        instant = self.clock()
        retard = max(0, int((instant - self._dernier_battement) * 1000) - PERIODE_MS)
        self._dernier_battement = instant
        if retard >= PERIODE_MS:
            self._emettre("retard_boucle", retard_ms=retard)
        if self.role == "principale":
            self.instantane()
        event.Skip()

    def instantane(self):
        """Etat wx et Win32 du meme HWND; aucun titre ou identifiant journalise."""
        if not self.actif:
            return
        try:
            largeur, hauteur = self.fenetre.GetSize()
            etat = dict(wx_maximise=bool(self.fenetre.IsMaximized()),
                        iconise=bool(self.fenetre.IsIconized()),
                        largeur=int(largeur), hauteur=int(hauteur))
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.IsZoomed.argtypes = [wintypes.HWND]
                user32.IsIconic.argtypes = [wintypes.HWND]
                user32.GetForegroundWindow.restype = wintypes.HWND
                hwnd = self.fenetre.GetHandle()
                etat.update(win32_maximise=bool(user32.IsZoomed(hwnd)),
                            win32_iconise=bool(user32.IsIconic(hwnd)),
                            premier_plan=user32.GetForegroundWindow() == hwnd)
            if etat != self._etat_precedent:
                self._emettre("etat", **etat)
                self._etat_precedent = etat
        except Exception:
            pass

    def _on_activation(self, event):
        if event.GetEventObject() is not self.fenetre:
            event.Skip()
            return
        self._emettre("activation", actif=bool(event.GetActive()))
        event.Skip()

    def _on_maximisation(self, event):
        if event.GetEventObject() is not self.fenetre:
            event.Skip()
            return
        self._emettre("maximisation", maximise=bool(self.fenetre.IsMaximized()))
        event.Skip()

    def _on_taille(self, event):
        if event.GetEventObject() is not self.fenetre:
            event.Skip()
            return
        try:
            largeur, hauteur = self.fenetre.GetSize()
            self._emettre("taille", largeur=int(largeur), hauteur=int(hauteur),
                          maximise=bool(self.fenetre.IsMaximized()))
        except Exception:
            pass
        event.Skip()

    def _on_iconisation(self, event):
        if event.GetEventObject() is not self.fenetre:
            event.Skip()
            return
        try:
            self._emettre("iconisation", iconise=bool(self.fenetre.IsIconized()))
        except Exception:
            pass
        event.Skip()

    def _on_destruction(self, event):
        if event.GetEventObject() is self.fenetre:
            self._arreter()
        event.Skip()

    @contextmanager
    def mesurer(self, operation):
        if not self.actif:
            yield
            return
        operation = operation if operation in OPERATIONS else "inconnue"
        debut = self.clock()
        erreur_type = "aucune"
        try:
            yield
        except Exception as err:
            erreur_type = type(err).__name__
            raise
        finally:
            fin = self.clock()
            duree = max(0, fin - debut)
            # La boucle wx ne peut traiter EVT_TIMER pendant une operation
            # bloquante. Cette mesure est estimee au retour de l'appel.
            sans_evenements = max(
                0, min(duree, fin - self._dernier_battement - PERIODE_MS / 1000.0)
            )
            self._emettre(
                "operation",
                operation=operation,
                duree_ms=int(duree * 1000),
                sans_evenements_ms=int(sans_evenements * 1000),
                erreur_type=erreur_type,
                maximise=bool(self.fenetre.IsMaximized()),
            )


@contextmanager
def mesurer(fenetre, operation):
    """Inerte hors diagnostic; accepte les faux dialogues des tests."""
    diagnostic = getattr(fenetre, "_diag_ui", None)
    if diagnostic is None:
        yield
        return
    with diagnostic.mesurer(operation):
        yield
