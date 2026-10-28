# OCR-02 — adaptateurs français locaux sur CPU

Statut : **code de développement sur `main`**, sans activation dans wx/Qt et
sans application des résultats aux données métier. OCR-01 (`9c9812b`, `647483e`)
reste le contrat de sortie : propositions à relire, `write_allowed=False`.

## Périmètre

`noethys/Utils/UTILS_OCR_local.py` fournit deux adaptateurs facultatifs :

| Adaptateur | Entrée | Sortie | Dépendances locales explicites |
|---|---|---|---|
| `TesseractFrenchCPU` | Une image de page imprimée française | Un champ par mot, boîte normalisée, confiance TSV / 100 ou inconnue | Pillow, exécutable Tesseract **5 CPU sans OpenCL**, `fra.traineddata` |
| `TrOCRFrenchCPU` | Une **ligne manuscrite française** découpée par l'appelant | Une proposition de texte, boîte du découpage, confiance inconnue | Pillow, PyTorch CPU, Transformers et snapshot TrOCR français |

Un modèle TrOCR anglophone standard n'est pas qualifié pour le français. Aucun
modèle français précis ni sa licence n'est encore qualifié par ce lot. L'opérateur
doit choisir et provisionner un modèle adapté, conserver sa révision et sa licence,
puis qualifier ses résultats sur des exemples fictifs représentatifs.

