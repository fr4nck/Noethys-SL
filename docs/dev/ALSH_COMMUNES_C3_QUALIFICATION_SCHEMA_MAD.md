# ALSH-C3 — qualification du schéma sur une sauvegarde MAD (lecture seule)

**Date : 03/11/2026.** Source : sauvegarde `.nod` du 10/09/2026, archive `mad_data.sql`, examinée exclusivement sous l'angle du schéma ; aucune donnée nominative traitée dans le rapport et aucune modification sur MAD.

Le dump indique **MySQL 5.7.31-log**. Les tables suivantes sont présentes et utilisent **InnoDB** :

| Table | Champs attendus et vérifiés |
|---|---|
| `individus` | `IDindividu`, `adresse_auto`, `rue_resid`, `cp_resid`, `ville_resid` |
| `consommations` | `IDconso`, `IDindividu`, `IDactivite`, `IDgroupe`, `IDunite`, `date`, `etat`, `quantite` |
| `activites` | `IDactivite`, `nom` |
| `groupes` | `IDgroupe`, `IDactivite`, `nom` |
| `unites` | `IDunite`, `IDactivite`, `nom` |

`individus.IDindividu` est un `int(11)`. Les colonnes d'adresse sont `varchar` ; `consommations.date` est `varchar(10)`. C1-C3 utilisent des dates ISO au format `YYYY-MM-DD`.

Les déclencheurs de C2 **ne sont pas installés par cette analyse** ; le dump précède leur développement. L'adresse actuelle ne prouve pas la commune de résidence historique d'un enfant.

## Barrières restant ouvertes

1. Sauvegarder et isoler une **copie jetable** de la base, avec restauration vérifiée.
2. Tester les migrations C1/C2, les triggers MySQL 5.7, leurs permissions et leurs transactions (insert, update, rollback, concurrent, héritage `adresse_auto`).
3. Vérifier l'interface wx C3 et les droits `consulter` / `exporter` / `modifier` sur un poste réel.
4. Vérifier code INSEE, conventions signées, règles de journées-enfants et justificatifs des périodes de résidence.
5. Requalifier les situations financières et acomptes dans l'outil de facturation Noethys existant ; **aucune facture automatique**.

**Verdict : compatibilité structurelle confirmée par lecture du dump, pas de qualification d'exécution MySQL.**
