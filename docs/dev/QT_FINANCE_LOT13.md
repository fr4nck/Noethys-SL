# Noethys SL Qt — Lot C13 : Facturation, Règlements et Comptabilité

Date : 27 octobre 2026 — périmètre branche qt.
Cette réalisation met les GROS MODULES À PORTÉE, avant le travail d'habillage.
Ce n'est ni un moteur de comptabilisation, ni une mise en production.

## 1. Objectif, sources et principes

Sur demande utilisateur, la priorité passe du raffinement esthétique à
l'existence de rubriques opérationnelles dans la coque principale Qt.
Les trois rubriques auparavant grisées sont activées en consultation :
Facturation, Règlements et Comptabilité.

Correspondances source wx vérifiées avant développement :
- noethys/Ol/OL_Factures.py : factures, IDcompte_payeur, comptes_payeurs,
  numéro, date d'édition, échéance, total, réglé, solde, état ;
- noethys/Ol/OL_Prestations.py : prestations, date, label, montant,
  IDfacture, IDindividu, IDcompte_payeur ;
- noethys/Ol/OL_Reglements.py : reglements, date, montant, IDmode,
  numéro pièce, IDdepot, modes_reglements, comptes_payeurs ;
- noethys/Ol/OL_Operations_tresorerie.py : compta_operations,
  type de débit/crédit, date, libellé, montant, compte bancaire, relevé ;
- noethys/Ol/OL_Depots.py : depots, nom, date, compte bancaire,
  verrouillage ; noethys/Ctrl/CTRL_Ventilation.py : ventilation
  liée aux règlements et prestations.

La consultation Qt ne réutilise pas les calculs métier wx comme
s'ils étaient déjà qualifiés. En particulier, le montant figurant
dans une facture, le montant réglé et le solde sont les CHAMPS
ENREGISTRÉS ; ils ne sont ni recalculés ni attestés.

## 2. Les 6 listes livrées

| Entrée dans la coque Qt | Liste 1 | Liste 2 |
| --- | --- | --- |
| Facturation | Factures | Prestations |
| Règlements | Règlements | Ventilation |
| Comptabilité | Opérations de trésorerie | Dépôts |

Ces six tableaux utilisent Qt natif, sans wx, avec chargement uniquement
à l'activation de la rubrique, filtrage exact par famille sur les
domaines qui ont un rattachement payeur, recherche texte paramétrée,
année via plage de dates [année, année suivante), lecture limitée à
250 lignes avec indication de troncature, et selection conservée en
absence de changement. La ventilation ne reçoit pas de filtre année,
car aucun champ date n'est porté dans son SELECT.

Navigation exacte :
1. Fiche Famille → « Factures de cette famille ».
2. Fiche Famille → « Règlements de cette famille ».
3. Facture sélectionnée → prestations rattachées par IDfacture.
4. Règlement sélectionné → lignes de ventilation par IDreglement.
5. Dépôt sélectionné → règlements du dépôt par IDdepot, avec retour
   possible vers la rubrique comptable.
6. Depuis une liste financière, ouverture de la famille du compte
   payeur quand l'identifiant source est disponible.

Les filtres famille viennent de comptes_payeurs.IDfamille et non de
categories_travail ou d'une déduction du rôle familial.

## 3. Montants et bornes de fidélité

La valeur financière est lue sans calcul et représentée via
Decimal(str(value)) pour AFFICHAGE ; aucune écriture ni arrondi vers
deux décimales. Exemples fictifs conservés : 12,005 ; -1,005 ;
1000,0003. Ce choix s'oppose à une conversion silencieuse des
montants au moment du rendu, sans résoudre les problèmes historiques
de calcul AFAS/BAIS. L'affichage fidèle ne certifie pas la qualité du
montant enregistré ou la conformité comptable.

Distinguer ABSOLUMENT :
- un état enregistré et consulté ;
- un montant recalculé selon la facturation ;
- le rapprochement paiement/prestation ;
- une écriture en banque ou un export comptable.

Seul le premier état est concerné ici. Il n'y a pas de total global
dérivé des 250 premières lignes.

