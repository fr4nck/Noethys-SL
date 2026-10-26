# -*- coding: utf-8 -*-
"""Diagnostic UI optionnel et anonymise pour les traitements Connecthys.

Active seulement par NOETHYS_SL_UI_DIAG=1. Ne journalise jamais de noms,
d'identifiants de familles, d'emails, de messages ou de montants.
Les evenements sont produits uniquement sur le thread wx.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager

ENVIRONNEMENT = "NOETHYS_SL_UI_DIAG"
PERIODE_MS = 250
OPERATIONS = frozenset((
    "demande.traitement",
    "demande.enregistrement",
    "demande.actualisation",
    "reservations.initialisation_grille",
    "reservations.calcul",
    "reservations.sauvegarde",
))


class Diagnostic:
    """Observer l'ecart entre les battements wx, jamais les donnees metier."""

    def __init__(self, fenetre, *, actif=None, clock=None, sortie=None, wx_module=None):
        self.actif = (os.environ.get(ENVIRONNEMENT) == "1" if actif is None
                      else bool(actif))
        self.fenetre = fenetre
        self.clock = clock or time.monotonic
        self.sortie = sortie
        self._dernier_battement = None
        self._timer = None
        self._wx = wx_module
        if not self.actif:
            return
        if self._wx is None:
            import wx
            self._wx = wx
        self._dernier_battement = self.clock()
        self._timer = self._wx.Timer(fenetre)
        fenetre.Bind(self._wx.EVT_TIMER, self._on_battement, self._timer)
        fenetre.Bind(self._wx.EVT_ACTIVATE, self._on_activation)
        fenetre.Bind(self._wx.EVT_MAXIMIZE, self._on_maximisation)
        fenetre.Bind(self._wx.EVT_SIZE, self._on_taille)
        fenetre.Bind(self._wx.EVT_ICONIZE, self._on_iconisation)
        fenetre.Bind(self._wx.EVT_WINDOW_DESTROY, self._on_destruction)
        self._timer.Start(PERIODE_MS)

    def _emettre(self, type_evenement, **champs):
        """Le schema est ferme: seuls des champs techniques sont admis."""
        valides = {
            "operation", "duree_ms", "sans_evenements_ms", "erreur_type",
            "retard_ms", "actif", "maximise", "largeur", "hauteur", "iconise",
        }
        evenement = {"evenement": type_evenement}
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

    def _on_battement(self, event):
        instant = self.clock()
        retard = max(0, int((instant - self._dernier_battement) * 1000) - PERIODE_MS)
        self._dernier_battement = instant
        if retard >= PERIODE_MS:
            self._emettre("retard_boucle", retard_ms=retard)
        event.Skip()

    def _on_activation(self, event):
        self._emettre("activation", actif=bool(event.GetActive()))
        event.Skip()

    def _on_maximisation(self, event):
        self._emettre("maximisation", maximise=bool(self.fenetre.IsMaximized()))
        event.Skip()

    def _on_taille(self, event):
        try:
            largeur, hauteur = self.fenetre.GetSize()
            self._emettre("taille", largeur=int(largeur), hauteur=int(hauteur),
                          maximise=bool(self.fenetre.IsMaximized()))
        except Exception:
            pass
        event.Skip()

    def _on_iconisation(self, event):
        try:
            self._emettre("iconisation", iconise=bool(self.fenetre.IsIconized()))
        except Exception:
            pass
        event.Skip()

    def _on_destruction(self, event):
        if event.GetEventObject() is self.fenetre and self._timer is not None:
            self._timer.Stop()
            self._timer = None
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
