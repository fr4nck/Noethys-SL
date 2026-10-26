# -*- coding: utf-8 -*-
"""Lecture en masse du sous-ensemble sans porc, sans informations nominatives.

Question individuelle/choix sont explicitement selectionnes dans le modele.
Noethys ne date pas les versions successives des reponses au questionnaire.
Le resultat refletera donc la reponse courante, non la preference historique.
"""

import GestionDB
from Utils import UTILS_Repas_alimentaires
from Utils import UTILS_Dates


def ChargerRepartition(question, choix, unites, date_debut, date_fin):
    """Renvoie par jour le total d'individus et le sous-total « sans porc ».

    Une unite est un couple (IDgroupe, IDunite), jamais un simple IDunite :
    deux groupes utilisant la meme unite ne doivent pas etre confondus.
    """
    unites = set((int(g), int(u)) for g, u in unites)
    if not unites:
        return {}
    try:
        id_question = int(question)
        id_choix = int(choix)
    except (ValueError, TypeError):
        raise ValueError("Selectionnez une question et une reponse sans porc")
    if id_question <= 0 or id_choix <= 0:
        raise ValueError("Identifiants alimentaires invalides")
    if date_debut is None or date_fin is None or date_debut > date_fin:
        raise ValueError("Dates de commande invalides")
    id_unites = ",".join(str(v) for v in sorted({u for _, u in unites}))
    base = GestionDB.DB()
    try:
        req = """SELECT q.controle, c.type FROM questionnaire_questions AS q
                 JOIN questionnaire_categories AS c ON q.IDcategorie=c.IDcategorie
                 WHERE q.IDquestion=%d""" % id_question
        if not base.ExecuterReq(req):
            raise ValueError("Impossible de lire la question alimentaire")
        question_rows = base.ResultatReq()
        if len(question_rows) != 1 or str(question_rows[0][1]).lower() != "individu":
            raise ValueError("La question sans porc doit etre individuelle")
        controle = question_rows[0][0]
        if controle != "case_coche":
            req = """SELECT IDchoix FROM questionnaire_choix
                     WHERE IDquestion=%d AND IDchoix=%d""" % (id_question, id_choix)
            if not base.ExecuterReq(req):
                raise ValueError("Impossible de verifier le choix sans porc")
            if not base.ResultatReq():
                raise ValueError("Le choix ne correspond pas a la question")
        UTILS_Repas_alimentaires.ConfigurationSansPorc(id_question, id_choix, controle)
        req = """SELECT date, IDgroupe, IDunite, IDindividu, etat
                 FROM consommations
                 WHERE date>='%s' AND date<='%s' AND IDunite IN (%s)
                   AND etat IN ('reservation','present')""" % (
                       date_debut.isoformat(), date_fin.isoformat(), id_unites)
        if not base.ExecuterReq(req):
            raise ValueError("Impossible de lire les repas")
        consos = []
        individus = set()
        for jour, groupe, unite, individu, etat in base.ResultatReq():
            if (groupe, unite) not in unites:
                continue
            jour = UTILS_Dates.DateEngEnDateDD(jour) if isinstance(jour, str) else jour
            consos.append({"date": jour, "IDgroupe": groupe, "IDunite": unite,
                           "IDindividu": individu, "etat": etat})
            individus.add(individu)
        reponses = {}
        if individus:
            ids = ",".join(str(int(i)) for i in sorted(individus))
            req = """SELECT IDindividu, reponse FROM questionnaire_reponses
                     WHERE IDquestion=%d AND IDindividu IN (%s)
                     ORDER BY IDreponse""" % (id_question, ids)
            if not base.ExecuterReq(req):
                raise ValueError("Impossible de lire les reponses alimentaires")
            for individu, reponse in base.ResultatReq():
                if individu in reponses:
                    raise ValueError("Plusieurs reponses contradictoires pour une question individuelle")
                reponses[individu] = reponse
    finally:
        base.Close()
    return UTILS_Repas_alimentaires.CompterSansPorc(consos, reponses, unites, id_choix, controle)




def _HeureRepas2C(valeur):
    """Horaire local qualifie (pas de seconde, de fuseau ou de repli)."""
    from datetime import datetime, time
    from Utils.UTILS_Repas_2c import _minute
    if isinstance(valeur, datetime):
        valeur = valeur.time()
    if isinstance(valeur, time):
        if valeur.second or valeur.microsecond or valeur.tzinfo is not None:
            raise ValueError("Horaire d accueil ambigu")
        return "%02d:%02d" % (valeur.hour, valeur.minute)
    if isinstance(valeur, str):
        valeur = valeur.strip()
        if len(valeur) == 8 and valeur.endswith(":00"):
            valeur = valeur[:5]
        _minute(valeur)
        return valeur
    raise ValueError("Horaires de la journee/demi-journee manquants")


