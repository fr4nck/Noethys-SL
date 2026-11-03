# Lot 2C-2 et garde tarifaire 2C-3 — panier familial

**Développement sur wx après RC9.1, pas encore version publique.** Le modèle de repas opt-in avec un quatrième choix `Repas apporté par la famille / sans repas PMSL` sert au calcul du fournisseur. La journée ou demi-journée réservée contient la présence midi si les **horaires explicites** du site/service en couvrent intégralement la plage. Aucun parent ne réserve une présence au repas séparée.

## Configuration de la commande

Configurer sur un nouveau modèle de commandes des colonnes régime habituelles et **une colonne « Panier apporté par la famille (hors commande) »**. Chaque colonne partage les mêmes quatre identifiants de réponse, site, service, unités de journée/demi-journée, horaires midi `HH:MM`, et le booléen explicite « La formule inclut normalement un repas PMSL ». Aucun texte du questionnaire n'est interprété comme un diagnostic/allergie. Les valeurs manquantes ou incohérentes bloquent la suggestion. Le mode nouveau exclut les paniers de la commande au restaurateur et des sous-totaux fournisseurs, sans effacer les présences.

En opt-in seulement, une absence de réponse signifie standard **si la formule fournit normalement un repas**. Sans offre, le logiciel refuse de présumer un repas ; seul un panier explicitement choisi est recevable. Les anciens modèles à trois choix conservent le statut « non renseigné ». Les enfants sont comptés au plus une fois par site/service. L'ajustement des colonnes enfants en fonction des paniers n'est automatique que si leurs unités correspondent exactement aux unités du nouveau modèle ; sinon aucune suggestion automatique.

## Facturation — barre de sécurité P0

Le module `UTILS_Repas_tarification_2c` **simule**, au centime, la composante repas à 0 € : 
- **repas séparé** : tarif d'accueil inchangé, composante repas à 0 € pour le panier ;
- **journée avec repas inclus** : tarif journée sans repas **distinct et approuvé requis**, aucun rabais implicite ;
- **prestation déjà facturée ou réglée** : arrêt et régularisation humaine ;
- tous les anciens tarifs et états CAF/AFAS sont laissés inchangés.

**Attention : cette politique n'est PAS raccordée à la création des prestations ni aux factures. Il est interdit de considérer que les paniers familiaux sont automatiquement exonérés sur une facture réelle à ce jalon.** La grille de tarification Noethys combine éventuellement plusieurs unités. L'activation exige la qualification des tarifs de chaque accueil PMSL et une méthode historique datée évitant les changements rétroactifs. Aucune migration ni correction automatique de factures ; le bouton CAF/AFAS V1 reste masqué.

## Tests

- Tests purs 2C-1 reportés à l'identique depuis `main`.
- Tests du calcul de composante financière, du refus des forfaits non approuvés et des factures existantes.
- Tests synthétiques SQLite des demi-journées, paniers hors fournisseurs, régimes hérités et contrôle de commande. Aucune donnée réelle ni email.

## Reste pour livraison métier

2C-3 : implémenter le raccordement tarifaire effectif, le prix sans repas des forfaits, les exceptions datées persistées et leur audit sur copie de base ALSH ; qualifier les factures avec/sans repas (y compris les factures existantes). Puis recette graphique Windows. RC9.1 publiée ne contient aucune de ces modifications.


## Lot 2C-3A — Audit tarifaire en lecture seule

Le module `UTILS_Repas_tarifs_audit_2c` (à partir du commit 2C-3A) expose trois opérations explicites :

1. `AuditerTarifsALSH(base, [IDactivite, ...])` : récupère uniquement les tarifs de ces activités, leurs combinaisons d'unités, le nombre de lignes de prix et des **comptages agrégés** de prestations, factures et ventilations/règlements. Aucune famille, aucun nom d'enfant, aucun diagnostic, aucune écriture SQL. Le drapeau `unites.repas=1` est seulement un **indice de repas inclus**, jamais une preuve de prix séparé.
2. `ValiderAccordTarifSepare(rapport, decision)` : exige l'identification d'un tarif journalier dédié à une seule unité repas, une plage de dates couverte par le tarif, l'activité, le site, le service, les identifiants du questionnaire, un approbateur, une preuve de tarif et deux confirmations humaines explicites : **repas distinct** et **accueil facturé indépendamment**. Les combinaisons, crédits ou données ambiguës sont refusés.
3. `SimulerNouvellePrestationPanier(accord, reponse_datee, accueil, repas)` : accepte uniquement un **choix daté et tracé**, un périmètre correspondant et l'absence de prestation/facture/règlement préexistant. Propose « ne pas créer de prestation repas payante », prix repas 0 €, prix accueil inchangé, en lecture seule. Un questionnaire *actuel* sans historique n'est pas une preuve de préférence passée et est refusé.

