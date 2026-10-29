# -*- coding: utf-8 -*-
"""ALSH : participation des communes par journee-enfant (Noethys-SL).

Moteur commun independant de wxPython, de GestionDB et des factures des familles.
Aucune requete SQL, aucune ecriture dans la base et aucun calcul de TVA.
Les donnees nominatives ne figurent jamais dans les editions de synthese.
"""

import csv
import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from pathlib import Path


SCHEMA = "noethys-sl.frequentation-collectivites.v1"
CONTROLES = ("frequentation", "prevision", "domiciliation", "acomptes")
ETATS = ("realise", "absence_injustifiee", "prevision")
COMMUNES_ALSH = (
    "Availles-sur-Seiche", "Bais", "Drouges", "La Guerche-de-Bretagne",
    "Mousse", "Moutiers", "Rannee", "La Selle-Guerchaise", "Visseiche",
)


class ErreurFrequentation(ValueError):
    """Incoherence empechant un calcul fiable."""


def _texte(v, nom):
    if not isinstance(v, str) or not v.strip():
        raise ErreurFrequentation("Renseignement obligatoire : %s" % nom)
    return v.strip()


def _date(v, nom):
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    raise ErreurFrequentation("Date non valide : %s (AAAA-MM-JJ)" % nom)


def _decimal(v, nom, decimales=None):
    if isinstance(v, bool) or v is None:
        raise ErreurFrequentation("Valeur manquante ou booleenne : %s" % nom)
    try:
        n = Decimal(str(v).replace("\u00a0", "").replace(" ", "").replace(",", "."))
        if not n.is_finite() or (decimales is not None and n != n.quantize(Decimal("1").scaleb(-decimales))):
            raise InvalidOperation
        return n
    except (InvalidOperation, ValueError, OverflowError):
        raise ErreurFrequentation("Valeur numerique incorrecte : %s" % nom)


def _centimes(v, nom):
    n = _decimal(v, nom, 2)
    if n < 0:
        raise ErreurFrequentation("Montant negatif interdit : %s" % nom)
    return int(n * 100)


def _journnees(v, nom, demi_autorisee=False):
    n = _decimal(v, nom, 1)
    if n < 0 or n != n.quantize(Decimal("1")) and (not demi_autorisee or (n * 2) != (n * 2).to_integral_value()):
        raise ErreurFrequentation(
            "Jours-enfants non valides : %s (demi-journees sur regle explicite uniquement)" % nom)
    return n


def _csv_centimes(v):
    if v is None:
        return "NON CALCULABLE"
    sign = "-" if v < 0 else ""
    euros, cents = divmod(abs(int(v)), 100)
    return "%s%d.%02d" % (sign, euros, cents)


def _fr_centimes(v):
    if v is None:
        return "Non calculable"
    signe = "-" if v < 0 else ""
    euros, centimes = divmod(abs(int(v)), 100)
    return "%s%s,%02d EUR" % (signe, format(euros, ",").replace(",", " "), centimes)


def _fr_jours(v):
    if v is None:
        return "Non calcule"
    texte = format(v, "f")
    return texte.rstrip("0").rstrip(".") if "." in texte else texte


def _en_centimes(jours, tarif_centimes):
    total = jours * tariff_decimal(tarif_centimes)
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tariff_decimal(cents):
    return Decimal(cents)


def _code_commune(nom):
    texte = unicodedata.normalize("NFKD", _texte(nom, "commune").casefold())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r"[^a-z0-9]+", " ", texte).strip()
    return {"la guerche de bgne": "la guerche de bretagne"}.get(texte, texte)


def modele(commune="Bais", annee=2026, arrete="2026-10-29"):
    """Modele avec tarifs des documents 2025-2026, A CONFIRMER avant diffusion.

    Convention generale (9 communes) : ALSH 11,54 EUR/journee-enfant.
    Convention ados fournie : Bais uniquement, 19,55 EUR/journee-enfant.
    Le modele ne presume ni les frequences, ni les versements, ni la signature.
    """
    a = int(annee)
    commune = _texte(commune, "commune")
    conventions = []
    if a in (2025, 2026) and _code_commune(commune) in {_code_commune(x) for x in COMMUNES_ALSH}:
        conventions.append({
            "id": "ALSH-2025-2026", "accueil": "ALSH classique",
            "debut": "2025-01-01", "fin": "2026-12-31", "tarif_jour": "11.54",
            "tarif_confirme": False, "demi_journee_autorisee": False,
            "justificatif_tarif": "Convention financement ALSH 2025-2026, articles 4-5",
        })
    if a in (2025, 2026) and _code_commune(commune) == _code_commune("Bais"):
        conventions.append({
            "id": "ADOS-2024-2026-BAIS", "accueil": "ALSH Ados",
            "debut": "2024-01-01", "fin": "2026-12-31", "tarif_jour": "19.55",
            "tarif_confirme": False, "demi_journee_autorisee": False,
            "justificatif_tarif": "Convention ALSH Ados 2024-2026, articles 4-5 (validation a verifier)",
        })
    return {
        "schema": SCHEMA,
        "emetteur": "PÊLE-MÊLE SPORTS ET LOISIRS",
        "commune": commune, "annee": a, "arrete": arrete,
        "conventions": conventions,
        "jours": [], "acomptes": [],
        "options_etats": {"absenti": False},
        "controles": {k: False for k in CONTROLES},
    }


