# -*- coding: utf-8 -*-
"""Inventaire RC7, sans dépendance UI, configuration, écriture ou régularisation.

Le lecteur injecté doit échouer sur toute erreur SQL et fournir un cliché cohérent.
Une seule requête SELECT couvre les liens ; aucune comparaison de date en SQL.
Les dates suspectes sont des indices, jamais une preuve de participation réelle.
"""
import datetime
from decimal import Decimal, InvalidOperation

VERSION_AUDIT = "1.0"
SOURCE_RC81 = "00f53db463d812e31f0eee7e56e0db00835b8162"
TABLES = ("cotisations", "prestations", "factures", "ventilation", "reglements")

REQUETE = """SELECT c.IDcotisation, c.IDindividu, c.IDfamille,
 c.IDtype_cotisation, c.IDunite_cotisation, c.date_saisie,
 c.date_debut, c.date_fin, c.IDprestation,
 p.IDprestation, p.IDcompte_payeur, p.IDindividu, p.IDfamille,
 p.categorie, p.date, p.date_valeur, p.montant, p.IDfacture,
 f.IDfacture, f.numero, f.date_edition, f.etat, f.IDcompte_payeur,
 v.IDventilation, v.IDcompte_payeur, v.IDreglement, v.montant,
 r.IDreglement, r.IDcompte_payeur, r.date, r.montant, r.encaissement_attente,
 (SELECT COUNT(*) FROM cotisations autres
  WHERE autres.IDprestation=c.IDprestation) AS nb_cotisations_liees
 FROM cotisations c
 LEFT JOIN prestations p ON p.IDprestation=c.IDprestation
 LEFT JOIN factures f ON f.IDfacture=p.IDfacture
 LEFT JOIN ventilation v ON v.IDprestation=c.IDprestation
 LEFT JOIN reglements r ON r.IDreglement=v.IDreglement
 WHERE c.observations LIKE '%[adhesion-auto]%'
 ORDER BY c.IDcotisation, v.IDventilation;"""


def date_iso(valeur):
    """Validation stricte : aucune date SQL invalide transformée en date plausible."""
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    if not isinstance(valeur, str) or len(valeur) != 10:
        raise ValueError("Date attendue au format AAAA-MM-JJ")
    date = datetime.date.fromisoformat(valeur)
    if date.isoformat() != valeur:
        raise ValueError("Date attendue au format AAAA-MM-JJ")
    return date


def _date(valeur, champ, motifs, obligatoire=True):
    if valeur is None or valeur == "":
        if obligatoire:
            motifs.append(champ + "_absente")
        return None
    try:
        return date_iso(valeur)
    except (ValueError, TypeError):
        motifs.append(champ + "_invalide")
        return None


def _montant(valeur):
    try:
        nombre = Decimal(str(valeur))
        return nombre if nombre.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _different(a, b):
    return a is not None and b is not None and a != b


