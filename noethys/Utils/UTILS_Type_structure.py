# -*- coding: utf-8 -*-
"""Classification fonctionnelle des entites gerees dans les fiches familles.

Les codes servent uniquement a identifier le type du dossier Noethys.
Ils ne modifient ni les categories Helios, ni les comptes payeurs, ni
les prestations, inscriptions ou factures existantes.
"""

TYPES_STRUCTURE = (
    (None, u"Famille / particulier"),
    ("ecole", u"Ecole / etablissement scolaire"),
    ("association", u"Association"),
    ("association_sportive", u"Association sportive"),
    ("collectivite", u"Commune / collectivite"),
    ("institution", u"Institution / organisme public"),
    ("entreprise", u"Entreprise / organisme prive"),
    ("autre", u"Autre entite"),
)


def CodeDepuisIndex(index):
    """Convertit le choix de l'interface en code stable pour la base."""
    if type(index) is not int or not (0 <= index < len(TYPES_STRUCTURE)):
        raise ValueError("Indice de type d'entite inconnu")
    return TYPES_STRUCTURE[index][0]


def IndexDepuisCode(code):
    """Ne remplace jamais silencieusement un type deja enregistre."""
    if code is None or code == "":
        return 0
    for index, (cle, _) in enumerate(TYPES_STRUCTURE):
        if cle == code:
            return index
    raise ValueError("Type d'entite non reconnu : %r" % (code,))


def LibelleDepuisCode(code):
    return TYPES_STRUCTURE[IndexDepuisCode(code)][1]
