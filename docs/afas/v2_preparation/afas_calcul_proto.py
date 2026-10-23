"""Prototype AFAS lot 3: agrégation d'intervalles fictifs, sans CAF implicite.

Aucun accès DB, aucun import wx. Les politiques conventionnelles sont injectées,
jamais inventées. Les prestations annexes ne créent pas d'heures de présence.
"""
from collections import defaultdict

class CalculAFASInvalide(ValueError):
    pass

def _minutes(start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= 1440:
        raise CalculAFASInvalide("Horaires invalides, minutes depuis minuit attendues")
    return start, end

def _union(intervals):
    total = 0
    limit = None
    for start, end in sorted(intervals):
        _minutes(start, end)
        if limit is None or start >= limit:
            total += end - start
            limit = end
        elif end > limit:
            total += end - limit
            limit = end
    return total

def _has_overlap(intervals):
    last = None
    for start, end in sorted(intervals):
        _minutes(start, end)
        if last is not None and start < last:
            return True
        last = max(last or 0, end)
    return False

def calculate(rows, eligible_pairs, policy):
    """Rows: individu/date/IDactivite/IDgroupe/unit_id/category/start/end/aeeh.

    Categories: accueil, garderie_matin, garderie_soir, annexe.
    Les heures facturees ne sont calculables que si policy contient une
    fonction de qualification explicite, évaluée par intervalle d'accueil.
    """
    if not isinstance(policy, dict) or policy.get("qualified") is not True:
        raise CalculAFASInvalide("Regles CAF non qualifiees")
    mode = policy.get("mode")
    if mode not in ("Périscolaire", "Extrascolaire"):
        raise CalculAFASInvalide("Mode conventionnel absent")
    if not callable(policy.get("billable_minutes")):
        raise CalculAFASInvalide("Regle de facturation CAF absente")
    if not isinstance(eligible_pairs, (set, frozenset)) or not eligible_pairs:
        raise CalculAFASInvalide("Perimetre vide")
    retained = defaultdict(lambda: defaultdict(list))
    seen_row_ids = set()
    flags = defaultdict(set)
    for row in rows:
        pair = (row["IDactivite"], row["IDgroupe"])
        if pair not in eligible_pairs:
            continue
        cat = row["category"]
        if cat not in ("accueil", "garderie_matin", "garderie_soir", "annexe"):
            raise CalculAFASInvalide("Unite non qualifiee")
        if cat == "annexe":
            continue
        # Identifiants de consommation optionnels, mais uniques quand fournis.
        consumption_id = row.get("IDconso")
        if consumption_id is not None:
            if consumption_id in seen_row_ids:
                raise CalculAFASInvalide("Consommation repetee : IDconso duplique")
            seen_row_ids.add(consumption_id)
        key = (row["individual"], row["date"])
        start, end = _minutes(row["start"], row["end"])
        retained[key][cat].append((start, end))
        flags[key].add(bool(row["aeeh"]))
    totals = dict(heures_realisees=0, heures_facturees_caf=0,
                  heures_realisees_aeeh=0, heures_facturees_aeeh=0,
                  garderie_matin=0, garderie_soir=0, garderie_total=0)
    for key, cats in retained.items():
        if len(flags[key]) != 1:
            raise CalculAFASInvalide("Statut AEEH contradictoire pour une journee")
        all_intervals = cats["accueil"] + cats["garderie_matin"] + cats["garderie_soir"]
        if _has_overlap(all_intervals):
            # Le moteur deduplique les intervalles mais expose le chevauchement
            # comme anomalie bloquante en attendant une regle conventionnee.
            raise CalculAFASInvalide("Chevauchement accueil/garderie ou doublon de presence")
        accueil = _union(cats["accueil"])
        matin = _union(cats["garderie_matin"])
        soir = _union(cats["garderie_soir"])
        minutes_facturees = policy["billable_minutes"](key, tuple(cats["accueil"]))
        if type(minutes_facturees) is not int or not 0 <= minutes_facturees:
            raise CalculAFASInvalide("Resultat facturation CAF invalide")
        # Le total facturable peut differer du realise, mais une valeur superieure
        # a 24 heures pour un individu/jour necessite un traitement hors prototype.
        if minutes_facturees > 1440:
            raise CalculAFASInvalide("Volume facture CAF incoherent (> 24h/jour)")
        if type(policy.get("include_garderie_realisee")) is not bool:
            raise CalculAFASInvalide("Regle heures realisees garderie non qualifiee")
        realised = accueil + (matin + soir if policy["include_garderie_realisee"] else 0)
        totals["heures_realisees"] += realised
        totals["heures_facturees_caf"] += minutes_facturees
        totals["garderie_matin"] += matin
        totals["garderie_soir"] += soir
        totals["garderie_total"] += matin + soir
        if True in flags[key]:
            totals["heures_realisees_aeeh"] += realised
            totals["heures_facturees_aeeh"] += minutes_facturees
    return {k: value / 60 for k, value in totals.items()}
