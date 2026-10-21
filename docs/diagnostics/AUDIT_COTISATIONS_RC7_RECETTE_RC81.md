# Inventaire RC7 et recette pilote RC8.1 — 21 octobre 2026

## Résultat et périmètre

Outil renforcé d'inventaire des cotisations portant `[adhesion-auto]`, pour une **copie isolée uniquement**. Aucun DELETE, UPDATE, INSERT, avoir, facture ou régularisation n'est exécuté par cet outil. La version publiée RC8.1 du 19 octobre n'est pas modifiée : cet audit externe et son correctif source sont un complément de préparation à la recette.

L'inventaire porte sur les cotisations automatiques marquées, toutes dates de saisie confondues. Le marqueur ne prouve pas qu'une ligne a été créée sous RC7. Les cotisations manuelles ne sont pas sélectionnées ; une prestation liée à plusieurs cotisations, y compris manuelles, est toutefois signalée. Une prestation orpheline sans aucun lien depuis une cotisation marquée reste hors périmètre. Les écritures non marquées ne sont pas déclarées saines.

## Lacunes démontrées dans l'audit RC8.1 original

Référence : `0500ff0baf6e2a3f6a085fb8e1872b5b0b64591c`, même blob du service sur `main`, `wx`, `qt` et le tag RC8.1 : `5c17b328be8c1ab1c9f0ea9b33e810e10e8408f3`.

| Cas fictif reproduit | Audit original | Audit renforcé |
|---|---|---|
| Prestation inexistante, validité déjà commencée, début = saisie | 0 ligne, en raison du filtre de dates SQL | Ligne conservée, `prestation_introuvable` |
| Prestation présente sans date, validité future | Présentée comme introuvable | Présence séparée de `date_prestation_absente` |
| Date de fin `0000-00-00`, validité future | `ValueError`, interruption de l'inventaire | Ligne conservée avec `date_fin_invalide` |

L'audit original signale bien `IDfacture` et compte les ventilations. Ses deux tests dédiés ne testent pas de vraie ventilation. Son statut rassemble factures et ventilations ; il n'exporte ni leurs détails ni les montants et ne vérifie pas les pièces référencées. Le motif original `participation_future` infère une participation depuis une date de validité : le nouveau motif `validite_future` décrit uniquement ce qui est réellement observé.

## Ce que contient le rapport

- Cotisation, titulaire enregistré, famille, type/unité et dates brutes/validées.
- ID de prestation demandé et présence réelle distincts ; catégorie, payeur, dates comptable/de valeur et montant signé.
- Référence de facture distincte de l'existence de la pièce, numéro, date et état stocké. Un lien cassé reste bloquant pour une décision comptable.
- Nombre et détail des ventilations : ID, montant signé, règlement référencé et existence de celui-ci ; marque d'encaissement en attente stockée. Une somme nulle ne fait pas disparaître les ventilations.
- Quatre états : `facturee`, `ventilee`, `facturee_et_ventilee`, `sans_facture_ni_ventilation_identifiee`. « Facturée » désigne ici une référence `IDfacture`, pas une validation de l'émission ou de l'export comptable.
- Liens partagés et incohérences d'individu/famille/payeur signalés pour examen. Aucune règle de titulaire personne morale/personne physique n'est recalculée.
- Totaux de prestations dédupliqués par ID ; montant inconnu distinct de zéro. Les montants ne représentent ni une proposition de remboursement ni un montant de régularisation.

**Ne pas conclure « impayé » en l'absence de ventilation.** Un règlement non affecté peut exister sur le compte payeur. Le montant total d'un règlement n'est pas le montant affecté à la cotisation. Une ventilation, un règlement stocké ou une facture marquée réglée ne prouvent pas l'encaissement bancaire. Les participations effectives, annulations, adhésions utilisées, périodes verrouillées et cas de titulaire doivent être vérifiés dans la recette et par le responsable comptable.

## Préparer la copie et l'environnement

