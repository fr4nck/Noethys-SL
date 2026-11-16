# AFAS 2026 — avancer sans connexion au serveur PMSL

Statut : **parcours de contrôle local**, pas une déclaration Caf validée. Le code AFAS V2 se trouve dans la préversion Windows RC11 ; la recette métier sur les données réelles n'est pas terminée. Aucun envoi automatique à AFAS.

## Priorité opérationnelle

Obtenir **quatre contrôles séparés** : ALSH périscolaire Bais, ALSH extrascolaire Bais, ALSH périscolaire La Guerche–Moutiers, ALSH extrascolaire La Guerche–Moutiers. Le Club ados et les minicamps restent distincts et ne sont pas présumés éligibles sans rattachement confirmé.

Pour l'actualisation de septembre 2026, rapprocher exclusivement le **réalisé du 01/01 au 30/09/2026** ; les prévisions octobre–décembre sont des valeurs différentes et ne doivent jamais être ajoutées au réalisé pour résoudre un écart.

## Prévol sans réseau PMSL

1. Réserver le travail sur copie sous `C:\\_Atelier_IA\\Noethys\\AFAS` sur un poste Windows. Aucun changement de profil Noethys en production, aucune écriture vers le serveur PMSL ; aucune création à la racine de C:\\.
2. Utiliser une **sauvegarde complète contenant réellement les ALSH et leurs consommations**. La sauvegarde du 10/09/2026 étudiée auparavant ne contient pas les activités ALSH nécessaires ; elle ne peut pas produire les chiffres Bais. Vérifier l'intégrité et la provenance d'une archive plus récente.
3. `tests/recette_afas2.py` ne lit **pas** une archive `.nod` directement. Ne jamais pointer une restauration sur la base PMSL : restaurer sur un serveur MySQL 5.7 **local jetable et isolé** ou employer une copie SQLite locale **déjà vérifiée**. Ne pas procéder à une restauration si le serveur, la cible ou la protection de la copie ne sont pas démontrés.
4. Sur une copie SQLite locale, l'outil existant permet une extraction pseudonymisée : `python tests/recette_afas2.py extraire <copie_DATA.dat> <extrait_DATA.dat> --annee 2026`. L'original ne doit pas être modifié. Les noms et montants privés ne doivent pas être déposés dans GitHub.
5. Préparer les quatre périmètres sans mélanger les groupes/sites, avec les unités/plages **réellement organisées** (la plage locale de l'unité `Repas` ne peut être devinée). Utiliser **Consommations → Déclarations AFAS** sur la copie, puis **Exporter le contrôle**. Pour comparaison à septembre, `python tests/recette_afas2.py rapprocher <extrait_DATA.dat> --annee 2026 --phase arrete_septembre --preset "<preset>" --attendus <attendus.csv> --sortie <dossier_controle>`. Les références du CSV doivent concerner **le même équipement, le même mode et la même période**.
6. Analyser les anomalies et conserver la provenance mois/site : journée avec demi-journée concomitante, repas isolé, calendrier incomplet, unité non classée, pointage en attente, régularisation/avoir, factures annulées, AEEH, séjours. **Ne pas substituer automatiquement des heures physiques indicatives aux heures CAF**.
7. Pour l'extrascolaire uniquement : une réservation d'un **mois clos** non annulée produit des heures **facturées CAF**, assimilées à une absence injustifiée ; elle ne prouve **aucune présence physique**. Une réservation du mois encore ouvert n'est retenue que si la facture a effectivement été émise et n'est pas annulée. Le périscolaire conserve ses règles de présence distinctes.

## Critères de sortie AFAS

Le module calcule à la seconde et affiche les heures au centième : la précision d'affichage n'est pas une explication d'un écart de milliers d'heures. Pour chaque dossier, rapprocher les jours, les heures, les groupes, les statuts, les ouvertures, les factures et les régularisations ; expliquer chaque différence et examiner les anomalies bloquantes. Les données et la prévision d'octobre–décembre ou les cases AEEH non vérifiées restent **non renseignées**, jamais remplacées par zéro.

Un calcul de contrôle peut être exporté malgré les anomalies ; **le report CAF n'est autorisable qu'après leur résolution et la validation des règles conventionnelles et du périmètre**. Ne pas annoncer la version stable sur la seule réussite des tests fictifs.

## Pistes de recette à distance du serveur

- Tests AFAS V2 Linux / Windows SQLite fictif : workflow `.github/workflows/noethys-sl-afas2-wx-qualification.yml`.
- MySQL 5.7.44 jetable et parité SQLite/MySQL : workflow `.github/workflows/noethys-sl-afas2-mysql.yml`, déclenché automatiquement sur modification AFAS de `wx`.
- Jeu et totaux fictifs de référence : `docs/recette/RECETTE_AFAS2_WINDOWS.md`.
- Connexion PMSL indisponible : diagnostiquer séparément la résolution du nom du serveur et le port MySQL ; ne jamais contourner silencieusement vers une IP ou une autre base.

Ce document ne contient volontairement **aucun chiffre, enfant, extrait SQL ou identifiant PMSL réel**.
