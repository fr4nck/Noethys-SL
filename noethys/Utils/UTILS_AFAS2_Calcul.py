# -*- coding: utf-8 -*-
"""AFAS V2 -- calcul des heures ALSH périscolaires et extrascolaires.

Moteur pur : il reçoit des données déjà chargées (consommations,
ouvertures, unités classées, périodes AEEH, séjours qualifiés, calendrier)
et n'importe ni wx ni GestionDB. Toutes les durées sont en secondes.

Règles contractuelles : UTILS_AFAS2_Conventions (traçabilité dans
docs/afas/TRACABILITE_CONVENTIONS_2025_2027.md). Aucune donnée n'est corrigée :
toute incohérence produit une anomalie ; une anomalie bloquante interdit la
validation et l'export déclaratif.
"""
import datetime

from Utils import UTILS_AFAS2_Conventions as Conventions
from Utils import UTILS_AFAS2_Calendrier as Calendrier

PERI = Conventions.PERISCOLAIRE
EXTRA = Conventions.EXTRASCOLAIRE

CATEGORIES = (
    ("accueil", "Accueil admissible (plage horaire)"),
    ("journee", "Journée facturée"),
    ("demi_journee", "Demi-journée facturée"),
    ("garderie_matin", "Garderie du matin"),
    ("garderie_soir", "Garderie du soir"),
    ("repas", "Repas"),
    ("sejour", "Séjour accessoire"),
    ("annexe", "Prestation annexe (sortie, supplément)"),
    ("exclue", "Unité exclue"),
    ("a_qualifier", "Unité à qualifier"),
)
CODES_CATEGORIES = tuple(code for code, libelle in CATEGORIES)
CATEGORIES_PLAGE_PERI = ("accueil", "journee", "demi_journee")
CATEGORIES_GARDERIE = ("garderie_matin", "garderie_soir")
CATEGORIES_FACTURATION_EXTRA = ("journee", "demi_journee")
CATEGORIES_IGNOREES = ("annexe", "exclue")
# Unités dont la plage horaire intervient dans un calcul : la plage
# réellement organisée doit être déclarée dans le preset et coïncider avec
# les horaires de l'unité dans Noethys.
CATEGORIES_A_PLAGE = ("accueil", "journee", "demi_journee", "repas", "garderie_matin", "garderie_soir")
# Unités constituant l'ouverture effective d'un site (amplitude extrascolaire).
CATEGORIES_OUVERTURE = ("accueil", "journee", "demi_journee", "repas")

INDICATEURS = (
    ("heures_realisees", "Heures de présence conventionnelles CAF"),
    ("heures_facturees", "Heures facturées CAF"),
    ("heures_realisees_aeeh", "Dont heures réalisées AEEH"),
    ("heures_facturees_aeeh", "Dont heures facturées AEEH"),
    ("heures_physiques", "Heures de présence physique (hors séjours)"),
    ("complement_inclusif_brut", "Complément inclusif : présence effective AEEH"),
    ("complement_inclusif_arrondi", "Complément inclusif : arrondi à l'heure supérieure par jour (hypothèse)"),
    ("garderie_matin", "Garderie matin"),
    ("garderie_soir", "Garderie soir"),
    ("garderie_total", "Total garderie"),
    ("heures_sejours", "Dont heures séjours (10 h par journée réalisée)"),
)
NON_APPLICABLES = {PERI: ("heures_facturees", "heures_facturees_aeeh", "heures_sejours"), EXTRA: ()}
# Nature de chaque indicateur dans la synthèse : « déclaratif » (actes à
# déclarer), « contrôle » (grandeur de vérification, jamais déclarée à la
# place d'un acte) ou « hypothèse » (modalité CAF non confirmée : jamais
# retenue automatiquement).
NATURES_INDICATEURS = {
    "heures_realisees": "déclaratif", "heures_facturees": "déclaratif",
    "heures_realisees_aeeh": "déclaratif", "heures_facturees_aeeh": "déclaratif",
    "heures_physiques": "contrôle", "complement_inclusif_brut": "contrôle",
    "complement_inclusif_arrondi": "hypothèse", "garderie_matin": "contrôle", "garderie_soir": "contrôle",
    "garderie_total": "contrôle", "heures_sejours": "déclaratif",
}

OPTIONS_DEFAUT = {"inclure_repas_meridien": True, "inclure_garderie_caf": False}


