# -*- coding: utf-8 -*-
"""Contrat de prevalidation des commandes avant PDF ou email (#430)."""

import ast
from datetime import date
from Utils.UTILS_Repas_totaux import TotauxRepas
from Utils import UTILS_Repas_regimes

ROLES = ("moins_6", "six_plus", "animateurs", "direction", "autres_adultes", "sans_porc")
CHAMPS = ("enfants_moins_6", "enfants_6_et_plus", "animateurs_repas",
          "direction_repas", "autres_adultes_repas", "sans_porc")
CLE_CHAMP = dict(zip(ROLES, CHAMPS))


def LireParametres(valeur):
    """Parametres d'un modele ou d'une colonne de commande, sans eval().

    Les parametres sont enregistres comme texte d'un dictionnaire Python
    litteral. Toute autre forme est refusee : aucun repli vers eval().
    """
    if valeur is None or isinstance(valeur, dict):
        return valeur
    if not isinstance(valeur, str):
        raise ValueError("Parametres de commande illisibles")
    if not valeur.strip():
        return None
    try:
        resultat = ast.literal_eval(valeur)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        raise ValueError("Parametres de commande illisibles : valeur non litterale refusee")
    if resultat is not None and not isinstance(resultat, dict):
        raise ValueError("Parametres de commande illisibles : dictionnaire attendu")
    return resultat


def ConstruireControle(donnees):
    """Construit une representation non nominative des cellules existantes.

    Refuse les roles redondants dans une meme plage ainsi que les erreurs de
    source. N'ecrit aucune donnee et n'infere pas les noms des colonnes.
    """
    colonnes = donnees.get("liste_colonnes", [])
    dates = [d for d in donnees.get("liste_dates", []) if isinstance(d, date)]
    cases = donnees.get("cases", {})
    if donnees.get("erreurs_sans_porc"):
        raise ValueError("Parametrage sans porc incomplet : %s" %
                         "; ".join(str(x) for x in donnees["erreurs_sans_porc"].values()))
    if donnees.get("erreurs_regimes"):
        raise ValueError("Repartition alimentaire indisponible : %s" %
                         "; ".join(sorted(set(str(x) for x in donnees["erreurs_regimes"].values()))))
    config = []
    non_classes = []
    for index, col in enumerate(colonnes):
        params = col.get("parametres") or {}
        role = params.get("role_repas", "aucun")
        if role not in ROLES and not UTILS_Repas_regimes.EstRoleRegime(role):
            if "numerique" in col.get("categorie", "") and "total" not in col.get("categorie", ""):
                non_classes.append(col.get("nom_colonne", "Colonne non classee"))
            continue
        site = str(params.get("site_directeur") or "").strip()
        service = str(params.get("service_directeur") or "").strip()
        if not site or not service:
            raise ValueError("Site et service manquants pour la colonne %s" % col.get("nom_colonne"))
        config.append((index, role, site, service))
    if not config:
        raise ValueError("Aucune colonne de repas classee : configurez les roles dans le modele")
    roles = set(role for _index, role, _site, _service in config)
    if "sans_porc" in roles and any(UTILS_Repas_regimes.EstRoleRegime(r) for r in roles):
        # Deux sources pour « sans porc » seraient ambigues pour le restaurateur.
        raise ValueError("Ne combinez pas « dont sans porc » et la repartition des regimes dans un meme modele")
    resultat = {}
    for row, jour in enumerate(dates):
        for col, role, site, service in config:
            cle = (jour, site, service)
            entree = resultat.setdefault(cle, {"date": jour, "site": site, "service": service,
                                                 "valeurs": {champ: 0 for champ in CHAMPS},
                                                 "regimes": {}, "cases": {}})
            if role in entree["cases"]:
                raise ValueError("Deux colonnes %s sur le meme site et service" % role)
            case = cases.get((row, col))
            if case is None:
                raise ValueError("Case de repas manquante dans la grille")
            valeur = case.GetValeur()
            if valeur is None:
                valeur = 0
            entree["cases"][role] = case
            if UTILS_Repas_regimes.EstRoleRegime(role):
                # Decomposition du total : jamais une entree de TotauxRepas.
                entree["regimes"][UTILS_Repas_regimes.ROLES_COLONNES[role]] = valeur
                if role == "regime_repas_apporte":
                    repartition_source = donnees.get("regimes", {}).get(colonnes[col].get("IDcolonne"), {})
                    entree["paniers_attendus"] = repartition_source.get(cle, {}).get("repas_apportes", 0)
                if "alertes_regimes" not in entree:
                    repartition = donnees.get("regimes", {}).get(colonnes[col].get("IDcolonne"))
                    entree["alertes_regimes"] = UTILS_Repas_regimes.SuggestionColonne(role, repartition, cle)[1]
                continue
            entree["valeurs"][CLE_CHAMP[role]] = valeur
            if role == "sans_porc":
                id_colonne = colonnes[col].get("IDcolonne")
                sous_totaux = donnees.get("sans_porc", {}).get(id_colonne, {})
                entree["non_renseignes"] = sous_totaux.get(jour, {}).get("non_renseignes", 0)
    lignes = []
    for key, entree in sorted(resultat.items()):
        entree["totaux"] = TotauxRepas(**entree["valeurs"])
        entree["colonnes_non_classees"] = tuple(non_classes)
        lignes.append(entree)
    return lignes