## 4. Architecture et isolation

Code :
- noethys_qt/finance_readonly_core.py : types, validation, SELECT
  statiques paramétrés SQLite/MySQL, filtres bornés et conversion
  d'affichage sans arrondi.
- noethys_qt/finance_readonly_ui.py : modèle/tableau Qt, deux sous-vues
  par rubrique, chargement et sélection, navigation entre liens.
- noethys_qt/noethys_native.py : activation des trois rubriques,
  entrées d'accueil, navigation depuis fiches Familles et retour.
- noethys_qt/people_details.py : actions familiales de consultation.
- tools/qt_c13_finance_fixture.py : extension EXCLUSIVEMENT temporaire
  de C8FictiveDatabase avec tables comptables entièrement inventées.
- tests_qt/test_finance_c13_readonly.py : tests SQL, domaines et coque.
- tools/qt_c13_native_finance_demo.py : lanceur interactif et pilotage
  du parcours de neuf étapes, à deux échelles Windows.

Le journal Qt ne touche ni aux données réelles, ni à la sauvegarde
NOD fournie, ni à la base réseau. SQLite est placé en PRAGMA query_only
lorsque la connexion est ouverte ; le code ne comporte aucun INSERT,
UPDATE, DELETE, COMMIT métier, ni déclenchement d'une écriture
administrative. Le seul SQL en écriture est confiné à la construction
volontaire de la base temporaire de tests.

Attention : le lanceur de coque Qt CONFIGURÉ, avec un accès à des
données réelles, n'est pas qualifié en usage professionnel par C13.

## 5. Prévol des branches et traçabilité

| Branche | SHA relevé au début | Verdict de propagation |
| --- | --- | --- |
| main | f6f5ccdf6a491025db052b7759aa6facc01b2eca | NON APPLICABLE / INCHANGÉ |
| wx | 11b85461607bd5186f4043fadde831832114911d | NON APPLICABLE / INCHANGÉ |
| qt | c401cf8758ce0b43e1ca6698a9419046890a529e | Développement Qt exclusif |

Commits C13 :
- 593714cf : socle SQL financier six domaines ;
- a6fe1ce2 : pages Qt finances, règlements et trésorerie ;
- dc5e0bdb : familles conservées et année invalidée sur ventilation ;
- 10a6f12d : raccordement de la coque Qt, menus et fiches famille ;
- fb0806cd : extension synthétique SQLite des tables C13 ;
- d138a63f : 26 tests nouveaux de consultation ;
- 17785466 : pilote et workflow de captures natifs Windows.

CI Windows de référence, EN COURS à rédaction :
https://github.com/fr4nck/Noethys-SL/actions/runs/40558968795

Les essais des anciens lots C6-C12 doivent rester non régressés.
Deux parcours C13 prévus (clair 100 % et sombre 150 %), neuf vues
chacun : Accueil, Factures, Prestations, Règlements, Ventilation,
Trésorerie, Dépôts, Règlements du dépôt, Factures globales.
L'intégrité de la base fictive doit être vérifiée avant/après et la
CI doit publier des PNG et JSON seulement si le parcours réussit.

## 6. Restrictions et étapes ultérieures

STOP-GATE maintenu pour toute écriture, émission et correction
de facture, règlements et encaissements, ventilation comptabilisée,
génération d'échéanciers, rapprochement, export comptable, gestion
des droits et périodes, contrôle réel MySQL, sécurité des accès,
packaging et publication. Les montants et l'historique métier ne
peuvent être déclarés de parité wx/Qt sans qualification distincte.

L'utilisateur pourra lancer la démonstration C13 depuis son
worktree Qt autonome, avec le nouveau fichier
tools/Noethys-Qt-C13-Finance-Demo.cmd. Le programme ne lit aucune
configuration de production et désactive l'éditeur d'activités.

Le prochain lot pourra ajouter les modules administratifs manquants
sans exiger de reprendre l'habillage de ce socle, tout en conservant
la séparation absolue entre consultation et écriture.
