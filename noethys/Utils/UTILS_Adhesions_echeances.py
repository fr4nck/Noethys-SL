# -*- coding: utf-8 -*-
"""P1 #426 : préparation explicite des cotisations à la clôture / facturation.

Aucun effet de bord lors de Proposer(). Les écritures ne commencent qu'après
confirmation sur l'écran de facturation et revalidation du cliché d'aperçu.
La sauvegarde des réservations ne déclenche JAMAIS ce service.
"""
import datetime

from Utils import UTILS_Adhesions as A


def _fenetre(date_debut, date_fin, date_reference):
    debut = A._en_date(date_debut)
    fin = A._en_date(date_fin)
    jour = A._en_date(date_reference) if date_reference else datetime.date.today()
    if debut is None or fin is None or debut > fin:
        raise ValueError(u"Dates de clôture/facturation incohérentes.")
    if jour > datetime.date.today():
        raise ValueError(u"La date de traitement ne peut pas être future.")
    return debut, fin, jour, min(jour, fin)


def _participants(debut, limite, activites, compte_payeur=None):
    liste = A._liste_sql(activites)
    filtre_payeur_c = (" AND IDcompte_payeur=%d" % int(compte_payeur)) if compte_payeur is not None else ""
    conso = A._lire("""SELECT DISTINCT IDindividu FROM consommations
    WHERE IDindividu IS NOT NULL AND IDactivite IN %s
    AND etat IN ('reservation', 'present') AND date>='%s' AND date<='%s'%s;"""
                    % (liste, debut, limite, filtre_payeur_c))
    presta = A._lire("""SELECT DISTINCT IDindividu FROM prestations
    WHERE IDindividu IS NOT NULL AND IDactivite IN %s
    AND categorie='consommation' AND date>='%s' AND date<='%s'%s
    AND NOT EXISTS (SELECT 1 FROM consommations c
        WHERE c.IDindividu=prestations.IDindividu
        AND c.IDactivite=prestations.IDactivite
        AND c.date=prestations.date);"""
                     % (liste, debut, limite, filtre_payeur_c))
    return sorted({int(row[0]) for row in conso + presta})


def Proposer(date_debut, date_fin, date_reference=None, liste_activites=None,
             IDcompte_payeur=None):
    """Liste les créations proposées, sans écriture. Refuse tout jour à venir.

    Les séquences plus anciennes sont examinées : on bloque une création
    si elle masquerait un premier passage non couvert avant le début
    sélectionné (la période doit être élargie ou examinée manuellement).
    """
    debut, fin, jour, limite = _fenetre(date_debut, date_fin, date_reference)
    resultat = {"date_debut": debut, "date_fin": fin, "date_reference": jour,
                "date_limite": limite, "propositions": [], "a_verifier": [],
                "IDcompte_payeur": IDcompte_payeur}
    if limite < debut:
        return resultat
    config = A.ResoudreConfiguration()
    liees = set(A.GetActivitesConcernees(config["IDtype_cotisation"]))
    retenues = sorted(liees.intersection(set(int(x) for x in liste_activites))
                     if liste_activites is not None else liees)
    resultat["activites"] = retenues
    if not retenues:
        return resultat
    groupes = {}
    for IDindividu in _participants(debut, limite, retenues, IDcompte_payeur):
        # La recherche historique évite la datation fausse d'une adhésion.
        participations = A.GetParticipations(IDindividu, retenues, datetime.date(1900, 1, 1), limite)
        for p in participations:
            if IDcompte_payeur is not None and p.get("IDcompte_payeur") != IDcompte_payeur:
                continue
            titulaire = A.ResoudreTitulaire(IDindividu, p)
            if titulaire["motif"]:
                resultat["a_verifier"].append({"IDindividu": IDindividu, "date": p["date"],
                                               "motif": titulaire["motif"]})
                continue
            cle = titulaire["IDtitulaire"]
            groupes.setdefault(cle, []).append((IDindividu, p, titulaire))

    for IDtitulaire, tuples in sorted(groupes.items()):
        # Une cotisation par titulaire et non par section, activité ou groupe.
        tuples.sort(key=lambda x: (x[1]["date"], x[0], x[1]["id"]))
        adhesions = A.GetAdhesions(IDtitulaire, config["IDtype_cotisation"])
        for IDindividu, participation, titulaire in tuples:
            jour_p = participation["date"]
            if any(A._est_valide(a, jour_p) for a in adhesions):
                continue
            if jour_p < debut:
                resultat["a_verifier"].append({
                    "IDindividu": IDindividu, "IDtitulaire": IDtitulaire,
                    "date": jour_p, "motif": "premiere_participation_anterieure"})
                break
            fin_cotisation = A.CalculerDateFin(jour_p, config["duree"])
            chevauchement = any(a["date_debut"] <= fin_cotisation and
                                a["date_fin"] >= jour_p for a in adhesions)
            if chevauchement:
                resultat["a_verifier"].append({
                    "IDindividu": IDindividu, "IDtitulaire": IDtitulaire,
                    "date": jour_p, "motif": "chevauchement"})
                break
            # La date de la prestation est celle du traitement du mois,
            # bornée à la fin de période : elle figure DANS l'aperçu.
            date_comptable = limite
            if date_comptable < jour_p:
                raise AssertionError("Prestation antérieure à la participation")
            # Une seule proposition par titulaire pour cette fenêtre.
            resultat["propositions"].append({
                "IDindividu": IDindividu,
                "IDtitulaire": IDtitulaire,
                "IDcompte_payeur": titulaire["IDcompte_payeur"],
                "participation": participation,
                "date_debut": jour_p, "date_fin": fin_cotisation,
                "date_prestation": date_comptable,
                "montant": config["montant"],
                "IDtype_cotisation": config["IDtype_cotisation"],
            })
            break
    return resultat


