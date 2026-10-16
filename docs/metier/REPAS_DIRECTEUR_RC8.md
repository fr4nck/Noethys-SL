# RC8 — supplement de repas du directeur detache (#430)

**Statut : source candidate, non publiee.** Aucun schema ou parametrage existant n'est migre.

Dans **Modele de commandes de repas**, modifier la colonne de type **Numerique (Avec suggestion)** representant les **repas de 6 ans et plus** pour un site. Activer **« +1 repas directeur detache non deja compte »**, et renseigner un identifiant stable du site et le service (ex. midi). La case est **desactivee par defaut** et les modeles existants restent inchanges.

Cette option signifie que **le repas du directeur detaché est prevu pour ce service et n'est pas deja dans les repas adultes**. Si le repas figure deja dans les effectifs du personnel, **laisser l'option decochee** : aucune information personnelle permettant de detecter cette situation ne doit etre recherchee.

Le supplement est **suggere** (et non emis immediatement) par date ouverte, sur le meme mecanisme que les effectifs ordinaires. Dans **Commandes des repas > Outils > Convertir les suggestions**, l'operateur confirme la proposition avant de sauvegarder ou produire le PDF. La cellule reste modifiable ; les valeurs saisies et les anciennes commandes ne sont jamais majorees automatiquement.

En cas de plusieurs colonnes actives pour le meme **site + service + date**, une seule recoit +1. Deux sites differents peuvent chacun recevoir +1. Le service different (midi/soir) est traite separement. Le calcul respecte le controle existant d'ouverture d'unites ; il n'ajoute rien quand la colonne ne peut pas etre modifiee.

**Important :** l'option est a activer uniquement sur la colonne « 6 ans et plus » : les colonnes de commande sont personnalisables et Noethys ne connait pas encore leur categorie d'age. Le supplement n'a **aucun effet sur le calcul d'encadrement #429**, sur les enfants de moins de 6 ans ni sur la categorie « sans porc ».

## Organisation multisite et renfort de direction

Dans chaque colonne « Numerique (Avec suggestion) » du modele :
- **Site** : identifiant stable du site ou le repas est comptabilise ;
- **Service** : service de restauration, par exemple midi ;
- **Direction commune a plusieurs sites** : cocher l'option et renseigner le **meme identifiant d'ensemble multisite** pour les sites partageant un directeur ;
- **Renfort eventuel de direction** : aucun (defaut), adjoint ou directeur stagiaire ;
- **+1 repas renfort de direction** : seconde case independante, desactivee par defaut, a cocher uniquement si cette personne mange et que son repas n'est pas deja compte.

Un directeur est comptabilise **au plus une fois pour (ensemble multisite, date, service)** parmi les colonnes de la meme commande. Quand un repas de renfort est explicitement selectionne, **au plus un repas complementaire** est suggere pour le meme ensemble/date/service, jamais automatiquement du seul fait de l'existence d'un renfort. Un site independant conserve son propre +1 directeur.

**Le site de prise de repas doit etre choisi** : activer le repas de direction uniquement sur les colonnes du site qui le fournit. Le systeme ne deduit pas de quel site releve physiquement le directeur partage. Ces champs sont des parametres locaux du modele ; ils ne constituent pas encore un referentiel global de personnels ou de multisites.

**Limite importante :** la garantie anti-doublon s'applique aux colonnes d'**une commande** ; le premier lot n'empeche pas deux commandes distinctes de commander un repas pour le meme directeur. A valider avant d'utiliser une commande par site. La mutualisation du poste de direction et le renfort eventuel pour le planning relèvent du ticket #429, sans modifier le nombre d'animateurs de terrain.

## Avant publication

- Tester sur une base fictive avec deux sites, plusieurs groupes, un jour ferme et des commandes existantes.
- Verifier l'apercu et le bon PDF du restaurateur sans envoyer d'email.
- Qualifier que la colonne retenue represente bien les 6 ans et plus et que le directeur n'est pas deja compris dans les adultes.
- Propager a `wx` et `qt` apres comparaison/qualification des fichiers correspondants et passage de CI.
