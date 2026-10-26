# -*- coding: utf-8 -*-
"""Lot 2C-3 : audit financier ALSH en lecture seule et accord de tarification.

Le flag unites.repas=1 signifie repas inclus, PAS tarif repas dissociable.
Aucune ecriture SQL, aucune facture recalculee, aucun nom de famille charge.
L'accord explicite n'est qu'un prevol, pas une autorisation de facturer :
la grille Noethys n'appelle pas ce module automatiquement.
"""
from datetime import date, datetime
from decimal import Decimal

from Utils.UTILS_Repas_tarification_2c import (
    EvaluerPanier, TarificationPanierInvalide
)


class AuditTarifs2CInvalide(ValueError):
    """Prevol financier bloque : intervention humaine necessaire."""


def _id(valeur, nom):
    if type(valeur) is not int or valeur <= 0:
        raise AuditTarifs2CInvalide("%s : identifiant entier strictement positif requis" % nom)
    return valeur


def _date(valeur, nom):
    if type(valeur) is date:
        return valeur
    if type(valeur) is str:
        try:
            resultat = date.fromisoformat(valeur)
        except ValueError:
            pass
        else:
            if resultat.isoformat() == valeur:
                return resultat
    raise AuditTarifs2CInvalide("%s : date ISO valide requise" % nom)


def _req(base, sql):
    if not sql.lstrip().upper().startswith("SELECT "):
        raise AuditTarifs2CInvalide("Audit obligatoirement en lecture seule")
    if not base.ExecuterReq(sql):
        raise AuditTarifs2CInvalide("Lecture des tarifs echouee")
    resultat = base.ResultatReq()
    if resultat is None:
        raise AuditTarifs2CInvalide("Resultat de base indisponible")
    return list(resultat)


def _index_lignes(resultats):
    sortie = {}
    for ident, *champs in resultats:
        sortie[int(ident)] = tuple(champs)
    return sortie


def AuditerTarifsALSH(base, activites):
    """Rapport anonyme sur tarifs, combinaisons et etat comptable.

    base: instance Noethys GestionDB.DB injectee ; fermeture par l'appelant.
    activites: IDactivite ALSH explicites. Aucun filtrage au libelle.
    """
    if not isinstance(activites, (list, tuple, set, frozenset)) or not activites:
        raise AuditTarifs2CInvalide("Selection explicite d'activites ALSH requise")
    ids = tuple(sorted({_id(valeur, "IDactivite") for valeur in activites}))
    if len(ids) > 50:
        raise AuditTarifs2CInvalide("Auditez au maximum 50 activites par passe")
    conditions = ",".join(str(i) for i in ids)
    lignes = _req(base, """SELECT t.IDtarif, t.IDactivite, t.type, t.methode,
       t.date_debut, t.date_fin, n.nom
       FROM tarifs AS t
       LEFT JOIN noms_tarifs AS n ON n.IDnom_tarif=t.IDnom_tarif
       WHERE t.IDactivite IN (%s)
       ORDER BY t.IDactivite,t.IDtarif""" % conditions)
    if not lignes:
        return {"activites": ids, "tarifs": (), "tarifs_a_qualifier": 0}
    tarifs = {}
    for ident, activite, typ, methode, debut, fin, nom in lignes:
        ident, activite = _id(ident, "IDtarif"), _id(activite, "IDactivite")
        if ident in tarifs:
            raise AuditTarifs2CInvalide("IDtarif duplique dans la source")
        tarifs[ident] = {
            "IDtarif": ident, "IDactivite": activite,
            "type": typ, "methode": methode,
            "date_debut": debut, "date_fin": fin,
            "nom_tarif": nom or "", "combinaisons": [],
            "nombre_lignes_prix": 0,
            "prestations_existantes": 0,
            "prestations_facturees": 0,
            "prestations_forfait": 0,
            "prestations_ventilees": 0,
            "statut": "A_QUALIFIER", "risques": [],
        }

    subset = ",".join(str(i) for i in sorted(tarifs))
    combos = _req(base, """SELECT c.IDtarif, c.IDcombi_tarif, c.type,
           cu.IDunite, u.IDactivite, u.repas
           FROM combi_tarifs AS c
           LEFT JOIN combi_tarifs_unites AS cu
             ON cu.IDcombi_tarif=c.IDcombi_tarif
           LEFT JOIN unites AS u ON u.IDunite=cu.IDunite
           WHERE c.IDtarif IN (%s)
           ORDER BY c.IDtarif, c.IDcombi_tarif, cu.IDunite""" % subset)
    par_tarif = {}
    for tarif, combi, nature, unite, activite, repas in combos:
        par_tarif.setdefault(int(tarif), {}).setdefault(int(combi), {
            "IDcombi_tarif": int(combi), "type": nature, "unites": []
        })["unites"].append({
            "IDunite": unite, "IDactivite": activite, "repas_inclus": repas
        })

    for ident, (count,) in _index_lignes(_req(base,
            "SELECT IDtarif, COUNT(*) FROM tarifs_lignes "
            "WHERE IDtarif IN (%s) GROUP BY IDtarif" % subset)).items():
        tarifs[ident]["nombre_lignes_prix"] = int(count)

    prestations = _req(base, """SELECT IDtarif, COUNT(*),
       SUM(CASE WHEN IDfacture IS NOT NULL THEN 1 ELSE 0 END),
       SUM(CASE WHEN forfait IS NOT NULL THEN 1 ELSE 0 END)
       FROM prestations WHERE IDtarif IN (%s) GROUP BY IDtarif""" % subset)
    for ident, total, factures, forfaits in prestations:
        row = tarifs[int(ident)]
        row["prestations_existantes"] = int(total)
        row["prestations_facturees"] = int(factures)
        row["prestations_forfait"] = int(forfaits)

    ventilation = _req(base, """SELECT p.IDtarif, COUNT(DISTINCT p.IDprestation)
       FROM prestations AS p
       JOIN ventilation AS v ON v.IDprestation=p.IDprestation
       WHERE p.IDtarif IN (%s) GROUP BY p.IDtarif""" % subset)
    for ident, count in ventilation:
        tarifs[int(ident)]["prestations_ventilees"] = int(count)

    for ident, ligne in tarifs.items():
        ligne["combinaisons"] = tuple(par_tarif.get(ident, {}).values())
        if ligne["type"] != "JOURN":
            ligne["risques"].append("TARIF_NON_JOURNALIER_OU_CREDIT")
        if len(ligne["combinaisons"]) != 1:
            ligne["risques"].append("COMBINAISONS_NON_UNIQUES")
        for combinaison in ligne["combinaisons"]:
            if combinaison["type"] != "JOURN" or len(combinaison["unites"]) != 1:
                ligne["risques"].append("COMBINAISON_COMPOSITE")
            for unite in combinaison["unites"]:
                if (type(unite["IDunite"]) is not int
                        or unite["IDactivite"] != ligne["IDactivite"]):
                    ligne["risques"].append("UNITE_INCONNUE_OU_INTERACTIVITES")
                if unite["repas_inclus"] != 1:
                    ligne["risques"].append("REPAS_INCLUS_NON_CONFIRME")
        if ligne["nombre_lignes_prix"] == 0:
            ligne["risques"].append("AUCUNE_LIGNE_TARIF")
        if ligne["prestations_facturees"]:
            ligne["risques"].append("FACTURES_EXISTANTES_A_PRESERVER")
        if ligne["prestations_ventilees"]:
            ligne["risques"].append("REGLEMENTS_EXISTANTS_A_PRESERVER")
        # Jamais un statut AUTO_APPROUVE : la qualification humaine
        # des prix, du site et de l'unite reste obligatoire.
        ligne["risques"] = tuple(dict.fromkeys(ligne["risques"]))
    return {
        "activites": ids,
        "tarifs": tuple(tarifs[k] for k in sorted(tarifs)),
        "tarifs_a_qualifier": len(tarifs),
    }