def AppliquerControle(lignes):
    """Applique uniquement les valeurs explicites du dialogue accepte."""
    for item in lignes:
        TotauxRepas(**item["valeurs"])
    for item in lignes:
        for role, case in item["cases"].items():
            if role in CLE_CHAMP:
                case.SetValeur(item["valeurs"][CLE_CHAMP[role]])
            elif UTILS_Repas_regimes.EstRoleRegime(role):
                # Correction explicite de la repartition dans le dialogue.
                case.SetValeur(item["regimes"][UTILS_Repas_regimes.ROLES_COLONNES[role]])


def ResumerControle(lignes):
    """Snapshot non nominatif des valeurs et du contexte confirmes.

    Une cellule changee apres validation invalide l'emission PDF/email.
    Aucun recalcul des suggestions ni lecture de la base n'est effectue ici.
    """
    resultat = []
    for ligne in lignes:
        totaux = TotauxRepas(**ligne["valeurs"])
        resultat.append({
            "date": ligne["date"],
            "site": ligne["site"],
            "service": ligne["service"],
            "totaux": dict(totaux),
            "non_renseignes": int(ligne.get("non_renseignes", 0)),
            "regimes": dict(ligne.get("regimes", {})),
        })
    return tuple(resultat)


def ErreursRegimes(lignes):
    """Repartitions saisies qui ne couvrent pas exactement le total du service.

    Une ligne sans colonne de regime n'est pas concernee. Les colonnes de
    regime d'un service doivent toutes etre presentes (standard, sans porc,
    vegetarien, non renseigne) et leur somme egaler le total des repas.
    """
    erreurs = []
    for ligne in lignes:
        regimes = ligne.get("regimes") or {}
        if not regimes:
            continue
        libelle = "%s %s %s" % (ligne["date"].strftime("%d/%m/%Y"), ligne["site"], ligne["service"])
        manquants = [c for c in UTILS_Repas_regimes.CHAMPS if c not in regimes]
        if manquants:
            erreurs.append("%s : colonnes de regime manquantes (%s)" % (libelle, ", ".join(manquants)))
            continue
        total = TotauxRepas(**ligne["valeurs"])["total_repas"]
        classes = sum(int(regimes[c]) for c in UTILS_Repas_regimes.CHAMPS)
        if classes != total:
            erreurs.append("%s : %d repas repartis pour %d repas commandes" % (libelle, classes, total))
        if "repas_apportes" in regimes and int(regimes["repas_apportes"]) != int(ligne.get("paniers_attendus", 0)):
            erreurs.append("%s : paniers apportes differents de la presence qualifiee" % libelle)
    return erreurs


def AcquittementsRegimes(lignes):
    """Points non bloquants a acquitter explicitement avant validation.

    Preferences non renseignees dans les quantites saisies, et anomalies de
    la source (age manquant, adulte avec consommation, multisite).
    """
    messages = []
    for ligne in lignes:
        if not ligne.get("regimes"):
            continue
        libelle = "%s %s %s" % (ligne["date"].strftime("%d/%m/%Y"), ligne["site"], ligne["service"])
        non_renseignes = int(ligne["regimes"].get("non_renseignes", 0))
        if non_renseignes:
            messages.append(u"%s : %d repas a preference non renseignee" % (libelle, non_renseignes))
        paniers = int(ligne["regimes"].get("repas_apportes", 0))
        if paniers:
            messages.append(u"%s : %d panier(s) apporte(s) par la famille, hors commande fournisseur" % (libelle, paniers))
        for alerte in ligne.get("alertes_regimes", []):
            if u"non renseign" not in alerte:
                messages.append(u"%s : %s" % (libelle, alerte))
    return messages


def ResumeDepuisDonnees(donnees):
    return ResumerControle(ConstruireControle(donnees))


def EstModeleType(donnees):
    return any((col.get("parametres") or {}).get("role_repas") not in
               (None, "", "aucun") for col in donnees.get("liste_colonnes", []))


def FusionTotauxPDF(resume):
    """Valeurs de fusion identiques pour le PDF et le brouillon de mail."""
    if not resume:
        return {}
    champs = {
        "{REPAS_TOTAL}": str(sum(x["totaux"]["total_repas"] for x in resume)),
        "{REPAS_6_PLUS}": str(sum(x["totaux"]["repas_6_et_plus"] for x in resume)),
        "{REPAS_ADULTES}": str(sum(x["totaux"]["total_adultes"] for x in resume)),
        "{REPAS_SANS_PORC}": str(sum(x["totaux"]["sans_porc"] for x in resume)),
    }
    if any(x.get("regimes") for x in resume):
        # Modele a regimes (jamais combine avec « dont sans porc ») : le
        # sans porc transmis est la categorie exclusive validee.
        for cle, champ in (("{REPAS_STANDARD}", "standard"), ("{REPAS_SANS_PORC}", "sans_porc"),
                           ("{REPAS_VEGETARIEN}", "vegetarien"), ("{REPAS_NON_RENSEIGNE}", "non_renseignes")):
            champs[cle] = str(sum(int(x["regimes"].get(champ, 0)) for x in resume))
    return champs
