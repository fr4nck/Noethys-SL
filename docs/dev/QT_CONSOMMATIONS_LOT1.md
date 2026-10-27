# Noethys SL Qt — Consommations, lot C1 (27/10/2026)

## Périmètre

- Écran Qt natif de consultation, intégré à la navigation ; aucun import wx.
- Filtres par clic indépendants pour les six états historiques, disponibles même sans donnée dans la période : réservation, attente, refus, présent, absence justifiée, absence injustifiée.
- Septième case « Autres / non renseignés », couvrant un code inconnu, la chaîne vide et NULL. Tout est coché au départ ; zéro case cochée donne zéro ligne, sans SQL.
- Année courante modifiable, recherche nom/prénom/activité/unité/groupe/ID ; SQL paramétré, pagination de sécurité par limite 300 + 1, sans COUNT global. Résultats triés par date et ID décroissants.
- Montants de prestations affichés individuellement, arrondis à deux décimales uniquement **à l'affichage** ; aucune somme, aucun calcul de facturation, aucune modification d'état. Une prestation peut être liée à plusieurs consommations.
- Accès SQL transitoire du pont \`NativeActivityEditorRepository\`. Mode \`--sqlite\` pour recette ; accès à une base configurée soumis à la garde existante \`NOETHYS_QT_BASE_CONFIGUREE=1\`. Sous SQLite, \`PRAGMA query_only=ON\` est appliqué à chaque connexion de consultation.
- Chargement hors thread graphique, connexion propre à l'exécution, requête la plus récente prioritaire. Aucun changement de schéma, migration, fichier de configuration ou donnée réelle.

## Qualification et limites

- Tests sur SQLite **entièrement fictif** : six états canoniques, autres/NULL/vides, année, recherche paramétrée, limite et affichage, refus des paramètres invalides, non-écriture, contrôles graphiques hors écran.
- Vérification statique ou locale non équivalente à la CI Windows PySide6 ; le verdict final doit porter sur le SHA effectivement poussé.
- Pas de total comptable, pas d'état de consommation à modifier, pas d'impression ou d'export, pas de liste exhaustive « toutes années », ni de qualification MySQL en lecture seule côté serveur.
- L'utilisation sur copie de recette, le contrôle visuel/DPI Windows et la parité avec les droits/paramètres historiques restent à qualifier avant toute diffusion.
- La ligne \`main\` et la ligne \`wx\` restent inchangées : lot exclusivement interface Qt, sans fusion des branches divergentes.

## Sources métier

- \`noethys/Ol/OL_Liste_consommations.py\` : jointures et six codes d'état.
- \`noethys_qt/activity_editor.py\` : pont d'accès base configurée/SQLite déjà gardé.
- \`AGENTS.md\` : trois branches, non-régression et STOP-GATE de publication.
