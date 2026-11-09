#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:           Ivan LUCAS
# Copyright:       (c) 2010-11 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------


import Chemins
from Utils.UTILS_Traduction import _
import wx
import six
import datetime
import matplotlib
import matplotlib.pyplot
from numpy import arange
from Utils import UTILS_Stats_modeles as MODELES
if six.PY3:
    import functools


DICT_COMPARATIF_NOMBRE = {"dictParametres" : {}, "dictResultats" : {} }

def GetComparatifNombre(DB, dictParametres) :
    dictResultats = {}
    
    # Vérifie si les données n'existent pas déjà
    global DICT_COMPARATIF_NOMBRE
    if DICT_COMPARATIF_NOMBRE["dictParametres"] == dictParametres :
        return DICT_COMPARATIF_NOMBRE["listeResultats"]
    
    if dictParametres["mode"] == "inscrits" :
        return dictResultats
    
    # Recherche des paramètres
    date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
    conditionsActivites = MODELES.GetConditionActivites(dictParametres)
    
    # Recherche des périodes de comparaison
    req = """SELECT MIN(date), MAX(date) 
    FROM consommations 
    WHERE consommations.etat IN ('reservation', 'present')
    AND IDactivite IN %s
    ;""" % conditionsActivites
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    try :
        if listeDonnees[0][0] == None or listeDonnees[0][1] == None : 
            return dictResultats
        date_min = MODELES.DateEngEnDateDD(listeDonnees[0][0])
        date_max = MODELES.DateEngEnDateDD(listeDonnees[0][1])
    except :
        return dictResultats
    listePeriodes = MODELES.GetPeriodesComparatives(DB, dictParametres, date_min, date_max)
    
    listeLabels = []
    listeValeurs = []
    indexPeriodeReference = 0
    index = 0
    for dictPeriode in listePeriodes :
        req = """SELECT COUNT(IDfamille)
        FROM consommations 
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = consommations.IDcompte_payeur
        WHERE date>='%s' AND date<='%s' 
        AND consommations.etat IN ('reservation', 'present')
        AND IDactivite IN %s
        GROUP BY comptes_payeurs.IDfamille
        ;""" % (dictPeriode["date_debut"], dictPeriode["date_fin"], conditionsActivites)
        DB.ExecuterReq(req)
        listeDonnees = DB.ResultatReq()
        nbreFamilles = len(listeDonnees)
        listeLabels.append(dictPeriode["label"])
        listeValeurs.append(nbreFamilles)
        if dictPeriode["date_debut"] == dictParametres["periode"]["date_debut"] and dictPeriode["date_fin"] == dictParametres["periode"]["date_fin"]:
            indexPeriodeReference = index
        index += 1
        
    dictResultats = {"labels":listeLabels, "valeurs":listeValeurs, "indexPeriodeReference":indexPeriodeReference}
    return dictResultats



DICT_CAISSES = {"dictParametres" : {}, "dictResultats" : {} }

def GetDictCaisses(DB, dictParametres):
    # Vérifie si les données n'existent pas déjà
    global DICT_CAISSES
    cache_ok, cache_valeur = MODELES.LireCacheStats(DB, "familles.caisses", dictParametres)
    if cache_ok:
        return cache_valeur

    # Recherche des paramètres
    date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
    conditionsActivites = MODELES.GetConditionActivites(dictParametres)
    
    req = """SELECT IDcaisse, nom FROM caisses;"""
    DB.ExecuterReq(req)
    listeCaisses = DB.ResultatReq()
    dictCaisses = {}
    for IDcaisse, nom in listeCaisses :
        dictCaisses[IDcaisse] = nom

    if dictParametres["mode"] == "presents" :
        req = """SELECT IDcaisse, COUNT(familles.IDfamille)
        FROM familles
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDfamille = familles.IDfamille
        LEFT JOIN consommations ON consommations.IDcompte_payeur = comptes_payeurs.IDcompte_payeur
        WHERE date>='%s' AND date<='%s' 
        AND consommations.etat IN ('reservation', 'present')
        AND IDactivite IN %s
        GROUP BY IDcaisse, familles.IDfamille
        ;""" % (date_debut, date_fin, conditionsActivites)
    else:
        req = """SELECT IDcaisse, COUNT(familles.IDfamille)
        FROM familles
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDfamille = familles.IDfamille
        LEFT JOIN inscriptions ON inscriptions.IDcompte_payeur = comptes_payeurs.IDcompte_payeur
        WHERE inscriptions.statut='ok' AND IDactivite IN %s
        GROUP BY IDcaisse, familles.IDfamille
        ;""" % conditionsActivites
        
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    if len(listeDonnees) == 0 : 
        return {}
    
    dictResultats = {}
    for IDcaisse, IDfamille in listeDonnees :
        if (IDcaisse in dictResultats) == False :
            if IDcaisse in dictCaisses :
                nom = dictCaisses[IDcaisse] 
            else :
                nom = _(u"Caisse inconnue")
            dictResultats[IDcaisse] = {"nom" : nom, "nbreFamilles" : 0}
        dictResultats[IDcaisse]["nbreFamilles"] += 1

    # Mémorisation des résultats
    return MODELES.EcrireCacheStats(DB, "familles.caisses", dictParametres,
                                   dictResultats)