def _FiltrerAccueilsMidi2C(consos, intervalles, services, plage_midi):
    """Garde les accueils couvrant midi sans reservation de repas distincte.

    Chaque intervalle provient des horaires de consommation ou, a defaut,
    de l'unite programmee. Une couverture partielle est bloquante.
    """
    from Utils.UTILS_Repas_2c import CouvreMidi, Repas2CInvalide
    eligibles = {}
    for cle, plages in intervalles.items():
        try:
            eligibles[cle] = CouvreMidi(plages, *plage_midi)
        except Repas2CInvalide as exc:
            raise ValueError("Plage meridienne a qualifier : %s" % exc)
    return [c for c in consos if eligibles.get(
        (c["date"], c["IDindividu"]) +
        services[(c["IDgroupe"], c["IDunite"])], False)]

def ChargerRepartitionRegimes(question, correspondance, services, date_debut, date_fin,
                              plage_midi=None, repas_pmsl_prevu=None):
    """Repartition standard / sans porc / vegetarien / non renseigne (#430).

    services : {(IDgroupe, IDunite): (site, service)}. Quatre lectures
    groupees, aucune ecriture ; meme limite d'historique que ci-dessus.
    """
    from Utils import UTILS_Repas_regimes
    services = UTILS_Repas_regimes.NormaliserServices(services)
    if not services:
        return {}
    if date_debut is None or date_fin is None or date_debut > date_fin:
        raise ValueError("Dates de commande invalides")
    id_question, choix = UTILS_Repas_regimes.ConfigurationRegimes(
        question, correspondance, UTILS_Repas_regimes.CONTROLE_REGIME)
    optin = UTILS_Repas_regimes.PANIER in choix
    if optin:
        from Utils.UTILS_Repas_2c import CouvreMidi
        if not isinstance(plage_midi, (tuple, list)) or len(plage_midi) != 2:
            raise ValueError("Horaires du service meridien obligatoires pour les paniers")
        CouvreMidi([tuple(plage_midi)], *plage_midi)
        if type(repas_pmsl_prevu) is not bool:
            raise ValueError("Offre repas de la formule a confirmer")
    id_unites = ",".join(str(v) for v in sorted({u for _, u in services}))
    base = GestionDB.DB()
    try:
        _VerifierQuestionRegime(base, id_question, choix)
        if optin:
            req = """SELECT consommations.date, consommations.IDgroupe, consommations.IDunite,
                            consommations.IDindividu, consommations.etat, individus.date_naiss,
                            consommations.heure_debut, consommations.heure_fin,
                            unites.heure_debut, unites.heure_fin
                     FROM consommations
                     LEFT JOIN individus ON individus.IDindividu = consommations.IDindividu
                     JOIN unites ON unites.IDunite = consommations.IDunite
                     WHERE consommations.date>='%s' AND consommations.date<='%s'
                       AND consommations.IDunite IN (%s)
                       AND consommations.etat IN ('reservation','present')""" % (
                           date_debut.isoformat(), date_fin.isoformat(), id_unites)
        else:
            req = """SELECT consommations.date, consommations.IDgroupe, consommations.IDunite,
                            consommations.IDindividu, consommations.etat, individus.date_naiss
                     FROM consommations
                     LEFT JOIN individus ON individus.IDindividu = consommations.IDindividu
                     WHERE consommations.date>='%s' AND consommations.date<='%s'
                       AND consommations.IDunite IN (%s)
                       AND consommations.etat IN ('reservation','present')""" % (
                           date_debut.isoformat(), date_fin.isoformat(), id_unites)
        if not base.ExecuterReq(req):
            raise ValueError("Impossible de lire les accueils de midi")
        consos, naissances, intervalles = [], {}, {}
        for ligne in base.ResultatReq():
            jour, groupe, unite, individu, etat, naissance = ligne[:6]
            if (groupe, unite) not in services:
                continue
            jour = UTILS_Dates.DateEngEnDateDD(jour) if isinstance(jour, str) else jour
            entree = {"date": jour, "IDgroupe": groupe, "IDunite": unite,
                      "IDindividu": individu, "etat": etat}
            consos.append(entree)
            naissances[individu] = naissance
            if optin:
                debut = ligne[6] if ligne[6] not in (None, "") else ligne[8]
                fin = ligne[7] if ligne[7] not in (None, "") else ligne[9]
                cle = (jour, individu) + services[(groupe, unite)]
                intervalles.setdefault(cle, []).append((_HeureRepas2C(debut), _HeureRepas2C(fin)))
        if optin:
            consos = _FiltrerAccueilsMidi2C(consos, intervalles, services, plage_midi)
            # Ne pas lire les reponses d'enfants hors du temps meridien.
            ids_midi = set(c["IDindividu"] for c in consos)
            naissances = {ident: naissance for ident, naissance in naissances.items()
                          if ident in ids_midi}
        reponses = {}
        if naissances:
            req = """SELECT IDindividu, reponse FROM questionnaire_reponses
                     WHERE IDquestion=%d AND IDindividu IN (%s)
                     ORDER BY IDreponse""" % (id_question, ",".join(str(int(i)) for i in sorted(naissances)))
            if not base.ExecuterReq(req):
                raise ValueError("Impossible de lire les reponses de regime")
            for individu, reponse in base.ResultatReq():
                if individu in reponses:
                    raise UTILS_Repas_regimes.RegimeInvalide(
                        "Plusieurs reponses de regime pour une meme personne")
                reponses[individu] = reponse
    finally:
        base.Close()
    return UTILS_Repas_regimes.RepartitionRegimes(consos, reponses, choix, services, naissances,
                                                repas_pmsl_prevu=repas_pmsl_prevu if optin else None)


