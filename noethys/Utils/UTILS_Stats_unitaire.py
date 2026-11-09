# -*- coding: utf-8 -*-
"""UI-432K : calcul de tableaux/textes eligibles sans faire passer wx en worker.

Liste blanche restreinte. Les graphes, le VFS wx, les caches globaux et
les tableaux reposant sur des services externes restent sur la GUI.
"""
import copy
import GestionDB

_CLASSES = frozenset((
    ("Utils.UTILS_Stats_individus", "Texte_nombre_individus"),
    ("Utils.UTILS_Stats_individus", "Tableau_nombre_individus"),
    ("Utils.UTILS_Stats_individus", "Tableau_repartition_ages"),
    ("Utils.UTILS_Stats_individus", "Tableau_repartition_annees_naiss"),
    ("Utils.UTILS_Stats_individus", "Tableau_repartition_tranches_ages"),
    ("Utils.UTILS_Stats_familles", "Texte_nombre_familles"),
    ("Utils.UTILS_Stats_familles", "Tableau_nombre_familles"),
))
_ATTRIBUTS = ("texte", "largeur", "colonnes", "lignes", "totaux")
_ETAT_INIT = ("nom", "code", "visible", "dictParametres") + _ATTRIBUTS


def est_compatible(objet):
    classe = type(objet)
    return (classe.__module__, classe.__name__) in _CLASSES


def preparer(objet, parametres, source_db):
    """Prepare une commande ne transportant aucun widget ni connexion.

    L'instance de calcul est recreee sans appeler son constructeur,
    lequel enregistrerait un wx.MemoryFSHandler depuis le worker.
    """
    if not est_compatible(objet):
        raise ValueError("Objet statistique non qualifie pour worker")
    if not isinstance(source_db, str) or not source_db:
        raise ValueError("Source de lecture SQL explicite requise")
    classe = type(objet)
    etat = {champ: copy.deepcopy(getattr(objet, champ))
            for champ in _ETAT_INIT if hasattr(objet, champ)}
    parametres = copy.deepcopy(parametres)

    def calcul():
        copie = classe.__new__(classe)
        copie.__dict__.update(copy.deepcopy(etat))
        db = GestionDB.DB(nomFichier=source_db, suffixe=None, pooling=False)
        try:
            copie.MAJ(DB=db, dictParametres=parametres)
            return {champ: copy.deepcopy(getattr(copie, champ))
                    for champ in _ATTRIBUTS if hasattr(copie, champ)}
        finally:
            db.Close()

    return calcul


def appliquer(objet, donnees):
    """Application exclusivement sur le thread GUI apres retour du worker."""
    if not est_compatible(objet):
        raise ValueError("Objet statistique non qualifie")
    if set(donnees) - set(_ATTRIBUTS):
        raise ValueError("Attribut inattendu dans le resultat statistique")
    for champ, valeur in donnees.items():
        setattr(objet, champ, valeur)
