# Lot D2 — Conventions partenaires, versions signees, tarifs et avenants

**Date : 03/11/2026. Statut : moteur metier et scripts SQL disponibles ; aucune migration ni installation en production.**

## 1. Portee et fondements

Le registre concerne les **conventions de prestations avec des partenaires** ; ce ne sont ni les conventions de financement Caf (AFAS) ni les contrats individuels historiques Noethys. Il s'appuie sur l'annuaire autonome du lot D1 (`partenaires_structures`). Il ne reutilise ni `compta_tiers` comme identite contractuelle, ni `contrats`, ni `documents_modeles` comme base contractuelle : ces objets gardent leur propre responsabilite.

Les conventions scolaires (cycles, classes et periodes) et les conventions associatives (tarifs horaires differencies selon les publics) sont deux cas distincts. Leur **programmation effective** n'est pas creee par D2 : elle appartient aux lots D3-D4. Aucune facture ni prestation n'est produite par D2 : ce raccordement reste D5.

## 2. Livraison source

- `noethys/Utils/UTILS_Partenaires_D2.py` : moteur sans wx/Qt, sur connexion DB-API explicitement fournie ; autorisation obligatoire et refusee par defaut.
- `noethys/Data/Migrations/partenaires_d2_sqlite.sql` : migration manuelle D2 apres D1, quatre tables nouvelles.
- `noethys/Data/Migrations/partenaires_d2_mysql57.sql` : DDL InnoDB **propose**, non qualifie sur serveur MySQL 5.7.
- `tests/test_partenaires_d2.py` : recette complete SQLite avec partenaires fictifs et tables Noethys sentinelles.

## 3. Modele retenu

| Table | Objet | Integrite |
| --- | --- | --- |
| `partenaires_conventions` | Convention, partenaire, type, reference, periode et cloture | Reference unique **par partenaire**, FK D1, sans suppression cascade |
| `partenaires_conventions_versions` | Version initiale ou avenant, clauses, modele, date d'effet, mode payant/gratuit, declaration de signature | Une seule version brouillon par convention, numero de version unique, version signee non modifiable via API |
| `partenaires_conventions_tarifs` | Tarifs explicites par categorie, prestation, unite et intervalle | Decimal exact (texte canonique pour SQLite, `DECIMAL(12,2)` pour MySQL) ; pas de float ; chevauchement refuse pour une meme prestation |
| `partenaires_conventions_evenements` | Historique des changements | Acteur et champs/operation, sans texte des clauses ni montant individuel dans le journal |

Le moteur cree une version **initiale** puis des **avenants** a dates d'effet strictement croissantes. Chaque avenant porte l'ensemble de ses propres tarifs : aucune recopie tacite du tarif precedent. La consultation d'une date anterieure a l'avenant continue de retourner la version signee initiale. Un brouillon n'est jamais applicable a une facturation.

Le mode `gratuite` est **explicite** et interdit les lignes tarifaires ; le mode `payante` exige au moins un tarif strictement positif avant validation. Aucun montant n'est deduit d'une reservation, d'une consommation ou d'une ancienne facture.

## 4. Signature et documents : limites importantes

`signer_version` **consigne la declaration** d'une signature : date, nom du signataire, empreinte SHA-256 du document signe transmise par l'appelant. Il n'effectue **aucune signature electronique** ni verification d'une signature presente dans un PDF. Il ne stocke pas les octets du document signe : l'archivage du fichier et la verification de l'empreinte par rapport a ce fichier seront a raccorder a une gestion documentaire autorisee. Un hash transmis seul ne constitue **pas** une preuve de signature.

A la declaration, le moteur fige une copie des coordonnees d'identification du partenaire, les clauses, le support et la reference du modele (Noedoc ou Word), les tarifs et les informations de signature. Une empreinte SHA-256 de cet instantane est recalculee en lecture : un changement non attendu de ces donnees est signale. **Ce checksum n'est pas une protection contre un acteur malveillant ayant le pouvoir de reecrire a la fois les donnees et le checksum.** Les permissions SQL, sauvegardes, journaux et documents originaux restent indispensables.

`preparer_export` restitue un instantane et les quelques champs **compatibles** avec le generateur de convention existant, sans appeler Noedoc ni creer de fichier. Une valeur impossible a determiner (lieu d'intervention, representant, planning, tarif horaire ambigu ou partiel) reste vide. La selection/validation d'un modele et le rendu Word/PDF depuis l'interface restent **non integres** : ne pas presenter l'export comme une convention generee ou signee automatiquement.

## 5. Recette executee

Sur un dossier isole, avec Python 3.13, SQLite `:memory:` et une sauvegarde/restauration SQLite fictive :

```bash
cd /chemin/vers/Noethys-SL
python -m unittest discover -s tests -p 'test_partenaires_d*.py' -v
python -m compileall -q noethys/Utils/UTILS_Partenaires_D1.py noethys/Utils/UTILS_Partenaires_D2.py tests/test_partenaires_d1.py tests/test_partenaires_d2.py
```

Cas testes : conventions homonymes independantes, types scolaire et associatif, doublons, dates, brouillon unique, clauses et tarifs obligatoires, `Decimal` et deux categories de prix, chevauchement, avenants, dates d'effet, prix historique, empreintes et controle de modification, droits de lecture et d'ecriture, journal sans contenu sensible, transaction/rollback et refus de supprimer en cascade, restauration SQLite et maintien des tables historiques fictives.

**Aucun test MySQL 5.7, Windows, wx ou Qt n'est revendique.** Les tests utilisent des structures et noms fictifs : aucune archive `.nod`, fiche famille, convention reelle ou donnee nominative n'est commitee.

## 6. Barriere de migration et suite

1. Aucun des scripts D1/D2 n'est applique automatiquement par l'application. D2 exige la presence du schema D1. Les CREATE TABLE D2 ne sont pas idempotents : une erreur de reexecution est volontaire.
2. Avant toute migration reelle : copie hors production, sauvegarde/restauration, comparaison d'inventaires, essais MySQL 5.7 (DDL auto-commit, **rollback DDL impossible**), verification des droits applicatifs et tests Windows.
3. D1 doit empecher qu'un partenaire avec conventions actives soit archive sans controle supplementaire de D2 : ce raccordement n'est pas implemente, ne pas le considerer qualifie.
4. La gestion des modeles Noedoc/Word reste celle deja qualifiee. Integrer le choix de partenaire et de version au dialogue apres avoir valide le chemin de creation documentaire et les droits, sans ecraser les champs historiques des familles.
5. D3-D4 devront generer les interventions/plannings a partir de versions signees et du calendrier reel ; D5 rattachera les interventions effectivement facturees au moteur de facturation historique avec anti-doublon.

**Branches canoniques :** le moteur commun et les tests sont cibles sur `main` ; les branches `wx` et `qt` ne sont ni fusionnees ni declarees synchronisees. Aucune publication Windows n'est induite par cette livraison.
