# -*- coding: utf-8 -*-
"""Part repas des attestations : règles datées et consommations facturées."""
import datetime
from decimal import Decimal, InvalidOperation
import json

CATEGORIE = 'attestations_fiscales_repas'


def ValiderRegles(regles):
    resultat = []
    for regle in regles:
        try:
            unite = int(regle['IDunite'])
            debut = datetime.date.fromisoformat(regle['date_debut'])
            fin = datetime.date.fromisoformat(regle['date_fin'])
            montant = Decimal(str(regle['montant']).replace(',', '.'))
        except (KeyError, ValueError, InvalidOperation, TypeError):
            raise ValueError('Chaque période doit préciser une réservation, deux dates et un montant valide.')
        if unite <= 0 or fin < debut or not montant.is_finite() or montant < 0 or montant.as_tuple().exponent < -2:
            raise ValueError('Vérifiez les dates et le montant du repas (positif ou nul, deux décimales maximum).')
        for autre in resultat:
            if autre['IDunite'] == unite and debut <= datetime.date.fromisoformat(autre['date_fin']) and fin >= datetime.date.fromisoformat(autre['date_debut']):
                raise ValueError('Deux périodes de prix se chevauchent pour la même réservation repas.')
        resultat.append(dict(IDunite=unite, date_debut=str(debut), date_fin=str(fin), montant=str(montant)))
    return resultat


def Charger(DB):
    marque = '%s' if DB.isNetwork else '?'
    DB.cursor.execute('SELECT parametre FROM parametres WHERE categorie=%s AND nom=%s' % (marque, marque),
                      (CATEGORIE, 'regles'))
    rows = DB.cursor.fetchall()
    if not rows:
        return []
    if len(rows) != 1:
        raise ValueError('Le paramétrage des repas est en double : faites vérifier la base.')
    return ValiderRegles(json.loads(rows[0][0]))


def Sauver(DB, regles):
    regles = ValiderRegles(regles)
    marque = '%s' if DB.isNetwork else '?'
    try:
        DB.cursor.execute('SELECT IDparametre FROM parametres WHERE categorie=%s AND nom=%s' % (marque, marque),
                          (CATEGORIE, 'regles'))
        rows = DB.cursor.fetchall()
        if len(rows) > 1:
            raise ValueError('Le paramétrage des repas est en double : faites vérifier la base.')
        contenu = json.dumps(regles, ensure_ascii=False)
        if rows:
            DB.cursor.execute('UPDATE parametres SET parametre=%s WHERE IDparametre=%s' % (marque, marque),
                              (contenu, rows[0][0]))
        else:
            DB.cursor.execute('INSERT INTO parametres (categorie, nom, parametre) VALUES (%s, %s, %s)' % (marque, marque, marque),
                              (CATEGORIE, 'regles', contenu))
        DB.Commit()
    except Exception:
        DB.connexion.rollback()
        raise


def Calculer(DB, prestations, regles):
    """Ne rapproche jamais deux prestations par leur libellé ou une date seule."""
    regles = ValiderRegles(regles)
    if not regles:
        return {}
    ids = {int(p[0]) for p in prestations}
    unites = {r['IDunite'] for r in regles}
    if not ids:
        return {}
    filtre_ids = ','.join(map(str, sorted(ids)))
    filtre_unites = ','.join(map(str, sorted(unites)))
    DB.cursor.execute('''SELECT c.IDconso, c.date FROM consommations c
        WHERE (c.IDprestation IS NULL OR c.IDprestation=0) AND c.IDunite IN (%s)
        AND EXISTS (SELECT 1 FROM prestations p WHERE p.IDprestation IN (%s)
            AND p.IDindividu=c.IDindividu AND p.IDactivite=c.IDactivite AND p.date=c.date)''' %
                      (filtre_unites, filtre_ids))
    sans_lien = DB.cursor.fetchone()
    if sans_lien is not None:
        raise ValueError('Un repas du %s n’est pas lié à la prestation facturée. Vérifiez la tarification avant de déduire automatiquement les repas.' % sans_lien[1])
    # Les identifiants sont convertis en entiers avant de composer le filtre.
    DB.cursor.execute('SELECT IDconso, IDprestation, IDunite, date, quantite FROM consommations WHERE IDprestation IN (%s) AND IDunite IN (%s)' %
                      (filtre_ids, filtre_unites))
    deductions = {}
    for IDconso, IDprestation, IDunite, date, quantite in DB.cursor.fetchall():
        date = str(date)[:10]
        correspondances = [r for r in regles if r['IDunite'] == IDunite and r['date_debut'] <= date <= r['date_fin']]
        if len(correspondances) != 1:
            raise ValueError('Il manque le prix du repas pour la réservation %s du %s. Complétez les périodes.' % (IDunite, date))
        quantite = Decimal(str(1 if quantite is None else quantite))
        if not quantite.is_finite() or quantite < 0 or quantite != quantite.to_integral_value():
            raise ValueError('La quantité du repas du %s doit être vérifiée.' % date)
        deductions[IDprestation] = deductions.get(IDprestation, Decimal('0')) + quantite * Decimal(correspondances[0]['montant'])
    return deductions


def Appliquer(montant, regle, deduction, ajustement=Decimal('0')):
    montant, regle = Decimal(str(montant)), Decimal(str(regle))
    deduction, ajustement = Decimal(str(deduction)), Decimal(str(ajustement))
    if deduction and (deduction > montant or montant < 0):
        raise ValueError('La part repas dépasse le montant de la prestation : vérifiez le paramétrage.')
    if deduction and 0 < regle < montant:
        raise ValueError('Une prestation avec repas est partiellement réglée. Vérifiez sa ventilation avant de générer cette attestation.')
    total = max(Decimal('0'), montant - deduction + ajustement)
    paye = max(Decimal('0'), regle - deduction + ajustement)
    return total, paye, max(Decimal('0'), total - paye)