DICT_MEMBRES = {"dictParametres" : {}, "dictResultats" : {} }

def GetDictMembres(DB, dictParametres):
    # Vérifie si les données n'existent pas déjà
    global DICT_MEMBRES
    cache_ok, cache_valeur = MODELES.LireCacheStats(DB, "familles.membres", dictParametres)
    if cache_ok:
        return cache_valeur

    # Recherche des paramètres
    date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
    conditionsActivites = MODELES.GetConditionActivites(dictParametres)
    
    # Recherche du nombre d'individus présents
    if dictParametres["mode"] == "presents" :
        req = """SELECT IDfamille, consommations.IDindividu
        FROM consommations 
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = consommations.IDcompte_payeur
        WHERE date>='%s' AND date<='%s' 
        AND consommations.etat IN ('reservation', 'present')
        AND IDactivite IN %s
        GROUP BY IDfamille, consommations.IDindividu
        ;""" % (date_debut, date_fin, conditionsActivites)
    else:
        req = """SELECT comptes_payeurs.IDfamille, inscriptions.IDindividu
        FROM inscriptions 
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = inscriptions.IDcompte_payeur
        WHERE inscriptions.statut='ok' AND IDactivite IN %s
        GROUP BY comptes_payeurs.IDfamille, inscriptions.IDindividu
        ;""" % conditionsActivites

    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    if len(listeDonnees) == 0 : 
        return {}
    
    dictFamilles = {}
    for IDfamille, IDindividu in listeDonnees :
        if (IDfamille in dictFamilles) == False :
            dictFamilles[IDfamille] = 0
        dictFamilles[IDfamille] += 1
    
    dictResultats = {}
    for IDfamille, nbreMembres in dictFamilles.items() :
        if (nbreMembres in dictResultats) == False :
            dictResultats[nbreMembres] = 0
        dictResultats[nbreMembres] += 1

    # Mémorisation des résultats
    return MODELES.EcrireCacheStats(DB, "familles.membres", dictParametres,
                                   dictResultats)


# --------------------------------------------------------------------------------------------------------------------------------------------------------------

def _TranchesTarifsExclusives(tranches):
    """Partition entiere de l'union des plages tarifaires, sans doublons.

    Les bornes tarifaires sont inclusives. Les trous restent hors des tranches
    et sont comptes dans 'Autre'. Aucune ligne de tarif n'est modifiee.
    """
    bornes = set()
    plages = []
    for qf_min, qf_max in tranches:
        if qf_min is None or qf_max is None:
            continue
        minimum, maximum = int(qf_min), int(qf_max)
        if minimum > maximum:
            continue
        plages.append((minimum, maximum))
        bornes.update((minimum, maximum + 1))
    bornes = sorted(bornes)
    resultat = []
    for debut, fin_exclu in zip(bornes, bornes[1:]):
        fin = fin_exclu - 1
        if any(minimum <= debut and fin <= maximum
               for minimum, maximum in plages):
            resultat.append((debut, fin))
    return resultat


def _QuotientsAlaDate(lignes, date_reference):
    """Un seul QF par famille au jour de reference, sans hasard d'ordre SQL.

    Si plusieurs types de QF portent des valeurs actives contradictoires,
    signaler "a_verifier" plutot que selectionner arbitrairement.
    """
    from decimal import Decimal, InvalidOperation
    reference = datetime.date.fromisoformat(str(date_reference)[:10])
    groupes = {}
    for ligne in lignes:
        IDfamille, IDquotient, debut, fin, quotient = ligne[:5]
        if IDfamille is None:
            continue
        etat = groupes.setdefault(IDfamille, {"valeurs": set(), "invalide": False})
        if IDquotient is None:
            continue
        try:
            if debut is None or fin is None:
                raise ValueError("Dates absentes")
            date_debut = datetime.date.fromisoformat(str(debut)[:10])
            date_fin = datetime.date.fromisoformat(str(fin)[:10])
            if date_debut > date_fin:
                raise ValueError("Dates inversees")
        except (ValueError, TypeError):
            etat["invalide"] = True
            continue
        if date_debut <= reference <= date_fin:
            try:
                valeur = Decimal(str(quotient))
                if not valeur.is_finite():
                    raise ValueError("QF non fini")
                etat["valeurs"].add(valeur)
            except (ValueError, InvalidOperation, TypeError):
                etat["invalide"] = True
    resultat = {}
    for IDfamille, etat in groupes.items():
        valeurs = etat["valeurs"]
        if etat["invalide"] or len(valeurs) > 1:
            resultat[IDfamille] = "a_verifier"
        elif valeurs:
            resultat[IDfamille] = next(iter(valeurs))
        else:
            resultat[IDfamille] = None
    return resultat


