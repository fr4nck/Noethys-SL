# Lot D7 — Securisation transactions et edition Word des factures partenaires

Date de qualification : 03/11/2026. **Candidat de developpement seulement.**

## 1. Objet et contexte

Le lot D6 enregistre une facture partenaire avec un numero et un instantane scelle, sans TVA et sans creer de famille ou de compte payeur historique. D7 n'active aucune migration. Le lot apporte :

- un contrat explicite de debut de transaction MySQL pour D1, D2 et D3-D4 ;
- des tests de connexion simulant un pilote MySQL en mode autocommit et une erreur de BEGIN ;
- un examen structurel hors ligne des DDL MySQL 5.7 des lots D1 a D6 ;
- une edition Word A4 **de controle**, a partir des factures D6 verifiees, sans envoi et sans effet en base.

## 2. Correctifs transactionnels

- D1 : exige `get_autocommit()` renvoyant exactement `False` et une methode `begin()` ; la mutation execute `begin()` avant toute ecriture.
- D2 : memes gardes de session et `begin()` dans `_ecrire`.
- D3-D4 : utilise la validation de session D2 et execute `begin()` avant `_ecrire`.
- D5-D6 : avaient deja une transaction explicite avec verrouillage du compteur au D6 ; aucune modification sur ce point.

Le code travaille sur une connexion DB-API dediee ; ces gardes ne prouvent pas la qualite du rollback du serveur ni les proprietes de verrouillage de MySQL 5.7. Il reste interdit de partager ces connexions avec des transactions externes.

## 3. Qualification du schema MySQL : **statique uniquement**

`tests/test_partenaires_d7_mysql_ddl.py` parcourt les scripts D1, D2, D3-D4, D5 et D6, en retirant les commentaires pour ne pas produire de faux positifs. Il verifie :

- 22 tables partenaire dediees, sans ALTER/DROP/DELETE/UPDATE sur les tables historiques ;
- InnoDB et charset utf8mb4 pour toutes les tables ;
- references de cles etrangeres definies dans l'ordre de migration ;
- unicites D6 bordereau / serie / ordre ;
- absence de champs de TVA D6, de CHECK enforce errone sur MySQL 5.7 et de fonctionnalites MySQL 8 explicites.

**Ne pas assimiler ces tests a une migration MySQL executee.** Aucun MySQL 5.7, MariaDB ni serveur distant n'etait disponible dans l'environnement de construction. Aucune base Noethys de production n'a ete ouverte. Avant l'activation : copie jetable d'une sauvegarde, pilote choisi par Noethys, executeur de migration transactionnel quand possible, test des verrous sur deux connexions, restauration et recette Windows de bout en bout.

## 4. Edition Word

`noethys/Utils/UTILS_Partenaires_D7_Documents.py` expose :

```python
from Utils.UTILS_Partenaires_D7_Documents import creer_docx_facture
word_bytes = creer_docx_facture(registre_d6, IDfacture_partenaire, acteur=identite_autorisee)
# L'appelant decide du chemin de sauvegarde dans une interface future.
```

Le moteur exige un `FacturesPartenaires` D6 et appelle `lire_facture(..., verifier_source=True)` avant de generer le document. Il controle l'existence de l'emetteur et du destinataire, les dates, les montants Decimal canoniques et l'egalite entre total et lignes. Il ne modifie aucun champ D6 ni aucune facture historique. Le DOCX porte en en-tete **EDITION DE CONTROLE - NON TRANSMISE**. Aucun PDF officiel, aucune facture electronique, aucun courriel, aucun paiement ou avoir n'est produit.

L'association PMSL a declare ne pas gerer de TVA : **aucune colonne, calcul ou taux TVA** dans le rendu. La `mention_fiscale` est une chaine provenant du profil D6, **jamais une conclusion juridique calculee**. Avant une facture finale, faire valider le regime fiscal, les mentions obligatoires, le SIRET, la serie de numerotation, les coordonnees de reglement, le contenu des conditions de retard, le destinataire et la conservation.

Dependance facultative `python-docx` pour ce seul export. Aucune installation automatique. S'il manque dans le paquet Windows, le rendu est refuse de maniere explicite. Noedoc peut exploiter les donnees `modele_noedoc()` existantes ; son raccordement effectif n'est pas encore realise.

## 5. Recette et rendu visuel

```
cd /mnt/data/lot_d_d7
PYTHONPATH=.:noethys python3 -m unittest discover -s tests -p 'test_partenaires_d*.py' -q
python3 -m compileall -q noethys/Utils/UTILS_Partenaires_D*.py tests/test_partenaires_d*.py
```

**182 tests uniques PASS**, 0 FAIL, 0 SKIP. Cela comprend 162 tests existants D1-D6 et 20 tests D7 (7 gardes de transaction, 5 audits DDL statiques, 8 tests Word). Les tests de Word utilisent uniquement un dossier SQLite recree en memoire, un acteur autorise et des personnes morales fictives ; verification des droits, absence d'effet en base, refus des donnees alterees, montant et suppression de tout traitement TVA.

Le fichier `Facture_partenaire_D7_EXEMPLE_FICTIF.docx` est un exemple a donnees entierement fictives. Rendu et inspection visuelle sur A4 : 1 page ; test additionnel 33 lignes : 2 pages avec repetition de l'en-tete du tableau et montant final en derniere page. Les artefacts de test multi-page sont exclus de GitHub.

## 6. Barriere de mise en service

- **MySQL 5.7 runtime : NON QUALIFIE.** Pas de serveur disponible.
- **Windows et wx : NON INTEGRES.** Aucune fenetre, aucun bouton, aucune recette GUI.
- **Qt : NON INTEGRE.** Aucune fusion des branches.
- **Noedoc : DONNEES PRETES, raccordement NON FAIT.**
- **Avoirs, paiements, emissions, archivage probant, numerotation historique : ABSENTS.**
- **Fiscalite : sans TVA selon declaration de l'association ; fondement et mentions a valider.**

La prochaine phase applicative est l'interface wx en lecture, apercu et validation humaine, une copie MySQL 5.7 de recette puis la gestion des avoirs. Ne publier aucune version Windows sans validation d'ensemble.