1. Utiliser une sauvegarde cohérente existante, restaurée dans un environnement de recette distinct. Conserver l'original et identifier la date/heure du point de sauvegarde. Ne jamais lancer les tests contre une base réseau réelle ou un profil Portable qui la désigne.
2. Séparer **copie A d'inventaire figée** et **copie B de recette GUI jetable**. La copie A n'est pas ouverte par l'application. La copie B peut recevoir les écritures explicitement provoquées par la recette ; elle n'est jamais reversée en production.
3. SQLite : fichier DATA cohérent, application arrêtée ; présence d'un WAL/journal => arrêt de l'outil, refaire une copie cohérente. Le lecteur utilise `mode=ro`, `query_only` et une liste d'opérations autorisées ; empreintes du fichier identiques avant/après exigées.
4. MySQL : copie **locale 127.0.0.1**, schéma nommé par exemple `pmsl_recette_rc81_DATA`, compte de lecture disposant seulement de SELECT sur cette copie. Ne pas utiliser un compte d'administration ni un tunnel vers la production. Le script ne crée pas le compte et ne restaure pas la base. Il exige les cinq tables en InnoDB et une transaction `READ ONLY / REPEATABLE READ / CONSISTENT SNAPSHOT`. Si les tables sont d'un autre moteur, **arrêter ; aucune conversion automatique**.
5. Python 3.10+ déjà disponible. SQLite n'exige aucun paquet. Pour MySQL, employer un environnement disposant déjà de `MySQLdb` ou `mysql.connector`. Aucun pilote n'est installé ni téléchargé par les scripts. Ne pas utiliser l'exécutable PyInstaller comme interpréteur Python.
6. Le script autonome n'importe ni GestionDB, ni wx, ni le profil Noethys. Ne pas appeler simplement le service historique depuis une console reliée au profil habituel : il peut ouvrir sa base par défaut. Les rapports contiennent des identifiants internes : conserver localement, accès restreint, pas de publication GitHub de données réelles.

## Exécuter l'inventaire sous Windows / PowerShell

Ces chemins sont des **exemples à adapter**, pas une affirmation sur le poste. Le dossier de sortie doit être nouveau et se trouver hors de la copie de base.

```powershell
# Windows 11 / PowerShell — dépôt de sources contenant ce lot d'audit
Set-Location 'C:\RecetteRC81\Noethys-SL'

# Cas SQLite, bibliothèque standard
py -3 .\tools\auditer_cotisations_rc7.py `
  --sqlite 'C:\RecetteRC81\CopieA\PMSL_DATA.dat' `
  --copie-confirmee --date-reference 2026-10-21 `
  --sortie 'C:\RecetteRC81\Rapports\Inventaire-20261021-A'

# OU : copie MySQL locale, avec un interpréteur dont le pilote est déjà installé
py -3 .\tools\auditer_cotisations_rc7.py `
  --mysql-base pmsl_recette_rc81_DATA --mysql-port 3306 `
  --mysql-utilisateur audit_rc81 `
  --copie-confirmee --date-reference 2026-10-21 `
  --sortie 'C:\RecetteRC81\Rapports\Inventaire-20261021-MySQL'
```

MySQL demande le mot de passe au clavier sans l'afficher ni l'écrire dans les rapports. Utiliser la date retenue pour la recette ; garder cette date fixe pour comparer deux rapports. Un refus, une erreur SQL ou une copie SQLite modifiée interrompt le traitement, code retour 2 ; ne jamais interpréter cet arrêt comme « 0 anomalie ». Le script ne fournit pas de commande de correction.

Fichiers produits : `inventaire.html` lisible hors ligne, `inventaire.json` détaillé, `inventaire.csv` à séparateur point-virgule, `validation_comptable.csv` à compléter manuellement, `SHA256SUMS.txt`. La fiche de validation laisse toutes les décisions vides ; elle n'est jamais réimportée par le programme. Seul le JSON conserve l'ensemble des dates brutes et détails de règlement.

## Vérifier sans aucune donnée PMSL

```powershell
# Windows / PowerShell — même dépôt, environnement Python existant
Set-Location 'C:\RecetteRC81\Noethys-SL'
py -3 -m unittest discover -s tests -p test_noethys_sl_audit_cotisations_rc7.py -v
py -3 .\tools\creer_exemple_audit_rc7.py 'C:\RecetteRC81\ExempleFictif'
py -3 .\tools\auditer_cotisations_rc7.py `
  --sqlite 'C:\RecetteRC81\ExempleFictif\FICTIF_recette_rc81_DATA.dat' `
  --copie-confirmee --date-reference 2026-10-21 `
  --sortie 'C:\RecetteRC81\Rapports\ExempleFictif'
```

Exemple attendu : **9 automatiques examinées, 8 signalées, 6 prestations distinctes signalées, 45,00 € de montants connus**. Une cotisation manuelle est exclue ; une automatique sans signal est examinée sans être affichée. Ces nombres sont exclusivement fictifs. La petite base de démonstration contient seulement les cinq tables d'audit : **elle ne permet pas d'ouvrir une recette complète Noethys**.

## Recette métier RC8.1 sur copie B uniquement

Contrôler la version affichée RC8.1 et la provenance des binaires ; ne pas réutiliser un profil de production. La référence publiée est `00f53db463d812e31f0eee7e56e0db00835b8162`, version interne de compatibilité `1.3.4.4`. Ne pas télécharger de binaire sans accord préalable. Pour un fichier déjà obtenu, vérifier son empreinte publiée : Setup `6eba424d93848516a2d04a79e532346a5bfe6d0251e43546c2704c4705b8ed22`, ZIP portable `c02add7f398ee6191a993047bf5bd8dc666a165d3a4850fb481a1e00eaa6673c`.