DICT_QUOTIENTS = {"dictParametres" : {}, "dictResultats" : {} }

def GetDictQuotients(DB, dictParametres):
    # Cache limite a cette connexion et cette date de reference.
    # Il ne doit pas traverser un changement de dossier de donnees.
    # Recherche des paramètres
    conditionsActivites = MODELES.GetConditionActivites(dictParametres)
    
    if dictParametres["mode"] == "presents" :
        date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
        req = """SELECT familles.IDfamille, quotients.IDquotient, quotients.date_debut, quotients.date_fin, quotients.quotient, quotients.IDtype_quotient
        FROM familles
        LEFT JOIN quotients ON quotients.IDfamille = familles.IDfamille
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDfamille = familles.IDfamille
        LEFT JOIN consommations ON consommations.IDcompte_payeur = comptes_payeurs.IDcompte_payeur
        WHERE consommations.date>='%s' AND consommations.date<='%s' 
        AND consommations.etat IN ('reservation', 'present')
        AND consommations.IDactivite IN %s
        GROUP BY familles.IDfamille, IDquotient
        ;""" % (date_debut, date_fin, conditionsActivites)
    else:
        date_debut = MODELES.GetDateExtremeActivites(DB, listeActivites=dictParametres["listeActivites"], typeDate="date_debut", mode="min")
        date_fin = MODELES.GetDateExtremeActivites(DB, listeActivites=dictParametres["listeActivites"], typeDate="date_fin", mode="max")
        req = """SELECT familles.IDfamille, quotients.IDquotient, quotients.date_debut, quotients.date_fin, quotients.quotient, quotients.IDtype_quotient
        FROM familles
        LEFT JOIN quotients ON quotients.IDfamille = familles.IDfamille
        LEFT JOIN comptes_payeurs ON comptes_payeurs.IDfamille = familles.IDfamille
        LEFT JOIN inscriptions ON inscriptions.IDcompte_payeur = comptes_payeurs.IDcompte_payeur
        WHERE inscriptions.statut='ok' AND inscriptions.IDactivite IN %s
        GROUP BY familles.IDfamille, IDquotient
        ;""" % conditionsActivites

    # Presents : photographie au dernier jour de la periode.
    # Inscrits (sans periode dans l'interface) : photographie au jour actuel.
    date_reference = (date_fin if dictParametres["mode"] == "presents"
                      else datetime.date.today())
    cache = getattr(DB, "_stats_qf_cache", None)
    if (cache is not None and cache["date_reference"] == date_reference
            and cache["dictParametres"] == dictParametres):
        return cache["dictResultats"]
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    dictQuotients = _QuotientsAlaDate(listeDonnees, date_reference)
    
    # Recherche des tranches de QF existantes
    req = """SELECT IDligne, qf_min, qf_max
    FROM tarifs_lignes
    WHERE IDactivite IN %s
    AND qf_min IS NOT NULL AND qf_max IS NOT NULL
    ;""" % conditionsActivites
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    dictTranchesTarifs = {"pasqf" : 0, "a_verifier": 0, "autre" : 0}
    plages_tarifs = [(qf_min, qf_max) for IDligne, qf_min, qf_max
                     in listeDonnees]
    for tranche in _TranchesTarifsExclusives(plages_tarifs):
        dictTranchesTarifs[tranche] = 0
    
    # Création des tranches de 100
    dictTranchesDefaut = {"pasqf" : 0, "a_verifier": 0, "autre" : 0}
    for x in range(0, 3000, 100) :
        tranche = (x+1, x+100)
        if x == 0 : tranche = (0, 100)
        dictTranchesDefaut[tranche] = 0    
    dictTranchesDefaut[(3001, 99999)] = 0
    
    # Répartition des QF par tranche
    for IDfamille, quotient in dictQuotients.items() :
        for dictTranches in (dictTranchesDefaut, dictTranchesTarifs) :
            if quotient == None :
                dictTranches["pasqf"] += 1
            elif quotient == "a_verifier":
                dictTranches["a_verifier"] += 1
            else :
                found = False
                for tranche in list(dictTranches.keys()) :
                    if isinstance(tranche, tuple) and quotient >= tranche[0] and quotient <= tranche[1] :
                        dictTranches[tranche] += 1
                        found = True
                        break
                if found == False :
                    dictTranches["autre"] += 1

    import copy
    resultat = {"dictTranchesTarifs": dictTranchesTarifs,
                "dictTranchesDefaut": dictTranchesDefaut,
                "date_reference": date_reference}
    DB._stats_qf_cache = {"dictParametres": copy.deepcopy(dictParametres),
                          "date_reference": date_reference,
                          "dictResultats": resultat}
    return resultat


