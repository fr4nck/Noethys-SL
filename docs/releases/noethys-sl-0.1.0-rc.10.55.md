# Noethys SL 0.1.0 RC10.55 — préversion cumulative Windows

**PMSL / 4 novembre 2026** — Source : branche `wx` ; édition wxPython / Python 3.
Cette RC ne modifie pas la version interne de compatibilité Noethys (`1.3.4.4`) et ne réalise pas de migration de base de données.

## Corrections incluses

- **État global des consommations** : rétablissement du sélecteur multiple natif historique, des quatre états (présent, réservation, absence justifiée et absence injustifiée), des profils inchangés, du bandeau et des boutons d'origine. Plus de boîte d'alerte CAF lors du chargement. La page est gelée : aucune modification ultérieure sans accord de la direction. Tests de non-régression.
- **AFAS V2 — actualisation de septembre 2026** : préconfiguration des quatre dossiers ALSH de Bais et La Guerche–Moutiers, récapitulatif distinct pour le Club Ados, conservation du réalisé si la prévision du dernier trimestre manque.
- **Périscolaire : repas méridien** : inclusion par défaut de la plage de repas admissible dès lors qu'une présence d'accueil du même site et du même jour est attestée. Une heure déjà couverte par une autre plage n'est pas doublée ; le plafond journalier conventionnel est conservé. La comparaison « sans repas » dans l'État global n'est qu'un contrôle diagnostique : elle ne change pas AFAS.
- **Prévision périscolaire** : ratio basé sur le réalisé du dernier trimestre N-1 et les jours d'ouverture périscolaires correspondants. Les ouvertures relevant des vacances extrascolaires ne gonflent plus le nombre de jours. Le moteur conserve et expose la période historique, les heures N-1, les jours ouverts et les heures projetées. Export supplémentaire `JUSTIFICATIF_PREVISION.csv`.
- **Comparaison des heures** : export `ECARTS_PRESENCE.csv` par enfant et date comparant présence physique et présence conventionnelle CAF, sans changer la comptabilité ni l'État global.
- **Libellés des profils** : noms libres, dont « Bais - Réel Septembre / Prèv Décembre ». L'année et la phase sont choisies dans les contrôles de calcul, jamais déduites du nom.
- **Journées facturées et communes** : une journée couverte par une facture valide est intégrée au même compteur de fréquentation, quel que soit le statut de consommation ; factures annulées et doublons écartés.
- **Adhésions/cotisations, facturation, fiches familles, sauvegardes, Connecthys** : correctifs cumulés de RC10.5 conservés.

## Contrôle des chiffres de Bais

Le rapport transmis pour la phase « Actualisation de septembre 2026 » affiche :

| Indicateur périscolaire Bais | Réalisé janv.–sept. | Prévision oct.–déc. | Total |
|---|---:|---:|---:|
| Heures conventionnelles CAF | 10 394,00 | 4 889,13 | 15 283,13 |
| Présence physique | 10 896,00 | 5 106,83 | 16 002,83 |
| Garderie | 911,00 | 379,83 | 1 290,83 |

**Ces valeurs correspondent à la RC antérieure, pas à un recalcul qualifié RC10.55.**
L'écart réalisé de 502 h entre les deux premières lignes doit être examiné avec l'export `ECARTS_PRESENCE.csv`. Le prévisionnel de 4 889,13 h provient de l'historique octobre–décembre 2025 corrigé du nombre de jours ouverts et ne doit pas être pris pour une programmation directe 2026. Aucun nombre modifié n'est annoncé sans recalcul sur le dossier utilisateur.

Le contrôle historique avec et sans repas sert uniquement à isoler l'origine des différences. La journée facturée du périscolaire et les heures d'option 2 extrascolaire correspondent à des calculs distincts ; l'utilisation de l'État global comme contrôle contradictoire est conservée.

## Livrables

- `Noethys-SL-0.1.0-rc.10.55-Setup.exe` : installation Windows
- `Noethys-SL-0.1.0-rc.10.55-Windows-portable.zip` : version portable avec profil isolé
- `SHA256SUMS.txt` : empreintes des deux livrables

**Préversion de recette** : ne pas remplacer la base/installation de production sans sauvegarde. La construction et les tests automatisés ne valent pas qualification d'une déclaration CAF et n'effectuent aucun envoi.
