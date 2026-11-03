# Lot D3-D4 - Interventions et programmations partenaires

**Date : 03/11/2026. Etat : moteur metier et migrations manuelles, sans integration UI ni deployment.**

## 1. Portee

D3-D4 depend du referentiel D1 et de la version contractuelle signee D2. Il n'utilise ni `compta_tiers`, ni `consommations`, ni `prestations`, ni `factures`. Ce lot **n'emporte aucune migration automatique, generation de factures, signature ou impression de document**. Il ne doit pas convertir une reservation Noethys en prestation realisee.

Le planning scolaire de reference 2025-2026 (La Providence) contient 60 lignes de reservation et 130 heures prevues dans ses trois groupes/cycles. Les horaires exceptionnels des 9-10 octobre sont **des exceptions**, les vacances sont indiquees explicitement. Les 130 heures ne sont pas la preuve de 130 heures realisees. Le modele associatif Atout Sports comporte des categories tarifaires et des creneaux de longueurs differentes. Les tests utilisent des tiers et educateurs fictifs, sans donnees nominatives reelles.

## 2. Fichiers

- `noethys/Utils/UTILS_Partenaires_D34.py` : moteur DB-API sans wx/Qt ni ouverture implicite de GestionDB. Permissions de lecture et ecriture **refusees par defaut**.
- `noethys/Data/Migrations/partenaires_d34_sqlite.sql` : **sept** tables D3-D4 sur copie SQLite, apres D1 et D2.
- `noethys/Data/Migrations/partenaires_d34_mysql57.sql` : **proposition** de DDL InnoDB MySQL 5.7, non executee en serveur MySQL.
- `tests/test_partenaires_d34.py` : recette SQLite fictive et regression des regles reelles de planning, sans connexion reseau.

## 3. Responsabilites

| Objet | Table | Contrat |
| --- | --- | --- |
| Programmation | `partenaires_programmations` | Liee a **une version D2 signee** ; brouillon puis validation interne ; periode ne traversant pas un avenant ulterieur signe |
| Creneau | `partenaires_creneaux` | Hebdomadaire (jour 0=lundi) ou ponctuel ; activite, groupe, lieu, intervenant descriptif et categorie tarifaire |
| Exclusion | `partenaires_exclusions` | Vacances, feries, fermetures, autres **saisis explicitement** ; dates inclusives ; plages non chevauchantes |
| Exception | `partenaires_exceptions` | Suppression ou deplacement date/heure/lieu d'une occurrence avant validation ; motif obligatoire |
| Intervention | `partenaires_interventions` | Identite stable unique `(IDcreneau, date_origine)` ; prevue, reportee, realisee, annulee ; heures/lieu/intervenant prevus et reels separes |
| Historique | `partenaires_interventions_historique` | Trace avant/apres des reports, realisations, annulations, remplacements, decisions, acteurs, motifs, references de demande ecrite |
| Evenements de calendrier | `partenaires_plan_evenements` | Creation de programmation, creneaux, exclusions, exceptions et validation interne ; pas de notes nominatives dans le journal |

Aucune suppression en cascade. D3-D4 ne cree aucune cle materielle vers les factures ou prestations ; ce rapprochement releve exclusivement de D5.

## 4. Cycle de vie et invariants

