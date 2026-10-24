# Noethys SL 0.1.0 RC9 — fiche de recette du candidat

**Candidat de recette, non valide pour production.**

- SHA construit : `ed30b3c90d1472328a5ad760fc7a43395fa64fd9` (run de construction
  [40101261780](https://github.com/fr4nck/Noethys-SL/actions/runs/40101261780)).
  Les commits de documentation postérieurs ne font pas partie du paquet.
- Empreintes SHA-256 à vérifier avant usage :
  - `Noethys-SL-0.1.0-rc.9-Setup.exe` : `4868cb4c8bc6be9da02e71941c5b36915a6a1cef56634996a954587a4883fddf`
  - `Noethys-SL-0.1.0-rc.9-Windows-portable.zip` : `93fd107ccfbd45371ab242eef9dd75b1ccfe68bda2ee0bbd3ceb9044d9a0d9c8`

## Règles de recette

- Le candidat **écrit** dans la base ouverte (types de cotisation, quotients,
  pièces, états des demandes Connecthys, suivi des emails). Une sauvegarde
  préalable n'autorise pas à tester ces écritures sur la base de travail.
- Toutes les saisies se font sur une **base fictive** ou sur une **copie de
  recette isolée** (fichier SQLite copié, ou base MySQL de recette), jamais
  sur la base PMSL.
- Emails : famille fictive et **adresses de test** uniquement ; aucun envoi à
  une famille réelle.
- Aucune coupure, erreur provoquée ni manipulation de serveur sur la base PMSL.
- Pour chaque contrôle : OK / KO, capture en cas d'écart, poste, version de
  Windows, type de base (SQLite local, SQLite partagé, MySQL), moteur d'envoi
  (Mailjet ou SMTP).

## A. Parcours ordinaires

### 1. Démarrage et conservation d'un réglage après redémarrage

1. Extraire le ZIP portable dans un dossier vide (par exemple `C:\Recette\RC9`),
   sur une session Windows de recette.
2. Lancer `Noethys.exe`. **Attendu** : la fenêtre principale s'ouvre ; le
   dossier `Portable\` contient `Config.json`.
3. Depuis l'interface, modifier un réglage bénin et visible (par exemple une
   préférence d'affichage), puis fermer **normalement** l'application.
4. Relancer le même `Noethys.exe`. **Attendu** : le réglage est appliqué ;
   aucun dossier Noethys créé dans `%APPDATA%` ni `%LOCALAPPDATA%`.

### 2. Type de cotisation : création, modification et réouverture

1. Créer un type individuel avec une unité, mode « Participations constatées
   uniquement ». **Attendu** : la fenêtre se ferme ; à la réouverture, nom,
   unité et mode sont identiques.
2. Modifier le nom, le montant d'une unité et le mode, valider, rouvrir.
   **Attendu** : les trois modifications sont présentes, aucune unité en
   double.

### 3. Pièce et quotient familial à validité illimitée

1. Saisir une attestation de quotient avec « validité illimitée » et la saisie
   du quotient cochée. **Attendu** : pièce et quotient enregistrés, fin au
   01/01/2999, aucun message « date trop élevée ».
2. Saisir directement un quotient avec fin au 01/01/2999. **Attendu** : accepté.

### 4. Dépôt : aperçu, colonnes, tri, filtre, total et pagination

Dépôt fictif d'au moins 60 règlements (montants positifs, négatifs et nuls,
libellés longs et accentués).

1. Aperçu. **Attendu** : 13 colonnes lisibles en paysage (Date, Mode, Émetteur,
   N° pièce, Famille, Payeur, Montant, Avis, Compte, Différé, Attente,
   Quittancier, Observations) ; en-têtes répétés sur chaque page ; toutes les
   lignes présentes ; titre « Règlements du dépôt - Dépôt complet » ; total au
   centime égal à celui de l'écran.
2. Trier par montant, croissant puis décroissant. **Attendu** : même ordre à
   l'impression.
3. Fenêtre d'ajout au dépôt, filtre par compte ou par mode, puis aperçu.
   **Attendu** : titre « Vue filtrée », filtre cité, « N règlement(s)
   imprimé(s) sur M », total des seules lignes imprimées.
4. Filtre sans résultat, puis dépôt vide. **Attendu** : message, aucun aperçu vide.
5. Refaire l'aperçu sur un dépôt verrouillé. **Attendu** : même contenu ;
   règlements et dépôt inchangés.

### 5. Confirmations Connecthys (famille et adresses de test)

Famille fictive avec deux adresses de test.

1. Traiter une demande avec envoi automatique de la réponse, les deux adresses
   acceptées. **Attendu** : demande validée ; états et réponses visibles côté
   portail identiques à RC8.1 (aucun nouvel état).
2. Retraiter la même demande sans modification. **Attendu** : aucun renvoi.
3. Une adresse de test refusée par le serveur d'envoi (adresse invalide).
   **Attendu** : la demande reste « en attente », journal « envoi partiel » ;
   après correction de l'adresse, seul le destinataire restant reçoit le
   message, puis la demande est validée.

## B. Essais de panne et de concurrence (copie de recette isolée uniquement)

1. **Type de cotisation, modification concurrente** : ouvrir le même type sur
   deux postes (ou deux fenêtres), enregistrer dans la première, puis dans la
   seconde. **Attendu** : « modifié ailleurs depuis l'ouverture », rien n'est
   écrit ; après réouverture, l'enregistrement fonctionne.
2. **Type de cotisation, erreur d'écriture** (copie SQLite en lecture seule,
   ou serveur MySQL **de recette** arrêté pendant la saisie). **Attendu** :
   « Rien n'a été modifié », ou, si la base ne confirme pas la validation,
   issue **indéterminée** avec demande de rouvrir le type ; aucune unité en
   double ; aucune nouvelle validation possible avant réouverture.
3. **MySQL de recette seulement** : une table `types_cotisations`,
   `unites_cotisations` ou `parametres` en MyISAM. **Attendu** : refus avant
   toute écriture, tables citées, aucune conversion.
4. **Connecthys, Mailjet sans éditeur, réponse perdue** (délai dépassé sur un
   compte de test). **Attendu** : aucune relance automatique, journal
   « acceptation incertaine » ; renvoi volontaire possible depuis l'éditeur.
5. **Connecthys, deux traitements simultanés** de la même demande sur deux
   postes en **MySQL de recette**. **Attendu** : un seul envoi. En SQLite
   partagé, ce cas n'est pas protégé entre postes (réserve).

## C. Réserves à décider avant l'usage opérationnel concerné

Non acceptées à ce jour ; non couvertes par cette recette :
- arrêt brutal du poste entre l'acceptation par le serveur d'envoi et
  l'écriture du suivi local : renvoi possible au traitement suivant ;
- SMTP : un échec est traité comme « non accepté » (aucune détection
  d'incertitude) : renvoi possible ;
- SQLite partagé entre plusieurs postes : la réservation d'une confirmation ne
  protège que le poste courant ;
- aucune garantie d'envoi « exactement une fois ».