class ContexteInvalide(ValueError):
    pass


def Secondes(heure):
    """'HH:MM' -> secondes depuis minuit ; None si absent ; ValueError si invalide."""
    if heure in (None, ""):
        return None
    if isinstance(heure, datetime.time):
        return heure.hour * 3600 + heure.minute * 60
    texte = str(heure)
    morceaux = texte.split(":")
    if len(morceaux) < 2 or not all(m.isdigit() for m in morceaux[:2]):
        raise ValueError("Heure invalide : %r" % (heure,))
    heures, minutes = int(morceaux[0]), int(morceaux[1])
    if heures > 24 or minutes > 59 or (heures == 24 and minutes):
        raise ValueError("Heure invalide : %r" % (heure,))
    return heures * 3600 + minutes * 60


def _date(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    return datetime.date.fromisoformat(str(valeur)[:10])


def _intervalle(debut, fin):
    if debut is None or fin is None or debut >= fin:
        return None
    return (debut, fin)


def _fusion(intervalles):
    """Intervalles triés et fusionnés (chevauchants ou contigus)."""
    resultat = []
    for debut, fin in sorted(intervalles):
        if resultat and debut <= resultat[-1][1]:
            resultat[-1] = (resultat[-1][0], max(resultat[-1][1], fin))
        else:
            resultat.append((debut, fin))
    return resultat


def TextePlage(intervalle):
    debut, fin = intervalle
    return "%02d:%02d-%02d:%02d" % (debut // 3600, debut % 3600 // 60, fin // 3600, fin % 3600 // 60)


def _entier_ou_none(valeur):
    return None if valeur in (None, "") else valeur


class Calculateur(object):
    """Calcul d'une période pour un équipement et un mode.

    contexte = {
      mode, equipement, couples {(IDactivite, IDgroupe): site},
      unites {IDunite: {nom, type, heure_debut, heure_fin, categorie, plage_declaree ('HH:MM-HH:MM')}},
      etats_realise, etats_facture, options,
      calendrier (UTILS_AFAS2_Calendrier.Calendrier),
      samedis_avec_ecole {annee_scolaire: frozenset(dates)} (calendrier daté établi),
      ouvertures set((IDactivite, IDunite, IDgroupe, date)),
      aeeh {IDindividu: [(date_debut, date_fin ou None)]},
      sejours [{site, date_debut, date_fin, ...}] (déjà validés),
      regularisations [{IDprestation, IDindividu, IDfamille, IDactivite, date, label, IDfacture, facture_etat}]
        (prestations négatives non rattachées à une consommation),
      regularisations_qualifiees {str(IDprestation): {consommations_annulees: [IDconso], justification}},
      date_reference (date du calcul : réservations antérieures non pointées),
    }

    Chaque consommation porte, outre ses champs Noethys, la prestation qui
    la facture (IDprestation, prestation_montant, prestation_forfait,
    prestation_forfait_debut, prestation_IDindividu) et sa facture
    (IDfacture, facture_etat)."""

    def __init__(self, contexte):
        self.ctx = contexte
        if contexte["mode"] not in (PERI, EXTRA):
            raise ContexteInvalide("Mode d'accueil inconnu")
        self.mode = contexte["mode"]
        self.etats_realise = Calendrier.ValiderEtatsRealise(contexte["etats_realise"])
        self.etats_facture = Calendrier.ValiderEtatsFacture(contexte["etats_facture"])
        self.options = dict(OPTIONS_DEFAUT)
        self.options.update({cle: valeur for cle, valeur in contexte.get("options", {}).items() if cle in OPTIONS_DEFAUT})
        if not contexte["couples"]:
            raise ContexteInvalide("Aucun site sélectionné")
        self.couples = contexte["couples"]
        self.samedis = contexte.get("samedis_avec_ecole")
        self.unites = {}
        for IDunite, unite in contexte["unites"].items():
            if unite.get("categorie") not in CODES_CATEGORIES:
                raise ContexteInvalide("Unité %s : catégorie inconnue %r" % (IDunite, unite.get("categorie")))
            self.unites[IDunite] = self._preparer_unite(unite)
        self.sejours = [dict(s, debut=_date(s["date_debut"]), fin=_date(s["date_fin"])) for s in contexte.get("sejours", [])]
        # Ouvertures indexées par date (amplitude calculée une fois par jour et par site, pas par enfant).
        self._ouvertures_par_date = {}
        for IDactivite, IDunite, IDgroupe, jour in contexte["ouvertures"]:
            self._ouvertures_par_date.setdefault(jour, []).append((IDactivite, IDunite, IDgroupe))
        self._ouvertures_calculees = {}
        self._dates_comparees = set()
        self.regularisations_qualifiees = contexte.get("regularisations_qualifiees", {})
        self._consos_annulees = {}
        for IDprestation, qualification in self.regularisations_qualifiees.items():
            for IDconso in qualification["consommations_annulees"]:
                self._consos_annulees[IDconso] = IDprestation

    @staticmethod
    def _preparer_unite(unite):
        """Plage horaire utilisable seulement si elle coïncide avec la plage
        réellement organisée déclarée dans le preset."""
        unite = dict(unite, plage=None, motif_plage="")
        try:
            reelle = _intervalle(Secondes(unite.get("heure_debut")), Secondes(unite.get("heure_fin")))
        except ValueError:
            reelle = None
        if unite["categorie"] not in CATEGORIES_A_PLAGE:
            unite["plage"] = reelle
            return unite
        declaree = unite.get("plage_declaree")
        if not declaree:
            unite["motif_plage"] = "plage réellement organisée non déclarée dans le preset"
        elif reelle is None:
            unite["motif_plage"] = "horaires de l'unité absents ou incohérents dans Noethys"
        else:
            try:
                attendue = tuple(Secondes(h) for h in declaree.split("-"))
            except ValueError:
                attendue = None
            if attendue != reelle:
                unite["motif_plage"] = "horaires Noethys %s différents de la plage déclarée %s" % (TextePlage(reelle), declaree)
            else:
                unite["plage"] = reelle
        return unite

    # -- outils ----------------------------------------------------------
    def _aeeh(self, IDindividu, date):
        for debut, fin in self.ctx["aeeh"].get(IDindividu, []):
            if _date(debut) <= date and (fin is None or date <= _date(fin)):
                return True
        return False

    def _ouverture(self, date, couple):
        """(amplitude, plages, motif) de l'ouverture effective d'un site un jour donné.

        Seules les unités d'accueil, de journée, de demi-journée et de repas
        ouvertes pour ce site (couple activité-groupe) sont retenues. Leur
        union doit être continue : des plages disjointes ne sont jamais
        combinées en une amplitude « première ouverture → dernière fermeture »."""
        cle = (date, couple)
        if cle not in self._ouvertures_calculees:
            self._ouvertures_calculees[cle] = self._calculer_ouverture(date, couple)
        return self._ouvertures_calculees[cle]

    def _calculer_ouverture(self, date, couple):
        plages = []
        for IDactivite, IDunite, IDgroupe in self._ouvertures_par_date.get(date, []):
            if (IDactivite, IDgroupe) != couple:
                continue
            unite = self.unites.get(IDunite)
            if unite and unite["categorie"] in CATEGORIES_OUVERTURE:
                if unite["plage"] is None:
                    return None, [], "unité ouverte %s : %s" % (unite["nom"], unite["motif_plage"])
                plages.append(unite["plage"])
        if not plages:
            return None, [], "aucune ouverture d'accueil ce jour-là pour ce site"
        union = _fusion(plages)
        if len(union) > 1:
            return None, union, "ouverture discontinue (%s) : plages non combinables en une amplitude" % ", ".join(
                TextePlage(p) for p in union)
        return union[0][1] - union[0][0], union, ""

    def _comparer_implantations(self, date, anomalies):
        """Signale une fois par jour des amplitudes différentes entre les sites déclarés."""
        if date in self._dates_comparees:
            return
        self._dates_comparees.add(date)
        amplitudes = {}
        for couple, site in self.couples.items():
            amplitude, plages, motif = self._ouverture(date, couple)
            if plages:
                amplitudes[site] = (amplitude, plages)
        if len({a for a, p in amplitudes.values()}) > 1:
            detail = ", ".join("%s %s" % (site, " + ".join(TextePlage(p) for p in plages))
                               for site, (a, plages) in sorted(amplitudes.items()))
            self._anomalie_jour(anomalies, date, "Amplitudes d'ouverture différentes selon les sites : %s" % detail,
                                "Contrôle : chaque journée est valorisée avec l'amplitude de son propre site", False)

    def _sejour(self, site, date):
        for sejour in self.sejours:
            if sejour["site"] == site and sejour["debut"] <= date <= sejour["fin"]:
                return sejour
        return None

    # -- calcul ----------------------------------------------------------
    def Calculer(self, consommations, date_debut, date_fin):
        date_debut, date_fin = _date(date_debut), _date(date_fin)
        if date_fin < date_debut:
            raise ContexteInvalide("Période invalide")
        totaux = {cle: 0 for cle, libelle in INDICATEURS}
        anomalies, lignes, jours = [], [], []
        par_jour = {}
        self._usages_prestations = {}
        for conso in consommations:
            date = _date(conso["date"])
            if not date_debut <= date <= date_fin:
                continue
            if (conso["IDactivite"], conso["IDgroupe"]) not in self.couples:
                continue
            par_jour.setdefault((conso["IDindividu"], date), []).append(dict(conso, date=date))
            if conso.get("IDprestation") is not None:
                self._usages_prestations.setdefault(conso["IDprestation"], set()).add((conso["IDindividu"], date))
        for (IDindividu, date) in sorted(par_jour, key=lambda cle: (cle[1], str(cle[0]))):
            resultat = self._Jour(IDindividu, date, par_jour[(IDindividu, date)], anomalies, lignes)
            if resultat:
                jours.append(resultat)
                for cle in totaux:
                    totaux[cle] += resultat.get(cle, 0)
        if self.mode == EXTRA:
            self._Regularisations(par_jour, anomalies)
        totaux["garderie_total"] = totaux["garderie_matin"] + totaux["garderie_soir"]
        for cle in NON_APPLICABLES[self.mode]:
            totaux[cle] = None
        return {"indicateurs": totaux, "anomalies": anomalies, "lignes": lignes, "jours": jours,
                "bloquant": any(a["bloquante"] for a in anomalies)}

    def _anomalie(self, anomalies, conso, nature, consequence, bloquante=True):
        anomalies.append({
            "date": conso["date"], "IDindividu": conso["IDindividu"], "individu": conso.get("individu", ""),
            "IDconso": conso.get("IDconso"), "IDactivite": conso.get("IDactivite"), "IDgroupe": conso.get("IDgroupe"),
            "site": self.couples.get((conso.get("IDactivite"), conso.get("IDgroupe")), ""),
            "IDunite": conso.get("IDunite"), "unite": self.unites.get(conso.get("IDunite"), {}).get("nom", ""),
            "nature": nature, "consequence": consequence, "bloquante": bloquante})

    def _anomalie_jour(self, anomalies, date, nature, consequence, bloquante, IDindividu=None, individu=""):
        anomalies.append({"date": date, "IDindividu": IDindividu, "individu": individu, "IDconso": None, "IDactivite": None,
                          "IDgroupe": None, "site": "", "IDunite": None, "unite": "", "nature": nature,
                          "consequence": consequence, "bloquante": bloquante})

    def _Jour(self, IDindividu, date, consos, anomalies, lignes):
        mode_jour = Calendrier.ModeDate(date, self.ctx["calendrier"], self.samedis)
        retenues = []
        for conso in sorted(consos, key=lambda c: (str(c.get("heure_debut")), c.get("IDconso") or 0)):
            statut, motif = self._Qualifier(conso, mode_jour, anomalies)
            unite = self.unites.get(conso["IDunite"], {})
            lignes.append({"date": date, "IDindividu": IDindividu, "individu": conso.get("individu", ""),
                           "IDconso": conso.get("IDconso"), "IDactivite": conso["IDactivite"], "IDgroupe": conso["IDgroupe"],
                           "site": self.couples[(conso["IDactivite"], conso["IDgroupe"])],
                           "IDunite": conso["IDunite"], "unite": unite.get("nom", ""), "categorie": unite.get("categorie", ""),
                           "etat": conso.get("etat"), "mode_jour": mode_jour, "statut": statut, "motif": motif,
                           "IDprestation": conso.get("IDprestation"), "IDfacture": conso.get("IDfacture")})
            if statut == "retenue":
                retenues.append(conso)
        if not retenues:
            return None
        self._Doublons(retenues, anomalies)
        if self.mode == PERI:
            return self._JourPeri(IDindividu, date, retenues, anomalies)
        return self._JourExtra(IDindividu, date, retenues, anomalies, mode_jour)

    def _Qualifier(self, conso, mode_jour, anomalies):
        """('retenue' | 'exclue' | 'bloquee', motif) avant tout calcul.

        Une consommation d'un jour hors du mode déclaré est exclue avant tout
        contrôle de classement ou de statut : elle relève de l'autre
        déclaration et n'y bloque rien."""
        unite = self.unites.get(conso["IDunite"])
        statut_etat = Calendrier.ClasserStatut(conso.get("etat"))
        if statut_etat == "technique":
            return "exclue", "état technique %s" % conso.get("etat")
        if unite is not None and unite["categorie"] in CATEGORIES_IGNOREES:
            return "exclue", "unité %s" % unite["categorie"]
        if mode_jour == Calendrier.INCONNU:
            calendrier = self.ctx["calendrier"]
            manquantes = calendrier.PeriodesManquantes(Calendrier.AnneeScolaire(conso["date"]))
            if manquantes:
                self._anomalie(anomalies, conso, "Calendrier des vacances incomplet pour l'année scolaire (manque : %s)"
                               % ", ".join(manquantes), "Calcul bloqué : saisir les vacances scolaires dans Noethys")
            else:
                self._anomalie(anomalies, conso, "Samedi déclaré avec école pendant des vacances scolaires",
                               "Calcul bloqué : corriger le calendrier des samedis avec école")
            return "bloquee", "calendrier incomplet"
        if mode_jour == Calendrier.SAMEDI_A_QUALIFIER:
            self._anomalie(anomalies, conso, "Samedi hors vacances : calendrier daté des samedis avec école non établi "
                           "pour l'année scolaire %d-%d" % (Calendrier.AnneeScolaire(conso["date"]),
                                                            Calendrier.AnneeScolaire(conso["date"]) + 1),
                           "Calcul bloqué : saisir les samedis avec école (ou aucun) dans le référentiel")
            return "bloquee", "samedi à qualifier"
        if self.mode == PERI and mode_jour != PERI:
            return "exclue", "hors période périscolaire (%s)" % mode_jour
        if self.mode == EXTRA and mode_jour == PERI:
            return "exclue", "hors période extrascolaire"
        if unite is None:
            self._anomalie(anomalies, conso, "Unité non classée dans le preset", "Calcul bloqué : classer l'unité")
            return "bloquee", "unité inconnue"
        if statut_etat == "inconnu":
            self._anomalie(anomalies, conso, "Statut de consommation inconnu ou absent : %r" % (conso.get("etat"),),
                           "Calcul bloqué : corriger le statut dans Noethys")
            return "bloquee", "statut inconnu"
        if unite["categorie"] == "a_qualifier":
            self._anomalie(anomalies, conso, "Unité à qualifier", "Calcul bloqué : classer l'unité dans le preset")
            return "bloquee", "unité à qualifier"
        if self.mode == EXTRA:
            site = self.couples[(conso["IDactivite"], conso["IDgroupe"])]
            sejour = self._sejour(site, conso["date"])
            if unite["categorie"] == "sejour" and sejour is None:
                self._anomalie(anomalies, conso, "Consommation de séjour hors séjour qualifié",
                               "Calcul bloqué : qualifier le séjour dans le référentiel ou reclasser l'unité")
                return "bloquee", "séjour non qualifié"
            if mode_jour == Calendrier.DIMANCHE and unite["categorie"] != "sejour":
                self._anomalie(anomalies, conso, "Dimanche hors séjour", "Non éligible (art. 1.1) : exclue", bloquante=False)
                return "exclue", "dimanche hors séjour"
        if self.mode == PERI and unite["categorie"] == "sejour":
            self._anomalie(anomalies, conso, "Unité de séjour en périscolaire", "Calcul bloqué : reclasser l'unité")
            return "bloquee", "séjour en périscolaire"
        if (conso["IDactivite"], conso["IDunite"], conso["IDgroupe"], conso["date"]) not in self.ctx["ouvertures"]:
            self._anomalie(anomalies, conso, "Consommation un jour sans ouverture de l'unité pour ce groupe",
                           "Calcul bloqué : vérifier le calendrier d'ouverture ou la consommation")
            return "bloquee", "sans ouverture"
        if conso.get("etat") == "reservation" and conso["date"] < self.ctx["date_reference"]:
            self._anomalie(anomalies, conso, "Pointage en attente sur une date passée",
                           "Calcul bloqué : pointer la présence ou l'absence")
            return "bloquee", "pointage en attente"
        return "retenue", ""

    def _Doublons(self, consos, anomalies):
        vues = {}
        for conso in consos:
            if conso["IDunite"] in vues and self._chevauchent(vues[conso["IDunite"]], conso):
                self._anomalie(anomalies, conso, "Même unité saisie deux fois (consommations %s et %s)"
                               % (vues[conso["IDunite"]].get("IDconso"), conso.get("IDconso")),
                               "Calcul bloqué : supprimer le doublon")
            vues.setdefault(conso["IDunite"], conso)
        sites = {}
        for conso in consos:
            sites.setdefault((conso["IDactivite"], conso["IDgroupe"]), []).append(conso)
        if len(sites) > 1:
            groupes = list(sites.values())
            for i, premier in enumerate(groupes):
                for second in groupes[i + 1:]:
                    for a in premier:
                        for b in second:
                            if self._chevauchent(a, b, plages=True):
                                self._anomalie(anomalies, b, "Même enfant sur deux sites aux mêmes horaires "
                                               "(consommations %s et %s)" % (a.get("IDconso"), b.get("IDconso")),
                                               "Calcul bloqué : une seule présence possible")

    def _chevauchent(self, a, b, plages=False):
        ia = self._plage_unite(a) if plages else self._horaires(a) or self._plage_unite(a)
        ib = self._plage_unite(b) if plages else self._horaires(b) or self._plage_unite(b)
        if ia is None or ib is None:
            return not plages
        return ia[0] < ib[1] and ib[0] < ia[1]

    def _plage_unite(self, conso):
        return self.unites[conso["IDunite"]]["plage"]

    def _horaires(self, conso):
        try:
            return _intervalle(Secondes(conso.get("heure_debut")), Secondes(conso.get("heure_fin")))
        except ValueError:
            return None

    def _physique(self, consos, anomalies, bloquant_si_absent):
        intervalles = []
        for conso in consos:
            horaire = self._horaires(conso)
            if horaire is None:
                if bloquant_si_absent:
                    self._anomalie(anomalies, conso, "Présence effective sans horaires valides",
                                   "Calcul bloqué : compléter les horaires de la consommation")
                continue
            intervalles.append(horaire)
        return Conventions.DureeUnion(intervalles) if intervalles else 0

    def _plages(self, consos, anomalies):
        plages = []
        for conso in consos:
            plage = self._plage_unite(conso)
            if plage is None:
                self._anomalie(anomalies, conso, "Plage horaire de l'unité inutilisable : %s"
                               % self.unites[conso["IDunite"]]["motif_plage"],
                               "Calcul bloqué : déclarer la plage réellement organisée et la faire correspondre à l'unité")
                continue
            plages.append(plage)
        return plages

    def _JourPeri(self, IDindividu, date, consos, anomalies):
        realise = [c for c in consos if c.get("etat") in self.etats_realise]
        categories_caf = list(CATEGORIES_PLAGE_PERI)
        if self.options["inclure_repas_meridien"]:
            categories_caf.append("repas")
        if self.options["inclure_garderie_caf"]:
            categories_caf.extend(CATEGORIES_GARDERIE)
        plages = self._plages([c for c in realise if self.unites[c["IDunite"]]["categorie"] in categories_caf], anomalies)
        heures = Conventions.PresencePeriscolaireJour(plages)
        physique = self._physique(realise, anomalies, False)
        matin = Conventions.DureeUnion(self._plages([c for c in realise if self.unites[c["IDunite"]]["categorie"] == "garderie_matin"], anomalies))
        soir = Conventions.DureeUnion(self._plages([c for c in realise if self.unites[c["IDunite"]]["categorie"] == "garderie_soir"], anomalies))
        return self._Resultat(IDindividu, date, PERI, heures, 0, physique, matin, soir, 0, None, [], [])

    def _JourExtra(self, IDindividu, date, consos, anomalies, mode_jour):
        sejours = [c for c in consos if self.unites[c["IDunite"]]["categorie"] == "sejour"]
        autres = [c for c in consos if self.unites[c["IDunite"]]["categorie"] != "sejour"]
        if sejours and autres:
            self._anomalie(anomalies, autres[0], "Séjour et accueil le même jour pour un enfant",
                           "Calcul bloqué : une journée ne peut relever des deux règles")
        heures_sejour = Conventions.SEJOUR_JOURNEE if any(c.get("etat") in self.etats_realise for c in sejours) else 0
        presents = [c for c in autres if c.get("etat") in self.etats_realise]
        categories_presence = ["accueil", "journee", "demi_journee", "repas"]
        if self.options["inclure_garderie_caf"]:
            categories_presence.extend(CATEGORIES_GARDERIE)
        physique = self._physique([c for c in presents if self.unites[c["IDunite"]]["categorie"] in categories_presence], anomalies, True)
        matin = Conventions.DureeUnion(self._plages([c for c in presents if self.unites[c["IDunite"]]["categorie"] == "garderie_matin"], anomalies))
        soir = Conventions.DureeUnion(self._plages([c for c in presents if self.unites[c["IDunite"]]["categorie"] == "garderie_soir"], anomalies))
        facture, amplitude, plages, justification = self._FactureOption2(autres, anomalies, date)
        # Séjours : actes fixés à 10 h par journée réalisée, intégrés aux actes
        # réalisés et facturés (jamais cumulés avec une journée d'accueil :
        # séjour et accueil le même jour sont bloquants).
        return self._Resultat(IDindividu, date, EXTRA, physique + heures_sejour, facture + heures_sejour, physique,
                              matin, soir, heures_sejour, amplitude, plages, justification)

    def _PrestationIndeterminee(self, conso):
        """Motif rendant indéterminable l'unité facturée par la prestation de la consommation, ou ''."""
        if conso.get("prestation_montant") is not None and conso["prestation_montant"] < 0:
            return "prestation de montant négatif rattachée à la consommation"
        if _entier_ou_none(conso.get("prestation_forfait")) or _entier_ou_none(conso.get("prestation_forfait_debut")):
            return "prestation forfaitaire : nombre de journées facturées non déterminable"
        if conso.get("quantite") not in (None, 1):
            return "quantité facturée %r" % (conso.get("quantite"),)
        if conso.get("prestation_IDindividu") not in (None, 0, conso["IDindividu"]):
            return "prestation facturée pour un autre enfant (%s)" % conso["prestation_IDindividu"]
        if len(self._usages_prestations.get(conso["IDprestation"], ())) > 1:
            return "prestation partagée entre plusieurs jours ou plusieurs enfants"
        return ""

    def _FactureOption2(self, consos, anomalies, date):
        """(heures facturées, amplitude, plages d'ouverture, justification).

        Chaque journée ou demi-journée retenue est justifiée par une prestation
        figurant sur une facture non annulée, dont la quantité est déterminée
        (une prestation = une unité, un jour, un enfant). Une remise ne retire
        pas l'unité ; un montant n'est jamais converti en heures."""
        prestations = {}
        for conso in consos:
            categorie = self.unites[conso["IDunite"]]["categorie"]
            facturee = conso.get("IDfacture") is not None and conso.get("facture_etat") != "annulation"
            if categorie not in CATEGORIES_FACTURATION_EXTRA:
                if facturee and categorie == "accueil":
                    self._anomalie(anomalies, conso, "Unité horaire facturée en extrascolaire",
                                   "Calcul bloqué : l'option n°2 ne retient que la journée ou la demi-journée")
                continue
            if conso.get("etat") not in self.etats_facture or not facturee:
                continue
            if conso.get("IDconso") in self._consos_annulees:
                continue  # annulée par une régularisation qualifiée
            if conso.get("IDprestation") is None:
                self._anomalie(anomalies, conso, "Facture sans prestation identifiable",
                               "Calcul bloqué : unité facturée non justifiable")
                return 0, None, [], []
            motif = self._PrestationIndeterminee(conso)
            if motif:
                self._anomalie(anomalies, conso, "Facturation indéterminable : %s" % motif,
                               "Calcul bloqué : la journée ou demi-journée facturée ne peut être justifiée")
                return 0, None, [], []
            cle = conso["IDprestation"]
            if cle in prestations:
                self._anomalie(anomalies, conso, "Une prestation couvre plusieurs unités journée/demi-journée "
                               "(consommations %s et %s) : nature facturée indéterminable"
                               % (prestations[cle][1].get("IDconso"), conso.get("IDconso")),
                               "Calcul bloqué : vérifier la tarification de la journée")
                return 0, None, [], []
            prestations[cle] = (categorie, conso)
        if not prestations:
            return 0, None, [], []
        natures = [categorie for categorie, conso in prestations.values()]
        premiere = list(prestations.values())[0][1]
        if natures.count("journee") > 1 or ("journee" in natures and "demi_journee" in natures) or natures.count("demi_journee") > 2:
            self._anomalie(anomalies, premiere, "Facturation supérieure à une journée pour un enfant (%s)" % ", ".join(sorted(natures)),
                           "Calcul bloqué : doublon de facturation")
            return 0, None, [], []
        couples = {(c["IDactivite"], c["IDgroupe"]) for categorie, c in prestations.values()}
        if len(couples) > 1:
            self._anomalie(anomalies, premiere, "Journée facturée sur plusieurs sites le même jour",
                           "Calcul bloqué : amplitude de référence indéterminable")
            return 0, None, [], []
        self._comparer_implantations(date, anomalies)
        amplitude, plages, motif = self._ouverture(date, couples.pop())
        textes = [TextePlage(p) for p in plages]
        if amplitude is None:
            self._anomalie(anomalies, premiere, "Amplitude d'ouverture indéterminable : %s" % motif,
                           "Calcul bloqué : vérifier les ouvertures et les plages des unités")
            return 0, None, textes, []
        if amplitude < Conventions.DUREE_MINIMALE_JOURNEE_EXTRA:
            self._anomalie(anomalies, premiere, "Amplitude d'ouverture inférieure à 2 h",
                           "Calcul bloqué : journée non conforme à l'art. 2-1")
            return 0, amplitude, textes, []
        justification = ["%s P%s F%s" % ("journée" if categorie == "journee" else "demi-journée", c["IDprestation"], c["IDfacture"])
                         for categorie, c in prestations.values()]
        return sum(Conventions.DureeJourneeOption2(nature, amplitude) for nature in natures), amplitude, textes, justification

    def _Regularisations(self, par_jour, anomalies):
        """Prestations négatives non rattachées à une consommation (avoirs,
        régularisations) concernant un enfant ou une famille du périmètre :
        elles peuvent annuler une journée facturée sans que Noethys le relie à
        une consommation. Bloquant tant qu'elles ne sont pas qualifiées."""
        enfants = {IDindividu for IDindividu, date in par_jour}
        familles = {c.get("IDfamille") for consos in par_jour.values() for c in consos if c.get("IDfamille")}
        activites = {IDactivite for IDactivite, IDgroupe in self.couples}
        for regul in self.ctx.get("regularisations", []):
            if str(regul["IDprestation"]) in self.regularisations_qualifiees:
                continue
            if regul.get("IDactivite") and regul["IDactivite"] not in activites:
                continue  # autre activité (cantine, adhésion...) : sans effet sur les unités déclarées
            if regul.get("IDindividu") in enfants or (not regul.get("IDindividu") and regul.get("IDfamille") in familles):
                self._anomalie_jour(anomalies, _date(regul["date"]),
                                    "Régularisation négative non rattachée à une consommation (prestation %s « %s »)"
                                    % (regul["IDprestation"], regul.get("label") or ""),
                                    "Calcul bloqué : qualifier la régularisation (consommations annulées ou aucune) "
                                    "dans le référentiel", True, regul.get("IDindividu"), regul.get("individu", ""))

    def _Resultat(self, IDindividu, date, mode, realise, facture, physique, matin, soir, sejour, amplitude, plages, justification):
        aeeh = self._aeeh(IDindividu, date)
        return {
            "date": date, "IDindividu": IDindividu, "mode": mode, "aeeh": aeeh, "amplitude": amplitude,
            "plages_ouverture": " + ".join(plages), "justification_facture": " ; ".join(justification),
            "heures_realisees": realise, "heures_facturees": facture,
            "heures_realisees_aeeh": realise if aeeh else 0, "heures_facturees_aeeh": facture if aeeh else 0,
            "heures_physiques": physique,
            "complement_inclusif_brut": physique if aeeh else 0,
            "complement_inclusif_arrondi": Conventions.ArrondiHeureSuperieure(physique) if aeeh else 0,
            "garderie_matin": matin, "garderie_soir": soir, "heures_sejours": sejour,
        }