def calculer(dossier):
    """Calcule presence x tarif communal, sans facture ni paiement de famille.

    `jours` est un etat *mensuel valide* de journees-enfants, avec une ligne
    maximum par convention/mois/etat. L'annee est toujours civile.
    `acomptes` contient des versements de commune explicitement affectes a N.
    Un solde certifiable ne peut pas etre deduit de donnees absentes : None.
    Le montant indicatif reste visible, avec avertissements.
    """
    if not isinstance(dossier, dict) or dossier.get("schema") != SCHEMA:
        raise ErreurFrequentation("Format du dossier incompatible. Ancien lot financier interdit.")
    nom = _texte(dossier.get("commune"), "commune")
    annee = dossier.get("annee")
    if isinstance(annee, bool) or not isinstance(annee, int) or not 2000 <= annee <= 2100:
        raise ErreurFrequentation("Annee civile incorrecte")
    arrete = _date(dossier.get("arrete"), "arrete")
    if arrete.year != annee:
        raise ErreurFrequentation("La date d'arrete doit etre dans l'annee civile")
    org = dossier.get("emetteur", "")
    if not isinstance(org, str):
        raise ErreurFrequentation("Nom d'organisme non textuel")
    # Old v1 dossiers without options keep the safe historical default.
    options = dossier.get("options_etats", {"absenti": False})
    if not isinstance(options, dict) or set(options) != {"absenti"} or not isinstance(options["absenti"], bool):
        raise ErreurFrequentation("Choix de comptage des absences invalide")
    compter_absenti = options["absenti"]
    verifs = dossier.get("controles")
    if not isinstance(verifs, dict) or any(not isinstance(verifs.get(c), bool) for c in CONTROLES):
        raise ErreurFrequentation("Controles obligatoires sous forme true/false")
    raw_conventions = dossier.get("conventions")
    if not isinstance(raw_conventions, list):
        raise ErreurFrequentation("Conventions attendues sous forme de liste")
    conventions = {}
    alertes = []
    for item in raw_conventions:
        if not isinstance(item, dict):
            raise ErreurFrequentation("Convention non structurée")
        ident = _texte(item.get("id"), "id convention")
        if ident in conventions:
            raise ErreurFrequentation("Convention dupliquee : %s" % ident)
        d0, d1 = _date(item.get("debut"), ident + ".debut"), _date(item.get("fin"), ident + ".fin")
        if d0 > d1 or d0.year > annee or d1.year < annee:
            raise ErreurFrequentation("Dates de convention incompatibles : %s" % ident)
        tarif = _centimes(item.get("tarif_jour"), ident + ".tarif_jour")
        if tarif <= 0:
            raise ErreurFrequentation("Tarif a la journee strictement positif requis : %s" % ident)
        conf = item.get("tarif_confirme")
        demi = item.get("demi_journee_autorisee", False)
        if not isinstance(conf, bool) or not isinstance(demi, bool):
            raise ErreurFrequentation("Confirmation explicite requise pour %s" % ident)
        accueil = _texte(item.get("accueil"), ident + ".accueil")
        if accueil == "ALSH Ados" and _code_commune(nom) != _code_commune("Bais") and ident == "ADOS-2024-2026-BAIS":
            raise ErreurFrequentation("Convention Ados de Bais non applicable a une autre commune")
        justificatif = _texte(item.get("justificatif_tarif"), ident + ".justificatif_tarif")
        if not conf:
            alertes.append("Tarif ou signature a confirmer : %s" % ident)
        conventions[ident] = {"accueil": accueil, "tarif_centimes": tarif, "debut": d0,
                              "fin": d1, "tarif_confirme": conf, "demi": demi,
                              "justificatif": justificatif,
                              "mensuel": {m: {"realise": Decimal("0"), "absence_injustifiee": Decimal("0"), "prevision": Decimal("0")} for m in range(1,13)}}
    raw_jours = dossier.get("jours")
    raw_acomptes = dossier.get("acomptes")
    if not isinstance(raw_jours, list) or not isinstance(raw_acomptes, list):
        raise ErreurFrequentation("Lignes mensuelles et acomptes sous forme de listes obligatoires")
    vus_jours = set()
    refs = set()
    lignes_sans_piece = []
    for n, ligne in enumerate(raw_jours, 1):
        champ = "jours[%d]" % n
        if not isinstance(ligne, dict):
            raise ErreurFrequentation("Ligne de frequentation invalide : %s" % champ)
        ident = _texte(ligne.get("id"), champ + ".id")
        if ident in refs:
            raise ErreurFrequentation("Reference en doublon : %s" % ident)
        refs.add(ident)
        cid = _texte(ligne.get("convention"), champ + ".convention")
        if cid not in conventions:
            raise ErreurFrequentation("Convention introuvable : %s" % cid)
        mois = ligne.get("mois")
        if isinstance(mois, bool) or not isinstance(mois, int) or not 1 <= mois <= 12:
            raise ErreurFrequentation("Mois incorrect : %s" % ident)
        nature = _texte(ligne.get("nature"), champ + ".nature")
        if nature not in ETATS:
            raise ErreurFrequentation("Nature de frequentation inconnue : %s" % ident)
        cle = (cid, mois, nature)
        if cle in vus_jours:
            raise ErreurFrequentation("Deux bilans de frequentation pour une meme periode : %s" % (cle,))
        vus_jours.add(cle)
        if nature == "absence_injustifiee" and not compter_absenti:
            raise ErreurFrequentation("Activer explicitement les absences injustifiees avant leur saisie : %s" % ident)
        if nature in ("realise", "absence_injustifiee") and mois > arrete.month:
            raise ErreurFrequentation("Journee retenue apres la date d'arrete : %s" % ident)
        if nature == "prevision" and mois < arrete.month:
            raise ErreurFrequentation("Ancienne reservation consideree comme future : %s" % ident)
        c = conventions[cid]
        month_start = date(annee, mois, 1)
        month_end = date(annee, mois, monthrange(annee, mois)[1])
        if not (c["debut"] <= month_start and c["fin"] >= month_end):
            raise ErreurFrequentation("Mois partiellement hors convention, detail journalier requis : %s" % ident)
        jours = _journnees(ligne.get("nombre"), ident, c["demi"])
        c["mensuel"][mois][nature] = jours
        if not isinstance(ligne.get("justificatif", ""), str) or not str(ligne.get("justificatif", "")).strip():
            lignes_sans_piece.append(ident)
    if lignes_sans_piece:
        alertes.append("Justificatif de frequentation manquant : %s" % ", ".join(lignes_sans_piece))
    acomptes = 0
    payes = {ident: 0 for ident in conventions}
    futurs_exclus = 0
    paiements_sans_piece = []
    for n, p in enumerate(raw_acomptes, 1):
        if not isinstance(p, dict):
            raise ErreurFrequentation("Acompte incorrect")
        idp = _texte(p.get("id"), "acompte.id")
        if idp in refs:
            raise ErreurFrequentation("Reference en doublon : %s" % idp)
        refs.add(idp)
        cid = _texte(p.get("convention"), idp + ".convention")
        if cid not in conventions:
            raise ErreurFrequentation("Acompte non attribue a une convention : %s" % idp)
        if isinstance(p.get("exercice"), bool) or p.get("exercice") != annee:
            raise ErreurFrequentation("Acompte sans affectation explicite a %s : %s" % (annee, idp))
        paiement = _date(p.get("date"), idp + ".date")
        montant = _centimes(p.get("montant"), idp + ".montant")
        if not isinstance(p.get("justificatif", ""), str) or not str(p.get("justificatif", "")).strip():
            paiements_sans_piece.append(idp)
        if paiement > arrete:
            futurs_exclus += 1
            continue
        payes[cid] += montant
        acomptes += montant
    if futurs_exclus:
        alertes.append("Versements futurs non consideres comme recus : %d" % futurs_exclus)
    if paiements_sans_piece:
        alertes.append("Justificatif d'acompte manquant : %s" % ", ".join(paiements_sans_piece))
    for cle, libelle in (("frequentation", "Frequentation reelle"), ("prevision", "Previsions"),
                         ("domiciliation", "Domiciles des enfants"), ("acomptes", "Acomptes communaux")):
        if not verifs[cle]:
            alertes.append("Exhaustivite non confirmee : %s" % libelle)
    if not org.strip():
        alertes.append("Organisme emetteur absent")
    if not raw_jours:
        alertes.append("Aucune donnee de frequentation ; ne pas assimiler a zero journee")
    source = dossier.get("import_noethys")
    source_valide = True
    if source is not None:
        if not isinstance(source, dict):
            raise ErreurFrequentation("Metadonnees d'import Noethys invalides")
        try:
            indetermines = int(source.get("domiciles_indetermines", 0))
        except (TypeError, ValueError):
            raise ErreurFrequentation("Nombre de domiciles non resolus invalide")
        if indetermines < 0 or isinstance(source.get("domiciles_indetermines"), bool):
            raise ErreurFrequentation("Nombre de domiciles non resolus invalide")
        if indetermines:
            source_valide = False
            alertes.append("Domiciles non resolus, consommations exclues : %d" % indetermines)
        if source.get("absenti_selectionne", False) is not compter_absenti:
            raise ErreurFrequentation("Choix des absences modifie : recharger les donnees Noethys")
        if source.get("perimetre_unites_confirme") is not True:
            source_valide = False
            alertes.append("Selection des unites ALSH non declaree exhaustive")
        if source.get("domiciliation_historique_verifiee") is not True:
            source_valide = False
            alertes.append("Adresses actuelles : domiciliation historique non verifiee")
    real = pred = absenti = Decimal("0")
    part_reelle = part_prevue = part_absenti = 0
    par_accueil = {}
    mensuel = {m: {"realise": Decimal("0"), "absence_injustifiee": Decimal("0"),
                   "prevision": Decimal("0"), "participation_absences": 0,
                   "participation": 0} for m in range(1, 13)}
    for cid, c in conventions.items():
        r = sum((c["mensuel"][m]["realise"] for m in range(1, 13)), Decimal("0"))
        p = sum((c["mensuel"][m]["prevision"] for m in range(1, 13)), Decimal("0"))
        a = sum((c["mensuel"][m]["absence_injustifiee"] for m in range(1, 13)), Decimal("0"))
        er = _en_centimes(r, c["tarif_centimes"])
        ep = _en_centimes(p, c["tarif_centimes"])
        ea = _en_centimes(a, c["tarif_centimes"])
        real += r
        pred += p
        absenti += a
        part_reelle += er
        part_prevue += ep
        part_absenti += ea
        par_accueil[cid] = {"accueil": c["accueil"], "tarif_centimes": c["tarif_centimes"],
                            "tarif_confirme": c["tarif_confirme"], "realise": r, "prevision": p,
                            "absences_injustifiees": a,
                            "participation_reelle": er, "participation_prevue": ep,
                            "participation_absences_injustifiees": ea,
                            "participation_estimee": er + ep + ea, "acomptes_recus": payes[cid]}
        for m in range(1, 13):
            mensuel[m]["realise"] += c["mensuel"][m]["realise"]
            mensuel[m]["absence_injustifiee"] += c["mensuel"][m]["absence_injustifiee"]
            mensuel[m]["prevision"] += c["mensuel"][m]["prevision"]
        # Allouer les fractions de centime au dernier mois renseigne afin que
        # le tableau mensuel reconcilie exactement le total annuel par accueil.
        for nature, total_cents in (("realise", er), ("absence_injustifiee", ea), ("prevision", ep)):
            monthly = {m: _en_centimes(c["mensuel"][m][nature], c["tarif_centimes"])
                       for m in range(1, 13)}
            correction = total_cents - sum(monthly.values())
            nonzero = [m for m in range(1, 13) if c["mensuel"][m][nature]]
            if correction and nonzero:
                monthly[nonzero[-1]] += correction
            for m, cents in monthly.items():
                mensuel[m]["participation"] += cents
                if nature == "absence_injustifiee":
                    mensuel[m]["participation_absences"] += cents
    # Les cases non renseignees sont indeterminees sauf lorsque leur
    # categorie a ete explicitement declaree exhaustive pour l'exercice.
    for m in range(1, 13):
        natures = [("realise", "frequentation"), ("prevision", "prevision")]
        if compter_absenti:
            natures.append(("absence_injustifiee", "frequentation"))
        for nature, controle in natures:
            applicable = m <= arrete.month if nature != "prevision" else m >= arrete.month
            if applicable and not verifs[controle] and not all(
                    (cid, m, nature) in vus_jours for cid in conventions):
                mensuel[m][nature] = None
        if any(mensuel[m][nature] is None for nature, _ in natures):
            mensuel[m]["participation"] = None
            if compter_absenti and mensuel[m]["absence_injustifiee"] is None:
                mensuel[m]["participation_absences"] = None
    if compter_absenti:
        alertes.append("Absences injustifiees retenues dans le calcul : accord communal ecrit a verifier. Ce ne sont PAS des presences reelles.")
    connu = bool(raw_jours and conventions)
    # Conventions fournies : journees realisees, sans regle explicite sur les
    # absences facturees. Le choix peut etre utilise pour simulation seulement.
    complet = bool(not compter_absenti and connu and org.strip() and all(verifs.values()) and
                   all(c["tarif_confirme"] for c in conventions.values()) and
                   not lignes_sans_piece and not paiements_sans_piece and source_valide)
    solde = part_reelle + part_absenti + part_prevue - acomptes if connu else None
    if solde is not None and solde < 0:
        alertes.append("Acomptes superieurs a la participation estimee : trop-percu possible")
    statut = ("ETAT VERIFIE - PREVISIONNEL" if complet else
              "PROVISOIRE - ABSENCES A VALIDER" if compter_absenti else
              "PROVISOIRE - A VERIFIER")
    return {
        "schema": SCHEMA, "emetteur": org.strip(), "commune": nom,
        "annee": annee, "arrete": arrete.isoformat(), "statut": statut,
        "options_etats": {"absenti": compter_absenti},
        "conventions": par_accueil,
        "mensuel": {str(m): mensuel[m] for m in range(1, 13)},
        "totaux": {"journees_reelles": real if connu else None,
                   "journees_absences_injustifiees": absenti if connu else None,
                   "journees_retenues": real + absenti if connu else None,
                   "journees_prevues": pred if connu else None,
                   "participation_reelle": part_reelle if connu else None,
                   "participation_absences_injustifiees": part_absenti if connu else None,
                   "participation_prevue": part_prevue if connu else None,
                   "participation_estimee": part_reelle + part_absenti + part_prevue if connu else None,
                   "acomptes_recus": acomptes if raw_acomptes or verifs["acomptes"] else None,
                   "solde_indicatif": solde,
                   "solde_verifie": solde if complet else None},
        "alertes": alertes,
    }


