# Qt C19d — contrat bloquant avant toute écriture sur les consommations et factures

**3 novembre 2026** · Branche prévue `qt` · [ticket #440](https://github.com/fr4nck/Noethys-SL/issues/440)

## Objectif

Documenter les règles réellement présentes dans le wx historique et créer un **évaluateur sans écriture** qui ne transforme jamais une déclaration de droits, une période ouverte ou une facture existante en permission d'agir. Le but est de préparer le travail d'authentification, d'autorisations transactionnelles, de périodes et de facturation, **pas** d'annoncer leur portage.

## Éléments confirmés dans la source wx

La source wx et sa copie sur `qt` sont identiques pour ces trois fichiers au moment de l'audit :

| Fichier | Blob Git | Observation vérifiée |
| --- | --- | --- |
| `noethys/Utils/UTILS_Utilisateurs.py` | `361b9fcdf6e2d20e6dde4e4443fdc3b2d535f690` | `VerificationDroitsUtilisateurActuel` appelle `VerificationDroits` en contexte `general`. La dernière retourne `True` quand le dictionnaire utilisateur/droits manque ou qu'aucune règle ne correspond. Hors fenêtre `general`, le wrapper retourne également `True`. Environnement historique **fail-open** : à ne PAS reproduire pour des écritures Qt. |
| `noethys/Utils/UTILS_Gestion.py` | `d4781ed3f5dd6361e32ab98cc34f9ea3c8ce0321` | `Gestion.Verification` examine `periodes_gestion` avec bornes **inclusives** ; la catégorie `consommations` étend ses contrôles au verrou `prestations` en plus de son propre verrou. Les périodes ont aussi des verrous distincts pour factures, règlements, dépôts, cotisations. |
| `noethys/Ctrl/CTRL_Grille_cases.py` | `46b1e02f9398f975747d831456adcb86bb596792` | Trois `ModifieEtat` (standard, multihoraire, événement) appellent la vérification de période. Si une prestation est déjà facturée et sans début de forfait, elles refusent les transitions qui franchissent la frontière `reservation/present/absenti` contre `attente/refus/absentj`. D'autres branches de saisie contrôlent `consommations_conso / modifier` par activité, les consommations verrouillées et les recalculs. |

**Important :** ces constats ne prouvent PAS l'exhaustivité du contrôle wx, ni sa résistance aux accès hors interface. Une contre-lecture du générateur wx a identifié le droit `facturation_factures / creer`, vérifié avec `IDactivite` pour **chaque activité sélectionnée** dans `noethys/Dlg/DLG_Factures_generation_parametres.py` (ligne 684 dans la source examinée). Si aucune activité n'est sélectionnée, le dialogue wx peut poursuivre après confirmation ; la boucle de contrôle des droits n'est alors pas exécutée. Ce comportement ne devra **jamais** devenir une autorisation Qt : un périmètre d'activités vide ou incomplet doit être refusé.

Le code `noethys/Dlg/DLG_Factures_generation_selection.py` (vers les lignes 269–295) crée les enregistrements `factures` puis rattache les `prestations` à leur `IDfacture` via `IDprestation`. Ces extraits ne démontrent pas à eux seuls la transactionnalité et l'idempotence du processus ; ces garanties restent à qualifier.

## Contrat de la nouvelle barrière C19d

`noethys_qt/legacy_write_barrier.py` ne contient **aucun accès aux bases**, aucun modèle Qt, aucun appel à `wx`, aucune mutation et **aucun writer**.

- Droits : un profil absent, une session non attestée, une règle absente, inconnue ou mal formée produisent `INCONNU`, jamais `autorisation`. Pour la création de facture, le code historique utilise `facturation_factures / creer`, mais C19d laisse cet examen `INCONNU` : il n'atteste ni la session, ni une liste complète des activités. La restriction par activité exige un identifiant numérique positif exact ; les restrictions par groupes exigent une correspondance groupe→activités. Une règle explicitement favorable ne reçoit que le statut **`DECLARE`**, jamais une habilitation authentifiée.
- Périodes : l'inventaire doit être complet et daté ; les bornes sont inclusives. En consommation, les deux verrous `consommations` et `prestations` sont requis. En préparation de facture, `prestations` + `factures` sont observés par prudence **sans prétendre équivaloir au générateur historique**. Une donnée manquante ou incohérente reste `INCONNU`.
- Frontière de facturation : un changement entre groupes tarifants, sur prestation déjà facturée sans forfait, est reconnu comme **`BLOQUE_WX`**. L'absence de blocage dans cette seule règle ne signifie **en aucun cas** que la transition est autorisée.
- Le rapport `WriteBarrierReport` impose **`executable=False`** et refuse sa construction avec `True`, même avec une capture de droits « favorable » et aucune période verrouillée. La condition de sortie de C19d est un affichage de contrôle, **pas** l'ouverture du moindre droit d'écriture.

Le panneau de précontrôle C19c affiche désormais ce rapport après avoir relu la prestation **uniquement dans la fixture C13**. En environnement normal, il reste absent et ne consulte ni droits d'utilisateur ni données de production.

## Tests et preuves attendues

- `tests_qt/test_c19d_legacy_write_barrier.py` : **22 tests**, dont des assertions sur les ancres de source wx, les règles absentes/interdites/restrictives, les groupes sans résolution, les périodes closes aux bornes, les verrous hérités, la frontière tarifante et l'impossibilité de forcer `executable=True`.
- Un test Qt supplémentaire du panneau vérifie la présence des lignes « Droits : INCONNU », « Périodes : INCONNU » et « VERDICT : BLOQUÉ » (codes sans accents dans le journal de diagnostic).
- Seuil de la suite complète : **529** tests (= 506 validables du lot C19c + 22 + 1), sans perte de tests.
- Nouveau workflow **Python stdlib seulement** sur Windows et Linux : `.github/workflows/qt-c19d-legacy-barrier.yml`. La recette Qt ciblée et la suite Qt complète sont conservées.

Le lot **C19c** était publié avec 30/30 tests Windows ciblés au run [41681864639](https://github.com/fr4nck/Noethys-SL/actions/runs/41681864639). La suite 506 tests [41681864642](https://github.com/fr4nck/Noethys-SL/actions/runs/41681864642) doit être qualifiée indépendamment. Aucun résultat C19d ne doit être annoncé avant ses nouveaux runs.

## Conditions avant un futur portage d'écritures

1. Système de session utilisateur authentifié, vérification **côté service métier**, et règles complètes chargées sans comportement fail-open.
2. Import/lecture transactionnelle des verrous `periodes_gestion` ; validation des périodes et des droits **au moment du commit**, pas uniquement lors d'un affichage.
3. Reprise contrôlée du calcul wx : inscription/quotient, tarifs par date, groupes, forfaits, cotisations, prestations liées, factures, paiements/ventilations, historique et absence de doublons ; tests d'égalité sur cas fictifs.
4. Transaction atomique et idempotence sous MySQL isolé ; non-régression Windows, tests adversariaux de concurrence, sauvegarde/restauration **sur base jetable** avant toute autorisation de facturer.

**STOP-GATE** : aucune écriture de consommation/facture, aucune migration, aucun déploiement Qt 0.2.0, aucune donnée PMSL. Le diagnostic de sauvegarde du i5-10400 [#437](https://github.com/fr4nck/Noethys-SL/issues/437) demeure différé.
