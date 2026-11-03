# Lot C — Deux fiches famille PMSL (03/11/2026)

## Références fournies

Les deux documents ne sont **pas interchangeables** :

1. `Fiche Famille(1).docx` : intitulé **ACCUEIL DE LOISIRS PÊLE-MÊLE — FICHE FAMILLE** ; site ALSH au choix **La Guerche, Moutiers ou Bais** ; deux pages A4. En page 1 : responsables légaux, régime CAF/MSA/autre et numéro d'allocataire ; en page 2 : **ENFANTS À INSCRIRE**, huit engagements et signature.
2. `Fiche Famille club ados.docx` : intitulé **Club ADOS PÊLE-MÊLE — FICHE FAMILLE**, site unique **BAIS** ; deux pages A4. Même structure commune, mais la première page comporte en plus une **case spécifique de consultation CAFPRO avec clause de renouvellement tacite**, et la seconde page porte **ADOS À INSCRIRE**.

Les enfants d'une fratrie ne sont pas automatiquement tous inscrits sur les deux fiches. Les formulaires individuels « Fiche Enfant » et « Fiche Ados » restent deux éditions séparées de ces fiches **famille**.

## Intégration Noethys-SL wx

Depuis le dossier famille, menu **Outils** :

- `Éditer la fiche famille ALSH (PDF)`
- `Éditer la fiche famille Club ados (PDF)`

Séquence de l'opérateur : choix des enfants à inscrire, choix du site pour l'ALSH (Bais fixé pour le Club ados), année scolaire proposée et modifiable, puis chemin du PDF. Les fichiers sont enregistrés **localement**, sans envoi automatique ni écriture SQL.

La fonction `UTILS_Accueil_familles.LireFamille` lit la famille, la caisse/régime, les représentants et les enfants depuis `familles`, `caisses`, `regimes`, `rattachements`, `individus`. Elle réutilise les adresses partagées `adresse_auto` et, pour chaque enfant sélectionnable, la scolarité à jour de `UTILS_Accueil_scolarite.LireScolariteActuelle`. Aucun contact simple n'est ajouté comme représentant légal.

La fonction `UTILS_Accueil_familles_impression.GenererPDF` imprime les deux documents sur des modèles distincts en noir et gris. Seuls les enfants **explicitement sélectionnés** sont inscrits. La case CAFPRO reste vide sur une nouvelle fiche à signer, même lorsqu'une valeur historique existe en base. La déclaration de consentement n'est pas créée automatiquement.

Les champs non garantis par le dossier existant (notamment la situation matrimoniale ou la qualité père/mère/tuteur lorsqu'elle n'est pas explicitement identifiée) ne sont pas inventés et restent à compléter manuellement sur le document.

Chaque modèle comporte **quatre lignes d'enfants**, comme le DOCX fourni. Si plus de quatre enfants sont sélectionnés, le logiciel demande une sélection plus réduite au lieu de tronquer une famille en silence.

## Qualification

Tests sur base fictive `tests/test_noethys_sl_accueil_familles.py` (lecture seule, classement représentants/enfants, caisse, adresses partagées, scolarité, choix distinct des enfants et famille inexistante) et
`tests/test_noethys_sl_accueil_familles_impression.py` (deux titres, sites, clause CAFPRO propre au Club ados, deux pages, refus d'entrées invalides, source non modifiée).
Tous deux ajoutés à la CI rapide Windows `wx`.

**État :** code candidat sur la branche `wx`, aucune release Windows ni migration PMSL. Le contrôle visuel final et la validation de la recette Windows sur le SHA gelé restent requis avant diffusion.
