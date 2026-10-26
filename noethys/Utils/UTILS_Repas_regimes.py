# -*- coding: utf-8 -*-
"""Repartition exclusive des repas par regime alimentaire (#430, lot 1).

Categories : standard / sans porc / vegetarien / non renseigne.
Source unique : une question individuelle Noethys a liste deroulante dont
trois choix explicites sont associes aux trois regimes. Une absence de
reponse reste « non renseignee » : elle n'est jamais assimilee a standard.

Module pur, sans base ni interface : utilisable par wx et Qt. Il ne lit ni
n'ecrit les quantites d'une commande ; les anciens modeles « dont sans
porc » (UTILS_Repas_alimentaires) restent inchanges et ne sont pas convertis.

Personnes de 18 ans et plus ayant une consommation : exclues de la
repartition des enfants (meme borne que la suggestion « 6 ans et plus »)
et seulement signalees ; les repas adultes restent saisis manuellement et
ne rejoignent la repartition que par IntegrerAdultes, classes
explicitement ou « non renseignes ».
"""

from datetime import date, datetime

from Utils.UTILS_Encadrement import AgeAuJour
from Utils.UTILS_Repas_totaux import EntierNaturel


CATEGORIES = ("standard", "sans_porc", "vegetarien")
PANIER = "sans_repas_pmsl"  # opt-in des nouveaux modeles uniquement
CHAMPS = CATEGORIES + ("non_renseignes",)
CONTROLE_REGIME = "liste_deroulante"
ETATS_REPAS = ("reservation", "present")
AGE_ADULTE = 18


class RegimeInvalide(ValueError):
    """ Reponse alimentaire inconnue ou contradictoire : aucun comptage. """


def ConfigurationRegimes(question, correspondance, controle):
    """Valide le contrat question/choix ; renvoie (IDquestion, {regime: IDchoix})."""
    try:
        id_question = int(question)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Question de regime alimentaire non identifiee")
    if isinstance(question, bool) or id_question <= 0:
        raise ValueError("Identifiant de question de regime invalide")
    if controle != CONTROLE_REGIME:
        raise ValueError("Le regime alimentaire exige une question a liste deroulante (choix unique)")
    if not isinstance(correspondance, dict) or set(correspondance) not in (set(CATEGORIES), set(CATEGORIES + (PANIER,))):
        raise ValueError("Associez exactement les choix standard, sans porc et vegetarien")
    choix = {}
    for regime in CATEGORIES + ((PANIER,) if PANIER in correspondance else ()):
        valeur = correspondance[regime]
        try:
            id_choix = int(valeur)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Choix %s non identifie" % regime)
        if isinstance(valeur, bool) or id_choix <= 0:
            raise ValueError("Identifiant de choix %s invalide" % regime)
        choix[regime] = id_choix
    if len(set(choix.values())) != len(choix):
        raise ValueError("Un meme choix ne peut pas representer deux regimes")
    return id_question, choix


def ClasserReponse(reponse, correspondance, repas_pmsl_prevu=None):
    """Regime d'une reponse brute ; « non_renseignes » si absente ou vide.

    Leve RegimeInvalide pour un choix inconnu ou plusieurs choix distincts.
    """
    if reponse is None:
        return "standard" if PANIER in correspondance and repas_pmsl_prevu is True else "non_renseignes"
    elements = [e.strip() for e in str(reponse).split(";") if e.strip()]
    if not elements:
        return "standard" if PANIER in correspondance and repas_pmsl_prevu is True else "non_renseignes"
    if len(set(elements)) > 1:
        raise RegimeInvalide("contradictoire")
    inverse = dict((str(v), k) for k, v in correspondance.items())
    if elements[0] not in inverse:
        raise RegimeInvalide("inconnue")
    return inverse[elements[0]]


