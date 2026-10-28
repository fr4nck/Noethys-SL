# Noethys SL wx — fiche de recette RC10

**Statut initial : À EXÉCUTER**. Toutes les données de cette fiche doivent être fictives. Ne jamais accéder à la base PMSL ni réutiliser un profil Portable réel.

## Prévol et paquet

- Contrôler sur GitHub le commit exact `wx`, le statut des deux jobs du workflow candidat RC10, la présence de `Setup.exe`, `Windows-portable.zip` et `SHA256SUMS.txt`.
- Télécharger les artefacts du même run GitHub, vérifier leurs SHA-256 et archiver la provenance ; ne jamais substituer l'exécutable RC9.1 ni renommer un ancien paquet.
- Extraire le portable dans un dossier neuf, avec `Portable/` vide à l'exception du marqueur ; utiliser exclusivement un dossier enfant/famille fictif. Vérifier `Noethys SL 0.1.0 RC10`, puis les deux démarrages et la persistance des préférences.
- Tester le Setup à part sur un environnement Windows de recette, contrôler le dossier proposé et les données préexistantes de test. Pas de désinstallation/remplacement silencieux du logiciel PMSL réel.

## Connecthys : demandes et interface

- Avec des demandes fictives et le portail simulé, vérifier Journée disponible, Journée pleine avec deux demi-journées, demi-journée partiellement réservée, annulations, quantités différentes de 1 et seconde tentative du même événement.
- Simuler une acceptation email partielle puis un refus : aucune relance implicite ni doublon ; fermer et reprendre la demande.
- Pendant la synchronisation simulée, ouvrir plusieurs fiches et vérifier la réactivité sans écriture de journal personnel par défaut.
- **STOP-GATE** : ne pas conclure à la sécurité complète en présence de deux postes simultanés tant que le cas de concurrence MySQL #435 n'a pas été qualifié.

## Repas

- Vérifier le questionnaire individuel `Type de repas` absent, déjà prêt, mal configuré et contenant des doublons. La préparation doit être idempotente.
- Sur modèles fictifs, vérifier standard, sans porc, végétarien et panier familial ; confronter le nombre total de présents au fournisseur.
- Vérifier qu'un panier familial ne déclenche **aucune exonération automatique sur une facture**, et que les anciens modèles ne changent pas de logique.

## Fiches Enfant/Famille et AEEH

- Importer une fiche Enfant Pêle-Mêle fictive à partir du dépôt de pièces simulé, puis une fiche Famille ; s'assurer que les pièces sont accessibles dans le dossier correspondant.
- Ouvrir `Outils → Contrôler une fiche enfant reçue` ; tester case AEEH vide, Oui/Non, date début/fin, période déjà connue, période chevauchante, justificatif manquant, date impossible, renouvellement et ouverture de l'onglet Médical.
- Essayer l'enregistrement contrôlé d'une période AEEH sur base fictive ; vérifier l'absence de doublon et la présence d'un événement d'historique avec l'agent identifié.
- Historiser une confirmation parentale après document signé et relu ; vérifier qu'aucune information détaillée sur allergies, traitements ou PAI n'apparaît dans l'historique général.
- Vérifier explicitement que recevoir une pièce ne met à jour aucun vaccin, PAI ou traitement automatiquement.
- **Aucun OCR à tester comme disponible dans RC10** : conserver l'original, l'analyse locale fait partie d'un lot ultérieur.

## Contrôles financiers et sortie

- Les états CAF/AFAS non qualifiés restent indisponibles ; vérifier factures, cotisations, exports et sauvegarde/restauration sur données fictives.
- Noter pour chaque anomalie : SHA, version, écran, étapes, attendu/obtenu et capture de test expurgée ; jamais de documents réels ni de données d'enfants dans GitHub.
- Verdict final **PASS / FAIL / NON EXÉCUTÉ**, séparément pour CI/build, recette visuelle, MySQL concurrence, AEEH MySQL et installation. Pas de mise en production avant validation.
