# RC8 — préparation des commandes de repas et validation préalable

**État : développement en cours sur `main`, non livré, pas de RC8.**

## Paramétrage

Dans les modèles de commandes de repas, chaque colonne « Numérique (avec suggestion) » peut recevoir un **rôle métier explicite** : enfants de moins de 6 ans, enfants de 6 ans et plus, repas des animateurs, repas de direction, autres adultes ou « dont sans porc ». L'absence de classification préserve les anciens modèles.

Renseigner le **site** et le **service** pour chaque colonne typée. Pour « sans porc », renseigner l'ID d'une question **individuelle** de questionnaire et l'ID exact du choix correspondant, ou choisir `1` pour une case à cocher « sans porc ». Ne pas inférer une préférence du nom, de notes médicales ou d'un libellé en texte libre.

Les réponses individuelles peuvent être saisies dans le questionnaire d'un individu : le moteur reconnaît les types `liste_deroulante`, `liste_coches` et `case_coche`. Les réponses non renseignées sont distinguées en interne. La base Noethys ne conserve **pas l'historique daté** des réponses individuelles ; sur une commande passée, le calcul automatique reflète le dernier choix actuellement enregistré et non un historique reconstitué.

## Calcul

- Pour les colonnes enfants, les âges sont calculés à la date de chaque consommation. Les consommations d'un même enfant sont dédupliquées dans la colonne ; un âge inconnu empêche une suggestion automatique fiable.
- Pour « dont sans porc », seules les consommations `reservation` et `present` des unités/groupe sélectionnés sont étudiées ; le résultat est un sous-ensemble, **jamais un supplément au total**. Une erreur de correspondance question/choix n'est pas traitée silencieusement.
- Les repas des animateurs, de la direction et des autres adultes peuvent être renseignés explicitement. Le nombre d'animateurs *nécessaires* pour l'encadrement **ne devient jamais automatiquement un nombre de repas**.
- Repas adultes = repas animateurs + repas direction + autres repas adultes.
- Repas « 6 ans et plus » destinés au restaurateur = enfants de 6 ans et plus + tous les repas adultes.
- Total général = enfants de moins de 6 ans + repas « 6 ans et plus ».
- Une correction d'une quantité ne s'applique aux cellules de la commande qu'après acceptation explicite de la fenêtre de contrôle.

## Contrôle avant PDF / email

Les boutons « Imprimer » et « Envoyer par Email » ouvrent désormais la fenêtre **Vérification des effectifs et des repas** pour les modèles avec rôles de colonnes renseignés. Le tableau affiche par date/site/service les six sous-totaux modifiables et les trois totaux recalculés. Annuler laisse la commande inchangée et empêche l'émission. En acceptant, les valeurs sont appliquées aux cellules actuelles ; le PDF et le Mailer reçoivent donc les mêmes valeurs.

Pour les anciens modèles sans rôles ou une configuration incompatible, un avertissement demande si l'utilisateur souhaite poursuivre avec les anciennes valeurs **sans prévalidation RC8** ; cette exception de compatibilité n'est pas une qualification.

**Aucun email automatique n'est lancé** par cette étape : l'action « Envoyer par Email » continue d'ouvrir le mailer existant après validation, sans modifier son choix d'envoi.

## Risques et recette avant publication

- Recette sur base fictive et poste Windows : questions à choix multiples, questionnaire individuel, enfants d'âge inconnu, réservations en doublon, absences, anciens modèles, correction manuelle, PDF, brouillon d'email.
- Le contrôle ne déduplique pas les repas de direction **entre deux commandes distinctes**. Une direction multisite doit être affectée manuellement à un seul site/commande jusqu'à résolution de cette limite.
- L'affichage peut comporter des colonnes numériques non classées : l'avertissement visible n'est pas une preuve de comptage complet. Les nouveaux modèles PMSL doivent typer leurs colonnes avant la recette.
- Plusieurs services ou sites figurant dans une même commande doivent être affectés précisément. **Le choix de l'ID de question et d'option est encore technique** ; une liste de sélection plus ergonomique reste souhaitable.
- Les préférences modifiées pendant une période n'ont aucun historique permettant de recalculer une commande ancienne. Ne pas prétendre résoudre ce point sans un nouveau contrat de stockage et une décision de migration.
- Toute émission reste à tester en conditions représentatives, en conservant les verrous de publication RC8. Aucun lien avec la facturation et aucune migration SQL dans ce lot.

Voir `docs/dev/REPRISE_CODEX.md` et les tickets #429 / #430.
