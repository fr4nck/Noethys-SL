# Noethys SL Qt — C9, première navigation métier

Date : 27 octobre 2026. Développement limité à la branche qt.

## Motif

Retour utilisateur réel C8 : pas de scintillement perceptible et moteur visuel plus homogène, mais parcours trop éloignés de Noethys. La priorité C9 est de rendre accessibles les repères familiers sans reproduire l'ensemble des dialogues wx.

## Réalisation

Le démonstrateur Windows C8 peut afficher un onglet de navigation regroupant quatre domaines : Familles, Individus, Activités et Inscriptions. Les listes sont non éditables, avec double clic guidant Familles → Individus → Inscriptions → Consommations. L'onglet Consommations conserve le calendrier et le panneau de précontrôle bloqué C3.

Les données sont lues sur la fixture C8 temporaire et contrôlées par son marqueur de source, en SQLite mode=ro et PRAGMA query_only. Aucune source configurée de Noethys n'est lue. Les catégories de rattachement présentes dans la fixture sont des constantes de démonstration, **non un référentiel de catégories familiales métier**. Aucun comportement de titularisation, tarification ou facturation n'est extrapolé.

La classe C8DemoWindow reste compatible lorsqu'aucune fixture de démonstration n'est fournie, pour préserver les anciens bancs C8.

## Tests et limites

Nouveaux tests C9 : liste des domaines, non-édition, navigation par double clic, compatibilité C8 et dump SQLite avant/après. Le test réel Windows graphique doit être distingué du rendu CI hors écran.

**STOP-GATE** : aucune écriture de consommations ou d'inscriptions, aucun portage autorisé du calcul de prestations, aucun installateur de production. Le démonstrateur sert seulement de référence ergonomique. Une navigation réelle entre fiches de familles/personnes restera à définir avec leurs droits et leurs relations métier.

## Matrice

- main : f6f5ccd — NON APPLICABLE ; inchangée.
- wx : 11b8546 — NON APPLICABLE ; inchangée.
- qt base : 5ff530d ; commit C9 : 205277f ; CI Windows 40538527990 SUCCESS : 234 tests, 0 échec (qualification C9 d'époque). Run : https://github.com/fr4nck/Noethys-SL/actions/runs/40538527990