def consolider_export_consommations(records, mapping_unites, commune, annee, arrete, inclure_absenti=False):
    """Prepare les bilans mensuels depuis des consommations exportees de Noethys.

    Pas d'acces direct a la base ; id enfant et commune doivent deja avoir ete
    verifies et fournis localement. Mapping explicite (activite:unite) =>
    {convention: id, poids: '1'/'0.5'/'0', demi_journee_confirmee: bool}.
    Un poids 0 exclut repas/garderie ; jamais de reconnaissance par libelle.
    Les reservations passees ne sont PAS des presences.
    """
    if not isinstance(inclure_absenti, bool):
        raise ErreurFrequentation("Choix absenti attendu sous forme vrai/faux")
    a = int(annee)
    cutoff = _date(arrete, "arrete")
    if cutoff.year != a:
        raise ErreurFrequentation("Arrete et exercice differents")
    if not isinstance(records, list) or not isinstance(mapping_unites, dict):
        raise ErreurFrequentation("Exports et mapping d'unites requis")
    c = _code_commune(commune)
    groupes = {}
    ids_conso = set()
    exclus = {"autres_communes": 0, "absences": 0, "reservations_passees": 0, "hors_annee": 0}
    for l in records:
        if not isinstance(l, dict):
            raise ErreurFrequentation("Consommation exportee non structuree")
        source_id = l.get("IDconso")
        if source_id is None or isinstance(source_id, bool) or not str(source_id).strip():
            raise ErreurFrequentation("Identifiant de consommation absent")
        ident = str(source_id).strip()
        if ident in ids_conso:
            raise ErreurFrequentation("IDconso repete dans l'export : %s" % ident)
        ids_conso.add(ident)
        jour = _date(l.get("date"), "date consommation")
        if jour.year != a:
            exclus["hors_annee"] += 1
            continue
        ville = l.get("commune_residence")
        if ville is None or not isinstance(ville, str) or not ville.strip():
            raise ErreurFrequentation("Domiciliation absente ; aucun rattachement implicite")
        if _code_commune(ville) != c:
            exclus["autres_communes"] += 1
            continue
        etat = _texte(l.get("etat"), "etat consommation").lower()
        # Excluded states do not become visits, even for a selected unit.
        if etat in ("absent", "absentj", "annule", "refus", "attente"):
            exclus["absences"] += 1
            continue
        if etat == "absenti" and (not inclure_absenti or jour > cutoff):
            exclus["absences"] += 1
            continue
        if etat not in ("present", "reservation", "absenti"):
            raise ErreurFrequentation("Etat de consommation inconnu : %s" % etat)
        if etat == "reservation" and jour <= cutoff:
            exclus["reservations_passees"] += 1
            continue
        if etat == "present" and jour > cutoff:
            raise ErreurFrequentation("Presence future : %s" % ident)
        cle_unite = "%s:%s" % (l.get("IDactivite"), l.get("IDunite"))
        regle = mapping_unites.get(cle_unite)
        if not isinstance(regle, dict):
            raise ErreurFrequentation("Unite Noethys non qualifiee : %s" % cle_unite)
        poids = _decimal(regle.get("poids"), cle_unite + ".poids", 1)
        if poids not in (Decimal("0"), Decimal("0.5"), Decimal("1")):
            raise ErreurFrequentation("Equivalence journee interdite : %s" % cle_unite)
        if poids == Decimal("0.5") and regle.get("demi_journee_confirmee") is not True:
            raise ErreurFrequentation("Regle de demi-journee non justifiee : %s" % cle_unite)
        if poids == 0:
            continue
        cid = _texte(regle.get("convention"), cle_unite + ".convention")
        enfant = l.get("IDindividu")
        if isinstance(enfant, bool) or enfant is None or str(enfant).strip() == "":
            raise ErreurFrequentation("Consommation sans identifiant enfant")
        cle = (str(enfant), jour, cid, etat)
        groupe = groupes.setdefault(cle, {})
        # Une unite ne compte qu'une fois par enfant/date/accueil/etat.
        if cle_unite in groupe:
            raise ErreurFrequentation("Deux consommations pour meme unite/enfant/jour : %s" % ident)
        groupe[cle_unite] = poids
    # Ne jamais compter reservation et presence du meme enfant/jour/accueil.
    par_jour = {}
    for (enfant, jour, cid, etat), poids in groupes.items():
        quantite = sum(poids.values(), Decimal("0"))
        if quantite > 1:
            raise ErreurFrequentation("Plus d'une journee par enfant/jour/accueil : %s %s" % (cid, jour))
        cle = (enfant, jour, cid)
        if cle in par_jour:
            raise ErreurFrequentation("Etats incompatibles le meme jour : %s %s" % (cid, jour))
        par_jour[cle] = (etat, quantite)
    # Un enfant ne peut totaliser deux journees pleines le meme jour sous
    # deux conventions ALSH differentes. Cas suspect = validation manuelle.
    par_enfant_jour = {}
    for (enfant, jour, _cid), (_etat, poids) in par_jour.items():
        cle = (enfant, jour)
        par_enfant_jour[cle] = par_enfant_jour.get(cle, Decimal("0")) + poids
        if par_enfant_jour[cle] > 1:
            raise ErreurFrequentation("Double comptage entre accueils le %s" % jour)
    par_mois = {}
    for (_enfant, jour, cid), (etat, quantite) in par_jour.items():
        nature = {"present": "realise", "reservation": "prevision",
                  "absenti": "absence_injustifiee"}[etat]
        cle = (cid, jour.month, nature)
        par_mois[cle] = par_mois.get(cle, Decimal("0")) + quantite
    lignes = []
    for i, ((cid, mois, nature), nombre) in enumerate(sorted(par_mois.items()), 1):
        lignes.append({"id": "EXPORT-%04d" % i, "convention": cid, "mois": mois,
                       "nature": nature, "nombre": str(nombre),
                       "justificatif": "Export Noethys : consommations / paramétrage des unités à vérifier"})
    return {"jours": lignes, "exclusions": exclus,
            "nb_enfants_jour": len(par_jour),
            "absenti_selectionne": inclure_absenti,
            "verification_domicile_requise": True}