| Scénario sur copie B | Résultat à constater et consigner |
|---|---|
| Sauver seulement une réservation future | 0 cotisation et 0 prestation nouvelle |
| Génération de factures incluant cotisations, refus explicite de préparation | 0 création de cotisation/prestation |
| Première participation passée éligible conservée, accord explicite avant aperçu | Une cotisation, une prestation, toutes deux visibles avant émission ; validité depuis première participation et date comptable bornée |
| Rejouer la préparation, plusieurs activités / postes | Pas de doublon ; tout changement entre proposition et validation bloque ou exige nouveau contrôle |
| Toutes participations du mois annulées, puis participation le mois suivant | Aucun nouveau financement sur les séances annulées ; cas historique déjà créé examiné séparément sans suppression automatique |
| Prestation facturée, ventilée, ou les deux ; adhésion manuelle coexistante | Aucune régularisation par l'audit ; préservation des écritures et adhésions manuelles |
| Période verrouillée, titulaire structure/personne, chevauchement | Blocage/contrôle conforme, traçabilité des résultats et des éventuelles créations partielles |
| Après participation, facture demandée pendant le mois ; clôture d'un mois terminé | Date comptable = min(date de traitement, fin de période), aucune séance future incluse |

**Attention : accepter la préparation crée les cotisations et prestations AVANT l'aperçu. Annuler ensuite l'assistant ne constitue pas une preuve de rollback de ces créations.** Relever les IDs et compter les lignes après chaque cas ; restaurer la copie B depuis son point initial pour les scénarios indépendants. Désactiver les canaux d'envoi et exports de production dans le profil de recette ; ne pas émettre de document officiel. La clôture est ce parcours explicite, pas un planificateur mensuel autonome.

## Qualification obtenue et limites

- 21/10/2026, conteneur Linux : **31 tests ciblés PASS, 0 FAIL, 0 SKIP**. SQLite réel, tables tirées de `DATA_Tables.DB_DATA`. Sous-cas facture/ventilation, dates, schéma erroné, somme nulle, compteurs dédupliqués, export, blocage des écritures et empreintes identiques couverts.
- API historique : corps réel testé isolément, avec connexion simulée pour vérifier arrêt sur erreur SQL et fermeture. Ce contrôle ne qualifie pas le runtime wx ni le routage de connexion d'un poste réel.
- Aucune base PMSL accessible, aucune opération de production, aucun pilote téléchargé. Pilote MySQL absent du conteneur : **nouveau parcours MySQL non exécuté sur serveur réel**. Les 11 tests MySQL annoncés pour la release ne qualifient pas ce nouvel audit.
- Les 465 tests Windows et 11 tests MySQL publiés le 19/10 sont des preuves antérieures de RC8.1, pas des tests rejoués dans ce lot. La suite complète wx, l'UI et la recette comptable restent à exécuter localement. Aucun nouveau binaire ni tag n'est produit ici.

## Sources et état terrain au 21/10/2026

- [Ticket #426](https://github.com/fr4nck/Noethys-SL/issues/426), ouvert, dernière mise à jour récupérée : 19/10/2026 14:19:05 UTC ; un commentaire, [bilan du 19/10](https://github.com/fr4nck/Noethys-SL/issues/426#issuecomment-6269435918).
- [Release RC8.1](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.8.1), publiée le 19/10/2026 14:16:19 UTC ; préversion de recette. Pas de release plus récente parmi les dix dernières retournées.
- [Commit d'audit original](https://github.com/fr4nck/Noethys-SL/commit/0500ff0baf6e2a3f6a085fb8e1872b5b0b64591c) et [passation wx au dernier SHA récupéré](https://github.com/fr4nck/Noethys-SL/blob/f48cf15c01ac3d9f1c962f819d7776d067da0aa7/docs/dev/REPRISE_CODEX.md).
- Branches initiales : main `0500ff0baf6e2a3f6a085fb8e1872b5b0b64591c`, wx `f48cf15c01ac3d9f1c962f819d7776d067da0aa7`, qt `7e9745ad3fb4f3b65ae8dd0eb48fb8ea51a70e91`. Recherche des issues mises à jour depuis le 19/10, dont recherche « recette » : aucune attestation terrain plus récente trouvée. Recherche documentaire disponible « RC8.1 », puis « Noethys recette » : aucun document retrouvé ; cette recherche vide n'est pas une preuve d'absence.

**Conclusion bornée : aucune nouvelle attestation de recette PMSL ou de déploiement n'a été trouvée dans les sources consultées. Cela ne prouve pas que ces opérations n'ont pas eu lieu.** Pour poursuivre sur les cas réels, il faut une copie cohérente locale identifiée ; pour régulariser, une décision comptable nominative et tracée reste indispensable. Le présent lot ne fournit aucun droit ni mécanisme de régularisation automatique.
