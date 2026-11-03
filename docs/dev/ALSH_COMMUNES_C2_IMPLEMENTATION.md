# ALSH-C2 : capture automatique des changements d'adresse et recalcul communal

**Date : 03/11/2026 — developpement commun, non deploye.**

## Demande metier

Quand une adresse de Noethys change, la commune prise en compte pour les presences de l'enfant doit suivre **automatiquement** le domicile applicable a chaque date. Il ne faut ni reinscrire les enfants, ni creer une activite par commune, ni resaisir chaque demenagement dans un second calendrier.

Noethys enregistre `individus.rue_resid`, `cp_resid`, `ville_resid` et `adresse_auto` (l'enfant peut heriter de l'adresse d'un autre individu, habituellement un representant). Les modifications ont lieu notamment dans `DLG_Individu_coords.Sauvegarde()` via `GestionDB.ReqMAJ`, mais des imports et d'autres chemins SQL existent : un branchement limite a une seule fenetre pourrait manquer des changements.

## Mise en oeuvre

- **Deux triggers de base** (INSERT et UPDATE des champs d'adresse de `individus`) enregistrent un instantane de l'adresse et du pointeur `adresse_auto` **dans la meme transaction** que la modification Noethys. Pas de double saisie ; aucune modification du code de la fiche ni de la facturation. Si la transaction Noethys est annulee, l'observation est annulee aussi. Une modification d'un simple telephone n'est pas enregistree.
- **Etat initial lors de l'installation** : les adresses deja presentes sont observees a cette date. Elles ne sont pas etendues artificiellement a des dates anterieures.
- **Resolution datee** : `UTILS_ALSH_AdresseAuto.py` retrouve, pour chaque consommation, la succession des adresses observees jusqu'a sa date. Il suit aussi les references `adresse_auto` : un demenagement du parent change la commune attribuee a l'enfant des la date concernee, meme si la fiche de l'enfant ne change pas.
- **Code communal** : une table de correspondances, configuree une fois par combinaison exacte (code postal, nom de ville normalise), fournit le **code INSEE verifie**. Le moteur ne transforme jamais arbitrairement un code postal en code INSEE, ni un nom de ville ambigu en commune payeuse.
- **Calcul a jour a la consultation** : les couples activite/groupe, correspondances d'unites et tarifs conventionnels sont conserves dans un **profil de calcul**. `calculer_automatiquement(debut, fin, nom_profil, acteur=...)` relit **les consommations courantes** et les observations, puis invoque le **moteur C1**. Des changements d'adresse ou de presence sont donc repercutes au recalcul, sans lancer un second journal de factures.
- **Situation anterieure validee** : si une periode de residence explicite C1 existe avant la premiere observation automatique, elle reste utilisable ; si elle **contredit** la residence automatiquement reconstruite, la ligne est refusee et signalera une anomalie.
- **Correction de date avec preuve** : si une adresse a ete modifiee tardivement, `valider_date_effet(IDobservation, date_effet, justificatif, acteur=...)` permet une correction explicite, auditee et non reecrite silencieusement. Par defaut, la date d'enregistrement en base est seulement une **date de constat**, pas une attestation de date reelle du demenagement.

## Ce qui est et n'est pas automatique

**Automatique apres installation** : capture de chaque changement d'adresse, suivi des enfants en `adresse_auto`, repartition des nouvelles presences par commune de residence et recalcul integral des brouillons avec regles enregistrees. Les exports C1 nominatifs filtres par commune continuent de fonctionner.

**A parametrer une fois et verifier** : code INSEE de chaque commune, activites et unites ALSH elegibles, tarifs dates de conventions signees, droits des utilisateurs. **Non recuperable par magie** : les demenagements deja survenus avant l'installation, si aucune periode datee probante n'a ete conservee. La seule adresse actuelle ne suffit pas a reconstituer les anciennes.

**Anomalies refusees** : adresses non trouvees, code postal/ville sans correspondance, pointeur `adresse_auto` circulaire, plusieurs modifications contradictoires le meme jour, periodes manuelles et automatiques incompatibles, unites et tarifs manquants. Le jour d'un changement ambigu n'est pas attribue sans validation.

**Statut des montants** : `BROUILLON NON FACTURABLE`. `calcul_complet` peut etre vrai si les chiffres sont mathematiquement complets, mais **`liquidable=False` reste impose** avant validation effective des domiciles, conventions et regles. Aucune facture n'est emise, numerotee ou payee. Aucun montant de TVA.

## Fichiers

- `noethys/Utils/UTILS_ALSH_Commune.py` : extension facultative `fournisseur_domiciles`, sans perturber le chemin manuel C1.
- `noethys/Utils/UTILS_ALSH_AdresseAuto.py` : profils conserves, correspondances INSEE, dates validees, calcul automatique.
- `noethys/Data/Migrations/alsh_communes_c2_sqlite.sql` : tables sidecar, triggers et observation initiale.
- `noethys/Data/Migrations/alsh_communes_c2_mysql57.sql` : **proposition** MySQL 5.7, non executee.
- `tests/test_alsh_communes_c2.py` : 40 tests isoles, en complement des 52 tests C1 existants.

## Recette et barrieres

92/92 tests SQLite sur donnees fictives et base isolee (52 C1 + 40 C2), dont changement parent/enfants, copie d'adresse, trois communes, demi-journees, retraitement, cas ambigus, imports SQL directs, rollback, deux connexions SQLite, interdiction de double facturation et export limite a une commune.

**STOP-GATE :** aucun schema C1/C2 n'a ete applique sur MAD ni la production ; aucun test de triggers sur **serveur MySQL 5.7 reel**, aucun portage wx/Qt de l'ecran de consultation, aucun chargement des vrais codes INSEE ou des vraies conventions, aucune validation de la performance sur une copie representant plusieurs annees. Les scripts sont destines a la recette sur copie **avec sauvegarde et revue des privileges TRIGGER**. Ne pas executer les migrations en production directement.

Le fonctionnement complet dans l'interface Noethys exige encore une fenetre de configuration du profil / verification des anomalies et de consultation des situations communales. Cette fenetre n'est **pas** incluse dans C2. Les adresses sont, en revanche, capturees independamment de la fenetre utilisee par le logiciel **apres installation de ces triggers**.