def Empreinte(propositions):
    """Cliché de proposition : vérifié intégralement avant la moindre écriture."""
    return tuple(sorted((
        int(p["IDindividu"]), int(p["IDtitulaire"]),
        int(p["IDcompte_payeur"]), str(p["date_debut"]),
        str(p["date_fin"]), str(p["date_prestation"]),
        p["participation"]["source"], int(p["participation"]["id"]),
        str(p["montant"]), int(p["IDtype_cotisation"])
    ) for p in propositions))


def Executer(proposition_validee, liste_activites=None, IDcompte_payeur=None,
             IDutilisateur=None, confirmation=False):
    """Applique uniquement un cliché confirmé. Une variation => STOP sans écriture.

    Les contrôles dans CreerAdhesion sont refaits sous verrou transactionnel.
    Aucun retour ne doit être masqué : des créations partielles exigent
    un nouveau contrôle avant tout aperçu ou émission de facture.
    """
    if confirmation is not True:
        raise ValueError(u"Création financière refusée sans confirmation explicite.")
    if not isinstance(proposition_validee, dict):
        raise ValueError("Proposition de facturation absente")
    debut, fin, jour, _limite = _fenetre(
        proposition_validee["date_debut"], proposition_validee["date_fin"],
        proposition_validee["date_reference"])
    config = A.ResoudreConfiguration()
    source_activites = (liste_activites if liste_activites is not None else
                        proposition_validee.get("activites", []))
    source_payeur = (IDcompte_payeur if IDcompte_payeur is not None else
                     proposition_validee.get("IDcompte_payeur"))
    actuel = Proposer(debut, fin, jour, source_activites, source_payeur)
    if (Empreinte(actuel["propositions"]) != Empreinte(proposition_validee["propositions"])
            or actuel["a_verifier"] != proposition_validee["a_verifier"]):
        raise ValueError(u"Les participations ou les cotisations ont changé : recalcul de l'aperçu obligatoire.")
    resultats = []
    for p in actuel["propositions"]:
        creation = A.CreerAdhesion(
            p["IDindividu"], p["participation"], config,
            date_reference=jour, IDutilisateur=IDutilisateur,
            date_prestation=p["date_prestation"])
        resultats.append(creation)
        if creation["statut"] not in (A.STATUT_CREE, A.STATUT_RIEN):
            # Les créations précédentes, déjà validées, sont signalées :
            # jamais de réussite trompeuse ; l'opérateur doit relire.
            break
    return resultats


def AuditerCotisationsAnticipees(date_reference=None):
    """Inventaire RC7 en lecture seule, sans regularisation implicite.

    Recherche les cotisations automatiques dont la validite commence apres la
    saisie OU apres la date du jour, ainsi que les prestations de cotisation
    qui leur sont liees. Les etats factures/ventiles restent signales :
    l'operateur doit examiner chaque ligne avant toute correction.
    """
    jour = A._en_date(date_reference) if date_reference else datetime.date.today()
    req = """SELECT c.IDcotisation, c.IDindividu, c.date_saisie,
        c.date_debut, c.date_fin, c.IDprestation,
        p.date, p.IDfacture,
        (SELECT COUNT(*) FROM ventilation v
         WHERE v.IDprestation=c.IDprestation) AS nb_ventilations
    FROM cotisations c
    LEFT JOIN prestations p ON p.IDprestation=c.IDprestation
    WHERE c.observations LIKE '%%[adhesion-auto]%%'
      AND (c.date_debut > c.date_saisie OR c.date_debut > '%s'
           OR (p.date IS NOT NULL AND p.date < c.date_debut))
    ORDER BY c.date_debut, c.IDcotisation;""" % jour
    lignes = A._lire(req)
    rapport = []
    for (IDcotisation, IDindividu, saisie, debut, fin, IDprestation,
         date_prestation, IDfacture, nb_ventilations) in lignes:
        date_debut = A._en_date(debut)
        date_saisie = A._en_date(saisie) if saisie else None
        date_fin = A._en_date(fin)
        date_comptable = A._en_date(date_prestation) if date_prestation else None
        motifs = []
        if date_saisie is not None and date_debut > date_saisie:
            motifs.append("validite_anticipee")
        if date_debut > jour:
            motifs.append("participation_future")
        if date_comptable is not None and date_comptable < date_debut:
            motifs.append("prestation_anticipee")
        if IDprestation is None or date_comptable is None:
            motifs.append("prestation_introuvable")
        rapport.append({
            "IDcotisation": IDcotisation, "IDindividu": IDindividu,
            "IDprestation": IDprestation, "date_saisie": date_saisie,
            "date_debut": date_debut, "date_fin": date_fin,
            "date_prestation": date_comptable,
            "IDfacture": IDfacture, "nb_ventilations": nb_ventilations or 0,
            "motifs": tuple(motifs),
            "statut": ("reglement_ou_facture_a_regolariser"
                       if IDfacture or nb_ventilations else
                       "a_verifier_avant_regularisation"),
        })
    return rapport

