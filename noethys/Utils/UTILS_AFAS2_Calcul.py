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

INDICATEURS = (
    ("heures_realisees", "Heures de présence conventionnelles CAF"),
    ("heures_facturees", "Heures facturées CAF"),
    ("heures_realisees_aeeh", "Dont heures réalisées AEEH"),
    ("heures_facturees_aeeh", "Dont heures facturées AEEH"),
    ("heures_physiques", "Heures de présence physique"),
    ("complement_inclusif_brut", "Complément inclusif : présence effective AEEH"),
    ("complement_inclusif_arrondi", "Complément inclusif : arrondi à l'heure supérieure par jour"),
    ("garderie_matin", "Garderie matin"),
    ("garderie_soir", "Garderie soir"),
    ("garderie_total", "Total garderie"),
    ("heures_sejours", "Heures séjours (10 h par journée réalisée)"),
)
NON_APPLICABLES = {PERI: ("heures_facturees", "heures_facturees_aeeh", "heures_sejours"), EXTRA: ()}

OPTIONS_DEFAUT = {"samedis_avec_ecole": False, "inclure_repas_meridien": True, "inclure_garderie_caf": False}


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


class Calculateur(object):
    """Calcul d'une période pour un équipement et un mode.

    contexte = {
      mode, equipement, couples {(IDactivite, IDgroupe): site},
      unites {IDunite: {nom, type, heure_debut, heure_fin, categorie}},
      etats_realise, etats_facture, options,
      calendrier (UTILS_AFAS2_Calendrier.Calendrier),
      ouvertures set((IDactivite, IDunite, IDgroupe, date)),
      aeeh {IDindividu: [(date_debut, date_fin ou None)]},
      sejours [{site, date_debut, date_fin, ...}] (déjà validés),
      date_reference (date du calcul : réservations antérieures non pointées),
    }"""

    def __init__(self, contexte):
        self.ctx = contexte
        if contexte["mode"] not in (PERI, EXTRA):
            raise ContexteInvalide("Mode d'accueil inconnu")
        self.mode = contexte["mode"]
        self.etats_realise = Calendrier.ValiderEtats(contexte["etats_realise"], "Statuts du réalisé")
        self.etats_facture = Calendrier.ValiderEtats(contexte["etats_facture"], "Statuts du facturé")
        self.options = dict(OPTIONS_DEFAUT)
        self.options.update(contexte.get("options", {}))
        if not contexte["couples"]:
            raise ContexteInvalide("Aucun site sélectionné")
        self.couples = contexte["couples"]
        self.unites = {}
        for IDunite, unite in contexte["unites"].items():
            if unite.get("categorie") not in CODES_CATEGORIES:
                raise ContexteInvalide("Unité %s : catégorie inconnue %r" % (IDunite, unite.get("categorie")))
            self.unites[IDunite] = dict(unite, debut=Secondes(unite.get("heure_debut")),
                                        fin=Secondes(unite.get("heure_fin")))
        self.sejours = [dict(s, debut=_date(s["date_debut"]), fin=_date(s["date_fin"])) for s in contexte.get("sejours", [])]

    # -- outils ----------------------------------------------------------
    def _aeeh(self, IDindividu, date):
        for debut, fin in self.ctx["aeeh"].get(IDindividu, []):
            if _date(debut) <= date and (fin is None or date <= _date(fin)):
                return True
        return False

    def _amplitude(self, date):
        """Amplitude d'ouverture effective de l'équipement ce jour-là : étendue des
        plages des unités d'accueil ouvertes pour les groupes déclarés."""
        plages = []
        for IDactivite, IDunite, IDgroupe, jour in self.ctx["ouvertures"]:
            if jour != date or (IDactivite, IDgroupe) not in self.couples:
                continue
            unite = self.unites.get(IDunite)
            if unite and unite["categorie"] in ("accueil", "journee", "demi_journee"):
                plage = _intervalle(unite["debut"], unite["fin"])
                if plage is None:
                    return None, "plage horaire absente pour l'unité ouverte %s" % unite["nom"]
                plages.append(plage)
        if not plages:
            return None, "aucune ouverture d'accueil ce jour-là"
        return max(f for d, f in plages) - min(d for d, f in plages), ""

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
        for conso in consommations:
            date = _date(conso["date"])
            if not date_debut <= date <= date_fin:
                continue
            if (conso["IDactivite"], conso["IDgroupe"]) not in self.couples:
                continue
            par_jour.setdefault((conso["IDindividu"], date), []).append(dict(conso, date=date))
        for (IDindividu, date) in sorted(par_jour, key=lambda cle: (cle[1], str(cle[0]))):
            resultat = self._Jour(IDindividu, date, par_jour[(IDindividu, date)], anomalies, lignes)
            if resultat:
                jours.append(resultat)
                for cle in totaux:
                    totaux[cle] += resultat.get(cle, 0)
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

    def _Jour(self, IDindividu, date, consos, anomalies, lignes):
        mode_jour = Calendrier.ModeDate(date, self.ctx["calendrier"], self.options["samedis_avec_ecole"])
        retenues = []
        for conso in sorted(consos, key=lambda c: (str(c.get("heure_debut")), c.get("IDconso") or 0)):
            statut, motif = self._Qualifier(conso, mode_jour, anomalies)
            unite = self.unites.get(conso["IDunite"], {})
            lignes.append({"date": date, "IDindividu": IDindividu, "individu": conso.get("individu", ""),
                           "IDconso": conso.get("IDconso"), "IDactivite": conso["IDactivite"], "IDgroupe": conso["IDgroupe"],
                           "site": self.couples[(conso["IDactivite"], conso["IDgroupe"])],
                           "IDunite": conso["IDunite"], "unite": unite.get("nom", ""), "categorie": unite.get("categorie", ""),
                           "etat": conso.get("etat"), "mode_jour": mode_jour, "statut": statut, "motif": motif})
            if statut == "retenue":
                retenues.append(conso)
        if not retenues:
            return None
        self._Doublons(retenues, anomalies)
        if self.mode == PERI:
            return self._JourPeri(IDindividu, date, retenues, anomalies)
        return self._JourExtra(IDindividu, date, retenues, anomalies, mode_jour)

    def _Qualifier(self, conso, mode_jour, anomalies):
        """('retenue' | 'exclue' | 'bloquee', motif) avant tout calcul."""
        unite = self.unites.get(conso["IDunite"])
        if unite is None:
            self._anomalie(anomalies, conso, "Unité non classée dans le preset", "Calcul bloqué : classer l'unité")
            return "bloquee", "unité inconnue"
        statut_etat = Calendrier.ClasserStatut(conso.get("etat"))
        if statut_etat == "technique":
            return "exclue", "état technique %s" % conso.get("etat")
        if statut_etat == "inconnu":
            self._anomalie(anomalies, conso, "Statut de consommation inconnu ou absent : %r" % (conso.get("etat"),),
                           "Calcul bloqué : corriger le statut dans Noethys")
            return "bloquee", "statut inconnu"
        if unite["categorie"] in CATEGORIES_IGNOREES:
            return "exclue", "unité %s" % unite["categorie"]
        if mode_jour == Calendrier.INCONNU:
            self._anomalie(anomalies, conso, "Calendrier des vacances absent pour l'année scolaire",
                           "Calcul bloqué : saisir le calendrier des vacances dans Noethys")
            return "bloquee", "calendrier absent"
        if unite["categorie"] == "a_qualifier":
            self._anomalie(anomalies, conso, "Unité à qualifier", "Calcul bloqué : classer l'unité dans le preset")
            return "bloquee", "unité à qualifier"
        if self.mode == PERI and mode_jour != PERI:
            return "exclue", "hors période périscolaire (%s)" % mode_jour
        if self.mode == EXTRA:
            if mode_jour == PERI:
                return "exclue", "hors période extrascolaire"
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
            unite = self.unites[conso["IDunite"]]
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
        unite = self.unites[conso["IDunite"]]
        return _intervalle(unite["debut"], unite["fin"])

    def _horaires(self, conso):
        try:
            return _intervalle(Secondes(conso.get("heure_debut")), Secondes(conso.get("heure_fin")))
        except ValueError:
            return None

    def _physique(self, consos, anomalies, bloquant_si_absent):
        intervalles = []
        for conso in consos:
            try:
                horaire = _intervalle(Secondes(conso.get("heure_debut")), Secondes(conso.get("heure_fin")))
            except ValueError:
                horaire = None
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
                self._anomalie(anomalies, conso, "Plage horaire de l'unité non définie",
                               "Calcul bloqué : définir la plage de l'unité dans Noethys")
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
        return self._Resultat(IDindividu, date, PERI, heures, 0, physique, matin, soir, 0, None)

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
        facture, amplitude = self._FactureOption2(autres, anomalies, date)
        return self._Resultat(IDindividu, date, EXTRA, physique, facture, physique, matin, soir, heures_sejour, amplitude)

    def _FactureOption2(self, consos, anomalies, date):
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
            cle = conso.get("IDprestation") or ("conso", conso.get("IDconso"))
            if cle in prestations and prestations[cle][0] != categorie:
                self._anomalie(anomalies, conso, "Prestation partagée entre une journée et une demi-journée",
                               "Calcul bloqué : classification incohérente")
                continue
            prestations.setdefault(cle, (categorie, conso))
        natures = [categorie for categorie, conso in prestations.values()]
        if not natures:
            return 0, None
        premiere = list(prestations.values())[0][1]
        if natures.count("journee") > 1 or ("journee" in natures and "demi_journee" in natures) or natures.count("demi_journee") > 2:
            self._anomalie(anomalies, premiere, "Facturation supérieure à une journée pour un enfant (%s)" % ", ".join(sorted(natures)),
                           "Calcul bloqué : doublon de facturation")
            return 0, None
        amplitude, motif = self._amplitude(date)
        if amplitude is None:
            self._anomalie(anomalies, premiere, "Amplitude d'ouverture indéterminable : %s" % motif,
                           "Calcul bloqué : vérifier les ouvertures et les plages des unités")
            return 0, None
        if amplitude < Conventions.DUREE_MINIMALE_JOURNEE_EXTRA:
            self._anomalie(anomalies, premiere, "Amplitude d'ouverture inférieure à 2 h",
                           "Calcul bloqué : journée non conforme à l'art. 2-1")
            return 0, amplitude
        return sum(Conventions.DureeJourneeOption2(nature, amplitude) for nature in natures), amplitude

    def _Resultat(self, IDindividu, date, mode, realise, facture, physique, matin, soir, sejour, amplitude):
        aeeh = self._aeeh(IDindividu, date)
        return {
            "date": date, "IDindividu": IDindividu, "mode": mode, "aeeh": aeeh, "amplitude": amplitude,
            "heures_realisees": realise, "heures_facturees": facture,
            "heures_realisees_aeeh": realise if aeeh else 0, "heures_facturees_aeeh": facture if aeeh else 0,
            "heures_physiques": physique,
            "complement_inclusif_brut": physique if aeeh else 0,
            "complement_inclusif_arrondi": Conventions.ArrondiHeureSuperieure(physique) if aeeh else 0,
            "garderie_matin": matin, "garderie_soir": soir, "heures_sejours": sejour,
        }