1. Creer une programmation **sur version signee et integre** : elle ne peut traverser la date d'effet d'un avenant signe. Une convention cloturee interdit une nouvelle programmation.
2. Ajouter des creneaux, vacances/fermetures explicites, exceptions horaires et dates en mode brouillon. Les plages invalides et chevauchements de groupe/intervenant **au sein du planning** sont rejetes. Les dates sans occurrence ne sont pas creees automatiquement.
3. `apercu_programmation` retourne les seances actives et les exclusions avec raisons, avant toute ecriture des interventions.
4. `valider_programmation` fige le calendrier par SHA-256 de ses donnees et cree les occurrences atomiquement. Relancer sans modification est idempotent : pas de deuxieme intervention ni de remise a zero des statuts. Le SHA-256 signale une alteration accidentelle ; **ce n'est pas une preuve cryptographique inviolable**.
5. `preparer_annexe` livre **uniquement des champs structures** du planning initial valide. Ce n'est **pas** un PDF/Word produit, ni une annexe signee par le partenaire ; les etats reels ulterieurs n'ecrasent pas cet instantane.
6. Apres validation, chaque intervention peut faire l'objet d'un report explicite, d'une annulation motivee avec origine et caractere justifie, d'un remplacement historique, ou d'une realisation constatee avec horaires/duree reels. Une demande ecrite **referencee** est obligatoire pour un report hors des bornes de programmation mais restant dans la convention et sa version applicable.
7. Toute intervention debute `decision_facturation='a_arbitrer'`. La decision `eligible` n'est possible qu'apres une **realisation constatee**, avec au moins un tarif categorie/date explicite de la version signee. Aucun prix n'est fixe ni aucune facture produite par cette eligibility. Les annulations meme justifiees **ne sont jamais automatisees en non-facturable** : une decision est necessaire.
8. Distinguer minutes initialement prevues, minutes actuellement planifiees et minutes reellement effectuees. Les totaux monetaires, le choix exact de tarif et la facture relèvent de D5.

## 5. Qualification

Depuis un arbre isole contenant les lots D1, D2 et D3-D4 :

```bash
cd /chemin/vers/Noethys-SL
python -m unittest discover -s tests -p 'test_partenaires_d*.py' -v
python -m compileall -q noethys/Utils/UTILS_Partenaires_D34.py tests/test_partenaires_d34.py
```

**110 tests PASS / 0 FAIL / 0 SKIP sur Python 3.13, SQLite fictif** : D1 18, D2 49 et D3-D4 43. Controle de `PRAGMA foreign_key_check`, replay de migration en echec explicite, transactions et rollback apres injection de defaut, restauration SQLite, audit des sources historiques fictives, refus d'un brouillon D2, refus de chevauchements, vacances, changement horaire, report sans doublon, remplacement, facturabilite non automatique, calendrier 60 lignes / 130 heures, recreation idempotente et protection des donnees signees.

**Aucun essai MySQL 5.7 ni runtime Windows ni wx/Qt ne peut etre revendique a ce stade.** Les scripts ne sont pas idempotents. Sur MySQL 5.7 les contraintes `CHECK` ne s'appliquent pas : validation Python et transaction InnoDB indispensables. MySQL applique des commits implicites sur DDL ; en cas de migration partielle, restaurer la copie. Ne pas lancer ces scripts sur une base reelle.

## 6. Limites et stop-gates

- L'identifiant d'educateur est **descriptif** (`intervenant` texte), pas un `IDsalarie` verifie ; aucun detection de conflits **entre partenaires differents** n'est qualifiee. Controle des chevauchements dans une programmation seulement. Ne pas deduire que la disponibilite du personnel est globalement garantie.
- Les vacances et jours feries ne sont **jamais telecharges ni deduits automatiquement** ; la validite du calendrier transmis et sa validation par le partenaire restent a organiser.
- D1-D2 n'ont pas encore de controle global empechant l'archivage d'une structure portant une convention ; verification d'integrite globale avant la recette UI.
- Les droits `autoriser(acteur, action)` doivent etre branches au controle d'acces de l'application : un callback fictif de test n'est **pas** une autorisation de production.
- Aucune adaptation wx, Qt, impression Word, Noedoc ou installation Windows. 
- Aucune autorisation de publication de logiciel ou migration en production. D5 doit implementer des rapprochements `IDprestation`/`IDfacture` avec idempotence et verification tarifaire, apres audit du moteur financier.

**Branches :** travail source commun sur `main` uniquement, sans fusion ni ecrasement de `wx`/`qt`; leurs divergences doivent etre qualifiees avant adaptation de l'interface.