def exporter_csv(resultat, destination):
    """Synthese non nominative, Excel compatible, sans TVA ni comptes familles."""
    p = Path(destination)
    with p.open("x", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp, delimiter=";")
        w.writerow(["SITUATION FREQUENTATION ALSH - PARTICIPATIONS COMMUNALES"])
        for key in ("commune", "annee", "arrete", "statut"):
            w.writerow([key, resultat[key]])
        w.writerow([])
        w.writerow(["Accueil", "Tarif EUR par journee-enfant", "Jours reels", "Jours previsionnels", "Participation reelle EUR", "Participation previsionnelle EUR", "Acomptes recus EUR", "Absences injustifiees retenues", "Participation absences injustifiees EUR"])
        for c in resultat["conventions"].values():
            w.writerow([c["accueil"], "%d.%02d" % divmod(c["tarif_centimes"], 100),
                        _fr_jours(c["realise"]), _fr_jours(c["prevision"]),
                        _csv_centimes(c["participation_reelle"]),
                        _csv_centimes(c["participation_prevue"]),
                        _csv_centimes(c["acomptes_recus"]),
                        _fr_jours(c["absences_injustifiees"]),
                        _csv_centimes(c["participation_absences_injustifiees"])])
        w.writerow([])
        w.writerow(["Mois", "Journees reelles", "Journees prevues", "Participation theorique EUR", "Absences injustifiees retenues", "Participation absences EUR"])
        for mois in range(1, 13):
            r = resultat["mensuel"][str(mois)]
            w.writerow(["%02d/%d" % (mois, resultat["annee"]), _fr_jours(r["realise"]),
                        _fr_jours(r["prevision"]), _csv_centimes(r["participation"]),
                        _fr_jours(r["absence_injustifiee"]), _csv_centimes(r["participation_absences"])])
        w.writerow([])
        for cle in ("journees_reelles", "journees_absences_injustifiees", "journees_retenues",
                    "journees_prevues", "participation_reelle", "participation_absences_injustifiees",
                    "participation_prevue", "participation_estimee", "acomptes_recus", "solde_indicatif", "solde_verifie"):
            val = resultat["totaux"][cle]
            if cle.startswith("journees"):
                val = _fr_jours(val)
            else:
                val = "NON CALCULABLE" if val is None else _csv_centimes(val)
            w.writerow([cle, val])
        w.writerow([])
        w.writerow(["OPTION ABSENCES INJUSTIFIEES", "INCLUSES" if resultat["options_etats"]["absenti"] else "EXCLUES"])
        w.writerow(["METHODE", "Les absences injustifiees retenues ne sont pas des presences reelles."])
        for msg in resultat["alertes"]:
            w.writerow(["CONTROLE", msg])
    return p


