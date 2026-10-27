# Noethys SL Qt — Lot C11 : navigation exacte des fiches aux consommations

Date : 27 octobre 2026. Travail limité à la branche canonique qt.

## Objectif

Après les essais utilisateurs positifs sur la fluidité Qt, relier la fiche
Individu et la fiche Inscription aux consommations par clés Noethys et non
par recherche de noms, sans introduire une nouvelle fenêtre ou une écriture.
La base reste intégralement fictive, isolée et supprimée après recette.

## Audit et versions

| Branche | SHA contrôlé | Verdict C11 |
| --- | --- | --- |
| main | f6f5ccdf6a491025db052b7759aa6facc01b2eca | NON APPLICABLE, non modifiée |
| wx | 11b85461607bd5186f4043fadde831832114911d | NON APPLICABLE, non modifiée |
| qt (avant) | 48d029e7f932fa4648c2aecae4ee962dec7dd79c | Base du lot C10 |
| qt (code + tests) | ee0fcaf8abdfe2685252083a106be35340e9fb05 | QUALIFIÉ, 255 tests Windows PASS |
| qt (captures) | 952f707684f350d9f44d7a12805d8454e872be07 | QUALIFIÉ, CI Windows et captures C11 PASS |

Commits C11 :
- 5389cc21 : raccordement des deux fiches à la page Qt et normalisation
  d'un seul contexte de filtres.
- 9cf9a2c3 : onze tests de non-régression SQL / widgets / sécurité.
- ee0fcaf8 : rectification du test C9 qui supposait le premier individu
  d'une liste triée toujours égal à l'ID 10.
- 952f7076 : recette graphique C11 en deux thèmes/échelles et dépôt d'artifact.

Les requêtes build_statement et build_month_statement possédaient déjà les
paramètres individual_id et inscription_id ; C11 n'a pas réinventé le
moteur métier mais exploité ce contrat de consultation existant.

## Parcours fonctionnel réellement développé

1. La fiche Individu affiche un accès direct aux consommations de l'individu
   sélectionné. Le filtre est exactement c.IDindividu = valeur paramétrée.
2. La fiche Inscription utilise le véritable IDinscription de sa ligne et
   relit IDindividu par SELECT paramétré sur le dossier source. La liste et
   le calendrier croisent les deux conditions, sans déduire l'individu du
   nom présenté à l'écran.
3. Les contrôles du calendrier affichent la mention « Filtre exact :
   Individu #... · Inscription #... » et permettent de la retirer.
4. Pour une navigation depuis une fiche, les filtres résiduels susceptibles
   de masquer la sélection (activité, texte, états, jour, année) sont remis
   en cohérence sous QSignalBlocker puis une unique actualisation logique
   liste et mois est demandée. Les fonctions restent en lecture seule.
5. La sélection des autres écrans ne passe pas par une boîte de dialogue :
   tout se déroule dans le démonstrateur Qt existant.

Un ID individuel incompatible avec un ID inscription ne renvoie aucune
consommation, jamais la liste globale. Un ID invalide déclenche une erreur
et préserve le contexte précédent. Les résultats asynchrones périmés ne
peuvent pas remplacer la sélection actuelle. Les requêtes restent bornées
à 300 lignes pour la liste et le calendrier conserve des agrégats SQL
indépendants du plafond.

## Qualification et preuves

Run Windows code + tests :
https://github.com/fr4nck/Noethys-SL/actions/runs/40549694485

Run Windows définitif avec images :
https://github.com/fr4nck/Noethys-SL/actions/runs/40550244620

Le run définitif est SUCCESS : Windows/Python 3.11/PySide6, compileall
PASS, unittest **255 PASS, 0 échec, 0 erreur, 0 traceback Qt**, contre
244 tests après C10 ; 11 nouveaux tests C11.

Exemples de tests :
- individu fictif #12 : 28 lignes et 28 comptages, aucune ligne d'un
  autre individu ;
- inscription fictive #503 liée à l'individu #12 : même intersection
  de 28 lignes et cohérence de la synthèse mensuelle ;
- individu #10 + inscription #503 : zéro résultat, sans repli global ;
- écriture adversariale sur une seule ligne de la base TEMPORAIRE
  synthétique : une consommation qui ne respecte plus l'IDindividu
  attendu est exclue de l'intersection (27 lignes valides) ;
- contrôle des paramètres SQL SQLite « ? » et MySQL « %s » sans
  interpolation d'ID dans les chaînes de requête ;
- suppression du filtre : retour aux 112 consommations fictives ;
- réinitialisation d'anciens filtres en une requête liste + une requête
  mois ; invalidité des IDs et de l'année refusée sans changer l'état ;
- précontrôle C3 toujours executable=False et aucune modification
  SQL lors d'un parcours normal de démonstration.

Graphique : deux parcours sont validés (clair 100 % et sombre 150 %),
avec chacun quatre captures : fiche Individu, consommations de
l'individu, consommations de l'inscription, puis vue globale rétablie.
Le dossier « qt-c11-parcours-exacts-fictifs » est archivé dans GitHub
Actions, artifact ID 12755261302 (147 699 octets, 8 PNG + 2 JSON,
rétention du workflow 14 jours). Les deux scénarios ont vérifié
l'identité du dump de la base SQLite fictive avant et après.

Les captures ne prouvent pas l'absence de scintillement sur le poste
utilisateur ; l'avis humain positif concernait le premier démonstrateur
Qt. La recette Windows C11 reste une validation automatisée hors écran.

## Traçabilité d'un échec intermédiaire

Les runs 40549096815 et 40549491102 ont échoué sur une assertion
historique C9 en supposant la ligne #10 première par ID dans une liste
triée sur le nom. La véritable première ligne était #12, ce qui
déclenchait le test. L'assertion corrigée teste les IDs de la ligne
réellement sélectionnée ET de l'inscription correspondante. Les runs
40549694485 et 40550244620 sont PASS. Aucun test n'a été supprimé.

## Conditions de publication et suite

Pas de saisie des consommations, de facturation, de contrôle effectif
des droits ou périodes, ni de calcul de montant métier nouveau.
Aucune base Noethys réelle, aucun import de sauvegarde personnelle,
aucune propagation main/wx et aucune publication de release.

STOP-GATE : cette interface est un démonstrateur ergonomique sur
données fictives. L'intégration définitive des parcours dans la coque
Qt produit et leur qualification sur une copie représentative et
sécurisée de la base restent à accomplir.

Prochain jalon possible : C12, faire converger l'expérience de
navigation du démonstrateur avec la coque Qt principale, conserver
la légèreté constatée et continuer les tests d'accessibilité et
de sécurité avant toute activation d'écriture.
