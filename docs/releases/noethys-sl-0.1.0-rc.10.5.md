# Noethys SL 0.1.0 RC10.5 — candidat cumulatif (non publie)

Statut : **candidat de consolidation sur `wx`**. Ce fichier sert de liste
de contenu pour la prochaine preversion. Il ne certifie ni une installation
Windows deja diffusee, ni la resolution des incidents de production.

## Correctifs retenus

- **#438 — fermeture Connecthys** : liberation explicite du canal SFTP et
  de la session `paramiko.SSHClient` sur les chemins normaux et en erreur.
  Les attentes de 1 et 30 secondes du worker Connecthys sont interruptibles.
  La fermeture acceptee arrete le worker ; une sauvegarde annulee ne le stoppe
  pas et conserve la fenetre ouverte.
- **#437 — sauvegardes MySQL** : conservation de l'export `mysqldump` surveille
  (sans `shell=True`, delais bornes et diagnostic), de la verification SQL et
  de la protection des anciennes archives. Le blocage `*_DOCUMENTS` de
  production et la validation d'une sauvegarde PMSL restaurable restent ouverts.
- **#426 — facturation** : controle explicite des erreurs de verification
  des cotisations avant calcul, sans facturer silencieusement une cotisation
  absente. La recette des donnees reelles demeure indispensable.
- **#436 — fiche enfant** : conservation des formulaires, du filtrage des
  donnees sensibles selon habilitations et du registre des autorisations.
- **Situation ALSH des communes** : conservation du choix explicite des
  absences injustifiees, separees des presences et des participations,
  sans activation implicite.

D'autres correctifs pourront rejoindre cette RC10.5 avant gel du SHA.
Les travaux non qualifies sur `wx` ne sont pas annonces comme correctifs
valides par la presente note.

## Barriere Windows avant publication

1. CI rapide Windows `wx` PASS sur le SHA exact retenu, y compris fermeture
   Connecthys, controle des autorisations et garde-reseau.
2. Construction `noethys-sl-rc105-windows.yml` avec `publier=false` :
   identité 0.1.0 RC10.5, verifications du binaire, de son demarrage,
   du profil portable, des clients MySQL 5.7 et des empreintes SHA-256.
3. Recette MySQL 5.7 **jetable** avec gros BLOB, sauvegarde et restauration.
   Elle ne vaut pas preuve de sauvegarde complete de la base PMSL.
4. Sur un poste Windows de recette, fermer Noethys apres une session
   Connecthys et prouver la disparition du PID et des connexions SSH.
   Qualifier le comportement en cas de synchronisation en cours.
5. Accord explicite de publication depuis `wx` seulement, apres les
   barrieres precedentes ; aucun `push` ne publie une release.

## Compatibilite et limites

- Version publique : `0.1.0-rc.10.5` ; version interne Noethys :
  **`1.3.4.4` inchangee**, sans migration SQL.
- Identifiant d'installation Inno Setup conserve pour les mises a jour
  existantes. Ne pas effacer le profil de production.
- La RC10.4 deja installee ne recoit **aucune** correction retroactive.
- Les tickets [#437](https://github.com/fr4nck/Noethys-SL/issues/437)
  et [#438](https://github.com/fr4nck/Noethys-SL/issues/438)
  restent ouverts jusqu'a validation terrain.
