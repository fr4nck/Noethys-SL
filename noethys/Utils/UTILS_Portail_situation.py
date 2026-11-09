# -*- coding: utf-8 -*-
"""Situation de famille en lecture seule dans le traitement Connecthys.

Le solde au jour n'est pas le solde global : les prestations et les
reglements futurs sont exclus. Les factures impayees utilisent les
prestations et ventilations actuelles (convention OL_Factures).
Aucune creation/renouvellement de cotisation ni ecriture SQL.
"""
import datetime
import html
from decimal import Decimal, ROUND_HALF_UP

import GestionDB

_CENTIME = Decimal("0.01")
_CIVILITES_MORALES = (6, 7, 8, 9)  # UTILS_Adhesions.CIVILITES_PERSONNE_MORALE


class SituationIndisponible(RuntimeError):
    pass


def _montant(valeur):
    try:
        return Decimal(str(valeur if valeur is not None else 0)).quantize(
            _CENTIME, rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ArithmeticError):
        raise SituationIndisponible("Montant comptable illisible")


def _date(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.date.fromisoformat(str(valeur)[:10])
    except (ValueError, TypeError):
        return None


def _identifiant(valeur, obligatoire=True):
    if valeur is None and not obligatoire:
        return None
    try:
        numero = int(valeur)
    except (ValueError, TypeError):
        raise SituationIndisponible("Identifiant de dossier invalide")
    if numero <= 0:
        raise SituationIndisponible("Identifiant de dossier invalide")
    return numero


def _lire(db, requete, arguments=()):
    if getattr(db, "echec", 0):
        raise SituationIndisponible("Connexion aux donnees indisponible")
    marque = "%s" if getattr(db, "isNetwork", False) else "?"
    try:
        db.cursor.execute(requete.replace("?", marque), tuple(arguments))
        return list(db.cursor.fetchall())
    except Exception as erreur:
        raise SituationIndisponible("Lecture de la situation impossible") from erreur


def _adhesion(db, IDfamille, IDindividu, au_jour):
    # Une structure ayant plusieurs personnes morales titulaires est ambigue.
    titulaires = _lire(db, """SELECT DISTINCT r.IDindividu
        FROM rattachements r
        JOIN individus i ON i.IDindividu=r.IDindividu
        WHERE r.IDfamille=? AND r.titulaire=1
          AND i.IDcivilite IN (6, 7, 8, 9)""", (IDfamille,))
    if len(titulaires) > 1:
        return {"statut": "a_verifier", "motif": "Plusieurs titulaires de structure"}
    titulaire_moral = int(titulaires[0][0]) if titulaires else None
    personnes = [IDindividu] if IDindividu else []
    if titulaire_moral is not None and titulaire_moral not in personnes:
        personnes.append(titulaire_moral)

    filtres = ["(c.IDfamille=? AND t.type='famille')"]
    valeurs = [IDfamille]
    if personnes:
        filtres.append("(c.IDindividu IN (%s) AND t.type='individu')" %
                       ", ".join("?" for _ in personnes))
        valeurs.extend(personnes)
    lignes = _lire(db, """SELECT c.IDcotisation, t.nom, t.carte, t.defaut,
             t.type, c.IDindividu, c.date_debut, c.date_fin, u.montant
             FROM cotisations c
             JOIN types_cotisations t ON t.IDtype_cotisation=c.IDtype_cotisation
             LEFT JOIN unites_cotisations u
               ON u.IDunite_cotisation=c.IDunite_cotisation
             WHERE %s
             ORDER BY c.date_fin DESC, c.IDcotisation DESC""" %
             " OR ".join(filtres), valeurs)
    valides, passees, futures = [], [], []
    illisibles = False
    for id_cotisation, nom, carte, defaut, genre, personne, debut, fin, montant in lignes:
        debut, fin = _date(debut), _date(fin)
        if debut is None or fin is None or fin < debut:
            illisibles = True
            continue
        # Le nom exact du type reste visible : une cotisation quelconque
        # n'est pas forcement une adhesion. Carte, type par defaut ou
        # denomination adhesion permettent un constat plus affirmatif.
        reconnu = bool(carte or defaut or "adh" in (nom or "").casefold())
        portee = ("structure" if titulaire_moral is not None and
                  personne == titulaire_moral and genre == "individu"
                  else "famille" if genre == "famille" else "enfant")
        entree = dict(nom=nom or "Cotisation sans libelle", debut=debut,
                      fin=fin, reconnue=reconnu, portee=portee,
                      montant=_montant(montant) if montant is not None else None,
                      IDcotisation=id_cotisation)
        if debut <= au_jour <= fin:
            valides.append(entree)
        elif fin < au_jour:
            passees.append(entree)
        else:
            futures.append(entree)
    if valides:
        valides.sort(key=lambda item: (item["reconnue"], item["fin"]), reverse=True)
        premiere = valides[0]
        return dict(premiere, statut="en_cours" if premiere["reconnue"] else "a_verifier",
                    motif=None if premiere["reconnue"] else ("Autre cotisation active : %s" % premiere["nom"]))
    if illisibles:
        return {"statut": "a_verifier", "motif": "Dates de cotisation incompletes"}
    if passees:
        return dict(max(passees, key=lambda v: v["fin"]), statut="expiree")
    if futures:
        return dict(min(futures, key=lambda v: v["debut"]), statut="a_venir")
    if IDindividu is None and titulaire_moral is None:
        return {"statut": "a_verifier", "motif": "Individu de la demande non identifie"}
    return {"statut": "absente"}



def _historique_annulations_connecthys(db, IDfamille, au_jour):
    """Rapport entre les demandes annulees et les reservations demandees.

    Perimetre : historique encore conserve de la famille dans
    portail_actions + portail_reservations, actions de reservations TRAITEES.
    Ceci ne reconstitue PAS les cancellations manuelles dans Noethys :
    'historique' les enregistre en texte libre, souvent en lots, sans
    identifiant de reservation stable. Le calcul n'est jamais presente
    comme exhaustif de toutes les annulations de la famille.

    Une cle de reservation est (inscription, unite portail, jour). Une
    demande repetee sur une cle encore active n'est pas une deuxieme
    reservation ; une suppression sans ajout anterieur retrouve est
    comptabilisee comme non appariee, pas comme annulation demontree.
    Apres suppression, un nouvel ajout constitue une nouvelle reservation.
    """
    lignes = _lire(db, """SELECT r.IDinscription, r.IDunite, r.date, r.etat,
           a.horodatage, a.IDaction, r.IDreservation
        FROM portail_reservations r
        JOIN portail_actions a ON a.IDaction=r.IDaction
        WHERE a.IDfamille=?
          AND a.categorie='reservations'
          AND a.etat='validation'
          AND a.horodatage<=?
        ORDER BY a.horodatage, a.IDaction, r.IDreservation""",
        (IDfamille, "%s 23:59:59" % au_jour.isoformat()))

    actives = set()
    reservations = annulations = orphelines = ignorees = doublons = 0
    premier = dernier = None
    for IDinscription, IDunite, jour, etat, horodatage, _action, _resa in lignes:
        date_seance = _date(jour)
        date_demande = _date(horodatage)
        if (IDinscription is None or IDunite is None or date_seance is None
                or date_demande is None or str(etat) not in ("0", "1")):
            ignorees += 1
            continue
        try:
            cle = (int(IDinscription), int(IDunite), date_seance)
            if cle[0] <= 0 or cle[1] <= 0:
                raise ValueError("identifiant nul")
        except (TypeError, ValueError):
            ignorees += 1
            continue
        premier = min(premier, date_demande) if premier else date_demande
        dernier = max(dernier, date_demande) if dernier else date_demande
        if str(etat) == "1":
            if cle not in actives:
                actives.add(cle)
                reservations += 1
            else:
                doublons += 1
        elif cle in actives:
            actives.remove(cle)
            annulations += 1
        else:
            orphelines += 1

    taux = (Decimal(annulations * 100) / Decimal(reservations)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP) if reservations else None
    return {
        "perimetre": "connecthys_traites_conserves",
        "reservations": reservations, "annulations": annulations,
        "taux": taux, "premiere_demande": premier, "derniere_demande": dernier,
        "annulations_non_appariees": orphelines,
        "lignes_inexploitables": ignorees, "doublons_ajout": doublons,
    }


def LireSituation(IDfamille, IDindividu=None, date_reference=None):
    """Retourne un bilan lu en base, sans rien enregistrer.

    Factures : une facture non soldee garde un reste a ventiler positif,
    meme si le compte familial dispose d'un avoir non affecte.
    """
    IDfamille = _identifiant(IDfamille)
    IDindividu = _identifiant(IDindividu, obligatoire=False)
    jour = _date(date_reference) if date_reference is not None else datetime.date.today()
    if jour is None:
        raise SituationIndisponible("Date de situation invalide")
    db = GestionDB.DB()
    try:
        charges = _lire(db, """SELECT SUM(montant) FROM prestations
            WHERE IDfamille=? AND date<=?""", (IDfamille, str(jour)))[0][0]
        versements = _lire(db, """SELECT SUM(r.montant) FROM reglements r
            JOIN comptes_payeurs cp ON cp.IDcompte_payeur=r.IDcompte_payeur
            WHERE cp.IDfamille=? AND r.date<=?""", (IDfamille, str(jour)))[0][0]
        solde = _montant(versements) - _montant(charges)

        factures = _lire(db, """SELECT f.IDfacture, f.numero, f.date_echeance,
            fp.prefixe, f.date_debut, f.date_fin FROM factures f
            JOIN comptes_payeurs cp ON cp.IDcompte_payeur=f.IDcompte_payeur
            LEFT JOIN factures_prefixes fp ON fp.IDprefixe=f.IDprefixe
            WHERE cp.IDfamille=? AND (f.date_edition IS NULL OR f.date_edition<=?)
            ORDER BY f.date_edition DESC, f.IDfacture DESC""",
            (IDfamille, str(jour)))
        impayees = []
        if factures:
            prestations = dict(_lire(db, """SELECT p.IDfacture, SUM(p.montant)
                FROM prestations p
                JOIN factures f ON f.IDfacture=p.IDfacture
                JOIN comptes_payeurs cp ON cp.IDcompte_payeur=f.IDcompte_payeur
                WHERE cp.IDfamille=? GROUP BY p.IDfacture""", (IDfamille,)))
            reglees = dict(_lire(db, """SELECT p.IDfacture, SUM(v.montant)
                FROM ventilation v
                JOIN prestations p ON p.IDprestation=v.IDprestation
                JOIN factures f ON f.IDfacture=p.IDfacture
                JOIN comptes_payeurs cp ON cp.IDcompte_payeur=f.IDcompte_payeur
                WHERE cp.IDfamille=? GROUP BY p.IDfacture""", (IDfamille,)))
            for id_facture, numero, echeance, prefixe, debut, fin in factures:
                reste = _montant(prestations.get(id_facture)) - _montant(
                    reglees.get(id_facture))
                if reste > 0:
                    impayees.append(dict(IDfacture=id_facture, numero=numero,
                                         prefixe=prefixe, echeance=_date(echeance),
                                         date_debut=_date(debut),
                                         date_fin=_date(fin),
                                         montant=_montant(prestations.get(id_facture)),
                                         reste=reste))
        adhesion = _adhesion(db, IDfamille, IDindividu, jour)
        try:
            historique_annulations = _historique_annulations_connecthys(
                db, IDfamille, jour)
        except SituationIndisponible:
            # Un historique absent/incomplet ne doit pas empecher l'affichage
            # des soldes, des factures ou des cotisations de la famille.
            historique_annulations = {
                "perimetre": "indisponible", "taux": None,
                "reservations": 0, "annulations": 0,
                "annulations_non_appariees": 0, "lignes_inexploitables": 0,
                "premiere_demande": None, "derniere_demande": None,
            }
        return dict(date=jour, solde_du_jour=solde,
                    factures_impayees=impayees,
                    total_factures=sum((f["reste"] for f in impayees), Decimal("0.00")),
                    adhesion=adhesion,
                    historique_annulations=historique_annulations)
    except SituationIndisponible:
        raise
    except Exception as erreur:
        raise SituationIndisponible("Situation non calculable") from erreur
    finally:
        db.Close()


def _euros(montant, symbole):
    return ("%.2f" % montant).replace(".", ",") + " " + html.escape(str(symbole))


def FormaterSituationHtml(situation, symbole="€", limite_factures=3):
    """HTML simple compatible wx.html.HtmlWindow ; libelles non fiables echappes."""
    jour = situation["date"]
    solde = situation["solde_du_jour"]
    etat = ("créditeur" if solde > 0 else
            "débiteur" if solde < 0 else "équilibré")
    lignes = [
        "<b>Solde au %s :</b> %s (%s)" %
        (jour.strftime("%d/%m/%Y"), _euros(solde, symbole), etat),
    ]
    factures = situation["factures_impayees"]
    if not factures:
        lignes.append("<b>Factures non soldées :</b> aucune")
    else:
        lignes.append("<b>Factures non soldées :</b> %d, total %s" %
                      (len(factures), _euros(situation["total_factures"], symbole)))
        details = []
        for facture in factures[:max(0, limite_factures)]:
            numero = (str(facture["prefixe"] or "") +
                      str(facture["numero"] if facture["numero"] is not None else
                          facture["IDfacture"]))
            echeance = facture["echeance"]
            statut = ("échue" if echeance and echeance < jour else "échéance")
            info = (" — %s %s" % (statut, echeance.strftime("%d/%m/%Y"))
                    if echeance else "")
            details.append("n°%s : %s%s" %
                           (html.escape(numero, quote=True),
                            _euros(facture["reste"], symbole), info))
        if len(factures) > limite_factures:
            details.append("+ %d autre(s)" % (len(factures) - limite_factures))
        if details:
            # Chaque numero et symbole sont deja echappes individuellement.
            lignes.append(" ; ".join(details))
    a = situation["adhesion"]
    statut = a["statut"]
    if statut == "en_cours":
        lignes.append("<b>Adhésion en cours :</b> %s (%s), jusqu'au %s" %
                      (html.escape(str(a["nom"]), quote=True),
                       html.escape(str(a["portee"]), quote=True),
                       a["fin"].strftime("%d/%m/%Y")))
    elif statut == "expiree":
        lignes.append("<b>Adhésion :</b> expirée le %s (%s)" %
                      (a["fin"].strftime("%d/%m/%Y"),
                       html.escape(str(a["nom"]), quote=True)))
    elif statut == "a_venir":
        lignes.append("<b>Adhésion :</b> à venir le %s (%s)" %
                      (a["debut"].strftime("%d/%m/%Y"),
                       html.escape(str(a["nom"]), quote=True)))
    elif statut == "absente":
        lignes.append("<b>Adhésion :</b> aucune cotisation active identifiée")
    else:
        motif = a.get("motif", "Données ambiguës")
        lignes.append("<b>Adhésion :</b> à vérifier (%s)" %
                      html.escape(str(motif), quote=True))
    return "<br>".join(lignes)
