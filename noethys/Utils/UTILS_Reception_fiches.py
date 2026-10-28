# -*- coding: utf-8 -*-
"""Controle manuel des informations transmises sur les fiches Pêle-Mêle (#436).

Moteur pur : ni lecture/ecriture de base, ni OCR, ni accessoire wx/Qt,
ni synchronisation Connecthys. Les declarations sont saisies par l'agent
APRES lecture du document et confirmation de l'enfant concerne.
"""
from datetime import date
import re


class ReceptionFicheInvalide(ValueError):
    """Document/choix non qualifie : aucune mise a jour ne doit etre tentee."""


CHOIX_AEEH = ("absent", "oui", "non")
RUBRIQUES_MEDICALES = (
    "vaccinations", "allergies", "traitements", "pai", "consignes_sortie",
)


def _id_enfant(valeur):
    if type(valeur) is not int or valeur <= 0:
        raise ReceptionFicheInvalide("Enfant non identifie")
    return valeur


def _tri_etat(valeur):
    if valeur is None or (type(valeur) is int and valeur in (0, 1)):
        return valeur
    raise ReceptionFicheInvalide("Etat AEEH courant invalide")


def _date(valeur, facultative=False):
    if valeur is None and facultative:
        return None
    if type(valeur) is date:
        return valeur
    if type(valeur) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        try:
            return date.fromisoformat(valeur)
        except ValueError:
            pass
    raise ReceptionFicheInvalide("Date invalide (AAAA-MM-JJ attendue)")


def EvaluerDeclarationAEEH(IDindividu, valeur_actuelle, choix_parent="absent",
                            document_relu=False):
    """Compare le choix effectivement coche au champ `individus.aeeh`.

    `absent` signifie case vide ou illisible, JAMAIS une reponse Non et
    JAMAIS une demande d'effacement du champ. Les reponses sont uniquement
    des *propositions* pour le controle wx existant ; cette fonction ne
    persiste rien. Le document doit etre relu pour produire une proposition.
    """
    _id_enfant(IDindividu)
    courant = _tri_etat(valeur_actuelle)
    if choix_parent not in CHOIX_AEEH or type(choix_parent) is not str:
        raise ReceptionFicheInvalide("Choix parent AEEH non qualifie")
    if type(document_relu) is not bool:
        raise ReceptionFicheInvalide("Indicateur de relecture invalide")

    resultat = {"IDindividu": IDindividu, "etat_courant": courant,
                "action": "aucune", "valeur_proposee": None,
                "ecriture_autorisee": False}
    if choix_parent == "absent":
        resultat["action"] = "non_renseigne_sur_piece"
    elif not document_relu:
        resultat["action"] = "relecture_requise"
    else:
        proposee = 1 if choix_parent == "oui" else 0
        resultat["valeur_proposee"] = proposee
        resultat["action"] = "identique" if proposee == courant else "a_reporter"
    return resultat


def ComparerPeriodeAEEH(date_debut=None, date_fin=None, periodes_existantes=()):
    """Compare des dates declarees aux droits deja historises, sans ecrire.

    Une periode signalee par les parents n'est jamais un droit valide
    automatiquement. Une date de fin absente n'est pas une expiration.
    Une periode chevauchante mais differente attend arbitrage humain.
    """
    if not isinstance(periodes_existantes, (tuple, list)):
        raise ReceptionFicheInvalide("Historique AEEH invalide")
    existantes = []
    for periode in periodes_existantes:
        if not isinstance(periode, dict):
            raise ReceptionFicheInvalide("Periode existante invalide")
        debut = _date(periode.get("date_debut"))
        fin = _date(periode.get("date_fin"), facultative=True)
        if fin is not None and fin < debut:
            raise ReceptionFicheInvalide("Historique avec dates inversees")
        existantes.append((debut, fin))
    if date_debut is None and date_fin is None:
        return {"action": "dates_non_communiquees", "ecriture_autorisee": False}
    debut = _date(date_debut)
    fin = _date(date_fin, facultative=True)
    if fin is not None and fin < debut:
        raise ReceptionFicheInvalide("Fin de droit anterieure au debut")
    if (debut, fin) in existantes:
        action = "periode_deja_connue"
    elif any(debut <= (b or date.max) and a <= (fin or date.max)
             for a, b in existantes):
        action = "periode_a_arbitrer"
    else:
        action = "periode_a_verifier"
    return {"action": action, "date_debut": debut.isoformat(),
            "date_fin": fin.isoformat() if fin else None,
            "ecriture_autorisee": False}


def PreparerControlesMedicaux(document_relu=False):
    """Rappelle les sections de la fiche originale : pas de diagnostics ici.

    Un document recu, meme relu, n'etablit pas a lui seul le statut
    vaccinal ni la validite d'un PAI. Chaque rubrique doit etre verifiee
    dans l'onglet medical de Noethys, justificatifs compris.
    """
    if type(document_relu) is not bool:
        raise ReceptionFicheInvalide("Indicateur de relecture invalide")
    return {rubrique: "a_verifier" for rubrique in RUBRIQUES_MEDICALES}
