# -*- coding: utf-8 -*-
"""UI-432K : rendu Agg de graphes explicitement qualifies, hors widgets wx.

Le worker n'ouvre aucune fenetre, ne transmet ni objet matplotlib ni
connexion SQL au thread wx. Le bitmap et le MemoryFS restent dans la GUI.
"""
import copy
import io

import GestionDB


# Les deux comparatifs n'utilisent que figure.add_subplot et pyplot.setp ;
# leurs requetes passent par la connexion fournie, sans ecriture/cache global.
_CLASSES = frozenset((
    ("Utils.UTILS_Stats_individus", "Graphe_nombre_individus"),
    ("Utils.UTILS_Stats_familles", "Graphe_nombre_familles"),
))
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DPI = 90


def est_compatible(objet):
    classe = type(objet)
    return (classe.__module__, classe.__name__) in _CLASSES


def preparer(objet, parametres, source_db):
    """Snapshot sans widget et calcul SQL/graphique dans le worker unique."""
    if not est_compatible(objet):
        raise ValueError("Graphe non qualifie pour le worker")
    if not isinstance(source_db, str) or not source_db:
        raise ValueError("Source SQL explicite requise")
    classe = type(objet)
    largeur, hauteur = objet.taille
    taille = (int(largeur), int(hauteur))
    if not (32 <= taille[0] <= 4096 and 32 <= taille[1] <= 4096):
        raise ValueError("Taille du graphe invalide")
    decalage_x = float(objet.decalage_x)
    params = copy.deepcopy(parametres)

    def calcul():
        # Figure Agg pure, sans pyplot.figure ni creation wx.
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        figure = Figure(figsize=(taille[0] / _DPI, taille[1] / _DPI), dpi=_DPI)
        FigureCanvasAgg(figure)
        copie = classe.__new__(classe)
        copie.taille = taille
        copie.decalage_x = decalage_x
        copie.dictParametres = {}
        db = GestionDB.DB(nomFichier=source_db, suffixe=None, pooling=False)
        try:
            resultat = copie.MAJ(figure=figure, DB=db, dictParametres=params)
            if resultat is not None and resultat is not figure:
                raise ValueError("Le graphe doit rendre sa propre figure")
            sortie = io.BytesIO()
            figure.savefig(sortie, format="png", dpi=_DPI)
            donnees = sortie.getvalue()
            if not donnees.startswith(_PNG_SIGNATURE):
                raise ValueError("Rendu PNG invalide")
            return donnees
        finally:
            db.Close()
            figure.clear()

    return calcul
