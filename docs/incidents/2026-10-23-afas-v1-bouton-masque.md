# 23/10/2026 — résultats AFAS V1 non qualifiés : bouton masqué

## Consigne pour les utilisateurs de RC8 et RC8.1

Dans Noethys SL 0.1.0 RC8 et RC8.1, l'état global des consommations affiche un bouton **« CAF / AFAS »**.

**Ses résultats ne doivent pas être utilisés pour une déclaration CAF sans contrôle manuel indépendant.**

Contrôle attendu avant toute déclaration : recompter les heures à partir des consommations et des prestations, en vérifiant notamment :

- que seules les consommations des activités et groupes de l'équipement déclaré sont retenues ;
- qu'un enfant n'est pas compté deux fois sur une même journée (journée + demi-journée, plages qui se chevauchent, consommation en double) ;
- que les journées périscolaires et extrascolaires ne sont pas mélangées, ni déclarées dans deux équipements ;
- que les statuts retenus (réservation non pointée, présent, absence justifiée, absence injustifiée) correspondent à la règle CAF applicable, séparément pour les heures réalisées et les heures facturées ;
- que les garderies et les repas ne sont pas ajoutés aux heures déclarées ;
- que le calendrier des vacances est saisi pour toute la période ;
- que les temps facturés des prestations sont cohérents (ni négatifs, ni supérieurs à la journée).

Les déclarations déjà transmises à partir de ces chiffres sont à revoir avec la même méthode.

## Mesure dans RC9 (branche `wx`)

- Le bouton « CAF / AFAS » est masqué et n'est plus raccordé à son action (`DLG_Etat_global.py`).
- Le code AFAS V1 est conservé sans modification (`OnAFAS`, `DLG_AFAS_Actualisation.py`, `UTILS_AFAS*.py`).
- Aucun calcul de l'état global n'est modifié ; ses autres fonctions restent disponibles.
- Mesure temporaire : elle ne remplace pas les corrections de fond.

## Anomalies reproduites (audit contradictoire du 23/10/2026, bases fictives)

| Priorité | Anomalie | Exemple reproduit |
|---|---|---|
| P0 | Filtrage par listes d'activités et de groupes indépendantes, au lieu des couples exacts | consommation hors périmètre comptée 9 h au lieu de 0 |
| P0 | Chevauchements et doublons non détectés | 14 h ou 18 h comptées pour 9 h attendues |
| P0 | Périscolaire et extrascolaire séparés uniquement par les options de jours | même consommation déclarable dans deux équipements |
| P0 | Une seule liste de statuts pour le réalisé et le facturé | réservation non pointée ou absence facturée comptée |
| P1 | Temps facturés non contrôlés, calendrier absent classé en période scolaire, consommations un jour de fermeture, anomalies du moteur non remontées | −1 h, 99 h ; jour d'été compté en périscolaire |

## Réactivation

Le bouton ne sera réactivé qu'après correction de ces anomalies sur `main`, conversion des tests contradictoires en tests de non-régression, requalification, puis report ciblé et testé sur `wx` avec recette Windows.
