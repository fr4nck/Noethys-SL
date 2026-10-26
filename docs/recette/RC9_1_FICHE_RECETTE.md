# Noethys SL wx — Recette RC9.1 (26/10/2026)

**Règle préalable :** poste Windows isolé, ZIP RC9.1 extrait dans un nouveau dossier, profil `Portable/` vierge et base **fictive uniquement**. Ne jamais pointer vers la base PMSL de production, ni envoyer d'email à une famille réelle. Les tests de démarrage automatisés GitHub ne remplacent pas cette recette visuelle.

## 1. Démarrage et identité

1. Vérifier « À propos » : `Noethys SL 0.1.0 RC9.1`. Vérifier que la rubrique Notes de versions commence par RC9.1 (sans perdre l'historique Noethys).
2. Quitter, relancer, vérifier que `Portable/Config.json` est conservé et qu'aucune configuration externe à `Portable/` n'a été créée ou modifiée.

## 2. Commandes de repas (Lot 1, 2A, 2B)

1. Sur la base fictive, créer une question individuelle de type **Liste déroulante** avec les trois réponses `Standard`, `Sans porc`, `Végétarien`. Un enfant sans réponse est `Non renseigné` **dans RC9.1** (le futur standard par défaut du Lot 2C n'est pas livré).
2. Créer un modèle de commande à colonnes « Régime : standard / sans porc / végétarien / préférence non renseignée », associées à la question/aux choix et aux unités, sites et services de repas.
3. Exemple vérifiable : **42 standard, 8 sans porc, 5 végétariens, 0 non renseigné** → **55 repas au total**, pas 63 ; contrôler les sites/services séparément.
4. Ajouter un enfant sans réponse : observer la colonne Non renseigné et vérifier la confirmation explicite ; modifier une suggestion et contrôler le signalement d'écart avant validation.
5. Vérifier PDF et brouillon d'email ; **aucun envoi SMTP/Mailjet réel**. Contrôler le non-double-compte des adultes (saisie manuelle) et des sous-totaux.
6. Ouvrir un ancien modèle « dont sans porc » ; vérifier qu'il conserve ses anciennes colonnes et valeurs.

## 3. Connecthys et éditeur de messages

1. Sur demande fictive et adresse d'essai, vérifier que l'édition d'un email ne bloque pas l'interface et que la fenêtre reste au premier plan.
2. Simuler un succès puis un refus SMTP/Mailjet sur les adresses de test, vérifier que seule l'adresse restante est proposée à la reprise et qu'une incertitude n'entraîne pas d'envoi silencieux.
3. Simuler la double validation d'une demande avec le même objet ; vérifier l'absence de réentrée et de doublon, puis l'état après fermeture/réouverture.
4. Vérifier l'ouverture/fermeture d'une boîte d'alerte pendant l'envoi et son rattachement à la fenêtre attendue.

## 4. Réserves / points de refus

- **Ne pas tester comme fonction livrée** le choix « Sans repas PMSL » : il n'est pas raccordé au questionnaire, aux commandes ni à la facturation ; aucune promesse de repas gratuit ne doit apparaître sur une facture RC9.1.
- **CAF/AFAS V1** demeure masqué et ne doit pas être utilisé pour une déclaration.
- Préférences non historisées, adultes manuels, limites de reprise SMTP et garantie non absolue des envois, interface Qt non couverte.
- Si un seul scénario échoue, relever la date, le site fictif, le service, le résultat attendu/obtenu, le type de base, la version et l'empreinte de l'artefact ; **STOP publication opérationnelle**.

## Résultat à renseigner après réception des fichiers

- Référence du run GitHub de construction :
- SHA exact de `wx` :
- SHA-256 Setup / Portable :
- Démarrage installé / 2 démarrages portable :
- Tests commandes de repas :
- Tests Connecthys :
- **Verdict : PASS / FAIL / NON EXÉCUTÉ**.