**STOP-GATE MAINTENUE :** aucun bouton d'activation ou chemin automatique depuis `CTRL_Grille`, aucune écriture dans `prestations`, `factures`, `ventilation`, `consommations` ou `questionnaire_reponses`. Les signatures humaines de cet audit ne sont pas une authentification intégrée à Noethys. L'accord `PREVOL_MANUEL_NON_ACTIF` et la proposition `SIMULATION_SANS_ECRITURE` sont *des sorties de test*. Ne pas annoncer zéro facturation automatique aux familles. Un audit anonymisé des **vrais tarifs ALSH**, sur copie isolée, est la condition de la connexion et de la recette financière complète.

Tester avec `python -m unittest tests.test_noethys_sl_repas_tarifs_audit_2c -v` dans le projet avec le chemin `noethys` chargé. Les cas de tests SQLite sont fictifs. Aucun export d'information personnelle.

## Garde des presences midi multisites (Lot C, 03/11/2026)

Le nouveau modele opt-in a quatre choix **refuse toute suggestion de repas**
quand un enfant est detecte sur plusieurs sites pour la meme date et le
meme service **dans le groupe de colonnes examine**. La lecture SQL est
terminee avant le blocage, et aucune information nominative ne figure dans
l'erreur. Cette erreur remonte via `erreurs_regimes` dans la grille et la
prevalidation PDF/email. La commande ne peut pas etre emise par le flux
type tant que les reservations contradictoires ne sont pas corrigees.

Les modeles historiques a trois choix conservent le comportement existant
(alerte de multisite sans blocage nouveau). Les autres invariants du
lot 2C restent inchanges ; en particulier, aucun changement de facturation,
de presence CAF/AFAS ou de base. **Limite non couverte :** un doublon reparti
entre deux groupes de parametrage distincts (plages midi ou offres repas
differentes, commandes separees) n'est pas detecte par cette seule garde.
Il exige une qualification inter-commandes avant une exploitation multisite.

Contre-epreuves : `tests/test_noethys_sl_repas_2c_wx_integration.py`
(deux sites simultanes bloques en opt-in, levee apres correction,
ancien modele inchange). Recette Windows native et verifications sur copie
ALSH a effectuer avant toute livraison.

## Colonnes d'informations dans les commandes (03/11/2026)

Decision PMSL : l'utilisation interne de Noethys-SL est reservee au personnel
habilite par mot de passe. Les colonnes `texte_infos`, comprenant les
informations utiles aux equipes, restent disponibles dans les modeles de
commandes. Le blocage ajoute au Lot C a ete retire au commit `613d49c6`.

Les controles d'effectifs et les verifications de double presence multisite
demeurent independants et inchanges. Aucune modification de la sauvegarde,
du controle d'acces, des PAI, des factures ou des tarifs.

## 03/11/2026 — Confrontation grille tarifaire et archive PMSL

La grille tarifaire papier `tarif 26-27.pdf` (document fourni) comporte un **repas séparé à 4,25 €**, en plus des prix journée et demi-journée. Exemples à la journée : QF 1000 et + = 11,75 € d'accueil ; QF 700 à 999 = 10,50 € ; QF 300 à 699 = 7,65 €. Le calcul pur `EvaluerPanier` est vérifié sur ces montants par `test_noethys_sl_repas_tarification_2c.py` : panier familial -> accueil intact, repas 0 € ; repas PMSL -> accueil + 4,25 €.

**Limite de la sauvegarde disponible** : l'archive `Noethys_20260910_1040.nod` inspectée en lecture seule contient seulement quatre activités d'encadrement sportif (IDs 5, 6, 7 et 11), et aucune des activités ALSH La Guerche / Moutiers / Bais. Les tables `restaurateurs`, `modeles_commandes` et `commandes` ne comportent aucun enregistrement dans cette archive. Les tarifs ALSH réels, leurs liaisons aux unités et les prestations à facturer **ne sont donc pas observables ici**. Ne pas interpréter ses 7 950 consommations globales comme des consommations ALSH.

**Conséquence pour 2C-3** : l'intention tarifaire 2026-2027 semble compatible avec une composante repas distincte, mais le raccordement automatique demeure NON QUALIFIÉ tant qu'une sauvegarde ALSH représentative ou une lecture agrégée de son paramétrage n'a pas démontré que le modèle Noethys opérationnel sépare bien les deux prestations. Aucun tarif, aucune facture ni aucune base PMSL n'a été modifié.
