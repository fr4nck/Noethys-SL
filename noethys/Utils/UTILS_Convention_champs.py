#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fournisseur de champs pour la catégorie de document Convention.

Sépare strictement :
- l'accès aux données Noethys (représentant, planning, tarifs), qui
  réutilise les mêmes mécanismes que le reste de l'application
  (UTILS_Infos_individus, UTILS_Impression_reservations.GetDonnees) ;
- le calcul pur (détection de tarif, résumé de planning), testable sans
  base de données ni wx.

Ne modifie jamais aucune donnée Noethys : les valeurs calculées ici ne
servent qu'à préremplir des champs de convention, jamais à corriger des
prestations existantes. Aucune saison, aucune structure, aucun taux
n'est jamais rendu obligatoire : ce qui ne peut pas être déterminé
automatiquement reste vide, à saisir manuellement.
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from Utils.UTILS_Traduction import _

JOURS_SEMAINE = [
    _(u"Lundi"), _(u"Mardi"), _(u"Mercredi"), _(u"Jeudi"),
    _(u"Vendredi"), _(u"Samedi"), _(u"Dimanche"),
]

SEUIL_RUPTURE_ESTIVALE_JOURS = 45


def _date_simple(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.datetime.strptime(str(valeur)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _rupture_estivale(date_precedente, date_suivante):
    """Sépare deux saisons uniquement sur une vraie coupure d'été."""
    if date_precedente is None or date_suivante is None:
        return False
    ecart = (date_suivante - date_precedente).days
    return (
        ecart >= SEUIL_RUPTURE_ESTIVALE_JOURS
        and date_precedente.month in (5, 6, 7)
        and date_suivante.month in (8, 9, 10)
    )


def GetPeriodeParDefaut(IDfamille, date_reference=None, DB=None):
    """Déduit la période des consommations réelles, sans saison théorique."""
    fermer = DB is None
    if DB is None:
        import GestionDB
        DB = GestionDB.DB()
    DB.ExecuterReq(
        """SELECT DISTINCT consommations.date
        FROM consommations
        INNER JOIN rattachements
            ON rattachements.IDindividu = consommations.IDindividu
        WHERE rattachements.IDfamille=%d
        AND (consommations.etat IS NULL OR consommations.etat <> 'refus')
        ORDER BY consommations.date;""" % int(IDfamille)
    )
    dates = [_date_simple(row[0]) for row in DB.ResultatReq()]
    if fermer:
        DB.Close()
    dates = sorted({d for d in dates if d is not None})
    if not dates:
        return None, None

    groupes = [[dates[0]]]
    for date in dates[1:]:
        if _rupture_estivale(groupes[-1][-1], date):
            groupes.append([date])
        else:
            groupes[-1].append(date)

    reference = _date_simple(date_reference) or datetime.date.today()
    def distance(groupe):
        debut, fin = groupe[0], groupe[-1]
        if debut <= reference <= fin:
            return 0
        return min(abs((reference - debut).days), abs((reference - fin).days))
    groupe = min(groupes, key=distance)
    return groupe[0], groupe[-1]


def SaisonDepuisPeriode(date_debut, date_fin):
    debut = _date_simple(date_debut)
    fin = _date_simple(date_fin)
    if debut is None or fin is None:
        return u""
    if debut.year == fin.year:
        return str(debut.year)
    return u"%d-%d" % (debut.year, fin.year)


def ComposerAdresseConvention(rue=None, cp=None, ville=None):
    """Compose une adresse sans répéter CP/ville déjà inclus dans la rue."""
    rue = (rue or u"").strip()
    cp = (str(cp).strip() if cp not in (None, u"") else u"")
    ville = (ville or u"").strip()
    suffixe = u" ".join(partie for partie in (cp, ville) if partie).strip()
    lignes = [ligne.strip() for ligne in rue.splitlines() if ligne.strip()]
    if suffixe:
        suffixe_upper = suffixe.upper()
        if lignes and lignes[-1].upper().endswith(suffixe_upper):
            prefixe = lignes[-1][:-len(suffixe)].rstrip(u" ,-")
            if prefixe:
                lignes[-1] = prefixe
            else:
                lignes.pop()
        if not lignes or lignes[-1].upper() != suffixe_upper:
            lignes.append(suffixe)
    return u"\n".join(lignes)


# ---------------------------------------------------------------------------
# Représentant : réutilise le mécanisme historique {REPRESENTANT_RATTACHE_x_*}
# ---------------------------------------------------------------------------

def GetRepresentant(IDfamille, informations=None):
    """ Retourne {"nom", "prenom", "nom_complet"} du premier représentant
    rattaché réellement nommé (une personne physique, donc avec un
    prénom), en réutilisant le dict {REPRESENTANT_RATTACHE_x_*} déjà
    calculé par UTILS_Infos_individus.Informations pour la fiche Famille.

    Renvoie None si aucun représentant nommé n'est rattaché : c'est le
    cas, par exemple, d'une famille qui ne représente qu'une structure
    (titulaire sans prénom, aucun contact secondaire) -- l'identité du
    représentant doit alors être saisie manuellement, elle n'existe nulle
    part dans Noethys pour cette famille.
    """
    if informations is None:
        from Utils import UTILS_Infos_individus
        informations = UTILS_Infos_individus.Informations(
            qf=False, inscriptions=False, messages=False, infosMedicales=False,
            cotisationsManquantes=False, piecesManquantes=False,
            questionnaires=False, scolarite=False, cotisations=False,
        )
    dictValeurs = informations.GetDictValeurs(mode="famille", ID=IDfamille, formatChamp=True)
    try:
        nbre = int(dictValeurs.get("{NBRE_REPRESENTANTS_RATTACHES}", 0) or 0)
    except (TypeError, ValueError):
        nbre = 0

    for index in range(1, nbre + 1):
        prefixe = "REPRESENTANT_RATTACHE_%d" % index
        prenom = (dictValeurs.get("{%s_PRENOM}" % prefixe) or u"").strip()
        if not prenom:
            # Entrée institutionnelle (la structure elle-même) : pas une
            # personne à présenter comme représentant.
            continue
        nom = (dictValeurs.get("{%s_NOM}" % prefixe) or u"").strip()
        nom_complet = (dictValeurs.get("{%s_NOM_COMPLET}" % prefixe) or u"").strip()
        return {"nom": nom, "prenom": prenom, "nom_complet": nom_complet}
    return None


# ---------------------------------------------------------------------------
# Tarifs : automatique si déterministe, manuel sinon
# ---------------------------------------------------------------------------

def _duree_heures(heure_debut, heure_fin):
    try:
        h1, m1 = (int(x) for x in str(heure_debut).split(":")[:2])
        h2, m2 = (int(x) for x in str(heure_fin).split(":")[:2])
    except (ValueError, TypeError, AttributeError):
        return None
    minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
    if minutes <= 0:
        return None
    return minutes / 60.0


def _montant_decimal(montant):
    try:
        return Decimal(str(montant))
    except (InvalidOperation, TypeError):
        return None


def _iter_consommations(dictDonnees):
    for dictIndividu in dictDonnees.values():
        for IDactivite, dictActivite in dictIndividu["activites"].items():
            for date, dictDate in dictActivite["dates"].items():
                for IDunite, listeConso in dictDate["unites"].items():
                    for conso in listeConso:
                        yield IDactivite, date, conso


def DetecterTarifs(dictDonnees):
    """Analyse les prestations et expose aussi une provenance vérifiable."""
    tauxParActivite = {}
    preuvesParActivite = {}
    nomsActivites = {}
    for dictIndividu in dictDonnees.values():
        for IDactivite, dictActivite in dictIndividu["activites"].items():
            nomsActivites[IDactivite] = dictActivite.get("nom") or u""
            for date, dictDate in dictActivite["dates"].items():
                for listeConso in dictDate["unites"].values():
                    for conso in listeConso:
                        prestation = conso.get("prestation")
                        if not prestation or prestation.get("montant") is None:
                            continue
                        duree = _duree_heures(conso.get("heure_debut"), conso.get("heure_fin"))
                        if not duree:
                            continue
                        montant = _montant_decimal(prestation["montant"])
                        if montant is None:
                            continue
                        taux = (montant / Decimal(str(duree))).quantize(Decimal("0.01"))
                        tauxParActivite.setdefault(IDactivite, set()).add(taux)
                        preuvesParActivite.setdefault(IDactivite, []).append({
                            "date": date,
                            "heure_debut": conso.get("heure_debut"),
                            "heure_fin": conso.get("heure_fin"),
                            "duree_minutes": int(round(duree * 60)),
                            "montant": montant,
                            "taux": taux,
                            "IDconso": conso.get("IDconso"),
                            "IDprestation": conso.get("IDprestation"),
                            "label": prestation.get("label") or u"",
                        })
    tauxRetenus = {}
    ambigu = False
    for IDactivite, ensembleTaux in tauxParActivite.items():
        if len(ensembleTaux) == 1:
            tauxRetenus[IDactivite] = next(iter(ensembleTaux))
        else:
            ambigu = True
    commun = {
        "taux_par_activite": tauxRetenus,
        "preuves_par_activite": preuvesParActivite,
        "noms_activites": nomsActivites,
    }
    if ambigu or not tauxRetenus:
        commun["mode"] = "manuel"
        return commun
    valeursDistinctes = set(tauxRetenus.values())
    if len(valeursDistinctes) == 1:
        commun.update({"mode": "unique", "taux": next(iter(valeursDistinctes))})
        return commun
    commun["mode"] = "detail"
    return commun


def CompleterIDconsosProvenance(resultatTarifs, DB=None):
    """Complète les preuves tarifaires avec l'IDconso réel sans modifier
    le moteur Réservations historique.

    GetDonnees() expose déjà l'IDprestation utilisé pour chaque séance.
    On s'en sert comme clé de traçabilité pour retrouver l'IDconso en
    lecture seule. Une preuve qui ne possède pas d'IDprestation reste
    simplement sans IDconso : aucune valeur n'est inventée.
    """
    preuves = resultatTarifs.get("preuves_par_activite", {})
    ids_prestations = sorted({
        preuve.get("IDprestation")
        for liste in preuves.values()
        for preuve in liste
        if preuve.get("IDprestation") is not None
    })
    if not ids_prestations:
        return resultatTarifs

    fermer = DB is None
    if DB is None:
        import GestionDB
        DB = GestionDB.DB()
    try:
        req = """SELECT IDconso, IDprestation
        FROM consommations
        WHERE IDprestation IN (%s)
        ORDER BY IDconso;""" % ", ".join(str(int(ID)) for ID in ids_prestations)
        DB.ExecuterReq(req)
        correspondances = {}
        for IDconso, IDprestation in DB.ResultatReq():
            if IDprestation not in correspondances:
                correspondances[IDprestation] = IDconso
        for liste in preuves.values():
            for preuve in liste:
                if preuve.get("IDconso") is None:
                    preuve["IDconso"] = correspondances.get(preuve.get("IDprestation"))
    finally:
        if fermer:
            DB.Close()
    return resultatTarifs


def _format_decimal_fr(valeur):
    return (u"%.2f" % float(valeur)).replace(".", ",")


def _format_montant_euro(valeur):
    if valeur in (None, u""):
        return u""
    try:
        return u"%s €" % _format_decimal_fr(valeur)
    except (TypeError, ValueError, InvalidOperation):
        return str(valeur)


def FormateProvenanceTarif(IDactivite, taux, resultatTarifs):
    preuves = [
        preuve for preuve in resultatTarifs.get("preuves_par_activite", {}).get(IDactivite, [])
        if preuve.get("taux") == taux
    ]
    if not preuves:
        return u""
    preuve = preuves[0]
    activite = resultatTarifs.get("noms_activites", {}).get(IDactivite, u"")
    duree = FormateDureeHeures(preuve["duree_minutes"])
    date = _formate_date_fr(preuve["date"])
    texte = _(u"%s € / %s = %s €/h") % (
        _format_decimal_fr(preuve["montant"]), duree, _format_decimal_fr(taux)
    )
    details = []
    if activite:
        details.append(activite)
    if date:
        details.append(date)
    if preuve.get("IDconso") is not None:
        details.append(_(u"consommation #%s") % preuve["IDconso"])
    if preuve.get("IDprestation") is not None:
        details.append(_(u"prestation #%s") % preuve["IDprestation"])
    if details:
        texte += u" — " + u", ".join(details)
    if len(preuves) > 1:
        texte += _(u" (%d séances au même taux)") % len(preuves)
    return texte


# ---------------------------------------------------------------------------
# Résumé du planning# ---------------------------------------------------------------------------
# Résumé du planning : déterministe, factuel, sans invention
# ---------------------------------------------------------------------------

def _jour_semaine(date):
    try:
        if isinstance(date, datetime.date):
            return date.weekday()
        return datetime.datetime.strptime(str(date)[:10], "%Y-%m-%d").date().weekday()
    except (ValueError, TypeError):
        return None


def _formate_heure(heure):
    if not heure:
        return u"?"
    return str(heure)[:5].replace(":", "h")


def _formate_date_fr(date):
    try:
        if isinstance(date, datetime.date):
            d = date
        else:
            d = datetime.datetime.strptime(str(date)[:10], "%Y-%m-%d").date()
        return u"%02d/%02d/%04d" % (d.day, d.month, d.year)
    except (ValueError, TypeError):
        return str(date)


def FormateDureeHeures(minutes):
    return u"%dh%02d" % (minutes // 60, minutes % 60)


# ---------------------------------------------------------------------------
# Représentation métier structurée du planning (indépendante de wx/PDF)
# ---------------------------------------------------------------------------

# Au-delà de cet écart entre deux séances d'un même créneau récurrent
# (jour + horaire identiques), on considère qu'il s'agit de deux périodes
# distinctes (vacances, interruption, ...) plutôt que d'un seul bloc
# continu : un cycle scolaire qui reprend le même jour/horaire plusieurs
# mois plus tard (ex. reprise en mai d'un créneau utilisé en septembre)
# ne doit jamais être présenté comme ininterrompu.
SEUIL_RUPTURE_PERIODE_JOURS = 21


class ConventionPeriode(object):
    """ Un groupement cohérent de séances (même groupe/cycle, même jour de
    semaine, même horaire, sans rupture de plus de
    SEUIL_RUPTURE_PERIODE_JOURS jours) sur la période demandée.

    Structure métier pure : aucune dépendance à wx, à ReportLab ni au
    modèle .ndc. Les noms de champs sont volontairement simples pour
    rester lisibles depuis les tests et un futur rendu alternatif. """

    def __init__(self, groupe, activite, jour_semaine, heure_debut, heure_fin,
                 date_debut, date_fin, nombre_seances, duree_minutes, montant_total):
        self.groupe = groupe
        self.activite = activite
        self.jour_semaine = jour_semaine
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.nombre_seances = nombre_seances
        self.duree_minutes = duree_minutes
        self.montant_total = montant_total


def _decoupe_en_sous_periodes(dates_triees, seuil_jours=SEUIL_RUPTURE_PERIODE_JOURS):
    """ Coupe une liste de dates triées en sous-listes dès qu'un écart de
    plus de seuil_jours sépare deux séances consécutives. """
    if not dates_triees:
        return []
    groupes = [[dates_triees[0]]]
    for date in dates_triees[1:]:
        precedente = groupes[-1][-1]
        try:
            ecart = (_date_obj(date) - _date_obj(precedente)).days
        except (ValueError, TypeError):
            ecart = 0
        if ecart > seuil_jours:
            groupes.append([date])
        else:
            groupes[-1].append(date)
    return groupes


def _date_obj(date):
    if isinstance(date, datetime.date):
        return date
    return datetime.datetime.strptime(str(date)[:10], "%Y-%m-%d").date()


def ConstruirePeriodes(dictDonnees, seuil_rupture_jours=SEUIL_RUPTURE_PERIODE_JOURS):
    """ Construit la liste des ConventionPeriode à partir du même dict que
    UTILS_Impression_reservations.GetDonnees()/Impression().

    Ne fabrique aucune information absente des données fournies : les
    libellés utilisés (groupe, activité) sont ceux réellement enregistrés
    dans Noethys. Si une information figurant dans un ancien document
    papier (discipline précise, lieu de pratique, ...) n'existe dans
    aucune de ces données, elle n'apparaît nulle part ici : elle reste du
    contenu manuel du modèle ou de la saisie ponctuelle.
    """
    brut = {}
    for dictIndividu in dictDonnees.values():
        label_groupe = u" ".join(
            partie for partie in (dictIndividu.get("nom"), dictIndividu.get("prenom")) if partie
        ).strip()
        for IDactivite, dictActivite in dictIndividu["activites"].items():
            nom_activite = dictActivite.get("nom") or u""
            for date, dictDate in dictActivite["dates"].items():
                for listeConso in dictDate["unites"].values():
                    for conso in listeConso:
                        jour = _jour_semaine(date)
                        cle = (label_groupe, IDactivite, nom_activite, jour,
                               conso.get("heure_debut"), conso.get("heure_fin"))
                        brut.setdefault(cle, []).append((date, conso))

    periodes = []
    for (label_groupe, IDactivite, nom_activite, jour, heure_debut, heure_fin), occurrences in brut.items():
        occurrences.sort(key=lambda item: str(item[0]))
        dates = [d for d, _c in occurrences]
        for sous_dates in _decoupe_en_sous_periodes(dates, seuil_rupture_jours):
            ensemble_sous_dates = set(sous_dates)
            sous_occurrences = [(d, c) for d, c in occurrences if d in ensemble_sous_dates]
            duree_totale = 0
            montant_total = Decimal("0")
            for _d, conso in sous_occurrences:
                duree = _duree_heures(conso.get("heure_debut"), conso.get("heure_fin"))
                if duree:
                    duree_totale += int(round(duree * 60))
                prestation = conso.get("prestation")
                if prestation and prestation.get("montant") is not None:
                    montant = _montant_decimal(prestation["montant"])
                    if montant is not None:
                        montant_total += montant
            periodes.append(ConventionPeriode(
                groupe=label_groupe, activite=nom_activite, jour_semaine=jour,
                heure_debut=heure_debut, heure_fin=heure_fin,
                date_debut=sous_dates[0], date_fin=sous_dates[-1],
                nombre_seances=len(sous_dates), duree_minutes=duree_totale,
                montant_total=montant_total,
            ))

    periodes.sort(key=lambda p: (
        p.groupe, str(p.date_debut),
        p.jour_semaine if p.jour_semaine is not None else 7,
        p.heure_debut or u"",
    ))
    return periodes


def FormatePeriode(periode):
    """ Rend une ConventionPeriode en une ligne de texte factuelle, sans
    aucune donnée absente de la période elle-même. """
    if periode.jour_semaine is not None and periode.heure_debut and periode.heure_fin:
        ligne = _(u"%s de %s à %s") % (
            JOURS_SEMAINE[periode.jour_semaine],
            _formate_heure(periode.heure_debut), _formate_heure(periode.heure_fin))
    else:
        ligne = _(u"%d séance(s)") % periode.nombre_seances

    if periode.activite:
        ligne += u" : %s" % periode.activite

    if periode.nombre_seances > 1:
        ligne += _(u" (%d séances, du %s au %s)") % (
            periode.nombre_seances, _formate_date_fr(periode.date_debut), _formate_date_fr(periode.date_fin))
    else:
        ligne += _(u" (le %s)") % _formate_date_fr(periode.date_debut)

    if periode.duree_minutes:
        ligne += _(u" — %s au total") % FormateDureeHeures(periode.duree_minutes)

    return ligne


def FormateCreneauxConvention(listePeriodes):
    """Liste compacte des créneaux récurrents, sans répéter toutes les dates."""
    lignes = []
    vus = set()
    for periode in listePeriodes:
        cle = (periode.jour_semaine, periode.heure_debut, periode.heure_fin, periode.activite)
        if cle in vus:
            continue
        vus.add(cle)
        if periode.jour_semaine is not None and periode.heure_debut and periode.heure_fin:
            ligne = _(u"%s de %s à %s") % (
                JOURS_SEMAINE[periode.jour_semaine],
                _formate_heure(periode.heure_debut), _formate_heure(periode.heure_fin),
            )
        else:
            ligne = _(u"Créneau à préciser")
        if periode.activite:
            ligne += u" : %s" % periode.activite
        lignes.append(u"- " + ligne)
    return u"\n".join(lignes)


def FormatePeriodes(listePeriodes):
    """ Regroupe les périodes par groupe/cycle (ordre stable, déjà trié
    par ConstruirePeriodes) et produit le texte final. """
    blocs = []
    groupe_courant = object()  # sentinelle : ne matche aucun vrai groupe
    lignes_courantes = []

    def _cloture_bloc():
        if not lignes_courantes:
            return
        if groupe_courant:
            blocs.append(groupe_courant + u" :\n" + u"\n".join(u"- " + l for l in lignes_courantes))
        else:
            blocs.extend(lignes_courantes)

    for periode in listePeriodes:
        if periode.groupe != groupe_courant:
            _cloture_bloc()
            groupe_courant = periode.groupe
            lignes_courantes = []
        lignes_courantes.append(FormatePeriode(periode))
    _cloture_bloc()

    return u"\n\n".join(blocs)


def GetResumePlanning(dictDonnees):
    """ Construit le résumé du planning (texte + totaux) à partir du même
    dict que UTILS_Impression_reservations.GetDonnees()/Impression().
    Voir ConstruirePeriodes() pour la structure sous-jacente. """
    periodes = ConstruirePeriodes(dictDonnees)
    total_seances = sum(p.nombre_seances for p in periodes)
    total_minutes = sum(p.duree_minutes for p in periodes)
    total_montant = sum((p.montant_total for p in periodes), Decimal("0"))
    return {
        "detail": FormatePeriodes(periodes),
        "creneaux": FormateCreneauxConvention(periodes),
        "nbre_seances": total_seances,
        "total_heures_minutes": total_minutes,
        "total_montant": total_montant,
        "periodes": periodes,
    }


# ---------------------------------------------------------------------------
# Assemblage final du dictionnaire de champs {CODE} -> valeur
# ---------------------------------------------------------------------------

def GetChampsConvention(
    IDfamille, date_debut=None, date_fin=None, saison=None,
    listeIDindividus=None, DB=None, informations=None, overrides=None,
):
    """ Construit le dict {"{CODE}": valeur} pour la catégorie Convention.

    listeIDindividus : individus (créneaux/cycles/personnes) rattachés à
    la famille à prendre en compte pour le planning ; si None, tous les
    individus rattachés à la famille sont utilisés.

    Ne rend jamais aucun champ obligatoire : un représentant, une saison
    ou un tarif introuvables automatiquement donnent simplement un champ
    vide, à compléter manuellement avant génération.

    overrides : dict optionnel {"{CODE}": valeur} appliqué APRES tout le
    calcul automatique ci-dessus -- typiquement les corrections saisies
    par l'utilisateur dans DLG_Generation_convention (nom du
    représentant, fonction, date/lieu de signature, tarif horaire quand
    l'auto-détection est ambiguë ou absente). Une clé absente
    d'overrides, ou dont la valeur est None, laisse la valeur calculée
    automatiquement inchangée. Ceci ne modifie et n'enregistre jamais
    aucune donnée Noethys (prestations, consommations, tarifs, individus,
    familles) : le résultat n'est qu'un dictionnaire de champs pour la
    génération du PDF en cours.
    """
    from Utils import UTILS_Impression_reservations

    if listeIDindividus is None:
        listeIDindividus = GetIndividusRattaches(IDfamille, DB=DB)

    dictDonnees = UTILS_Impression_reservations.GetDonnees(
        listeIDindividus=listeIDindividus, date_debut=date_debut, date_fin=date_fin, DB=DB,
    )

    if informations is None:
        from Utils import UTILS_Infos_individus
        informations = UTILS_Infos_individus.Informations(
            qf=False, inscriptions=False, messages=False, infosMedicales=False,
            cotisationsManquantes=False, piecesManquantes=False,
            questionnaires=False, scolarite=False, cotisations=False,
        )

    # Champs Famille historiques ({FAMILLE_NOM}, {FAMILLE_RUE}, ...) :
    # réutilise tel quel le même dictionnaire que les autres catégories de
    # documents (UTILS_Infos_individus.Informations), sans reconstruire de
    # requête SQL dédiée. Une seule instance de Informations sert à la
    # fois à ce dictionnaire de base et à GetRepresentant() ci-dessous.
    champs = dict(informations.GetDictValeurs(mode="famille", ID=IDfamille, formatChamp=True))

    # Tous les champs optionnels {CONVENTION_*} sont explicitement
    # initialisés à une chaîne vide : le moteur [[SI {CHAMP}=->...]]
    # (utilisé par les modèles pour afficher un texte de repli quand une
    # donnée n'a pas pu être déterminée) ne détecte correctement "vide"
    # que si la clé existe dans le dict -- une clé absente ne déclenche
    # NI la branche "<>" (rempli) NI la branche "=" (vide), le bloc
    # [[SI ...]] entier disparaît silencieusement. Voir
    # DLG_Saisie_formule.ResolveurFormule. Posés après le dict Famille
    # pour que ces clés dédiées à la convention restent toujours
    # présentes, quel que soit le contenu du dict Famille.
    champs.update({
        "{IDFAMILLE}": IDfamille,
        "{CONVENTION_REPRESENTANT_NOM}": u"",
        "{CONVENTION_REPRESENTANT_PRENOM}": u"",
        "{CONVENTION_REPRESENTANT_NOM_COMPLET}": u"",
        "{CONVENTION_REPRESENTANT_FONCTION}": u"",
        "{CONVENTION_SAISON}": u"",
        "{CONVENTION_DATE_DEBUT}": u"",
        "{CONVENTION_DATE_FIN}": u"",
        "{CONVENTION_DATE_SIGNATURE}": u"",
        "{CONVENTION_LIEU_SIGNATURE}": u"",
        "{CONVENTION_TARIF_HORAIRE}": u"",
        "{CONVENTION_TARIF_ADULTE}": u"",
        "{CONVENTION_TARIF_ENFANT}": u"",
        "{CONVENTION_TARIF_HORAIRE_AFFICHE}": u"",
        "{CONVENTION_TARIF_ADULTE_AFFICHE}": u"",
        "{CONVENTION_TARIF_ENFANT_AFFICHE}": u"",
        "{CONVENTION_TARIF_HORAIRE_PROVENANCE}": u"",
        "{CONVENTION_TARIF_ADULTE_PROVENANCE}": u"",
        "{CONVENTION_TARIF_ENFANT_PROVENANCE}": u"",
        "{CONVENTION_ADRESSE_STRUCTURE}": u"",
    })

    champs["{CONVENTION_ADRESSE_STRUCTURE}"] = ComposerAdresseConvention(
        champs.get("{FAMILLE_RUE}"), champs.get("{FAMILLE_CP}"), champs.get("{FAMILLE_VILLE}")
    )

    representant = GetRepresentant(IDfamille, informations=informations)
    if representant is not None:
        champs["{CONVENTION_REPRESENTANT_NOM}"] = representant["nom"]
        champs["{CONVENTION_REPRESENTANT_PRENOM}"] = representant["prenom"]
        champs["{CONVENTION_REPRESENTANT_NOM_COMPLET}"] = representant["nom_complet"]

    if saison:
        champs["{CONVENTION_SAISON}"] = saison
    if date_debut:
        champs["{CONVENTION_DATE_DEBUT}"] = date_debut
    if date_fin:
        champs["{CONVENTION_DATE_FIN}"] = date_fin

    resume = GetResumePlanning(dictDonnees)
    champs["{CONVENTION_PLANNING_DETAIL}"] = resume["detail"]
    champs["{CONVENTION_PLANNING_CRENEAUX}"] = resume["creneaux"]
    champs["{CONVENTION_PLANNING_NBRE_SEANCES}"] = resume["nbre_seances"]
    champs["{CONVENTION_PLANNING_TOTAL_HEURES}"] = FormateDureeHeures(resume["total_heures_minutes"])
    champs["{CONVENTION_PLANNING_TOTAL_MONTANT}"] = float(resume["total_montant"])

    tarifs = DetecterTarifs(dictDonnees)
    CompleterIDconsosProvenance(tarifs, DB=DB)
    if tarifs["mode"] == "unique":
        champs["{CONVENTION_TARIF_HORAIRE}"] = float(tarifs["taux"])
        IDactivite = next(iter(tarifs["taux_par_activite"]))
        champs["{CONVENTION_TARIF_HORAIRE_PROVENANCE}"] = FormateProvenanceTarif(
            IDactivite, tarifs["taux"], tarifs
        )
    elif tarifs["mode"] == "detail":
        _CompleterTarifsAdulteEnfant(champs, tarifs, dictDonnees)

    if overrides:
        correspondance_provenance = {
            "{CONVENTION_TARIF_HORAIRE}": "{CONVENTION_TARIF_HORAIRE_PROVENANCE}",
            "{CONVENTION_TARIF_ADULTE}": "{CONVENTION_TARIF_ADULTE_PROVENANCE}",
            "{CONVENTION_TARIF_ENFANT}": "{CONVENTION_TARIF_ENFANT_PROVENANCE}",
        }
        for code, valeur in overrides.items():
            if valeur is not None:
                if code in correspondance_provenance and valeur != champs.get(code):
                    champs[correspondance_provenance[code]] = _(u"Saisie manuelle dans le générateur.")
                champs[code] = valeur

    for code, code_affiche in (
        ("{CONVENTION_TARIF_HORAIRE}", "{CONVENTION_TARIF_HORAIRE_AFFICHE}"),
        ("{CONVENTION_TARIF_ADULTE}", "{CONVENTION_TARIF_ADULTE_AFFICHE}"),
        ("{CONVENTION_TARIF_ENFANT}", "{CONVENTION_TARIF_ENFANT_AFFICHE}"),
    ):
        champs[code_affiche] = _format_montant_euro(champs.get(code))

    return champs, dictDonnees


def _CompleterTarifsAdulteEnfant(champs, tarifs, dictDonnees):
    """Expose les taux adulte/enfant uniquement quand le libellé le démontre."""
    tauxParActivite = tarifs["taux_par_activite"]
    nomsActivites = {}
    for dictIndividu in dictDonnees.values():
        for IDactivite, dictActivite in dictIndividu["activites"].items():
            nomsActivites[IDactivite] = dictActivite.get("nom") or u""
    for IDactivite, taux in tauxParActivite.items():
        nom = nomsActivites.get(IDactivite, u"").lower()
        if "enfant" in nom and not champs.get("{CONVENTION_TARIF_ENFANT}"):
            champs["{CONVENTION_TARIF_ENFANT}"] = float(taux)
            champs["{CONVENTION_TARIF_ENFANT_PROVENANCE}"] = FormateProvenanceTarif(
                IDactivite, taux, tarifs
            )
        elif "adulte" in nom and not champs.get("{CONVENTION_TARIF_ADULTE}"):
            champs["{CONVENTION_TARIF_ADULTE}"] = float(taux)
            champs["{CONVENTION_TARIF_ADULTE_PROVENANCE}"] = FormateProvenanceTarif(
                IDactivite, taux, tarifs
            )


def GetIndividusRattaches(IDfamille, DB=None):
    """ Individus (créneaux/cycles/personnes) rattachés à la famille.
    Fonction publique : réutilisée à la fois par GetChampsConvention() et
    par le bouton "Imprimer le planning" de DLG_Generation_convention,
    pour garantir que la Convention et le Planning séparé portent
    toujours exactement sur les mêmes individus. """
    fermer = DB is None
    if DB is None:
        import GestionDB
        DB = GestionDB.DB()
    DB.ExecuterReq(
        "SELECT IDindividu FROM rattachements WHERE IDfamille=%d;" % int(IDfamille)
    )
    listeIndividus = [row[0] for row in DB.ResultatReq()]
    if fermer:
        DB.Close()
    return listeIndividus