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