def exporter_xlsx(resultat, destination, dossier=None, fictif=False):
    """Export Excel non nominatif : frequentation, tarifs et acomptes communaux.

    Les montants sont numeriques et les calculs annuels restent des formules
    modifiables. Les montants deja calcules sont fournis en cache de formule.
    XlsxWriter fait deja partie des dependances de Noethys-SL.
    """
    from io import BytesIO
    try:
        import xlsxwriter
    except ImportError as exc:
        raise ErreurFrequentation("Export Excel indisponible : XlsxWriter manque") from exc

    sortie = Path(destination)
    if sortie.exists():
        raise FileExistsError("Refus d'ecraser l'export existant : %s" % sortie)
    if dossier is not None and calculer(dossier) != resultat:
        raise ErreurFrequentation("Dossier et situation calculee non concordants")

    totaux = resultat["totaux"]
    connu = totaux["participation_estimee"] is not None
    acomptes = list(dossier["acomptes"]) if dossier is not None else []
    justifs = {c["id"]: c.get("justificatif_tarif", "")
               for c in dossier["conventions"]} if dossier is not None else {}
    arrete = _date(resultat["arrete"], "arrete")
    contenu = BytesIO()
    classeur = xlsxwriter.Workbook(contenu, {
        "in_memory": True, "strings_to_formulas": False,
        "strings_to_urls": False,
    })
    titre = classeur.add_format({"bold": True, "font_size": 13})
    entete = classeur.add_format({"bold": True, "bottom": 1})
    nb = classeur.add_format({"num_format": "0.##"})
    euros = classeur.add_format({"num_format": '#,##0.00 "€";[Red](#,##0.00 "€");"-"'})
    date_fmt = classeur.add_format({"num_format": "dd/mm/yyyy"})
    reserve = classeur.add_format({"font_color": "#9A5300"})

    def texte(feuille, ligne, colonne, valeur, fmt=None):
        # Ne jamais executer une formule provenant d'une saisie utilisateur.
        feuille.write_string(ligne, colonne, str(valeur), fmt)

    def nombre(feuille, ligne, colonne, valeur, fmt=nb):
        if valeur is None:
            texte(feuille, ligne, colonne, "NON CALCULABLE", reserve)
        else:
            feuille.write_number(ligne, colonne, float(valeur), fmt)

    def monnaie(feuille, ligne, colonne, centimes):
        nombre(feuille, ligne, colonne, None if centimes is None else centimes / 100, euros)

    try:
        situation = classeur.add_worksheet("Situation")
        situation.hide_gridlines(2)
        situation.set_column("A:B", 25)
        situation.set_column("C:E", 18)
        situation.set_column("F:J", 24)
        situation.set_column("K:K", 20)
        situation.set_column("L:L", 62)
        situation.set_column("M:N", 30)
        situation.freeze_panes(8, 2)
        texte(situation, 0, 0, "SITUATION DE FREQUENTATION ALSH", titre)
        for ligne, label, valeur in (
            (1, "Association", resultat["emetteur"]),
            (2, "Commune", resultat["commune"]),
            (3, "Annee civile", resultat["annee"]),
            (4, "Arrete", resultat["arrete"]),
            (5, "Statut", resultat["statut"]),
        ):
            texte(situation, ligne, 0, label)
            texte(situation, ligne, 1, valeur,
                  reserve if ligne == 5 and totaux["solde_verifie"] is None else None)
        mentions = []
        if fictif:
            mentions.append("EXEMPLE FICTIF - NE PAS TRANSMETTRE")
        if totaux["solde_verifie"] is None:
            mentions.append("ETAT PROVISOIRE : les sommes ne sont pas certifiees")
        if resultat["options_etats"]["absenti"]:
            mentions.append("ABSENCES INJUSTIFIEES RETENUES - ACCORD COMMUNAL A VERIFIER")
        if mentions:
            texte(situation, 6, 0, " | ".join(mentions), reserve)
        colonnes = ("Accueil", "Convention", "Tarif €/jour", "Jours realises", "Jours prevus",
                    "Participation realisee €", "Participation prevue €", "Participation estimee €",
                    "Acomptes saisis €", "Solde indicatif €", "Tarif confirme", "Source convention",
                    "Absences injustifiees retenues", "Participation des absences €")
        for col, label in enumerate(colonnes):
            texte(situation, 7, col, label, entete)
        debut = 8
        for index, (ident, convention) in enumerate(resultat["conventions"].items()):
            ligne = debut + index
            num = ligne + 1
            texte(situation, ligne, 0, convention["accueil"])
            texte(situation, ligne, 1, ident)
            monnaie(situation, ligne, 2, convention["tarif_centimes"])
            if ident in justifs:
                situation.write_comment(ligne, 2, "Source : " + justifs[ident])
            texte(situation, ligne, 10, "OUI" if convention["tarif_confirme"] else "A CONFIRMER")
            texte(situation, ligne, 11, justifs.get(ident, "Non fournie"))
            if not connu:
                for col in (3, 4, 5, 6, 7, 9, 12, 13):
                    texte(situation, ligne, col, "NON CALCULABLE", reserve)
            else:
                nombre(situation, ligne, 3, convention["realise"])
                nombre(situation, ligne, 4, convention["prevision"])
                nombre(situation, ligne, 12, convention["absences_injustifiees"])
                situation.write_formula(ligne, 13, "=ROUND(C%d*M%d,2)" % (num, num),
                                        euros, convention["participation_absences_injustifiees"] / 100.0)
                for col, formule, cache in (
                    (5, "=ROUND(C%d*D%d,2)" % (num, num), convention["participation_reelle"]),
                    (6, "=ROUND(C%d*E%d,2)" % (num, num), convention["participation_prevue"]),
                    (7, "=F%d+G%d+N%d" % (num, num, num), convention["participation_estimee"]),
                    (9, "=H%d-I%d" % (num, num), convention["participation_estimee"] - convention["acomptes_recus"]),
                ):
                    situation.write_formula(ligne, col, formule, euros, cache / 100.0)
            # Si les versements sont detailles, la synthese reste liee a eux.
            if acomptes:
                fin_vers = len(acomptes) + 3
                situation.write_formula(
                    ligne, 8,
                    "=SUMIF(Versements!$B$4:$B$%d,B%d,Versements!$F$4:$F$%d)" % (
                        fin_vers, num, fin_vers),
                    euros, convention["acomptes_recus"] / 100.0)
            else:
                monnaie(situation, ligne, 8, convention["acomptes_recus"])
        fin = debut + len(resultat["conventions"])
        texte(situation, fin, 0, "TOTAL", entete)
        for colonne, champ in ((3, "journees_reelles"), (4, "journees_prevues"),
                               (5, "participation_reelle"), (6, "participation_prevue"),
                               (7, "participation_estimee"), (8, "acomptes_recus"),
                               (9, "solde_indicatif"), (12, "journees_absences_injustifiees"),
                               (13, "participation_absences_injustifiees")):
            if totaux[champ] is None or fin == debut:
                texte(situation, fin, colonne, "NON CALCULABLE", reserve)
            else:
                lettre = chr(65 + colonne)
                cache = float(totaux[champ]) if colonne in (3, 4, 12) else totaux[champ] / 100.0
                situation.write_formula(fin, colonne, "=SUM(%s%d:%s%d)" % (
                    lettre, debut + 1, lettre, fin), nb if colonne in (3, 4, 12) else euros, cache)
        texte(situation, fin + 2, 0, "Solde verifie (€)")
        if totaux["solde_verifie"] is None:
            texte(situation, fin + 2, 1, "NON CALCULABLE", reserve)
        else:
            situation.write_formula(fin + 2, 1, "=J%d" % (fin + 1), euros,
                                    totaux["solde_verifie"] / 100.0)
        if totaux["acomptes_recus"] is None:
            texte(situation, fin + 4, 0, "Acomptes non confirms : solde strictement indicatif.", reserve)

        mensuel = classeur.add_worksheet("Mensuel")
        mensuel.hide_gridlines(2)
        mensuel.set_column("A:A", 18)
        mensuel.set_column("B:C", 24)
        mensuel.set_column("D:D", 30)
        mensuel.set_column("E:F", 32)
        mensuel.freeze_panes(3, 1)
        texte(mensuel, 0, 0, "FREQUENTATION MENSUELLE", titre)
        texte(mensuel, 1, 0, "Commune : %s / %d" % (resultat["commune"], resultat["annee"]))
        for col, label in enumerate(("Mois", "Jours realises", "Jours prevus", "Participation (€)",
                                     "Absences injustifiees retenues", "Participation des absences (€)")):
            texte(mensuel, 2, col, label, entete)
        incomplet = False
        for mois in range(1, 13):
            ligne = mois + 2
            vals = resultat["mensuel"][str(mois)]
            texte(mensuel, ligne, 0, "%02d/%d" % (mois, resultat["annee"]))
            nombre(mensuel, ligne, 1, vals["realise"])
            nombre(mensuel, ligne, 2, vals["prevision"])
            monnaie(mensuel, ligne, 3, vals["participation"])
            nombre(mensuel, ligne, 4, vals["absence_injustifiee"])
            monnaie(mensuel, ligne, 5, vals["participation_absences"])
            incomplet |= any(vals[k] is None for k in ("realise", "prevision", "participation", "absence_injustifiee"))
        # Sources des nombres de journees, sans noms d'enfants.
        if dossier is not None:
            sources_mensuelles = {}
            for releve in dossier["jours"]:
                cle = (releve["mois"], releve["nature"])
                sources_mensuelles.setdefault(cle, []).append(
                    "%s : %s" % (releve["convention"], releve.get("justificatif", "")))
            for (mois, nature), sources in sources_mensuelles.items():
                col = {"realise": 1, "prevision": 2, "absence_injustifiee": 4}[nature]
                mensuel.write_comment(mois + 2, col, "\n".join(sources)[:32000])
        texte(mensuel, 15, 0, "TOTAL", entete)
        for col, nom in ((1, "journees_reelles"), (2, "journees_prevues"),
                         (3, "participation_estimee"),
                         (4, "journees_absences_injustifiees"),
                         (5, "participation_absences_injustifiees")):
            if incomplet or totaux[nom] is None:
                texte(mensuel, 15, col, "NON CALCULABLE", reserve)
            else:
                lettre = chr(65 + col)
                cache = float(totaux[nom]) if col in (1, 2, 4) else totaux[nom] / 100.0
                mensuel.write_formula(15, col, "=SUM(%s4:%s15)" % (lettre, lettre),
                                      nb if col in (1, 2, 4) else euros, cache)
        if incomplet:
            texte(mensuel, 17, 0, "Les mois non documentes ne sont pas assimiles a zero.", reserve)

        versements = classeur.add_worksheet("Versements")
        versements.hide_gridlines(2)
        versements.set_column("A:B", 27)
        versements.set_column("C:C", 18)
        versements.set_column("D:F", 23)
        versements.set_column("G:G", 60)
        texte(versements, 0, 0, "ACOMPTES COMMUNAUX", titre)
        texte(versements, 1, 0, "Seuls les versements recus a la date d'arrete sont retenus.")
        for col, label in enumerate(("Reference", "Convention", "Date perception",
                                     "Montant €", "Recu a l'arrete", "Retenu €", "Justificatif")):
            texte(versements, 2, col, label, entete)
        for i, paiement in enumerate(acomptes):
            ligne = i + 3
            num = ligne + 1
            jour = _date(paiement["date"], "date versement")
            cents = _centimes(paiement["montant"], "acompte")
            inclus = jour <= arrete
            texte(versements, ligne, 0, paiement["id"])
            texte(versements, ligne, 1, paiement["convention"])
            versements.write_datetime(ligne, 2, datetime.combine(jour, datetime.min.time()),
                                      date_fmt)
            monnaie(versements, ligne, 3, cents)
            if paiement.get("justificatif"):
                versements.write_comment(ligne, 3, "Source : %s" % paiement["justificatif"])
            texte(versements, ligne, 4, "OUI" if inclus else "NON")
            versements.write_formula(ligne, 5, '=IF(E%d="OUI",D%d,0)' % (num, num),
                                     euros, cents / 100.0 if inclus else 0.0)
            texte(versements, ligne, 6, paiement.get("justificatif", ""))
        if dossier is None:
            texte(versements, 3, 0, "Versements detailles non fournis ; voir les totaux de Situation.")
        elif not acomptes:
            texte(versements, 3, 0, "Aucun acompte saisi.")
        total_ligne = 3 + len(acomptes)
        texte(versements, total_ligne, 4, "TOTAL", entete)
        if acomptes:
            cache = sum(_centimes(a["montant"], "acompte") for a in acomptes
                        if _date(a["date"], "date acompte") <= arrete) / 100.0
            versements.write_formula(total_ligne, 5, "=SUM(F4:F%d)" % total_ligne,
                                     euros, cache)
        else:
            monnaie(versements, total_ligne, 5, totaux["acomptes_recus"])

        controles = classeur.add_worksheet("Controles")
        controles.hide_gridlines(2)
        controles.set_column("A:A", 110)
        texte(controles, 0, 0, "CONTROLES ET RESERVES", titre)
        texte(controles, 1, 0, resultat["statut"], reserve if totaux["solde_verifie"] is None else None)
        texte(controles, 2, 0, "Absences injustifiees : incluses sous reserve d'accord communal" if resultat["options_etats"]["absenti"] else "Absences injustifiees : exclues par choix", reserve)
        if fictif:
            texte(controles, 2, 0, "EXEMPLE FICTIF - NE PAS TRANSMETTRE", reserve)
        for num, message in enumerate(resultat["alertes"], 3):
            texte(controles, num, 0, message, reserve)
        if not resultat["alertes"]:
            texte(controles, 3, 0, "Aucune alerte emise par le moteur de calcul.")
    finally:
        classeur.close()

    with sortie.open("xb") as fichier:
        fichier.write(contenu.getvalue())
    return sortie