def ValiderAccordTarifSepare(rapport, decision):
    """Prevol opt-in : ni migration ni activation des ecritures Noethys."""
    if not isinstance(decision, dict) or not isinstance(rapport, dict):
        raise AuditTarifs2CInvalide("Rapport et decision explicites obligatoires")
    activite = _id(decision.get("IDactivite"), "IDactivite")
    tarif = _id(decision.get("IDtarif_repas"), "IDtarif_repas")
    unite = _id(decision.get("IDunite_repas"), "IDunite_repas")
    question = _id(decision.get("IDquestion"), "IDquestion")
    choix = _id(decision.get("IDchoix_panier"), "IDchoix_panier")
    debut = _date(decision.get("date_debut"), "date_debut")
    fin = _date(decision.get("date_fin"), "date_fin")
    if fin < debut:
        raise AuditTarifs2CInvalide("Intervalle de validite inverse")
    for champ in ("site", "service", "approbateur", "preuve_tarif"):
        valeur = decision.get(champ)
        if not isinstance(valeur, str) or not valeur.strip() or valeur != valeur.strip():
            raise AuditTarifs2CInvalide("%s : valeur verifiable requise" % champ)
    if (decision.get("tarif_repas_dedie_confirme") is not True
            or decision.get("accueil_facture_independamment_confirme") is not True):
        raise AuditTarifs2CInvalide("Separation repas/accueil non approuvee")
    try:
        horodatage = datetime.fromisoformat(decision["approuve_le"])
    except (TypeError, ValueError, KeyError):
        raise AuditTarifs2CInvalide("Horodatage d'approbation invalide")
    if horodatage.tzinfo is None or horodatage.utcoffset() is None:
        raise AuditTarifs2CInvalide("Approbation avec fuseau requise")
    ligne = next((x for x in rapport.get("tarifs", ())
                  if x["IDtarif"] == tarif and x["IDactivite"] == activite), None)
    if ligne is None or activite not in rapport.get("activites", ()):
        raise AuditTarifs2CInvalide("Tarif non trouve dans l'audit de l'activite")
    if ligne["type"] != "JOURN" or len(ligne["combinaisons"]) != 1:
        raise AuditTarifs2CInvalide("Forfait ou tarif composite non separable")
    combinaison = ligne["combinaisons"][0]
    if combinaison["type"] != "JOURN" or len(combinaison["unites"]) != 1:
        raise AuditTarifs2CInvalide("Combinaison non limitee a un seul repas")
    unites = combinaison["unites"]
    if (unites[0]["IDunite"] != unite
            or unites[0]["IDactivite"] != activite
            or unites[0]["repas_inclus"] != 1):
        raise AuditTarifs2CInvalide("Unite de repas dediee non demontree")
    if not ligne["nombre_lignes_prix"]:
        raise AuditTarifs2CInvalide("Tarif sans lignes de calcul")
    if ligne["date_debut"] is None or debut < _date(ligne["date_debut"], "debut tarif"):
        raise AuditTarifs2CInvalide("Tarif hors periode de validite")
    if ligne["date_fin"] is not None and fin > _date(ligne["date_fin"], "fin tarif"):
        raise AuditTarifs2CInvalide("Periode de decision depassant le tarif")
    return {
        "IDactivite": activite, "IDtarif_repas": tarif,
        "IDunite_repas": unite, "IDquestion": question,
        "IDchoix_panier": choix, "date_debut": debut, "date_fin": fin,
        "site": decision["site"], "service": decision["service"],
        "approbateur": decision["approbateur"],
        "preuve_tarif": decision["preuve_tarif"],
        "approuve_le": decision["approuve_le"],
        "etat": "PREVOL_MANUEL_NON_ACTIF",
    }