def TrierQF(listeTranches=None):
    """Tranches numeriques puis sans QF, a verifier et autre."""
    ordre = {"pasqf": 0, "a_verifier": 1, "autre": 2}
    return sorted(listeTranches or [], key=lambda x: (
        (0, x[0], x[1]) if isinstance(x, tuple)
        else (1, ordre.get(x, 9), 0)))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------


class Texte_nombre_familles(MODELES.Texte):
    def __init__(self):
        """ Recherche du nombre de familles dont les individus sont présents """
        MODELES.Texte.__init__(self)
        self.nom = _(u"Nombre de familles")
        self.code = "texte_nombre_familles"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        
        date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
        conditionsActivites = MODELES.GetConditionActivites(dictParametres)
        
        # Recherche du nombre d'individus présents
        if dictParametres["mode"] == "presents" :
            req = """SELECT COUNT(IDfamille)
            FROM consommations 
            LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = consommations.IDcompte_payeur
            WHERE date>='%s' AND date<='%s' 
            AND consommations.etat IN ('reservation', 'present')
            AND IDactivite IN %s
            GROUP BY comptes_payeurs.IDfamille
            ;""" % (date_debut, date_fin, conditionsActivites)
        else :
            req = """SELECT COUNT(comptes_payeurs.IDfamille)
            FROM inscriptions 
            LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = inscriptions.IDcompte_payeur
            WHERE inscriptions.statut='ok' AND IDactivite IN %s
            GROUP BY comptes_payeurs.IDfamille
            ;""" % conditionsActivites
        
        DB.ExecuterReq(req)
        listeDonnees = DB.ResultatReq()
        
        if dictParametres["mode"] == "presents" :
            mot = _(u"présent")
        else:
            mot = _(u"inscrit")
            
        if len(listeDonnees) == 0 or listeDonnees[0][0] == 0 : 
            self.texte = _(u"Aucune famille dont les membres sont %ss.") % mot
        else:
            self.texte = _(u"%d familles dont les membres sont %ss.") % (len(listeDonnees), mot)




class Tableau_nombre_familles(MODELES.Tableau):
    """ Répartition du nombre de familles par activité """
    def __init__(self):
        MODELES.Tableau.__init__(self)
        self.nom = _(u"Répartition du nombre de familles par activité")
        self.code = "tableau_nombre_familles"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        self.colonnes = []
        self.lignes = []
        self.totaux = []
        
        # Recherche des paramètres
        date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
        conditionsActivites = MODELES.GetConditionActivites(dictParametres)

        # Recherche du nombre d'individus présents
        if dictParametres["mode"] == "presents" :
            req = """SELECT IDactivite, COUNT(IDfamille)
            FROM consommations 
            LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = consommations.IDcompte_payeur
            WHERE date>='%s' AND date<='%s' 
            AND consommations.etat IN ('reservation', 'present')
            AND IDactivite IN %s
            GROUP BY IDactivite, IDfamille
            ;""" % (date_debut, date_fin, conditionsActivites)
        else:
            req = """SELECT IDactivite, COUNT(comptes_payeurs.IDfamille)
            FROM inscriptions 
            LEFT JOIN comptes_payeurs ON comptes_payeurs.IDcompte_payeur = inscriptions.IDcompte_payeur
            WHERE inscriptions.statut='ok' AND IDactivite IN %s
            GROUP BY IDactivite, comptes_payeurs.IDfamille
            ;""" % conditionsActivites
            
        DB.ExecuterReq(req)
        listeDonnees = DB.ResultatReq()
        if len(listeDonnees) == 0 : 
            return
        
        dictActiTemp = {}
        for IDactivite, nbreConso in listeDonnees :
            if (IDactivite in dictActiTemp) == False :
                dictActiTemp[IDactivite] = 0
            dictActiTemp[IDactivite] += 1
        
        # Création du tableau
        self.largeur = "400"
        self.colonnes = [ (_(u"Activité"), "250"), (_(u"Nombre de familles"), "150") ]
        self.lignes = []
        for IDactivite, listeFamilles in dictActiTemp.items() :
            nomActivite = dictParametres["dictActivites"][IDactivite]
            self.lignes.append((nomActivite, listeFamilles))



