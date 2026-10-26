# Noethys SL 0.1.0 RC9.1 — préversion Windows wx de recette

**Date : 26 octobre 2026. Candidat de recette uniquement, à utiliser sur une base fictive et un profil Portable isolé, jamais directement sur une base PMSL de production.** Cette préversion complète la [RC9 publiée](noethys-sl-0.1.0-rc.9.md) sans l'écraser et sans modifier la version numérique interne de compatibilité de Noethys.

## Nouvelles fonctions depuis la RC9 officielle

### Commandes de repas — Lots 1, 2A et 2B (#430)

- La question individuelle « Type de repas » peut associer trois choix explicites : **Standard**, **Sans porc**, **Végétarien** ; le calcul distingue une quatrième colonne **Non renseigné**.
- Les quatre colonnes sont réparties par date, site et service sans additionner une seconde fois les variantes au total. Les adultes doivent toujours être classés manuellement.
- Les nouvelles commandes à modèle « régimes » proposent des suggestions, une validation d'écart et une correction explicite avant édition du PDF et préparation du brouillon d'email.
- Les anciens modèles « dont sans porc » restent compatibles et ne sont pas convertis silencieusement. La lecture des paramètres des modèles ne recourt plus à `eval()`.
- Les réponses du questionnaire ne sont **pas encore historisées** pour les commandes anciennes : vérifier les anciennes périodes avant toute réimpression. La qualification visuelle Windows reste nécessaire.

### Connecthys et éditeur d'emails — lots wx postérieurs à RC9

- Traitement asynchrone des envois Mailjet et SMTP, avec prise en charge des fenêtres visibles et masquées pour préserver la réactivité de l'interface.
- Limitation des répétitions après un envoi incertain, reprise ciblée de l'étape d'enregistrement, contrôle de la réentrance des boîtes de dialogue et gestion de certaines réservations partiellement appliquées.
- Diagnostic de réactivité UI en **activation facultative**, sans écriture de diagnostic par défaut. La livraison ne garantit pas un envoi réseau « exactement une fois » en toutes circonstances.

## Fonctions non livrées

- **« Repas apporté par la famille / Sans repas PMSL »** et son effet de **0 € sur la prestation repas** : **NON DISPONIBLES** dans RC9.1. Le Lot 2C-1 est un prototype pur sur `main`, non branché sur `wx`. La présence méridienne et le calcul CAF/AFAS ne changent pas.
- Le bouton **CAF / AFAS V1 reste masqué** : résultats non qualifiés pour les déclarations CAF. Ne pas le réactiver.
- Aucune migration de base, correction des factures anciennes ou requalification automatique des préférences.
- Aucun module Qt de commande de repas.

## Tests et publication

Le workflow Windows RC9.1 vérifie le contrat de version, les tests de régression des régimes, les gardes Connecthys, la construction et la sauvegarde/restauration MySQL sur serveur jetable, le démarrage installé, les deux démarrages du portable et `Config.json`. En cas de succès, il produit **Setup.exe**, **Windows-portable.zip** et leurs **SHA256SUMS**.

**Construction candidate** automatique après commit explicitement marqué `[candidate rc9.1]` sur `wx` ; **aucune publication GitHub Release par simple push**. Une publication éventuelle exige un lancement manuel depuis `wx`, `publier=true` et une réussite intégrale du job build, sans remplacer le tag RC9.

Voir la fiche de recette [RC9.1](../recette/RC9_1_FICHE_RECETTE.md).
