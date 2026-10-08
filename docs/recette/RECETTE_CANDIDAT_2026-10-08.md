# Recette du candidat local du 08/10/2026 — Franck et le comptable

Artefact : `Noethys-SL-0.1.0-rc.2+<commit>-local-Windows-portable.zip` (version portable Windows construite localement, non publiée). Le titre de la fenêtre affiche encore « Noethys SL 0.1.0 RC2 » ; le commit exact figure dans `Noethys\BUILD-INFO.txt`.

## Règle absolue

**Ne jamais ouvrir la base de production avec ce candidat.** Il crée des adhésions et des prestations automatiquement. La recette se fait sur le fichier fictif « Recette » (ou sur une copie restaurée hors production).

## Préparation (Franck, 10 minutes)

1. Extraire l'archive dans un dossier dédié, par exemple `C:\Candidat-NoethysSL\` (jamais dans `C:\Noethys`).
2. Depuis le dépôt Noethys-SL, créer le fichier fictif et le profil de test à côté de l'exécutable :
   `python tests\recette_creer_fichier_fictif.py . C:\Candidat-NoethysSL\Noethys\Portable`
3. Vérifier que `C:\Candidat-NoethysSL\Noethys\Portable\Config.json` désigne `Recette` (aucun fichier réseau).
4. Lancer `C:\Candidat-NoethysSL\Noethys\Noethys.exe`. Code d'identification : `recette2026`.
5. Le titre doit afficher `[Recette]`. S'il affiche un autre fichier : fermer immédiatement.

## Parcours à valider

| # | Parcours | Attendu |
|---|---|---|
| 1 | Paramétrage > Comptabilité > Modes de règlements | La liste s'ouvre avec les vignettes. « Ajouter » ouvre la saisie ; après Ok, le nouveau mode apparaît dans la liste. |
| 2 | Paramétrage > Comptabilité > Emetteurs de règlements | Idem pour un émetteur rattaché au mode choisi. |
| 3 | **Comptable** — Fiche famille FICTIF > Règlements > Saisir un règlement > petits boutons à droite de **Mode** puis d'**Émetteur** | Chaque bouton ouvre la fenêtre de paramétrage (plus d'absence de réaction) ; un mode ou un émetteur ajouté est proposé dans la liste au retour. |
| 4 | Fiche famille FICTIF > Consommations : réserver Arthur le 14/10/2026, valider ; puis réserver Arthur le 07/10/2026, valider | Une seule adhésion « Adhésion annuelle - 2026-2027 » (7,50 €). À la seconde validation, la fenêtre « Adhésions à vérifier » indique Arthur, la période du 07/10/2026 au 07/10/2027 et le chevauchement. |
| 5 | Fiche famille CLUB FICTIF > Consommations : réserver la section A puis la section B | Une seule adhésion, au nom de « CLUB FICTIF », une seule prestation. |
| 6 | Fiche famille FICTIF : Lina participe aussi | Arthur et Lina ont chacun leur adhésion ; aucune adhésion au nom de la mère ni de la famille. |
| 7 | Fiche famille FICTIF > Générer un devis > Aperçu (un règlement de 50 € n'est pas ventilé) | Le devis s'ouvre et le PDF s'affiche, sans exiger de ventilation. |
| 8 | Paramétrage > Modèles de documents > Convention : ouvrir un modèle d'exemple dans Noedoc | Le texte « Corps » est dans le cadre, en haut, sans déborder sous la page ; la suite éventuelle est signalée. Fermer sans enregistrer, puis rouvrir : rien n'a bougé. |
| 9 | Générer une convention > sortie Word avec un modèle personnel | Un mot-clé inconnu est refusé avec sa liste ; aucun fichier partiel n'est laissé. |
| 10 | Changer la mise à l'échelle Windows (125 %, 150 %) et rouvrir Noedoc et la saisie d'un règlement | Lisibilité et mise en page correctes (non vérifié automatiquement). |

## Points connus

- À la fermeture, après le « Rappel de sauvegarde », le processus peut se terminer par une erreur Windows (code 0xC0000005). Le même comportement existe dans la RC2.1 publiée ; il ne concerne pas les données (fermeture déjà effectuée). À noter si une fenêtre d'erreur apparaît.
- L'installateur Setup n'a pas été construit localement (Inno Setup absent du poste) : seule la version portable est disponible.

## Retour attendu

Pour chaque ligne : conforme / non conforme, capture en cas d'écart, poste et date. Aucune correction de données réelles ne doit être faite à partir de ce candidat.