def NormaliserServices(services):
    """{(IDgroupe, IDunite): (site, service)} avec site et service explicites.

    Refuse deux libelles qui ne different que par la casse ou les espaces,
    pour que la cle (date, site, service) reste non ambigue.
    """
    resultat = {}
    vus = {}
    for (groupe, unite), cible in dict(services).items():
        site, service = (str(x or "").strip() for x in cible)
        if not site or not service:
            raise ValueError("Site et service obligatoires pour chaque unite de repas")
        for libelle in (site, service):
            if vus.setdefault(libelle.casefold(), libelle) != libelle:
                raise ValueError("Libelles de site/service ambigus : %r" % libelle)
        resultat[(int(groupe), int(unite))] = (site, service)
    return resultat


def _jour(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    raise ValueError("Consommation sans date valide")


def RepartitionRegimes(consommations, reponses, correspondance, services, naissances, repas_pmsl_prevu=None):
    """Repartit les enfants ayant un repas par (date, site, service).

    consommations : dicts date, IDindividu, IDgroupe, IDunite, etat.
    reponses : {IDindividu: reponse brute} (une seule par individu).
    correspondance : {regime: IDchoix} valide par ConfigurationRegimes.
    services : {(IDgroupe, IDunite): (site, service)}.
    naissances : {IDindividu: date de naissance}.

    Une personne n'est comptee qu'une fois par cle, quels que soient ses
    groupes, unites ou etats. Sortie non nominative.
    """
    services = NormaliserServices(services)
    personnes = {}
    for ligne in consommations:
        if ligne.get("etat") not in ETATS_REPAS:
            continue
        cible = services.get((ligne.get("IDgroupe"), ligne.get("IDunite")))
        if cible is None:
            continue
        individu = ligne.get("IDindividu")
        if individu is None:
            raise ValueError("Consommation sans individu valide")
        cle = (_jour(ligne.get("date")),) + cible
        personnes.setdefault(cle, set()).add(individu)

    # Une meme personne sur deux sites pour une meme date/service.
    sites = {}
    for (jour, site, service), ids in personnes.items():
        for individu in ids:
            sites.setdefault((jour, service, individu), set()).add(site)

    sortie = {}
    anomalies = {"inconnue": 0, "contradictoire": 0}
    for cle, ids in personnes.items():
        jour, site, service = cle
        entree = dict((champ, 0) for champ in CHAMPS)
        entree.update({"date": jour, "site": site, "service": service,
                       "adultes_avec_conso": 0, "ages_inconnus": 0, "multisites": 0,
                       "repas_apportes": 0, "repas_apportes_moins_6": 0,
                       "repas_apportes_six_plus": 0})
        for individu in ids:
            if len(sites[(jour, service, individu)]) > 1:
                entree["multisites"] += 1
            age = AgeAuJour(naissances.get(individu), jour)
            if age is None:
                entree["ages_inconnus"] += 1
                continue
            if age >= AGE_ADULTE:
                entree["adultes_avec_conso"] += 1
                continue
            try:
                type_repas = ClasserReponse(reponses.get(individu), correspondance, repas_pmsl_prevu)
                if PANIER in correspondance and repas_pmsl_prevu is False and type_repas != PANIER:
                    raise RegimeInvalide("inconnue")  # pas de fournisseur prevu
                if type_repas == PANIER:
                    entree["repas_apportes"] += 1
                    entree["repas_apportes_moins_6" if age < 6 else "repas_apportes_six_plus"] += 1
                else:
                    entree[type_repas] += 1
            except RegimeInvalide as exc:
                anomalies[str(exc)] += 1
        entree["total_repas"] = sum(entree[champ] for champ in CHAMPS)
        entree["enfants_presents_midi_classes"] = entree["total_repas"] + entree["repas_apportes"]
        # Meme regle que la suggestion par age : pas de suggestion partielle.
        entree["complet"] = entree["ages_inconnus"] == 0
        VerifierInvariant(entree)
        sortie[cle] = entree
    if anomalies["inconnue"] or anomalies["contradictoire"]:
        raise RegimeInvalide("Reponses alimentaires a corriger : %d inconnue(s), %d contradictoire(s)"
                             % (anomalies["inconnue"], anomalies["contradictoire"]))
    return sortie


def VerifierInvariant(valeurs):
    total = sum(EntierNaturel(valeurs[champ], champ) for champ in CHAMPS)
    if total != EntierNaturel(valeurs["total_repas"], "total_repas"):
        raise ValueError("Repartition incoherente : %d repas classes pour %d"
                         % (total, valeurs["total_repas"]))
    return True


def IntegrerAdultes(entree, adultes_repas, classification=None):
    """Ajoute les repas adultes saisis a une repartition d'enfants.

    Seuls les adultes classes explicitement rejoignent un regime ; le reste
    est « non renseigne ». Aucun adulte n'est deduit des consommations.
    """
    adultes = EntierNaturel(adultes_repas, "adultes_repas")
    classes = {}
    for regime, nombre in (classification or {}).items():
        if regime not in CATEGORIES:
            raise ValueError("Regime adulte inconnu : %s" % regime)
        classes[regime] = EntierNaturel(nombre, regime)
    if sum(classes.values()) > adultes:
        raise ValueError("Plus d'adultes classes que de repas adultes")
    resultat = dict((champ, EntierNaturel(entree[champ], champ)) for champ in CHAMPS)
    for regime, nombre in classes.items():
        resultat[regime] += nombre
    resultat["non_renseignes"] += adultes - sum(classes.values())
    resultat["total_repas"] = EntierNaturel(entree["total_repas"], "total_repas") + adultes
    resultat["dont_adultes"] = adultes
    VerifierInvariant(resultat)
    return resultat


def EcartsAvecCommande(validees, actuelles):
    """Liste les ecarts (cle, champ, valide, actuel) sans rien modifier.

    Une commande validee garde ses quantites : un changement de preference
    ulterieur est seulement signale, jamais applique automatiquement.
    """
    ecarts = []
    for cle in sorted(set(validees) | set(actuelles)):
        avant = validees.get(cle, {})
        apres = actuelles.get(cle, {})
        for champ in CHAMPS + ("total_repas",):
            if avant.get(champ, 0) != apres.get(champ, 0):
                ecarts.append((cle, champ, avant.get(champ, 0), apres.get(champ, 0)))
    return ecarts


# --- Raccordement aux colonnes de commande (lot 2A) -------------------------

# Roles de colonnes de repartition ; distincts des ROLES RC8 additifs.
ROLES_COLONNES = {
    "regime_standard": "standard",
    "regime_sans_porc": "sans_porc",
    "regime_vegetarien": "vegetarien",
    "regime_non_renseigne": "non_renseignes",
    "regime_repas_apporte": "repas_apportes",
}


def EstRoleRegime(role):
    return role in ROLES_COLONNES


def EstVarianteAlimentaire(role):
    """Colonnes qui decomposent le total : jamais additionnees au total."""
    return role == "sans_porc" or EstRoleRegime(role)


def ParametresColonne(parametres):
    """(IDquestion, {regime: IDchoix}, site, service) d'une colonne de regime.

    Controle de forme uniquement : la conformite a la base est verifiee
    par UTILS_Repas_source lors de la lecture.
    """
    parametres = parametres or {}
    question, choix = ConfigurationRegimes(parametres.get("question_regime"),
                                           parametres.get("choix_regimes"), CONTROLE_REGIME)
    site = str(parametres.get("site_directeur") or "").strip()
    service = str(parametres.get("service_directeur") or "").strip()
    if not site or not service:
        raise ValueError("Site et service obligatoires pour une colonne de regime")
    if PANIER in choix:
        from Utils.UTILS_Repas_2c import CouvreMidi
        debut, fin = parametres.get("midi_debut"), parametres.get("midi_fin")
        CouvreMidi([(debut, fin)], debut, fin)  # refuse tout horaire inconnu
        if type(parametres.get("repas_pmsl_prevu")) is not bool:
            raise ValueError("Confirmez si la formule inclut normalement le repas PMSL")
    return question, choix, site, service


def GroupesColonnesRegimes(colonnes):
    """Regroupe les colonnes de regime pour une seule lecture par parametrage.

    Renvoie (groupes, erreurs) : groupes = [{"question", "choix", "services",
    "colonnes"}] ; erreurs = {IDcolonne: message}. Une unite ne peut pas
    appartenir a deux couples site/service dans un meme groupe.
    """
    groupes, erreurs = {}, {}
    for colonne in colonnes:
        parametres = colonne.get("parametres") or {}
        if not EstRoleRegime(parametres.get("role_repas")):
            continue
        try:
            question, choix, site, service = ParametresColonne(parametres)
        except ValueError as exc:
            erreurs[colonne["IDcolonne"]] = str(exc)
            continue
        nouveau = PANIER in choix
        midi = (parametres.get("midi_debut"), parametres.get("midi_fin")) if nouveau else None
        offre = parametres.get("repas_pmsl_prevu") if nouveau else None
        cle = (question, tuple(sorted(choix.items())), midi, offre)
        groupe = groupes.setdefault(cle, {"question": question, "choix": choix,
                                          "services": {}, "colonnes": [], "conflit": None,
                                          "plage_midi": midi, "repas_pmsl_prevu": offre,
                                          "roles": set()})
        groupe["roles"].add(parametres.get("role_repas"))
        groupe["colonnes"].append(colonne["IDcolonne"])
        for groupe_unite in parametres.get("unites", []):
            groupe_unite = tuple(int(x) for x in groupe_unite)
            if groupe["services"].setdefault(groupe_unite, (site, service)) != (site, service):
                groupe["conflit"] = "Une unite est rattachee a deux sites/services differents"
    resultat = []
    for groupe in groupes.values():
        if PANIER in groupe["choix"] and "regime_repas_apporte" not in groupe["roles"]:
            for ID in groupe["colonnes"]:
                erreurs[ID] = "Ajoutez une colonne « Repas apporte par la famille » hors fournisseur"
            continue
        groupe.pop("roles", None)
        if groupe.pop("conflit") is not None:
            for ID in groupe["colonnes"]:
                erreurs[ID] = "Une unite est rattachee a deux sites/services differents"
            continue
        resultat.append(groupe)
    return resultat, erreurs


def SuggestionColonne(role, repartition, cle, erreur=None):
    """(suggestion ou None, alertes) pour une case de colonne de regime.

    Aucune suggestion si le parametrage est en erreur ou la repartition
    incomplete : une valeur partielle ne doit pas paraitre fiable.
    """
    if erreur:
        return None, [u"Répartition alimentaire indisponible : %s" % erreur]
    entree = (repartition or {}).get(cle)
    if entree is None:
        return 0, []
    alertes = []
    if not entree["complet"]:
        alertes.append(u"Répartition incomplète : %d âge(s) manquant(s)" % entree["ages_inconnus"])
    if entree["adultes_avec_conso"]:
        alertes.append(u"%d personne(s) de 18 ans et plus avec consommation, hors répartition"
                       % entree["adultes_avec_conso"])
    if entree["multisites"]:
        alertes.append(u"%d personne(s) inscrite(s) sur plusieurs sites pour ce service"
                       % entree["multisites"])
    if entree["non_renseignes"]:
        alertes.append(u"%d préférence(s) non renseignée(s)" % entree["non_renseignes"])
    if not entree["complet"]:
        return None, alertes
    if entree.get("repas_apportes"):
        alertes.append(u"%d panier(s) familial(aux), hors commande fournisseur" % entree["repas_apportes"])
    return entree[ROLES_COLONNES[role]], alertes