def exporter_pdf(resultat, destination, fictif=False):
    """Synthese non nominative pour evaluation du solde de l'annee civile."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    p = Path(destination)
    styles = getSampleStyleSheet()
    bleu = colors.HexColor("#20384f")
    titre = ParagraphStyle("AlshTitre", parent=styles["Heading1"], fontName="Helvetica-Bold",
                           fontSize=15, leading=19, textColor=bleu, spaceAfter=7)
    sous = ParagraphStyle("AlshSous", parent=styles["Heading2"], fontName="Helvetica-Bold",
                          fontSize=10.3, leading=14, textColor=bleu, spaceBefore=8, spaceAfter=4)
    corps = ParagraphStyle("AlshCorps", parent=styles["BodyText"], fontName="Helvetica",
                           fontSize=8.6, leading=12)
    petite = ParagraphStyle("AlshPetite", parent=corps, fontSize=7.8, leading=10.7)
    doc = SimpleDocTemplate(str(p), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=14*mm)
    t = resultat["totaux"]
    story = [Paragraph("SITUATION DE FREQUENTATION  -  ALSH", titre),
             Paragraph("<b>%s</b>" % escape(resultat["emetteur"]), corps),
             Paragraph("Commune : <b>%s</b>  |  Année civile : <b>%s</b>  |  Arrêté : <b>%s</b>" % (
                 escape(resultat["commune"]), resultat["annee"], resultat["arrete"]), corps),
             Spacer(1, 2*mm), Paragraph("Statut : <b>%s</b>" % escape(resultat["statut"]), corps)]
    if fictif:
        story.append(Paragraph("<font color='#b52e2e'><b>EXEMPLE DE TEST - DONNEES FICTIVES - NE PAS TRANSMETTRE</b></font>", corps))
    story.append(Paragraph("Participations par accueil", sous))
    headers = ["Accueil", "€/journée", "Présents", "Abs. inj. retenues", "Prévus", "Participation estimée"]
    tableau = [headers]
    for c in resultat["conventions"].values():
        tableau.append([c["accueil"], _fr_centimes(c["tarif_centimes"]),
                        _fr_jours(c["realise"]), _fr_jours(c["absences_injustifiees"]),
                        _fr_jours(c["prevision"]), _fr_centimes(c["participation_estimee"])])
    if len(tableau) == 1:
        tableau.append(["Aucune convention", "-", "-", "-", "-", "-"])
    col_w = [40*mm, 25*mm, 22*mm, 32*mm, 18*mm, 35*mm]
    table = Table(tableau, colWidths=col_w, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), bleu), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#eff3f7")]),
        ("ALIGN",(1,0),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story += [table, Paragraph("Situation financière de la participation communale", sous)]
    resumes = [
        ("Journées-enfants effectivement réalisées", _fr_jours(t["journees_reelles"]), "jours"),
        ("Absences injustifiées retenues (non présences)", _fr_jours(t["journees_absences_injustifiees"]), "jours"),
        ("Journées-enfants encore prévues", _fr_jours(t["journees_prevues"]), "jours"),
        ("Participation correspondant aux journées réalisées", _fr_centimes(t["participation_reelle"]), "EUR"),
        ("Participation optionnelle des absences injustifiées", _fr_centimes(t["participation_absences_injustifiees"]), "EUR"),
        ("Participation prévisionnelle jusqu'au 31 décembre", _fr_centimes(t["participation_prevue"]), "EUR"),
        ("Participation annuelle estimée", _fr_centimes(t["participation_estimee"]), "EUR"),
        ("Acomptes communaux effectivement reçus", _fr_centimes(t["acomptes_recus"]), "EUR"),
        ("Solde indicatif pour 2026", _fr_centimes(t["solde_indicatif"]), "EUR"),
    ]
    synthese = [[Paragraph(escape(nom), corps), valeur] for nom, valeur, _ in resumes]
    st = Table(synthese, colWidths=[119*mm, 53*mm], hAlign="LEFT")
    st.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.whitesmoke,colors.white]),
        ("ALIGN",(1,0),(1,-1),"RIGHT"), ("FONTNAME",(1,0),(1,-1),"Helvetica-Bold"),
        ("FONTSIZE",(1,0),(1,-1),8.5), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LINEABOVE",(0,6),(-1,6),.7,colors.HexColor("#a0abb9")),
        ("LINEABOVE",(0,8),(-1,8),.9,bleu),
    ]))
    story += [st, Paragraph("Détail par mois civil - tous accueils", sous)]
    mois_table = [["Mois", "Jours réels", "Abs. injustifiées", "Jours prévus", "Participation estimée"]]
    for mois in range(1, 13):
        m = resultat["mensuel"][str(mois)]
        mois_table.append(["%02d" % mois, _fr_jours(m["realise"]),
                           _fr_jours(m["absence_injustifiee"]),
                           _fr_jours(m["prevision"]), _fr_centimes(m["participation"])])
    mt = Table(mois_table, colWidths=[17*mm, 35*mm, 42*mm, 32*mm, 46*mm], hAlign="LEFT",repeatRows=1)
    mt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),bleu), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f3f6f9")]),
        ("FONTSIZE",(0,0),(-1,-1),7.7), ("ALIGN",(1,0),(-1,-1),"RIGHT"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),2.1), ("BOTTOMPADDING",(0,0),(-1,-1),2.1),
    ]))
    story.append(mt)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("<b>Méthode :</b> journées-enfants des habitants de la commune × tarif conventionnel propre à chaque accueil. "
                           "Les montants conventionnels intègrent déjà les autres ressources ayant servi à fixer le tarif. "
                           "Les prévisions ne constituent pas des présences réalisées. "
                           "Les absences injustifiées retenues, si l'option est cochée, restent des absences "
                           "et leur prise en compte par la commune doit être validée.", petite))
    if resultat["alertes"]:
        story.append(Paragraph("Points à vérifier", sous))
        for alerte in resultat["alertes"][:8]:
            story.append(Paragraph("- " + escape(alerte), petite))
        if len(resultat["alertes"]) > 8:
            story.append(Paragraph("Autres alertes : %d" % (len(resultat["alertes"])-8), petite))
    if t["solde_verifie"] is None:
        story.append(Paragraph("<b>Document provisoire :</b> solde indicatif calculé sur les données saisies, "
                               "à contrôler avant toute transmission officielle.", petite))
    doc.build(story)
    return p