# UI-432K — banc de rendu PDF en processus isole (09/11/2026)

## Objectif
Qualifer le rendu d'une facture unique sans bloquer la GUI, **sans** faire
tourner ReportLab, Noedoc, wx.MemoryDC ou leurs variables globales dans un
thread de l'application principale.

## Candidat experimental
- `UTILS_PDF_processus.Generer` lance un nouveau processus Windows avec
  `multiprocessing.spawn`. Il cree sa propre `wx.App` et sa connexion
  SQLite explicite, interdit les boites de dialogue interactives invisibles,
  puis signale succes ou type d'erreur par un Pipe prive.
- La GUI demarre ce rendu via `UTILS_Etapes_ui.TravailFond`, dont la boucle
  modale reste active. Les `wx.Colour` des options sont convertis en tuples
  **avant** de transmettre les donnees au worker.
- `UTILS_PDF_securise.Generer` publie atomiquement le document final
  uniquement si le processus reussit et que le PDF a un marqueur de fin.
- Source obligatoire : fichier SQLite explicite existant, jamais le
  dernier dossier utilisateur ni une base reelle en tests. Aucun chemin de
  base ou identite n'est inscrit dans les journaux.
- Ce mode est **INACTIF par defaut**, accessible pour recette isolee avec
  `NOETHYS_SL_PDF_PROCESSUS=1`. Aucun basculement automatique ni repli
  silencieux vers la production ne doit etre ajoute avant preuve runtime.

## Qualification necessaire
1. Comparer les PDF historiques et isoles sur la fixture SQLite canonique,
   dont une facture avec prestation liee a une activite et une autre sans
   activite. Cas enrichi avec `bloc_texte` qui active `wx.MemoryDC`.
2. Verifier nombre de pages, validite PDF, absence de fichiers partiels et
   equivalence fonctionnelle des montants, champs de fusion et mise en page.
3. Tester la reactivite MainFrame (HWND) pendant 8 s de rendu unitaire force
   dans le processus. Aucun popup enfant, double envoi, ni callback wx hors
   thread principal.
4. Qualifier l'installeur PyInstaller Windows (freeze_support, ressources,
   polices, source SQLite, puis MySQL separement) **avant** activation par
   defaut ou publication RC.

## Limites
- Les autres exportations et le rendu global ne sont pas modifies.
- Aucun traitement MySQL distant, aucune photo PHOTOS ou modele complexe
  n'est qualifie par le seul test initial.
- Le mode par defaut reste synchrone tant que la recette Windows installee
  et l'equivalence documentaire ne sont pas etablies.
- La branche `qt` et la branche `main` restent hors de ce lot wx.

**Statut initial : candidat / CI ciblee a obtenir ; issue #432 ouverte.**
