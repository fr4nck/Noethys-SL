# Noethys-SL - Choix des absences injustifiees dans la situation des communes

## Fonctionnement

Le module **Facturation > Situation des communes (ALSH)** distingue :

- les journees-enfants **presentes** (`present`), et les reservations passees ou absences injustifiees **facturees** : toutes dans la meme categorie de frequentation ;
- les **absences injustifiees non facturees** (`absenti`), comptabilisees uniquement sur choix explicite de l'utilisateur, en simulation ;
- les reservations `reservation` du futur, isolees dans les previsions ;
- les absences justifiees `absentj` (meme facturees), attentes `attente` et refus `refus`, non retenus pour le bilan communal.

Le choix se fait par **commune, annee et dossier** avec la case « Compter les absences
injustifiees », **decochee par defaut**. Les factures des absences injustifiees sont prises en compte par defaut, meme dans un ancien dossier. L'option permet seulement d'ajouter des absences non facturees. Le choix est enregistre dans le JSON local du dossier.

Lorsque l'option change apres un premier releve, le logiciel demande une confirmation
avant de supprimer les lignes mensuelles pour recalculer les journees. Les acomptes
communaux sont preserves. L'import automatique des consommations est en lecture seule,
et le parametre est transmis sans utiliser de controle wx dans un thread secondaire.

## Calcul

```
Participation = (journees presentes + reservations passees facturees + absences injustifiees facturees) * tarif conventionnel
              + absences injustifiees non facturees * tarif conventionnel [simulation optionnelle]
              + journees futures reservees * tarif conventionnel
Solde indicatif = participation - acomptes communaux recus et affectes a N
```

Les jours presents et les jours factures admissibles alimentent **un seul compteur de frequentation** dans l'ecran et les exports PDF, CSV et Excel. L'option non facturee reste isolee car elle est une simulation. Les montants familiaux ne sont pas utilises.
Le moteur refuse qu'une meme journee-enfant soit comptee deux fois a partir d'etats
ou d'unites contradictoires. Les etats inconnus restent des erreurs explicites.

**Reserve contractuelle :** les conventions mises a disposition font reference aux
journees-enfants realisees. La facturation aux familles ne remplace pas la verification de la convention communale. Le moteur ne modifie ni la base de consommations ni les factures. La validation des clauses locales reste sous la responsabilite de l'operateur. Une validation ecrite de
la commune/convention doit etre apportee avant la transmission comme solde definitif.

## Qualification

Tests de regression sur SQLite fictif, aucun acces ni modification de production :
choix par defaut et opt-in, exclusion `absentj`/`attente`/`refus`, `absenti` futur,
calculs et cache Excel, double comptage, integrite de la provenance, export PDF/CSV,
refus d'option incoherente ou d'un changement de perimetre sans reimport. Pas de
reconstruction d'executable Windows ni de test runtime wx dans cet environnement.