Candidat concret à cette recette, **sans téléchargement ni validation dans ce
lot** : [`dj0w/trocr-french-handwriting-v5`, révision
`6047032cbe5f3c7f17244a4c3dd21d9356f15480`](https://huggingface.co/dj0w/trocr-french-handwriting-v5/tree/6047032cbe5f3c7f17244a4c3dd21d9356f15480).
La fiche de l'auteur le déclare adapté aux lignes françaises, entraîné sur RIMES
et sous licence MIT ; le dépôt propose `model.safetensors`. Cette provenance
documentaire ne démontre ni sa précision ni son fonctionnement sur les postes
i5-10400. Si retenu, exporter uniquement poids et fichiers d'inférence, conserver
la fiche/licence et exclure `training_args.bin`, inutile à l'inférence. Ne pas
reprendre les exemples de chargement Hub de sa fiche dans l'application.

Pas de détection automatique des lignes manuscrites, de routage imprimé/manuscrit,
d'interprétation des cases, d'extraction de champs métier, de PDF multipage ou de
rasterisation implicite. Le résultat vide reste vide. Les erreurs de moteur ou de
format ne produisent aucun résultat partiel.

## Installation et modèles : décision explicite hors application

L'import du module ne charge ni moteur, ni Pillow, ni PyTorch/Transformers, ni
toolkit graphique, ni base. L'appel ne lance aucun installateur et n'effectue
aucun téléchargement. Les dépendances lourdes ne sont pas ajoutées aux dépendances
générales de Noethys et les modèles ne sont pas embarqués dans Git.

Pour l'imprimé, fournir les chemins de l'exécutable et du répertoire contenant
`fra.traineddata`. Pas de recherche automatique dans PATH ni de langue anglaise de
secours. Tesseract 4 et les distributions annonçant OpenCL sont refusés avant
reconnaissance. Utiliser une distribution CPU : les anciennes distributions
OpenCL peuvent lancer leur propre sélection de périphérique avec mesures de
performance, ce qui sort du périmètre autorisé.

Pour TrOCR, fournir un export **local complet**, sans liens symboliques,
compatible avec `TrOCRProcessor` et `VisionEncoderDecoderModel`. Interfaces
documentées de Transformers 4.57.1/PyTorch 2.x ; runtime réel **non qualifié** ici.
Le dossier doit contenir au minimum :

- `config.json` : `model_type=vision-encoder-decoder`, décodeur `model_type=trocr` ;
- `preprocessor_config.json`, `tokenizer_config.json` et tous les fichiers du tokenizer ;
- les poids **non fragmentés** `model.safetensors` (aucun repli pickle `.bin`) ;
- `ocr-model.json`, déclaration de provenance fournie par l'opérateur :

```json
{
  "model_id": "identifiant-et-revision-du-modele-francais-choisi",
  "language": "fr",
  "unit": "line"
}
```

La déclaration `language=fr` est vérifiée, mais ne démontre pas les capacités
linguistiques du modèle. Le chargement utilise exclusivement des chemins locaux,
`local_files_only=True`, `token=False`, `trust_remote_code=False` et
`use_safetensors=True`. Un fichier manquant entraîne une erreur, sans repli Hub.
Le dossier est empreinté avant/après chargement ; le modèle résident conserve cette
provenance. Ne pas modifier un snapshot pendant son chargement.

## Utilisation depuis un processus de travail explicite

Depuis la racine du dépôt, après provisionnement manuel :

```python
from noethys.Utils.UTILS_OCR_local import TesseractFrenchCPU, TrOCRFrenchCPU

printed = TesseractFrenchCPU(
    r"C:\OCR\Tesseract\tesseract.exe", r"C:\OCR\Tesseract\tessdata",
    threads=2, timeout=60,
)
proposals = printed.recognize_page(r"C:\OCR\fixtures\imprime-fictif.png", source_page=1)
review = proposals.to_review_payload()

handwriting = TrOCRFrenchCPU(r"C:\OCR\modeles\trocr-fr-revision-fixee", threads=2)
proposals = handwriting.recognize_line(
    r"C:\OCR\fixtures\manuscrit-fictif.png",
    key="document.ligne.1", source_page=2, bbox=(0.1, 0.2, 0.9, 0.3),
)
review = proposals.to_review_payload()  # toujours à relire, aucune écriture
```

Les chemins sont des exemples, pas des chemins d'exploitation découverts.
La boîte d'entrée est normalisée sur le raster complet. Le découpage manuscrit
est arrondi vers l'extérieur aux pixels ; la boîte retournée désigne le découpage
effectivement reconnu. Aucune rotation EXIF implicite n'est appliquée. Fournir une
page rasterisée orientée correctement ; `source_page` est le numéro dans le
document d'origine. `source_sha256` empreinte les octets de cette image de page,
**pas le PDF d'origine**. Le lien PDF/page reste à établir par un futur appelant.

Limites : 32 Mio par source et 20 millions de pixels ; une seule image PNG, JPEG,
TIFF monopage, BMP ou PPM ; transparence aplatie sur blanc. Deux threads par défaut,
plage explicite 1–12, Tesseract limité à 60 secondes par processus par défaut ;
TrOCR limité à 128 nouveaux tokens par défaut (maximum 512), sans garantie de délai
mural. Aucun lot parallèle ni mesure de performance. Une instance TrOCR garde un
modèle résident ; les appels TrOCR sont sérialisés. Le réglage PyTorch des threads
est restauré après succès/échec ; il reste global au processus pendant l'appel :
prévoir un processus de travail séparé pour un futur raccordement UI.

La provenance comprend l'empreinte du modèle français Tesseract ou celle du
snapshot TrOCR complet, et les versions des moteurs. Les confiances des moteurs
ne sont pas comparables ; la sortie TrOCR conserve `None`. Aucun score n'autorise
une écriture automatique. Les erreurs publiques ne recopient pas stderr ni le
contenu documentaire.

## Tests fonctionnels ciblés et portée des preuves

```powershell
py -3.10 -m unittest -v tests.test_noethys_sl_ocr_contract tests.test_noethys_sl_ocr_local tests.test_noethys_sl_consumption_states_shared
```

Sur le poste de développement Windows/Python 3.10 avec Pillow déjà installé :
**38 PASS, 0 FAIL, 0 SKIP** (5 OCR-01, 21 OCR-02, 12 C17 préservés).
Les tests OCR-02 lisent de vraies images fictives et vérifient le raster envoyé,
le découpage, les accents, les coordonnées, l'empreinte source/modèle, les erreurs,
les bornes de ressources, l'absence de repli réseau, le CPU et la relecture.
Tesseract et les bibliothèques TrOCR sont **simulés** : ce résultat ne qualifie pas
la reconnaissance, la compatibilité des poids ou la mémoire sur un i5-10400.
Le test d'import est également exécuté dans un processus sans dépendance OCR.
Les appels réseau sont interdits pendant les tests d'adaptateurs ; aucune base ni
configuration Noethys n'est importée. C17 utilise seulement SQLite en mémoire.

La CI rapide Windows exécute explicitement les deux modules OCR après ses
dépendances habituelles, sans installation ni modèle OCR supplémentaire. Les tests
de raster sont ignorés si Pillow est absent ; cette dépendance est déjà requise par
la CI Windows. Aucun benchmark, téléchargement de moteur/modèle ou build Windows
complet n'est demandé par ce lot.

## Recette réelle à effectuer avant activation

Sur chacun des trois postes déclarés dans PMSL-Arch : Windows 10 x64,
i5-10400, 16 Go minimum (24 Go pour `DESKTOP-0OTERF7`), relever les versions
Python/dépendances réellement installées. L'inventaire déclaratif
[`1119772`](https://github.com/fr4nck/PMSL-Arch/commit/11197723e448d26c5f0814d2bc4a225883d164f5)
et son index
[`4278869`](https://github.com/fr4nck/PMSL-Arch/commit/4278869079b0ad87a4d35fc888e3c20173d9c671)
ne constituent pas une qualification technique des moteurs.

Après provisionnement explicite, couper l'accès réseau et appeler les exemples
sur une page imprimée fictive avec accents et une ligne réellement manuscrite
fictive avec transcription connue. Vérifier le texte, la page/boîte, les empreintes,
les fichiers source inchangés et `write_allowed=False`. Rejouer avec modèle absent,
tokenizer incomplet et image invalide : erreur locale, aucun téléchargement.
Conserver versions, révision/licence du modèle et résultats textuels attendus/obtenus,
sans chronométrage ni comparaison de performances. Ces recettes restent **EN ATTENTE**,
de même que le choix du modèle français et tout raccordement wx/Qt.

Références primaires : [CLI/TSV Tesseract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html),
[OpenCL Tesseract](https://tesseract-ocr.github.io/tessdoc/TesseractOpenCL),
[TrOCR](https://huggingface.co/docs/transformers/main/model_doc/trocr),
[chargement hors ligne Transformers](https://huggingface.co/docs/transformers/v4.57.1/en/installation#offline-mode).
