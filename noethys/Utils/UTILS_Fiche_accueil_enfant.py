# -*- coding: utf-8 -*-
"""Contrat metier pur de la fiche d'accueil par enfant (#436).

Projection en lecture seule : aucune migration, aucune ecriture SQL, aucune
lecture de donnees medicales et aucune publication sur le portail. Les sources
restent individus.aeeh, aeeh_periodes et le questionnaire repas existant.
L'appelant doit verifier les droits AVANT toute lecture de donnees sensibles.
"""
from datetime import date, datetime
import re


class FicheAccueilInvalide(ValueError):
    pass


AUTORISATIONS = (
    "piscine_baignade", "photos_prise", "photos_usage_interne",
    "photos_site_imprimes", "photos_reseaux_sociaux", "maquillage",
    "activites_physiques",
)
RUBRIQUES = ("repas", "aeeh", "pai", "autorisations")
TYPES_REPAS = ("standard", "sans_porc", "vegetarien", "sans_repas_pmsl")
ETATS_PAI = ("non_renseigne", "non", "signale", "document_a_verifier", "valide")


def _date(valeur, obligatoire=True):
    if valeur is None and not obligatoire:
        return None
    if type(valeur) is date:
        return valeur
    if isinstance(valeur, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        try:
            return date.fromisoformat(valeur)
        except ValueError:
            pass
    raise FicheAccueilInvalide("Date ISO invalide")


def _identifiant(valeur):
    if type(valeur) is not int or valeur <= 0:
        raise FicheAccueilInvalide("Identifiant enfant invalide")
    return valeur


def _trietat(valeur):
    if valeur is None:
        return "non_renseigne"
    if type(valeur) is int and valeur in (0, 1):
        return "oui" if valeur == 1 else "non"
    raise FicheAccueilInvalide("Etat attendu : NULL, 0 ou 1")


def _periode(debut, fin, reference):
    debut = _date(debut)
    fin = _date(fin, obligatoire=False)
    if fin is not None and fin < debut:
        raise FicheAccueilInvalide("Fin avant debut")
    return debut <= reference and (fin is None or reference <= fin)


def _horodatage(valeur):
    if not isinstance(valeur, str):
        raise FicheAccueilInvalide("Horodatage manquant")
    try:
        moment = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        raise FicheAccueilInvalide("Horodatage invalide")
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise FicheAccueilInvalide("Fuseau horaire obligatoire")
    return moment


def _acces(habilitations, rubrique):
    """Refus par defaut. Aucun repli sur les droits historiques permissifs."""
    return (isinstance(habilitations, dict) and
            habilitations.get(rubrique) is True)


def EtatAEEH(statut, periodes, au):
    """Ne deduit jamais individus.aeeh des periodes, ni l'inverse."""
    reference = _date(au)
    etat = _trietat(statut)
    if not isinstance(periodes, (tuple, list)):
        raise FicheAccueilInvalide("Periodes AEEH invalides")
    actives = []
    intervalles = []
    for ligne in periodes:
        if not isinstance(ligne, dict):
            raise FicheAccueilInvalide("Periode AEEH invalide")
        debut = _date(ligne.get("date_debut"))
        fin = _date(ligne.get("date_fin"), obligatoire=False)
        actives.append(_periode(debut, fin, reference))
        intervalles.append({"date_debut": debut.isoformat(),
                            "date_fin": fin.isoformat() if fin else None})
    return {"etat": etat, "periode_active": any(actives) if actives else None,
            "periodes": intervalles}


def EtatPAI(metadonnees, au):
    """Seulement des etats operationnels, jamais diagnostic ou document."""
    reference = _date(au)
    if metadonnees is None:
        return {"etat": "non_renseigne"}
    if not isinstance(metadonnees, dict):
        raise FicheAccueilInvalide("Metadonnees PAI invalides")
    etat = metadonnees.get("statut", "non_renseigne")
    if etat not in ETATS_PAI:
        raise FicheAccueilInvalide("Statut PAI invalide")
    if etat != "valide":
        return {"etat": etat}
    if not (metadonnees.get("document_verifie") is True and
            type(metadonnees.get("valide_par")) is int and
            metadonnees["valide_par"] > 0):
        return {"etat": "document_a_verifier"}
    debut = metadonnees.get("date_debut")
    fin = metadonnees.get("date_fin")
    actif = _periode(debut, fin, reference)
    intervalle = {"date_debut": _date(debut).isoformat(),
                  "date_fin": _date(fin, False).isoformat() if fin is not None else None}
    if actif:
        return dict(etat="valide", **intervalle)
    if fin is not None and _date(fin) < reference:
        return dict(etat="expire", **intervalle)
    return {"etat": "non_renseigne"}


def EtatAutorisation(historique, IDindividu, type_autorisation, au, perimetre="general"):
    """Selection de preuves datees, refus distinct de la non-reponse.

    Une preuve sans signataire, version de texte ou reference n'autorise
    jamais un OUI. En cas de reponses concurrentes, arbitrage explicite.
    """
    reference = _date(au)
    enfant = _identifiant(IDindividu)
    if not isinstance(historique, (tuple, list)):
        raise FicheAccueilInvalide("Historique d'autorisations invalide")
    if not isinstance(perimetre, str) or not perimetre.strip():
        raise FicheAccueilInvalide("Perimetre requis")
    candidats, expires = [], []
    for preuve in historique:
        if not isinstance(preuve, dict):
            raise FicheAccueilInvalide("Preuve d'autorisation invalide")
        if ((type(preuve.get("IDindividu")) is not int or preuve["IDindividu"] != enfant) or
                preuve.get("type") != type_autorisation or
                preuve.get("perimetre") != perimetre):
            continue
        horodatage = _horodatage(preuve.get("repondu_le"))
        if horodatage.date() > reference:
            continue
        valeur = _trietat(preuve.get("valeur"))
        debut, fin = _date(preuve.get("date_debut")), _date(preuve.get("date_fin"), False)
        if fin is not None and fin < debut:
            raise FicheAccueilInvalide("Periode d'autorisation invalide")
        valide = (preuve.get("autorite_verifiee") is True and
                  type(preuve.get("signataire")) is int and preuve["signataire"] > 0
                  and isinstance(preuve.get("texte_version"), str) and
                  bool(preuve["texte_version"].strip()) and
                  isinstance(preuve.get("preuve"), str) and bool(preuve["preuve"].strip()))
        entree = (horodatage, valeur, valide, debut, fin,
                  preuve["signataire"] if valide else None,
                  preuve["texte_version"] if valide else None,
                  preuve["preuve"] if valide else None)
        if debut <= reference and (fin is None or reference <= fin):
            candidats.append(entree)
        elif fin is not None and fin < reference:
            expires.append(entree)
    if not candidats:
        return {"etat": "expire" if expires else "non_renseigne"}
    instant = max(item[0] for item in candidats)
    dernieres = [item[1:] for item in candidats if item[0] == instant]
    if len(set(dernieres)) != 1 or not dernieres[0][1]:
        return {"etat": "a_verifier"}
    _valeur, _preuve_valide, debut, fin, _signataire, _version, _ref_preuve = dernieres[0]
    return {"etat": _valeur, "date_debut": debut.isoformat(),
            "date_fin": fin.isoformat() if fin else None}


def ConstruireFiche(IDindividu, au, habilitations=None, *, type_repas=None,
                    aeeh=None, periodes_aeeh=(), pai=None, autorisations=(),
                    perimetre="general"):
    """Projection minimale, sans effet de bord et portail desactive.

    Les valeurs sont *fournies* par un adaptateur de lecture controle. Les
    champs non habilites ne sont ni evalues ni renvoyes, meme indirectement.
    La lecture sur la base doit elle aussi etre bloquee pour ces rubriques.
    """
    enfant = _identifiant(IDindividu)
    reference = _date(au)
    fiche = {"IDindividu": enfant, "date_reference": reference.isoformat(),
             "portail": {rubrique: False for rubrique in RUBRIQUES}}
    if _acces(habilitations, "repas"):
        if type_repas is not None and type_repas not in TYPES_REPAS:
            raise FicheAccueilInvalide("Type de repas inconnu")
        fiche["repas"] = {"etat": type_repas or "non_renseigne"}
    else:
        fiche["repas"] = {"etat": "restreint"}
    fiche["aeeh"] = (EtatAEEH(aeeh, periodes_aeeh, reference)
                     if _acces(habilitations, "aeeh") else {"etat": "restreint"})
    fiche["pai"] = (EtatPAI(pai, reference)
                    if _acces(habilitations, "pai") else {"etat": "restreint"})
    fiche["autorisations"] = (
        {code: EtatAutorisation(autorisations, enfant, code, reference, perimetre)
         for code in AUTORISATIONS}
        if _acces(habilitations, "autorisations") else
        {code: {"etat": "restreint"} for code in AUTORISATIONS})
    return fiche
