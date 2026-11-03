# Lot D5 - Bordereaux partenaires et controle anti-doublon

**3 novembre 2026. Statut : moteur de rapprochement PREPARATOIRE et SQL en recette locale fictive. Aucune facture officielle, aucun paiement et aucun deploiement.**

## 1. Audit du schema historique de Noethys-SL

Sources inspectees sur `main` : `noethys/Data/DATA_Tables.py`, `noethys/Utils/UTILS_Facturation.py`, `noethys/Dlg/DLG_Factures_generation.py` et les migrations D1 a D3-D4. Le compte payeur de `prestations` et `factures` est `IDcompte_payeur` ; il est historiquement rattache a `comptes_payeurs` et aux familles. `compta_tiers` est un annuaire comptable independant. Un partenaire D1 **n'est pas automatiquement une famille ni un compte payeur**. Un lien D1 `partenaires_liens_noethys` n'autorise pas, seul, une facture famille. Aucun mapping fiable de facturation partenaire native n'a ete identifie dans le perimetre examine.

**Decision** : ne jamais creer de fausse famille ni ecrire automatiquement dans `prestations`, `factures`, `comptes_payeurs`, `compta_tiers`, `ventilation` ou `reglements` pour contourner cette difference de modele. La creation de factures officielles necessite une conception et une recette specifiques.

## 2. Flux exact de D5

1. Une intervention D3-D4 doit etre **realisee** avec horaires reels constates, puis **eligible** par decision humaine. Une seance prevue, reportee, annulee, non facturable ou encore a arbitrer ne peut jamais etre financee.
2. Un responsable cree un **bordereau sur un seul mois civil** pour une convention d'un partenaire, sans prendre en charge de donnees famille.
3. Chaque ligne est selectionnee explicitement par `(IDintervention, IDtarif_convention)`. Le tarif doit appartenir a la version D2 signee applicable a la date reelle, a la meme categorie et a la meme periode tarifaire. Les tarifs `forfait` sont **refuses** faute de regle contractuelle d'allocation par seance : ils requierent un traitement separe.
4. Les tarifs `heure` sont calcules avec `Decimal` en fonction des **minutes reellement effectuees / 60** ; les tarifs `seance` comptent une occurrence realisee. Arrondi **par ligne a deux decimales, ROUND_HALF_UP**, puis somme des lignes. Ni le montant previsionnel ni des heures non constatees ne sont facturables.
5. `proposer_bordereau` est une **lecture seule**. `valider_bordereau` exige une empreinte de l'apercu recent, verrouille les interventions dans une transaction, recalcule les tarifs, puis insere les lignes **sans possibilite de doublonner `IDintervention`**. La contrainte unique SQL est la seconde barriere, y compris lors d'une concurrence de deux connexions SQLite.
6. Une fois le bordereau valide, les lignes et les totaux sont figes. Le correctif commun D3-D4 refuse les modifications d'une intervention deja engagee dans une ligne D5. Un controle de source et de digest detecte egalement les modifications inattendues ; ces SHA-256 ne remplacent ni les droits SQL ni un audit externe.
7. `preparer_csv` retourne du texte CSV en memoire, sans ecriture de fichier. En-tete obligatoire **"DOCUMENT PREPARATOIRE - PAS UNE FACTURE"**, mention de TVA non qualifiee ; libelles proteges contre les formules de tableur. La preparation n'emet pas de facture.
8. `declarer_facture_externe` permet seulement de memoriser **une reference manuelle de facture externe** et son empreinte fournie par l'utilisateur, si le montant declare est egal au total du bordereau. Il ne verifie pas l'authenticite du document ni son paiement. Une reference externe est unique par partenaire (sans distinction de casse ASCII), et une seule declaration est permise par bordereau.

## 3. Fichiers et tables

- `noethys/Utils/UTILS_Partenaires_D5.py` : calcul et tracabilite, aucune ouverture de base implicite, permissions explicites `autoriser(acteur, operation) is True`.
- `noethys/Utils/UTILS_Partenaires_D34.py` : **correction commune D3-D4** ; refuse les changements de seance une fois la ligne D5 engagee, tout en conservant la compatibilite des anciennes bases D3-D4 sans migration D5.
- `noethys/Data/Migrations/partenaires_d5_sqlite.sql` : quatre nouvelles tables pour la recette sur SQLite jetable.
- `noethys/Data/Migrations/partenaires_d5_mysql57.sql` : **DDL InnoDB propose**, avec colonnes FK `INT UNSIGNED` compatibles avec D1-D4. Non execute sur serveur MySQL 5.7.
- `tests/test_partenaires_d5.py` : echecs d'autorisation, tarifs, verrous, sauvegarde/restauration, concurrence, montant exact, absence de modification du modele historique, etc.

