# Incident du 14/10/2026 — identifiants MySQL de production versionnés

## Constat

- `noethys/Portable/Config.json` et sa copie identique `Config.json.bak` ont été
  ajoutés au suivi Git par le commit `67ca93a4` (13/10/2026 21:49 +0200,
  « test: renforcer tests de régression et adapter workflow pour RC5 »).
- La clé `nomFichier` (et `derniersFichiers`) contient la chaîne de connexion
  réseau `hôte;port;utilisateur;mot de passe[RESEAU]base` de la base MySQL de
  production. Le contenu n'est reproduit dans aucun document, journal ni PR.
- Le dépôt `fr4nck/Noethys-SL` est **public** : les identifiants doivent être
  tenus pour **compromis** depuis le premier push de `67ca93a4`.
- Ils restent lisibles :
  - dans l'historique de `wx` (commit `67ca93a4` et suivants jusqu'au retrait) ;
  - dans le tag `noethys-sl-0.1.0-rc.7` (commit `e8488e71`) et les archives
    « Source code » (zip/tar.gz) de la release RC7, générées depuis ce tag ;
  - dans les refs `refs/pull/*/head` de toute PR ouverte depuis une branche
    contenant ces commits, et dans les caches/clones/forks éventuels.
- Les branches `main` et `qt` et les tags antérieurs à RC7 ne contiennent pas
  ces fichiers. Le nom d'utilisateur et le mot de passe n'apparaissent dans
  aucun autre fichier suivi.
- Les exécutables RC7 (Setup et ZIP portable) ne sont pas fabriqués à partir de
  `noethys/Portable/` : la spec PyInstaller n'embarque que `Static/` et quelques
  fichiers, et le workflow crée un dossier `Portable/` ne contenant que
  `packaging/portable/README.txt`. Une vérification du contenu des binaires
  publiés reste recommandée (voir ci-dessous).

## Corrigé dans la PR

- `Config.json` et `Config.json.bak` retirés de l'index (`git rm --cached`) ;
  les copies locales des postes sont conservées.
- `.gitignore` : `**/Portable/Config.json` et `**/Portable/Config.json.*`.
- Garde de non-régression `tests/test_noe_config_portable_non_versionnee.py`
  (lit uniquement l'index Git), ajoutée à la CI rapide.

## Données de recette

`noethys/Portable/Data/Recette_{DATA,DOCUMENTS,PHOTOS}.dat` ont été contrôlés
(lecture seule SQLite + recherche brute dans les pages libres) : contenu
conforme à `tests/recette_creer_fichier_fictif.py` (famille « FICTIF »,
« CLUB FICTIF », « Association de recette », administrateur « RECETTE Admin »),
référentiels par défaut. Aucun courriel, numéro de téléphone, IBAN, NIR, ni
fragment des identifiants MySQL. Ils restent suivis.

## Actions restant à mener (humaines, hors PR)

Par ordre de priorité.

1. **Changer le mot de passe du compte MySQL concerné** (et, si possible, le nom
   du compte), puis mettre à jour la configuration des postes légitimes.
   C'est la seule mesure qui neutralise la fuite : la réécriture de
   l'historique ne retire pas ce qui a déjà été copié.
2. **Restreindre l'exposition du serveur MySQL** : vérifier qu'il n'écoute pas
   sur Internet (pare-feu, `bind-address`), limiter le compte aux hôtes
   légitimes (`'utilisateur'@'réseau local'`) et à ses seuls privilèges.
3. **Rechercher une utilisation frauduleuse** depuis le 13/10/2026 : journaux
   de connexion MySQL / pare-feu, table `historique` de Noethys, comptes
   inconnus. En cas d'accès non autorisé à des données personnelles :
   évaluer la notification CNIL (72 h, art. 33 RGPD).
4. **Purger l'historique Git** (exige un force-push, non effectué ici) :
   - `git filter-repo --invert-paths --path noethys/Portable/Config.json --path noethys/Portable/Config.json.bak`
     sur un clone miroir, puis force-push de `wx` et de toutes les branches
     concernées, information des détenteurs de clones (re-clone obligatoire) ;
   - les commits réécrits changent d'empreinte : les références de commit
     citées dans la documentation et les releases deviendront caduques.
5. **Tag et release RC7** (suppression non effectuée ici) : le tag
   `noethys-sl-0.1.0-rc.7` pointe un commit contenant les identifiants, et la
   release publie les archives sources correspondantes. Options :
   - supprimer la release RC7 et le tag, puis republier un RC (RC7.1/RC8) depuis
     un commit purgé, en ré-attachant des exécutables reconstruits ;
   - ou, à défaut, passer la release en brouillon. Les exécutables RC7 eux-mêmes
     peuvent rester inchangés s'ils sont vérifiés sains (point 6).
6. **Vérifier les exécutables RC7 publiés** sur un poste disposant de l'archive :
   l'archive ZIP portable et le Setup ne doivent contenir aucun `Config.json`
   (l'attendu est `Portable/README.txt` seul).
7. **Après purge**, demander à GitHub Support la suppression des vues en cache
   et des refs `refs/pull/*` qui référencent encore les anciens commits
   (procédure « Removing sensitive data from a repository »).
8. Activer **Secret scanning** et **Push protection** sur le dépôt.

## Bonnes pratiques

Un profil `Portable/` de poste réel ne doit jamais être commité : n'utiliser
pour la recette que le profil fictif produit par
`tests/recette_creer_fichier_fictif.py`, et contrôler `git status` avant tout
`git add -A`.
