# Lot 2C-1 — Présence méridienne et origine du repas (#433)

État : **moteur pur testé, NON raccordé aux commandes, factures ou AFAS**. Aucun nouveau choix n'est encore disponible dans l'interface. Aucune migration SQL.

## Contrat utilisateur à implémenter

Le parent réserve une journée ou une demi-journée, jamais une « présence repas » supplémentaire. L'horaire d'accueil détermine si la plage du service de midi est couverte. Le type de repas détermine uniquement qui le fournit :

- Standard, Sans porc, Végétarien : un repas PMSL si la formule autorise la fourniture.
- Repas apporté par la famille (sans repas PMSL) : présence midi conservée, zéro repas fournisseur.
- Réponse absente : standard par défaut seulement si la formule couvrant midi prévoit normalement un repas PMSL ; sinon situation « à qualifier », sans commande implicite.
- Exception datée : priorité sur la réponse habituelle, pour un enfant, une date, un site et un service donnés ; auteur technique et horodatage avec fuseau obligatoires.

L'expression « sans repas PMSL » n'implique jamais une absence de l'enfant.

## Contrat technique opt-in

Module pur : noethys/Utils/UTILS_Repas_2c.py.

- ConfigurationTypeRepas : valide une question individuelle à liste déroulante et quatre identifiants de choix uniques.
- CouvreMidi : fusionne des intervalles d'accueil qualifiés ; retourne non pour une demi-journée hors midi et bloque une couverture partielle ambiguë. Les plages midi doivent provenir de la configuration du site, jamais d'un horaire universel codé en dur.
- RepartirAccueils : entrées enfants qualifiées, date, site, service, statut, plage d'accueil, plage midi et booléen repas_pmsl_prevu. Ce dernier est une offre de la formule d'accueil **distincte d'une éventuelle unité repas**. Il doit être déterminé explicitement par l'adaptateur ; ne pas le déduire aveuglément de unites.repas.
- Mode prevision : états reservation/present ; mode realise : present uniquement. Il ne s'agit ni du décompte officiel des heures CAF, ni de l'état AFAS.
- Invariants : présents midi = repas fournisseur + repas apportés + à qualifier ; repas fournisseur = standard + sans porc + végétarien. Pas de doublon enfant/date/site/service. Aucune sortie nominative.
- Exceptions : mapping d'entrée avec type_repas, auteur et horodatage ; **aucune persistance, aucun historique réel** pour le moment. Un schéma versionné et qualifié sur SQLite/MySQL sera nécessaire avant son branchement en production.
- Contrôle des entrées : états inconnus, sites multiples simultanés, offres contradictoires, réponses contradictoires et plages partielles déclenchent une erreur. Les sorties incomplètes ne doivent pas être envoyées au restaurateur.

## Tests / limitations

22 tests purs sur données inventées ; 30 présents = 24 standard + 3 sans porc + 2 végétariens + 1 panier = 29 repas fournisseur. Contrôles des demi-journées avec et sans midi, plages jointives, exceptions, défaut conditionnel, statuts et absence de doublon.

**Barrières** : anciennes colonnes de repas et modèles RC8/RC9 inchangés ; aucun branchement à la base, aux écrans wx/Qt, à la tarification ou aux envois. « Zéro facturation du repas » reste un objectif du Lot 2C-3, non une garantie du lot actuel. AFAS V1 reste masqué sur RC9 ; pas d'invention d'heure CAF supplémentaire ni de doublon avec une journée déjà comptée.

Prochaines étapes : qualifier le schéma d'exceptions datées, créer l'adaptateur de présence et de formulaire sur wx (2C-2), puis la logique de tarification des repas séparés et forfaits journée (2C-3). Recette visuelle et manuel utilisateur exigés avant livraison.