def _VerifierQuestionRegime(base, id_question, choix):
    """Question individuelle a liste deroulante et choix qui lui appartiennent."""
    from Utils import UTILS_Repas_regimes
    req = """SELECT q.controle, c.type FROM questionnaire_questions AS q
             JOIN questionnaire_categories AS c ON q.IDcategorie=c.IDcategorie
             WHERE q.IDquestion=%d""" % id_question
    if not base.ExecuterReq(req):
        raise ValueError("Impossible de lire la question de regime")
    lignes = base.ResultatReq()
    if len(lignes) != 1:
        raise ValueError("Question de regime introuvable")
    if str(lignes[0][1]).lower() != "individu":
        raise ValueError("La question de regime doit etre individuelle")
    UTILS_Repas_regimes.ConfigurationRegimes(id_question, choix, lignes[0][0])
    req = """SELECT IDchoix FROM questionnaire_choix
             WHERE IDquestion=%d AND IDchoix IN (%s)""" % (
                 id_question, ",".join(str(v) for v in sorted(choix.values())))
    if not base.ExecuterReq(req):
        raise ValueError("Impossible de verifier les choix de regime")
    if len(set(r[0] for r in base.ResultatReq())) != len(choix):
        raise ValueError("Les choix de regime ne correspondent pas a la question")


def VerifierParametrageRegimes(question, correspondance):
    """Controle d'un parametrage saisi ; renvoie (IDquestion, {regime: IDchoix})."""
    from Utils import UTILS_Repas_regimes
    id_question, choix = UTILS_Repas_regimes.ConfigurationRegimes(
        question, correspondance, UTILS_Repas_regimes.CONTROLE_REGIME)
    base = GestionDB.DB()
    try:
        _VerifierQuestionRegime(base, id_question, choix)
    finally:
        base.Close()
    return id_question, choix


def ListerQuestionsRegime():
    """[(IDquestion, libelle)] des questions individuelles a liste deroulante."""
    base = GestionDB.DB()
    try:
        req = """SELECT q.IDquestion, q.label, c.type FROM questionnaire_questions AS q
                 JOIN questionnaire_categories AS c ON q.IDcategorie=c.IDcategorie
                 WHERE q.controle='liste_deroulante'
                 ORDER BY c.ordre, q.ordre, q.IDquestion"""
        if not base.ExecuterReq(req):
            raise ValueError("Impossible de lire les questions")
        return [(int(i), label or u"") for i, label, typ in base.ResultatReq()
                if str(typ).lower() == "individu"]
    finally:
        base.Close()


def ListerChoixQuestion(question):
    """[(IDchoix, libelle)] d'une question, dans l'ordre du questionnaire."""
    base = GestionDB.DB()
    try:
        req = """SELECT IDchoix, label FROM questionnaire_choix
                 WHERE IDquestion=%d ORDER BY ordre, IDchoix""" % int(question)
        if not base.ExecuterReq(req):
            raise ValueError("Impossible de lire les choix")
        return [(int(i), label or u"") for i, label in base.ResultatReq()]
    finally:
        base.Close()
