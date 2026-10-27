# -*- coding: utf-8 -*-
"""Priorite a l'interface pour les traitements Python longs hors thread wx (#432).

wxPython relache le GIL a chaque appel wx. Pendant qu'un thread de fond execute
du Python pur (construction ORM de la synchro Connecthys), chaque appel wx du
thread principal attend que ce thread rende le GIL : un traitement d'interface
de 0,25 s pouvait durer plusieurs secondes et figer la fenetre.

Le thread de fond appelle ceder() a ses points de controle. Un "ping" trivial
est poste sur la boucle wx ; s'il n'est pas traite rapidement, l'interface est
occupee et le thread de fond se met en pause (sans GIL) jusqu'a son traitement,
dans une limite qui garantit la progression de la synchro. Aucune donnee n'est
lue ni modifiee.
"""
import time

DELAI_OCCUPE_S = 0.05
PERIODE_PING_S = 0.02
PAUSE_MAX_S = 2.0
TRANCHE_MIN_S = 0.2
PAS_S = 0.005


def _poster_wx():
    try:
        import wx
        if wx.GetApp() is not None and not wx.IsMainThread():
            return wx.CallAfter
    except Exception:
        pass
    return None


class PrioriteUI:
    def __init__(self, poster=None, horloge=time.monotonic, dormir=time.sleep):
        self._poster = poster if poster is not None else _poster_wx()
        self._horloge = horloge
        self._dormir = dormir
        self._ping = None          # instant d'envoi du ping en attente
        self._dernier_ping = None
        self._reprise = None       # fin de la tranche garantie apres une pause plafonnee
        self.pauses = 0
        self.duree_pauses = 0.0

    @property
    def actif(self):
        return self._poster is not None

    def _pong(self):
        # Execute sur le thread wx : l'interface traite de nouveau ses evenements.
        self._ping = None

    def ceder(self):
        if self._poster is None:
            return
        maintenant = self._horloge()
        if self._ping is None:
            if self._dernier_ping is None or maintenant - self._dernier_ping >= PERIODE_PING_S:
                self._dernier_ping = self._ping = maintenant
                try:
                    self._poster(self._pong)
                except Exception:
                    self._poster = None  # application fermee : ne plus ralentir
                    self._ping = None
            return
        if maintenant - self._ping < DELAI_OCCUPE_S:
            return
        if self._reprise is not None and maintenant < self._reprise:
            return
        debut, fin = maintenant, maintenant + PAUSE_MAX_S
        while self._ping is not None and self._horloge() < fin:
            self._dormir(PAS_S)
        apres = self._horloge()
        self.pauses += 1
        self.duree_pauses += apres - debut
        # Interface toujours occupee apres la pause maximale : laisser
        # progresser la synchro pendant une tranche avant la pause suivante.
        self._reprise = apres + TRANCHE_MIN_S if self._ping is not None else None


TAILLE_FLUSH = 500
TAILLE_LOT = 2000


def session_cooperative(session, priorite, taille_flush=TAILLE_FLUSH):
    """session.add() cede d'abord la priorite a l'interface, et les objets
    ajoutes sont ecrits par tranches (flush) dans la meme transaction : le
    commit final n'est plus un long bloc ininterruptible."""
    if not priorite.actif:
        return session
    ajouter = session.add
    compteur = [0]

    def add(instance, *args, **kwargs):
        priorite.ceder()
        resultat = ajouter(instance, *args, **kwargs)
        compteur[0] += 1
        if compteur[0] % taille_flush == 0:
            session.flush()
        return resultat

    session.add = add
    return session


def enregistrer_par_lots(session, objets, priorite, taille=TAILLE_LOT):
    """bulk_save_objects par lots, la priorite etant cedee entre deux lots."""
    for debut in range(0, len(objets), taille):
        priorite.ceder()
        session.bulk_save_objects(objets[debut:debut + taille])