| Table | Utilite | Garantie |
| --- | --- | --- |
| `partenaires_bordereaux` | Entete et periode mensuelle | Unique `(IDpartenaire,reference)`, etat brouillon/valide/reference_externe |
| `partenaires_bordereaux_lignes` | Tarification et capture de source | **`IDintervention` UNIQUE**, FK vers intervention, version et tarif, snapshot calcule |
| `partenaires_bordereaux_references` | Declaration manuelle de document externe | Une seule reference/bordereau ; unique par partenaire/referentiel |
| `partenaires_bordereaux_evenements` | Trace de creation, validation, document declare | Date, acteur, action, sans contenu nominatif |

SQLite utilise `TEXT` monetaire canonique pour ne pas transformer les montants en flottants ; MySQL utilise `DECIMAL(12,2)`. Aucune table historique Noethys n'est modifiee. Les scripts ne sont pas rejouables : un `CREATE TABLE` existant fait echouer la reprise. `PRAGMA foreign_keys=ON` est obligatoire sur **chaque** connexion SQLite. Sur MySQL 5.7, les contraintes `CHECK` ne sont pas appliquees ; le moteur Python et les transactions InnoDB restent indispensables.

## 4. Tests executes et reproductibilite

Commande depuis la racine du kit D1-D5 :

```bash
python -m unittest discover -s tests -p 'test_partenaires_d*.py' -v
python -m compileall -q noethys/Utils/UTILS_Partenaires_D1.py noethys/Utils/UTILS_Partenaires_D2.py noethys/Utils/UTILS_Partenaires_D34.py noethys/Utils/UTILS_Partenaires_D5.py tests/test_partenaires_d*.py
```

**140 tests PASS / 0 FAIL / 0 SKIP : 18 D1 + 49 D2 + 43 D3-D4 + 30 D5** (Python 3.13.5, SQLite fictif). Test de deux validations simultanees sur une sauvegarde SQLite jetable : une reussit, l'autre est refusee ; une seule ligne reste enregistre. `PRAGMA foreign_key_check` vide. Les tables factures, prestations, comptes payeurs, familles, consommations et compta_tiers ont conserve leurs lignes sentinelles intactes. Les cas avec 90 minutes, 1 minute, tarif par seance, apercu obsolete, tarif non applicable, avenant, forfait non pris en charge, alteration d'instantane et rollback par injection sont couverts.

**Non executes :** MySQL 5.7 reel, runtime Windows, wx et Qt, permissions applicatives reelles, generation de facture et test d'impression, traitement TVA/avoir, rapprochement de paiements. La signature D2 est **une declaration de signature**, non une validation cryptographique de document PDF signe. La reference de facture externe D5 est egalement une declaration, pas une preuve.

## 5. Barriere pour production

- Aucun code d'application ne lance les nouvelles migrations, ne fabrique de facture, n'associe automatiquement un tiers a un compte famille, ou ne genere une ligne Noethys. **Pas de deploiement recommande**.
- Avant d'activer la facturation partenaire native : definir modele de compte payeur pour des personnes morales, regimes TVA, numerotation de facture, avoirs/corrections apres validation, cas des forfaits et frais, controles d'acces et verrou de lecture/ecriture SQL. Concevoir un export officiel conforme et le valider juridiquement/comptablement avec la structure.
- Recette MySQL 5.7 sur copie reconstituee avec gestion du rollback DDL et verifications FK et concurrentes, puis tests Windows UI sur branche cible apres comparaison des differences `wx`, `qt`, `main`.
- Pour D1, empecher l'archivage intempestif d'un partenaire ayant des conventions/bordereaux non soldes. Le raccordement n'est pas implemente et demeure un **STOP-GATE**.
- Les trois branches ne sont pas synchronisees par cette livraison. D5 commun sur `main` uniquement ; porter les changements applicables a `wx` et `qt` par adaptation ciblee avant toute release.
