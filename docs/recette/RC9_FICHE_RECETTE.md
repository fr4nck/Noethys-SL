# Noethys SL 0.1.0 RC9 — fiche de recette du candidat

**Candidat de recette, non valide pour production.** À exécuter sur un poste
Windows de test, avec une base **fictive** (jamais la base PMSL) et, pour
les emails, des **adresses de test** uniquement.

Avant de commencer : vérifier l'empreinte SHA-256 du fichier téléchargé
(voir `docs/dev/REPRISE_CODEX.md`, lot 6) et noter le SHA source indiqué
dans `BUILD-INFO.txt`.

## 1. Démarrage du ZIP portable (deux lancements)

1. Extraire le ZIP dans un dossier vide (par exemple `C:\Recette\RC9`).
2. Lancer `Noethys.exe`. **Attendu** : la fenêtre principale s'ouvre ; le
   dossier `Portable\` contient `Config.json`, `Temp`, `Lang` ; rien n'est
   créé dans `%APPDATA%` ni `%LOCALAPPDATA%` pour Noethys.
3. Modifier un réglage simple (par exemple une option d'affichage), fermer.
4. Relancer. **Attendu** : le réglage est conservé ; aucun nouveau profil
   hors de `Portable\`.

## 2. Type de cotisation

1. Créer un type individuel avec une unité et « Participations constatées
   uniquement ». **Attendu** : enregistrement, réouverture identique.
2. Modifier le nom, une unité et le mode, valider. **Attendu** : les trois
   changements sont présents à la réouverture.
3. Modification concurrente (deux postes, ou deux fenêtres sur un même
   type) : enregistrer dans la première, puis dans la seconde. **Attendu**
   pour la seconde : message « modifié ailleurs depuis l'ouverture », rien
   n'est écrit ; après réouverture, l'enregistrement fonctionne.
4. Erreur (si possible, base en lecture seule ou serveur MySQL coupé
   pendant la saisie). **Attendu** : message « Rien n'a été modifié » ou,
   si la base ne confirme pas la validation, message d'issue
   **indéterminée** demandant de rouvrir le type ; aucune unité en double.
5. Base MySQL de test seulement : si une table `types_cotisations`,
   `unites_cotisations` ou `parametres` n'est pas InnoDB, **attendu** :
   refus avant toute écriture, tables citées, aucune conversion.

## 3. Confirmation Connecthys partielle (destinataires de test)

Famille fictive avec deux adresses de test, dont une refusée par le
serveur d'envoi de test (ou une adresse invalide pour Mailjet).

1. Traiter une demande avec envoi automatique de la réponse. **Attendu** :
   la demande reste « en attente » ; le journal indique l'envoi partiel.
2. Corriger l'adresse refusée, retraiter. **Attendu** : seul le
   destinataire restant reçoit le message ; la demande passe validée.
3. Retraiter encore la même demande sans modification. **Attendu** :
   aucun renvoi.
4. Mailjet sans éditeur, si une réponse est perdue (délai dépassé) :
   **attendu** : aucune relance automatique, journal « acceptation
   incertaine » ; le renvoi volontaire reste possible depuis l'éditeur.
5. Les états et réponses visibles côté portail Connecthys sont ceux
   d'avant (aucun nouvel état).

## 4. Pièce et quotient familial à validité illimitée

1. Saisir une attestation de quotient avec « validité illimitée » et la
   saisie du quotient cochée. **Attendu** : la pièce et le quotient sont
   enregistrés, fin au 01/01/2999 ; aucun message « date trop élevée ».
2. Saisir directement un quotient avec fin au 01/01/2999. **Attendu** :
   accepté.

## 5. Impression d'un dépôt

Dépôt fictif d'au moins 60 règlements (montants positifs, négatifs, nuls,
libellés longs et accentués), une fois verrouillé, une fois non verrouillé.

1. Aperçu. **Attendu** : 13 colonnes lisibles en paysage (Date, Mode,
   Émetteur, N° pièce, Famille, Payeur, Montant, Avis, Compte, Différé,
   Attente, Quittancier, Observations), en-têtes répétés sur chaque page,
   toutes les lignes présentes, titre « Règlements du dépôt - Dépôt
   complet », total au centime égal à celui de l'écran.
2. Trier par montant (croissant puis décroissant). **Attendu** : même ordre
   à l'impression.
3. Fenêtre d'ajout au dépôt, filtre par compte ou mode : imprimer.
   **Attendu** : titre « Vue filtrée », filtre cité, « N règlement(s)
   imprimé(s) sur M », total des seules lignes imprimées.
4. Filtre sans résultat, puis dépôt vide. **Attendu** : message, aucun
   aperçu vide.
5. Ne rien modifier : vérifier ensuite que les règlements et le dépôt sont
   inchangés.

## À consigner

Pour chaque point : OK / KO, capture d'écran en cas d'écart, poste,
version de Windows, type de base (SQLite local, SQLite partagé, MySQL).
