"""AFAS V2: resolution explicite, sans acces DB ni import wx.

Le referentiel de Noethys est injecte par l'appelant; aucune correspondance
n'est devinee et aucune connexion de production n'est ouverte ici.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict


class ReferentialError(ValueError):
    pass


@dataclass(frozen=True)
class Group:
    activity_id: int
    group_id: int
    activity_name: str
    group_name: str


def parse_groups(rows):
    """Lit des lignes (IDactivite, IDgroupe, nom_activite, nom_groupe).

    Chaque IDgroupe appartient exactement a une activite. Les doublons
    d'identifiants avec contenus discordants sont refuses.
    """
    found = {}
    for row in rows:
        if len(row) != 4:
            raise ReferentialError('Ligne du referentiel incomplete')
        a, g, an, gn = row
        if type(a) is not int or type(g) is not int or a <= 0 or g <= 0:
            raise ReferentialError('IDactivite / IDgroupe invalides')
        if not isinstance(an, str) or not an.strip() or not isinstance(gn, str) or not gn.strip():
            raise ReferentialError('Libelle absent')
        item = Group(a, g, an, gn)
        if g in found and found[g] != item:
            raise ReferentialError('IDgroupe ambigu dans le referentiel')
        found[g] = item
    return found


def verify_mapping(catalog, rows, matrix, *, require_verified=True):
    """Valide un catalogue personnalise en confrontant CHAQUE lien au referentiel.

    catalog[(activite_logique, mode)][libelle] = {IDactivite, IDgroupe, verified}
    Les groupes peuvent reapparaitre dans plusieurs modes de la meme activite.
    Aucune modification de catalogue ou de base n'est effectuee.
    """
    reference = parse_groups(rows)
    logical_owners = defaultdict(set)
    result = {}
    for context, expected in matrix.items():
        if context not in catalog:
            raise ReferentialError('Contexte absent: %r' % (context,))
        entries = catalog[context]
        if not isinstance(entries, dict) or not entries:
            raise ReferentialError('Contexte vide')
        if 'Bais' in entries or (context[1] == 'Périscolaire' and any('Minicamps' in x for x in entries)):
            raise ReferentialError('Libelle ou mode incompatible')
        if context[0] == 'ALSH Ados' and any('Bais' in x and x != 'Bais Club Ados' for x in entries):
            raise ReferentialError('Libelle Bais Ados incompatible')
        resolved = {}
        for label, binding in entries.items():
            if not isinstance(label, str) or not label.strip() or not isinstance(binding, dict):
                raise ReferentialError('Lien invalide')
            a, g = binding.get('IDactivite'), binding.get('IDgroupe')
            if type(a) is not int or type(g) is not int or g not in reference or reference[g].activity_id != a:
                raise ReferentialError('Identifiant absent ou couple incoherent: ' + label)
            if require_verified and binding.get('verified') is not True:
                raise ReferentialError('Correspondance non verifiee: '+label)
            pair = (a, g)
            if pair in resolved.values():
                raise ReferentialError('Deux libelles pointent vers le meme groupe')
            resolved[label] = pair
            logical_owners[pair].add(context[0])
        result[context] = resolved
    if any(len(owners) > 1 for owners in logical_owners.values()):
        raise ReferentialError('Groupe partage entre ALSH et ALSH Ados')
    return result


def exact_scope(resolved_context, selected_labels, rows):
    """Produit exclusivement des couples (activite,groupe) verifies.

    Les filtres independants d'activites et groupes sont insuffisants pour
    definir seuls un perimetre: le consommateur doit tester chaque couple.
    """
    reference = parse_groups(rows)
    if not selected_labels or len(selected_labels) != len(set(selected_labels)):
        raise ReferentialError('Selection vide ou dupliquee')
    result = set()
    for label in selected_labels:
        if label not in resolved_context:
            raise ReferentialError('Groupe non autorise: '+str(label))
        pair = resolved_context[label]
        if pair[1] not in reference or reference[pair[1]].activity_id != pair[0]:
            raise ReferentialError('Couple devenu obsolete')
        result.add(pair)
    return frozenset(result)


def eligible_consumption(consumption, scope):
    """Filtre exact AVANT comptage, avec les deux ID obligatoires."""
    return (consumption['IDactivite'], consumption['IDgroupe']) in scope
