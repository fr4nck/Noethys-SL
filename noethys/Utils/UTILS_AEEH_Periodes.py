#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Lecture et validation des périodes de droit AEEH historisées (table
`aeeh_periodes`), sans dépendance wx.

Ne touche jamais à `individus.aeeh` (statut tri-état NULL/0/1, cf.
Utils.UTILS_Aeeh) : ce module ne lit et ne valide que `aeeh_periodes`,
sans jamais déduire ni modifier le statut AEEH courant de l'individu, ni
créer de période automatiquement. Aucune donnée médicale. """

import GestionDB


_DATE_INFINIE = "9999-12-31"


class PeriodeAEEHInvalide(Exception):
    """ Levée explicitement par ValiderPeriode() en cas de période invalide
    -- jamais de comportement silencieux. """
    pass


def GetPeriodes(IDindividu):
    """ Liste des périodes de droit AEEH de cet individu, triée
    chronologiquement (date_debut croissante) :

    [{"IDperiode": ..., "IDindividu": ..., "date_debut": ..., "date_fin": ...}, ...]

    Ne fusionne jamais deux périodes entre elles. """
    req = """SELECT IDperiode, IDindividu, date_debut, date_fin
    FROM aeeh_periodes
    WHERE IDindividu=%d
    ORDER BY date_debut;""" % IDindividu
    DB = GestionDB.DB()
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    DB.Close()
    return [
        {"IDperiode": IDperiode, "IDindividu": IDindividu_ligne, "date_debut": date_debut, "date_fin": date_fin}
        for IDperiode, IDindividu_ligne, date_debut, date_fin in listeDonnees
    ]


def EstAEEHActif(IDindividu, date):
    """ True si `date` tombe dans au moins une période de droit AEEH de cet
    individu, bornes inclusives :

    - date_debut <= date <= date_fin ;
    - ou, si date_fin est NULL (période ouverte) : date >= date_debut.

    Ne compte jamais deux fois une même date (simple test d'appartenance,
    peu importe que plusieurs périodes la couvrent). """
    date = str(date)
    for periode in GetPeriodes(IDindividu):
        date_debut = str(periode["date_debut"])
        date_fin = periode["date_fin"]
        if date_fin is None:
            if date >= date_debut:
                return True
        elif date_debut <= date <= str(date_fin):
            return True
    return False


def _chevauche(date_debut_1, date_fin_1, date_debut_2, date_fin_2):
    """ Deux intervalles inclusifs [date_debut_1, date_fin_1] et
    [date_debut_2, date_fin_2] se chevauchent ssi :

    date_debut_1 <= date_fin_2 ET date_debut_2 <= date_fin_1

    NULL (période ouverte) est traité comme +infini. """
    fin_1 = str(date_fin_1) if date_fin_1 is not None else _DATE_INFINIE
    fin_2 = str(date_fin_2) if date_fin_2 is not None else _DATE_INFINIE
    return str(date_debut_1) <= fin_2 and str(date_debut_2) <= fin_1


def ValiderPeriode(IDindividu, date_debut, date_fin=None, IDperiode_exclue=None):
    """ Valide une période de droit AEEH avant écriture dans
    `aeeh_periodes` (l'écriture elle-même reste à la charge de
    l'appelant -- ce module ne modifie jamais la base) :

    - date_debut est obligatoire ;
    - date_fin est facultative (None = période ouverte, droit toujours actif) ;
    - si date_fin est renseignée, elle doit être >= date_debut ;
    - aucun chevauchement toléré avec une période existante du même
      IDindividu (bornes inclusives, cf. _chevauche ci-dessus) -- des
      périodes successives sans chevauchement (ex. 01/01-30/06 puis
      01/07-31/12) ou disjointes restent autorisées.

    IDperiode_exclue permet d'ignorer, lors de la vérification de
    chevauchement, la période dont c'est l'IDperiode -- pour éditer une
    période existante sans la comparer à elle-même, sans bricolage côté
    appelant.

    Lève PeriodeAEEHInvalide explicitement en cas de violation -- jamais
    de comportement silencieux. Ne lit/valide que pour ce seul
    IDindividu : aucune isolation à gérer côté appelant. """
    if date_debut is None:
        raise PeriodeAEEHInvalide(u"date_debut est obligatoire.")

    if date_fin is not None and str(date_fin) < str(date_debut):
        raise PeriodeAEEHInvalide(
            u"date_fin (%r) doit être postérieure ou égale à date_debut (%r)." % (date_fin, date_debut)
        )

    for periode in GetPeriodes(IDindividu):
        if IDperiode_exclue is not None and periode["IDperiode"] == IDperiode_exclue:
            continue
        if _chevauche(date_debut, date_fin, periode["date_debut"], periode["date_fin"]):
            raise PeriodeAEEHInvalide(
                u"Cette période chevauche la période existante IDperiode=%s (%s - %s)." % (
                    periode["IDperiode"], periode["date_debut"], periode["date_fin"])
            )
