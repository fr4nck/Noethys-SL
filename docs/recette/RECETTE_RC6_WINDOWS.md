# Recette manuelle — Noethys SL 0.1.0 RC6 (Windows, wxPython)

Candidat de recette, **non publié**. Aucune release tant que cette recette n'est pas signée.
Les artefacts RC4 et RC5 restent inchangés (ne pas les écraser).

## Prérequis de sécurité — à cocher avant toute action

- [ ] Poste ou VM de recette **Windows propre** (pas le poste de production, pas le bureau d'un utilisateur actif).
- [ ] Base : **copie Docker MySQL 5.7** isolée (par exemple `noethys-mysql57` sur `127.0.0.1:3307`), jamais le serveur de production ni un profil `Portable/` qui le désigne.
- [ ] **Messagerie redirigée vers un serveur SMTP de capture** avant tout envoi (par exemple Mailpit : `docker run --rm -p 127.0.0.1:1025:1025 -p 127.0.0.1:8025:8025 axllent/mailpit`, puis dans Noethys : Paramétrage > Adresses d'expédition, SMTP `127.0.0.1`, port `1025`, sans TLS ni authentification). La copie contient de vraies adresses de familles : **aucun envoi sans capture vérifiée**.
- [ ] Empreintes SHA-256 des artefacts contrôlées contre `SHA256SUMS.txt` du run CI.

## A. Installation et profil

1. **ZIP portable** : extraire dans un dossier contenant espaces et accents (ex. `C:\Recette Noethys\Élan RC6`). Vérifier que `Portable\README.txt` et `mysql-client\bin\mysqldump.exe` existent.
2. Lancer `Noethys.exe` : titre « Noethys SL 0.1.0 RC6 ». Fermer.
3. Vérifier que la configuration est dans `Portable\` (`Config.json`, `Temp\`) et que `%APPDATA%\noethys` **n'a pas été créé**.
4. **Setup** : installer, lancer, fermer. Vérifier `C:\Program Files\...\mysql-client\bin\` et la configuration dans `%APPDATA%\noethys`. Réinstaller par-dessus : la configuration est conservée.

## B. Parcours métier sur la copie Docker

Ouvrir le fichier réseau de la copie (`127.0.0.1:3307`), puis :

| # | Action | Résultat attendu | OK |
|---|---|---|---|
| 1 | Créer une famille fictive « RECETTE RC6 » avec une adresse `recette@example.org` | Fiche enregistrée | |
| 2 | Inscrire un enfant à une activité | Inscription visible | |
| 3 | Saisir des consommations sur la grille | Consommations enregistrées | |
| 4 | Saisir un règlement | Règlement et ventilation corrects | |
| 5 | Éditer une facture | PDF correct | |
| 6 | Éditer le reçu, bouton « Envoyer par Email » | Message visible dans Mailpit, PDF joint ; historique Email renseigné | |
| 7 | Couper Mailpit, renvoyer le reçu | Erreur affichée ; **aucun** historique « envoyé », aucun reçu mémorisé comme envoyé | |
| 8 | Fermer Noethys, relancer, rouvrir le fichier | Famille, inscription, consommations, règlement, facture et reçu toujours présents | |

## C. Sauvegarde et restauration réseau (lot A)

1. Menu Fichier > Créer une sauvegarde : fichier réseau de la copie, destination locale. Attendu : aucun dialogue demandant un répertoire MySQL ; `.nod` créé ; il contient `<base>.sql` débutant par `-- NOETHYS-SQL-MANIFEST-V1`.
2. Avec un utilisateur MySQL dont le mot de passe contient `#` et un accent : la sauvegarde aboutit.
3. Avec un mot de passe erroné : message d'erreur explicite (`1045`), **aucun** `.nod` produit.
4. Modifier une donnée fictive, puis restaurer le `.nod` **sur la copie Docker uniquement** (la base de la copie est remplacée) : données identiques à l'étape 1.
5. Restaurer, sur une copie Docker jetable, un `.nod` produit par une version antérieure (RC4/RC5 ou Noethys historique) : restauration acceptée, ou refus explicite sans aucune modification si l'ancien dump est incomplet.
6. Après chaque opération : aucun fichier `logintemp.cnf` dans `Portable\Temp` (ou `%APPDATA%\noethys\Temp`).

## Résultat

| Bloc | Résultat | Testeur, date |
|---|---|---|
| A. Installation et profil | | |
| B. Parcours métier | | |
| C. Sauvegarde et restauration | | |

Décision : ☐ RC6 acceptée pour prérelease ☐ refusée (anomalies à reporter avec étapes de reproduction).
