# -*- coding: utf-8 -*-
"""Methodes source wx isolees de l'UI. Reproduction textuelle des extraits
verifies sur wx SHA e86fabedece82f6cc1cade70074207291f8d9dfb.
Les shims _MODELES et _ sont definis hors des methodes, seulement pour le banc.
Source: noethys/Utils/UTILS_Stats_familles.py#L199-365,#L700-749,#L920-982
        noethys/Ctrl/CTRL_Grille.py#L3471-3490
Attention : PAS un import de l'application installee.
"""
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot
from numpy import arange

class _Tableau:
    def __init__(self):
        self.nom = ''
        self.colonnes = []
        self.lignes = []
        self.totaux = []

class _Graphe:
    def __init__(self):
        self.nom = ''
        self.decalage_x = 0

class _MODELES:
    Tableau = _Tableau
    Graphe = _Graphe
    COULEUR_VERT_POMME = (151, 253, 79)

    @staticmethod
    def ConvertitCouleur2(RGB):
        return [v / 255.0 for v in RGB]

    @staticmethod
    def GetDatesPeriode(parametres):
        return parametres['periode']['date_debut'], parametres['periode']['date_fin']

    @staticmethod
    def GetConditionActivites(parametres):
        nums = parametres['listeActivites']
        return '(' + ','.join(str(x) for x in nums) + ')' if nums else '()'

MODELES = _MODELES
_ = lambda x: x

# ------------------ START COPIE LITTERALE / wx STATS ------------------
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
# ------------------ END COPIE LITTERALE / wx STATS ------------------


class CTRLGrilleRechercheQF:
    def __init__(self, quotients):
        self.dictQuotientsFamiliaux = quotients

    # START verbatim wx CTRL_Grille.py:RechercheQF (indentation base preserved)
    def RechercheQF(self, dictTarif=None, IDfamille=None, date=None):
        """ Pour Facturation Recherche du QF de la famille """
        # Si la famille a un QF :
        if IDfamille in self.dictQuotientsFamiliaux :
            listeQuotientsFamiliaux = self.dictQuotientsFamiliaux[IDfamille]
            for date_debut, date_fin, quotient, IDtype_quotient in listeQuotientsFamiliaux :
                if date >= date_debut and date <= date_fin and (dictTarif["IDtype_quotient"] == None or dictTarif["IDtype_quotient"] == IDtype_quotient) :
                    return quotient

        # Si la famille n'a pas de QF, on attribue le QF le plus élevé :
        listeQF = []
        for ligneCalcul in dictTarif["lignes_calcul"] :
            qf = ligneCalcul["qf_max"]
            if qf:
                qf = float(qf)
            listeQF.append(qf)
        listeQF.sort()
        if len(listeQF) > 0 :
            if listeQF[-1] != None :
                return listeQF[-1]

        return None
    # END verbatim