def SimulerNouvellePrestationPanier(accord, reponse_datee, montant_accueil,
                                   montant_repas, prestation_existante=None,
                                   facture_emise=False, prestation_reglee=False):
    """Prepare 'ne pas creer de repas payant', sans ecrire ou toucher CAF."""
    if accord.get("etat") != "PREVOL_MANUEL_NON_ACTIF":
        raise AuditTarifs2CInvalide("Tarif panier non qualifie")
    if not isinstance(reponse_datee, dict):
        raise AuditTarifs2CInvalide("Source historique individuelle requise")
    jour = _date(reponse_datee.get("date"), "date de presence")
    if not accord["date_debut"] <= jour <= accord["date_fin"]:
        raise AuditTarifs2CInvalide("Presence hors periode de la decision")
    if (_id(reponse_datee.get("IDindividu"), "IDindividu") <= 0
            or reponse_datee.get("IDactivite") != accord["IDactivite"]
            or reponse_datee.get("IDtarif_repas") != accord["IDtarif_repas"]
            or reponse_datee.get("IDunite_repas") != accord["IDunite_repas"]
            or reponse_datee.get("site") != accord["site"]
            or reponse_datee.get("service") != accord["service"]):
        raise AuditTarifs2CInvalide("Evenement hors perimetre")
    if reponse_datee.get("type_repas") != "sans_repas_pmsl":
        raise AuditTarifs2CInvalide("Exoneration reservee au panier explicite")
    if (_id(reponse_datee.get("IDquestion"), "IDquestion") != accord["IDquestion"]
            or _id(reponse_datee.get("IDchoix_panier"), "IDchoix_panier") != accord["IDchoix_panier"]):
        raise AuditTarifs2CInvalide("Choix panier non rattache au questionnaire valide")
    if (reponse_datee.get("presence_midi_qualifiee") is not True
            or reponse_datee.get("origine_plage") not in ("journee", "demi_journee_avec_midi")
            or reponse_datee.get("etat_accueil") not in ("reservation", "present")):
        raise AuditTarifs2CInvalide("Presence midi non demontree par la formule d accueil")
    if reponse_datee.get("provenance") not in ("exception_datee", "snapshot_date"):
        raise AuditTarifs2CInvalide("Questionnaire actuel non historique refuse")
    if type(reponse_datee.get("horodatage")) is not str:
        raise AuditTarifs2CInvalide("Instant de choix trace requis")
    try:
        instant = datetime.fromisoformat(reponse_datee["horodatage"])
    except ValueError:
        raise AuditTarifs2CInvalide("Horodatage de choix illisible")
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise AuditTarifs2CInvalide("Horodatage de choix sans fuseau")
    if prestation_existante is not None or facture_emise or prestation_reglee:
        raise AuditTarifs2CInvalide("Prestation ou facture preexistante : regularisation manuelle")
    try:
        cout = EvaluerPanier("sans_repas_pmsl", "repas_separe",
                            montant_accueil, montant_repas,
                            facture_emise=facture_emise,
                            prestation_reglee=prestation_reglee)
    except TarificationPanierInvalide as exc:
        raise AuditTarifs2CInvalide(str(exc))
    return {
        "action": "NE_PAS_CREER_PRESTATION_REPAS_PAYANTE",
        "montant_repas": Decimal("0.00"),
        "montant_accueil": cout["accueil"],
        "montant_total": cout["total"],
        "IDtarif_repas": accord["IDtarif_repas"],
        "date": jour,
        "statut": "SIMULATION_SANS_ECRITURE",
    }