class Graphe_nombre_familles(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Comparatif du nombre de familles")
        self.code = "graphe_nombre_familles"
        self.taille = (470, 360)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        dictResultats = GetComparatifNombre(DB, dictParametres)
        if dictResultats == None or len(dictResultats) == 0 :
            return figure
        
        listeLabels = dictResultats["labels"]
        listeValeurs = dictResultats["valeurs"]
        indexPeriodeReference = dictResultats["indexPeriodeReference"]
        
        # Création du graph
        ind = arange(len(listeLabels)) + self.decalage_x
        width = 0.5
        for x in range(len(listeLabels)) :
            if x == indexPeriodeReference :
                couleur = MODELES.ConvertitCouleur2(MODELES.COULEUR_VERT_POMME)
            else:
                couleur = MODELES.ConvertitCouleur2(MODELES.COULEUR_BLEU_CIEL)
            barre = ax.bar(ind[x], listeValeurs[x], width, color=couleur)
        
        # Axe horizontal
        ind = arange(len(listeLabels)) 
        ax.set_xticks(ind + width) 
        ax.set_xticklabels(listeLabels)
        labelsx = ax.get_xticklabels()
        labelsy = ax.get_yticklabels()
        matplotlib.pyplot.setp(labelsx, rotation=45, fontsize=9, horizontalalignment='right')
        
        # Axe vertical
        ax.set_ylabel("Nbre de familles", fontsize=8)
        
        labels = ax.get_yticklabels()
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        
        # Titre
        title = ax.set_title(_(u"Comparatif du nombre de familles"), weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        
        figure.subplots_adjust(left=None, bottom=0.4, right=None, wspace=None, hspace=None)
        
        # Affiche les grilles
        ax.grid(True, linestyle=":")
        
        return figure



class Tableau_repartition_caisses(MODELES.Tableau):
    """ Répartition des familles par caisse """
    def __init__(self):
        MODELES.Tableau.__init__(self)
        self.nom = _(u"Répartition des familles par caisse")
        self.code = "tableau_repartition_caisses"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        self.colonnes = []
        self.lignes = []
        self.totaux = []
        
        dictCaisses = GetDictCaisses(DB, dictParametres)
        
        # Création du tableau
        self.largeur = "400"
        self.colonnes = [ (_(u"Caisse"), "250"), (_(u"Nombre de familles"), "150") ]
        self.lignes = []
        
        # Tri par nbre de familles
        listeCaisses = []
        for IDcaisse, valeurs in dictCaisses.items() :
            nbreFamilles = valeurs["nbreFamilles"]
            nomCaisse = valeurs["nom"]
            listeCaisses.append((nbreFamilles, nomCaisse))
        listeCaisses.sort(reverse=True)
        
        for nbreFamilles, nomCaisse in listeCaisses :
            self.lignes.append((nomCaisse, nbreFamilles))



class Graphe_repartition_caisses(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Répartition par caisse")
        self.code = "graphe_repartition_caisses"
        self.taille = (450, 280)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        dictCaisses = GetDictCaisses(DB, dictParametres)
        
        listeValeurs = []
        listeLabels = []
        listeCouleurs = []
        
        # Tri par nbre de familles
        listeCaisses = []
        nbreTotalFamilles = 0
        for IDcaisse, valeurs in dictCaisses.items() :
            nbreFamilles = valeurs["nbreFamilles"]
            nomCaisse = valeurs["nom"]
            listeCaisses.append((nbreFamilles, nomCaisse))
            nbreTotalFamilles += nbreFamilles
        listeCaisses.sort(reverse=True)
                
        index = 1
        for nbreFamilles, nomCaisse in listeCaisses :
            listeValeurs.append(nbreFamilles)
            listeLabels.append(nomCaisse)
            
            couleur = 1.0 * nbreFamilles / nbreTotalFamilles
            couleur = matplotlib.cm.hsv(index * 0.1)
            listeCouleurs.append(couleur)
            
            index += 1
        
        cam = ax.pie(listeValeurs, labels=listeLabels, colors=listeCouleurs, autopct='%1.1f%%', shadow=False)
        title = ax.set_title(_(u"Répartition par caisse"), weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        ax.set_aspect(1)
        labels, labelsPourcent = cam[1], cam[2]
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        matplotlib.pyplot.setp(labelsPourcent, rotation=0, fontsize=9) 
    
        return figure




class Tableau_nombre_membres(MODELES.Tableau):
    """ Répartition du nombre de membres présents ou inscrits sur l'activité """
    def __init__(self):
        MODELES.Tableau.__init__(self)
        self.nom = _(u"Nombre de membres présents")
        self.code = "tableau_nombre_membres"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        self.colonnes = []
        self.lignes = []
        self.totaux = []
        
        # Recherche des paramètres
        date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
        conditionsActivites = MODELES.GetConditionActivites(dictParametres)
        dictResultats = GetDictMembres(DB, dictParametres) 
        
        if dictParametres["mode"] == "presents" :
            self.nom = _(u"Nombre de membres présents")
        else:
            self.nom = _(u"Nombre de membres inscrits")

        # Création du tableau
        self.largeur = "400"
        self.colonnes = [ (_(u"Nombre de membres"), "250"), (_(u"Nombre de familles"), "150") ]
        self.lignes = []
        for nbreMembres, nbreFamilles in dictResultats.items() :
            self.lignes.append((nbreMembres, nbreFamilles))
        self.lignes.sort() 




class Graphe_nombre_membres(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Nombre de membres présents")
        self.code = "graphe_nombre_membres"
        self.taille = (450, 280)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        # Recherche des paramètres
        date_debut, date_fin = MODELES.GetDatesPeriode(dictParametres)
        conditionsActivites = MODELES.GetConditionActivites(dictParametres)
        dictResultats = GetDictMembres(DB, dictParametres) 
        
        if dictParametres["mode"] == "presents" :
            self.nom = _(u"Nombre de membres présents")
        else:
            self.nom = _(u"Nombre de membres inscrits")
        
        listeValeurs = []
        listeLabels = []
        listeCouleurs = []
        
        listeResultats = []
        nbreTotalFamilles = 0
        for nbreMembres, nbreFamilles in dictResultats.items() :
            listeResultats.append((nbreMembres, nbreFamilles))
            nbreTotalFamilles += nbreFamilles
        listeResultats.sort() 
            
        index = 1
        for nbreMembres, nbreFamilles in listeResultats :
            listeValeurs.append(nbreFamilles)
            if nbreMembres == 1 :
                label = _(u"1 membre")
            else:
                label = _(u"%d membres") % nbreMembres
            listeLabels.append(label)
            
            couleur = 1.0 * nbreFamilles / nbreTotalFamilles
            couleur = matplotlib.cm.hsv(index * 0.1)
            listeCouleurs.append(couleur)
            
            index += 1
        
        cam = ax.pie(listeValeurs, labels=listeLabels, colors=listeCouleurs, autopct='%1.1f%%', shadow=False)
        title = ax.set_title(self.nom, weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        ax.set_aspect(1)
        labels, labelsPourcent = cam[1], cam[2]
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        matplotlib.pyplot.setp(labelsPourcent, rotation=0, fontsize=9) 
    
        return figure


class Tableau_qf_tarifs(MODELES.Tableau):
    """ QF par tranches de tarifs """
    def __init__(self):
        MODELES.Tableau.__init__(self)
        self.nom = _(u"Quotients familiaux par tranches de tarifs")
        self.code = "tableau_qf_tarifs"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        self.colonnes = []
        self.lignes = []
        self.totaux = []
        
        donneesQF = GetDictQuotients(DB, dictParametres)
        dictTranches = donneesQF["dictTranchesTarifs"]
        self.nom = _(u"Quotients familiaux par tranches de tarifs") + (u" (QF au %s)" %
                    donneesQF["date_reference"].strftime("%d/%m/%Y"))
        
        # Création du tableau
        self.largeur = "400"
        self.colonnes = [ (_(u"Tranche QF"), "250"), (_(u"Nombre de familles"), "150") ]
        self.lignes = []
        
        # Tri des tranches par ordre croissant
        listeTranches = []
        listeTranches = list(dictTranches.keys())
        # listeTranches.sort()
        listeTranches = TrierQF(listeTranches)
        
        # Création du tableau des valeurs
        for tranche in listeTranches :
            if tranche == "autre" : 
                label = _(u"Autre")
                if dictTranches[tranche] == 0 : 
                    label = None
            elif tranche == "pasqf" :
                label = _(u"Sans QF")
            elif tranche == "a_verifier":
                label = _(u"QF à vérifier")
            else :
                label = u"%d - %d" % tranche
            if label != None :
                self.lignes.append((label, dictTranches[tranche]))
            

class Graphe_qf_tarifs(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Quotients familiaux par tranches de tarifs")
        self.code = "graphe_qf_tarifs"
        self.taille = (450, 280)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        donneesQF = GetDictQuotients(DB, dictParametres)
        dictTranches = donneesQF["dictTranchesTarifs"]
        self.nom = _(u"Quotients familiaux par tranches de tarifs") + (u" (QF au %s)" %
                    donneesQF["date_reference"].strftime("%d/%m/%Y"))
        
        listeValeurs = []
        listeLabels = []
        listeCouleurs = []
        
        # Tri des tranches par ordre croissant
        listeTranches = list(dictTranches.keys())
        # listeTranches.sort()
        listeTranches = TrierQF(listeTranches)
        
        nbreTotal = 0
        for tranche in listeTranches :
            nbreTotal += dictTranches[tranche]
        
        # Création du tableau des valeurs
        index = 1
        if nbreTotal > 0 :
            for tranche in listeTranches :
                valeur = dictTranches[tranche]
                if tranche == "autre" : 
                    label = _(u"Autre")
                    if dictTranches[tranche] == 0 : 
                        label = None
                elif tranche == "pasqf" :
                    label = _(u"Sans QF")
                elif tranche == "a_verifier":
                    label = _(u"QF à vérifier")
                else :
                    label = u"%d - %d" % tranche
                if label != None :
                    # Mémorisation des valeurs
                    listeValeurs.append(valeur)
                    listeLabels.append(label)
                    # Couleur
                    couleur = 1.0 * valeur / nbreTotal
                    couleur = matplotlib.cm.hsv(index * 0.1)
                    listeCouleurs.append(couleur)
                    index += 1
        
        cam = ax.pie(listeValeurs, labels=listeLabels, colors=listeCouleurs, autopct='%1.1f%%', shadow=False)
        title = ax.set_title(self.nom, weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        ax.set_aspect(1)
        labels, labelsPourcent = cam[1], cam[2]
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        matplotlib.pyplot.setp(labelsPourcent, rotation=0, fontsize=9) 
    
        return figure


class Tableau_qf_defaut(MODELES.Tableau):
    """ QF par tranches de tarifs """
    def __init__(self):
        MODELES.Tableau.__init__(self)
        self.nom = _(u"Quotients familiaux par tranches de 100")
        self.code = "tableau_qf_defaut"
    def MAJ(self, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        self.colonnes = []
        self.lignes = []
        self.totaux = []
        
        donneesQF = GetDictQuotients(DB, dictParametres)
        dictTranches = donneesQF["dictTranchesDefaut"]
        self.nom = _(u"Quotients familiaux par tranches de 100") + (u" (QF au %s)" %
                    donneesQF["date_reference"].strftime("%d/%m/%Y"))
        
        # Création du tableau
        self.largeur = "400"
        self.colonnes = [ (_(u"Tranche QF"), "250"), (_(u"Nombre de familles"), "150") ]
        self.lignes = []
        
        # Tri des tranches par ordre croissant
        listeTranches = list(dictTranches.keys())
        # listeTranches.sort()
        listeTranches = TrierQF(listeTranches)
        
        # Création du tableau des valeurs
        for tranche in listeTranches :
            if tranche == "autre" : 
                label = _(u"Autre")
                if dictTranches[tranche] == 0 : 
                    label = None
            elif tranche == "pasqf" :
                label = _(u"Sans QF")
            elif tranche == "a_verifier":
                label = _(u"QF à vérifier")
            else :
                label = u"%d - %d" % tranche
            if label != None :
                self.lignes.append((label, dictTranches[tranche]))
            

class Graphe_qf_defaut2(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Quotients familiaux par tranches de 100")
        self.code = "graphe_qf_defaut"
        self.taille = (450, 280)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        donneesQF = GetDictQuotients(DB, dictParametres)
        dictTranches = donneesQF["dictTranchesDefaut"]
        self.nom = _(u"Quotients familiaux par tranches de 100") + (u" (QF au %s)" %
                    donneesQF["date_reference"].strftime("%d/%m/%Y"))
        
        listeValeurs = []
        listeLabels = []
        listeCouleurs = []
        
        # Tri des tranches par ordre croissant
        listeTranches = list(dictTranches.keys())
        # listeTranches.sort()
        listeTranches = TrierQF(listeTranches)
        
        nbreTotal = 0
        for tranche in listeTranches :
            nbreTotal += dictTranches[tranche]
        
        # Création du tableau des valeurs
        index = 1
        for tranche in listeTranches :
            valeur = dictTranches[tranche]
            if tranche == "autre" : 
                label = _(u"Autre")
                if dictTranches[tranche] == 0 : 
                    label = None
            elif tranche == "pasqf" :
                label = _(u"Sans QF")
            elif tranche == "a_verifier":
                label = _(u"QF à vérifier")
            else :
                label = u"%d - %d" % tranche
            if label != None and valeur != 0 :
                # Mémorisation des valeurs
                listeValeurs.append(valeur)
                listeLabels.append(label)
                # Couleur
                couleur = 1.0 * valeur / nbreTotal
                couleur = matplotlib.cm.hsv(index * 0.1)
                listeCouleurs.append(couleur)
                index += 1
        
        cam = ax.pie(listeValeurs, labels=listeLabels, colors=listeCouleurs, autopct='%1.1f%%', shadow=False)
        title = ax.set_title(self.nom, weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        ax.set_aspect(1)
        labels, labelsPourcent = cam[1], cam[2]
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        matplotlib.pyplot.setp(labelsPourcent, rotation=0, fontsize=9) 
    
        return figure


class Graphe_qf_defaut(MODELES.Graphe):
    def __init__(self):
        MODELES.Graphe.__init__(self)
        self.nom = _(u"Quotients familiaux par tranches de 100")
        self.code = "graphe_qf_defaut"
        self.taille = (450, 280)
    def MAJ(self, figure=None, DB=None, dictParametres={}):
        self.dictParametres = dictParametres
        # Création du graph
        ax = figure.add_subplot(111)
        
        donneesQF = GetDictQuotients(DB, dictParametres)
        dictTranches = donneesQF["dictTranchesDefaut"]
        self.nom = _(u"Quotients familiaux par tranches de 100") + (u" (QF au %s)" %
                    donneesQF["date_reference"].strftime("%d/%m/%Y"))

        listeValeurs = []
        listeLabels = []
        
        # Tri des tranches par ordre croissant
        listeTranches = list(dictTranches.keys())
        # listeTranches.sort()
        listeTranches = TrierQF(listeTranches)
        
        # Création du tableau des valeurs
        index = 1
        for tranche in listeTranches :
            valeur = dictTranches[tranche]
            if tranche == "autre" : 
                label = None
            elif tranche in ("pasqf", "a_verifier"):
                label = None
            else :
                label = u"%d - %d" % tranche
            if label != None and valeur != 0 :
                #if index % 2 == 0 : label = ""
                # Mémorisation des valeurs
                listeValeurs.append(valeur)
                listeLabels.append(label)
                index += 1
                        
        # Création du graph
        ind = arange(len(listeLabels)) + self.decalage_x
        width = 0.5
        barres = ax.bar(ind, listeValeurs, width, color=MODELES.ConvertitCouleur2(MODELES.COULEUR_VERT_POMME))
        
        # Axe horizontal
        ax.set_xlabel(_(u"Tranches"), fontsize=8)
        ind = arange(len(listeLabels)) 
        ax.set_xticks(ind + width) 
        ax.set_xticklabels(listeLabels)
        labelsx = ax.get_xticklabels()
        labelsy = ax.get_yticklabels()
        matplotlib.pyplot.setp(labelsx, rotation=45, fontsize=8, horizontalalignment='right')
        
        # Axe vertical
        ax.set_ylabel("Nbre de familles", fontsize=8)
        labels = ax.get_yticklabels()
        matplotlib.pyplot.setp(labels, rotation=0, fontsize=9) 
        
        # Titre
        title = ax.set_title(self.nom, weight="bold", horizontalalignment = 'center')#, position=(0.5, 0.97))
        matplotlib.pyplot.setp(title, rotation=0, fontsize=9)
        
        figure.subplots_adjust(left=None, bottom=0.28, right=None, wspace=None, hspace=None)
        
        # Affiche les grilles
        ax.grid(True, linestyle=":")
        
        return figure










if __name__ == '__main__':
    """ TEST d'un objet """
    app = wx.App(0)
    #wx.InitAllImageHandlers()
    annee = 2014
    dictParametres = {
        "mode" : "inscrits",
        "periode" : {"type":"annee", "annee":annee, "date_debut":datetime.date(annee, 1, 1), "date_fin":datetime.date(annee, 12, 31)}, 
        "listeActivites" : [1, 2, 3, 4, 5], 
        "dictActivites" : {1 : _(u"Centre de Loisirs"), 2 : _(u"Action 10-14 ans"), 3 : _(u"Camp 4-6 ans"), 4 : _(u"Camp 6-9 ans"), 5 : _(u"Camp 10-14 ans"), 6 : _(u"Art floral"), 7 : _(u"Yoga")}, 
        }
    frame_1 = MODELES.FrameTest(objet=Tableau_nombre_familles(), dictParametres=dictParametres)
    app.SetTopWindow(frame_1)
    frame_1.Show()
    app.MainLoop()