def ConstruireInventaire(lire, date_reference):
    """Retourne les suspects et la couverture ; aucun appel métier créateur.

    Aucun filtre de date de saisie : les anomalies historiques restent visibles.
    Les adhésions manuelles ne sont pas sélectionnées. Les liens financiers
    absents, partagés ou incohérents sont conservés pour contrôle comptable.
    """
    jour = date_iso(date_reference)
    groupes = {}
    for row in lire(REQUETE):
        if len(row) != 33:
            raise ValueError("Schéma d'audit inattendu ; rapport interrompu")
        groupes.setdefault(row[0], []).append(row)
    lignes = []
    for rows in groupes.values():
        row = rows[0]
        (cid, individu, famille, type_c, unite, saisie, debut, fin, pid,
         p_existe, payeur, p_individu, p_famille, categorie, date_p,
         date_valeur, montant_p, fid, f_existe, numero, edition, etat,
         f_payeur) = row[:23]
        motifs = []
        dates = {champ: _date(valeur, champ, motifs) for champ, valeur in (
            ("date_saisie", saisie), ("date_debut", debut), ("date_fin", fin))}
        d, s, f = dates["date_debut"], dates["date_saisie"], dates["date_fin"]
        if d and s and d > s:
            motifs.append("validite_anticipee")
        if d and d > jour:
            motifs.append("validite_future")
        if d and f and f < d:
            motifs.append("validite_inversee")
        if pid is None or p_existe is None:
            motifs.append("prestation_introuvable")
        dp = _date(date_p, "date_prestation", motifs) if p_existe is not None else None
        dv = _date(date_valeur, "date_valeur", motifs, False)
        if d and dp and dp < d:
            motifs.append("prestation_anticipee")
        if d and dv and dv < d:
            motifs.append("date_valeur_anticipee")
        montant = _montant(montant_p)
        if p_existe is not None:
            if categorie != "cotisation":
                motifs.append("categorie_prestation_inattendue")
            if montant is None:
                motifs.append("montant_prestation_invalide")
            if payeur is None:
                motifs.append("payeur_prestation_absent")
            if _different(individu, p_individu):
                motifs.append("individu_prestation_incoherent")
            if _different(famille, p_famille):
                motifs.append("famille_prestation_incoherente")
        nb_liees = row[32]
        if nb_liees > 1:
            motifs.append("prestation_partagee")
        # Une référence comptable, même cassée, interdit de conclure « libre ».
        facture_referencee = fid not in (None, 0)
        if facture_referencee and f_existe is None:
            motifs.append("facture_introuvable")
        if _different(payeur, f_payeur):
            motifs.append("payeur_facture_incoherent")
        ventilations = []
        for vrow in rows:
            vid, vpayeur, rid, vmontant, r_existe, rpayeur, rdate, rmontant, attente = vrow[23:32]
            if vid is None:
                continue
            vm = _montant(vmontant)
            if vm is None:
                motifs.append("montant_ventilation_invalide")
            if _different(payeur, vpayeur) or _different(payeur, rpayeur):
                motifs.append("payeur_ventilation_ou_reglement_incoherent")
            if r_existe is None:
                motifs.append("reglement_introuvable")
            ventilations.append({
                "IDventilation": vid, "IDcompte_payeur": vpayeur,
                "IDreglement": rid, "montant": str(vm) if vm is not None else None,
                "reglement_existe": r_existe is not None,
                "reglement_date": str(rdate) if rdate is not None else None,
                "reglement_montant_total": str(rmontant) if rmontant is not None else None,
                "encaissement_attente": attente,
            })
        montants_v = [_montant(v["montant"]) for v in ventilations]
        total_v = sum(montants_v, Decimal("0")) if all(v is not None for v in montants_v) else None
        etat_comptable = ("facturee_et_ventilee" if facture_referencee and ventilations else
                          "facturee" if facture_referencee else "ventilee" if ventilations else
                          "sans_facture_ni_ventilation_identifiee")
        # Historique n'est pas équivalent à « anomalie encore active ».
        anticipation = any(m in motifs for m in (
            "validite_anticipee", "validite_future", "prestation_anticipee", "date_valeur_anticipee"))
        if motifs:
            lignes.append({
                "IDcotisation": cid, "IDindividu": individu, "IDfamille": famille,
                "IDtype_cotisation": type_c, "IDunite_cotisation": unite,
                "IDprestation": pid, **dates, "date_prestation": dp, "date_valeur": dv,
                "dates_brutes": {"saisie": str(saisie), "debut": str(debut), "fin": str(fin),
                                  "prestation": str(date_p), "valeur": str(date_valeur)},
                "prestation_existe": p_existe is not None,
                "categorie_prestation": categorie, "IDcompte_payeur": payeur,
                "montant_prestation": str(montant) if montant is not None else None,
                "nb_cotisations_liees": nb_liees,
                "IDfacture": fid, "facture_referencee": facture_referencee,
                "facture_existe": f_existe is not None, "numero_facture": numero,
                "date_edition_facture": str(edition) if edition is not None else None,
                "etat_facture": etat, "nb_ventilations": len(ventilations),
                "montant_ventile": str(total_v) if total_v is not None else None,
                "ventilations": ventilations, "etat_comptable": etat_comptable,
                "anticipation_detectee": anticipation, "motifs": tuple(sorted(set(motifs))),
                "statut": ("reglement_ou_facture_a_regolariser" if facture_referencee or ventilations
                           else "a_verifier_avant_regularisation"),
                "action_automatique": "aucune", "participation_reelle_verifiee": False,
            })
    lignes.sort(key=lambda r: (r["date_debut"] or datetime.date.min, r["IDcotisation"]))
    # Une prestation partagée n'est comptée qu'une fois dans les montants.
    prestations = {r["IDprestation"]: r for r in lignes if r["prestation_existe"]}
    montants = [_montant(r["montant_prestation"]) for r in prestations.values()]
    total = sum((m for m in montants if m is not None), Decimal("0"))
    return {
        "version_audit": VERSION_AUDIT, "source_rc81": SOURCE_RC81,
        "date_reference": jour, "cotisations_automatiques_examinees": len(groupes),
        "cotisations_signalees": len(lignes), "prestations_distinctes_signalees": len(prestations),
        "total_montants_prestations_connus": str(total),
        "prestations_montant_inconnu": sum(m is None for m in montants),
        "regularisation_automatique": False, "lignes": lignes,
        "limites": ["Marqueur [adhesion-auto] seulement ; origine RC7 non prouvée par le marqueur.",
                    "Absence de facture/ventilation ne prouve ni absence de règlement du compte ni droit de suppression.",
                    "Ventilation et règlement référencé ne prouvent pas l'encaissement bancaire.",
                    "Aucune présence réelle, annulation, utilisation, période verrouillée ou règle de titulaire requalifiée.",
                    "Montants signés indicatifs, pas un montant de remboursement ni de régularisation."],
    }
