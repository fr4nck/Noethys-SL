# ALSH-C1 — Fréquentation par commune et domiciles historiques

**Statut : prototype métier en moteur commun, non déployé.** Aucun nouveau module de facturation, aucune facture générée, aucune migration exécutée sur MAD. Développé le 3 novembre 2026.

## Fondement vérifié

Le schéma de l'instantané MAD du 10 septembre 2026 comporte notamment `consommations` (`IDconso`, `IDindividu`, `IDactivite`, `IDgroupe`, `IDunite`, `date`, `etat`, `quantite`), `individus`, `activites`, `groupes`, `unites`. Les adresses courantes `individus.rue_resid/cp_resid/ville_resid` et le pointeur `adresse_auto` **ne donnent pas l'historique daté des résidences**. L'instantané MAD contient essentiellement les activités sportives, pas de jeu représentatif ALSH. Aucune identité personnelle réelle n'a été reprise dans les tests ni les exemples.

Le moteur AFAS existant traite le seul état `present` par défaut pour les présences réelles. Le calcul ALSH-C1 suit ce principe et distingue explicitement les autres états.

## Code et API

- `noethys/Utils/UTILS_ALSH_Commune.py` : `SituationCommunesALSH(connexion, dialecte='sqlite'|'mysql', autoriser=callback)` ; droits **refusés par défaut**. La connexion est fournie par l'appelant ; ouverture implicite de MAD interdite.
- `ajouter_domicile(IDindividu, date_debut, date_fin, rue, code_postal, ville, code_insee, acteur, complement='', pays='France', justificatif)` : périodes **[début inclus, fin exclue]**, `date_fin=None` pour domicile actuel, code commune INSEE contrôlé, justificatif obligatoire, refus d'un chevauchement pour un enfant. Ne prend jamais l'adresse actuelle pour un ancien domicile supposé.
- `cloturer_domicile(IDdomicile, date_fin, acteur)` : clôture auditée, puis ajout de la nouvelle résidence. Les modifications sont atomiques en SQLite et prévoient une sérialisation MySQL par verrou de l'individu.
- `calculer(debut, fin, perimetres, unites, acteur, tarifs=None)` : sélection des couples **exacts** `(IDactivite, IDgroupe)` ; `unites={IDunite:'J'|'M'|'A'|'exclu'}` **choisies par un opérateur**. `present` seul comptable ; `reservation`, `absentj`, `absenti` non comptables. `J=1`, `M/A=0,5`, combinaison M+A = 1, repas et garderies exclus explicitement. Tout doublon, absence d'historique, quantité ambiguë, unité non configurée ou tarif manquant est signalé et interdit un calcul complet ; aucune attribution fictive à une commune.
- Tarifs **optionnels et explicitement fournis**, jamais déduits de la base : liste de dictionnaires `{code_insee, IDactivite, IDgroupe, date_debut, date_fin, prix_jour, reference}`. Chaque grille doit correspondre à la **vraie convention signée** avant toute utilisation de ses montants. Montants calculés en `Decimal`, **sans TVA**. L'arrondi est reconcilié par enfant/jour/commune/tarif (deux demi-journées d'un tarif de 11,55 € donnent 11,55 €, pas 11,56 €). L'édition ne vaut pas mise en facturation.
- Retour : `communes` (nombre d'enfants distincts **par commune**, journées, montants), `enfants` (un groupe **enfant × commune × période de résidence** avec adresse complète et dates), `lignes` (chaque consommation d'origine avec statut et résidence), `anomalies`, `enfants_distincts_global`, `journees_global`, `montant_total_eur`, `liquidable`. Le nombre d'enfants par commune ne s'additionne pas pour obtenir le nombre global distinct. Le statut demeure **« BROUILLON NON FACTURABLE »**, y compris quand `liquidable=True` (qui signifie seulement calcul arithmétique complet, pas facture approuvée).
- `csv_recap_enfants(...)` et `csv_nominatif(...)` : exports nominatifs **par code de commune obligatoire**, adresse complète et dates, séparateur `;`, encodage UTF-8 BOM compatible Excel. Contrôle d'anomalies, protection contre formules injectées, journalisation de l'export (acteur, période, commune, nombre de lignes). `csv_anonyme(...)` contient seulement des agrégats sans noms/adresses.

## Principes métiers et cas particuliers

Un enfant peut résider à Bais puis Moutiers, voire revenir à Bais, pendant le même exercice. **Chaque consommation est attribuée au code commune dont la période de résidence englobe la date exacte de présence**. Un enfant peut apparaître dans plusieurs annexes, sans que les mêmes journées y apparaissent plusieurs fois. Si la date du déménagement n'est pas connue, une période restera **à vérifier**, non attribuée.

Une demi-journée ne signifie pas toujours exactement 0,5 journée-enfant : cette interprétation est une **configuration explicite de C1**, à valider par la convention pour chaque site et groupe avant le passage en production. Les absences facturées aux familles ne sont **pas** assimilées par défaut aux présences communales.

Les identifiants de commune sont ceux des communes de **résidence**, pas les centres d'accueil. L'activité ou le groupe désigne le lieu / périmètre d'accueil. Les tarifs peuvent être différents, par exemple ALSH classique et Club Ados, pour la même commune et la même année : le tarif est donc toujours rattaché à un couple activité/groupe et à une période.

## Recette et limites

- **52 tests synthétiques SQLite**, aucun échec ni test ignoré : 3 déménagements, mêmes enfants dans 3 communes, M+A, contrôles doublons et chevauchements, absences, groupes distincts, conventions différentes selon activité, arrondis, sécurité des CSV, droits et historique, concurrent SQLite (une seule insertion admise), sentinelles sur tables `prestations` et `factures`.
- SQL SQLite et **MySQL 5.7 proposé** dans `noethys/Data/Migrations/alsh_communes_c1_*`. La validation syntaxique MySQL et la concurrence sur serveur MySQL réel restent **non effectuées** ; les DDL ne sont jamais lancés automatiquement. Le connecteur accepte `.begin()` (MySQLdb) ou `.start_transaction()` (mysql-connector) si `get_autocommit() is False`.
- **Pas encore implémentés** : interface wx/Qt, saisie conviviale de l'historique des domiciles, validation juridique/sur pièces des résidences alternées, paramétrage durable des activités et coefficients, liaison vérifiée à la convention D2, gel/révision de situations validées, acomptes et solde de convention, génération d'un PDF ou d'un vrai fichier XLSX, raccordement à la **facturation historique Noethys**, recherche des adresses passées non documentées dans MAD.
- **STOP-GATE** : pas de facture, encaissement, déploiement, migration ou export nominatif de vrais enfants sans qualification et autorisation des utilisateurs. Les CSV du moteur sont des **brouillons**.

### Exemple de lancement local des tests (hors production)

Depuis la racine du dépôt ou du kit :

```bash
python -m unittest discover -s tests -p 'test_alsh_communes_c1.py' -v
```

**Prochain lot C2 :** interface de saisie/validation des domiciles et choix ALSH des couples activité/groupe et unités ; affichage par commune, par enfant et date ; branchement sur le Noethys existant après recette sur copie comportant de vraies données ALSH. **C3 :** situation annuelle avec acomptes, solde, gel des lignes et édition justificative conforme, sans deuxième facturier.
