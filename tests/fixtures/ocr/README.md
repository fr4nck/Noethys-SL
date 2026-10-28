# Images OCR fictives

Ces deux PNG ont été rendus avec Pillow 12.3.0 le 28/10/2026 : fond blanc RGB,
texte noir, boîte ajustée au texte et marge de 24 pixels. La transcription de
référence et les empreintes des images figurent dans `samples.json`.

- `printed_fr.png` : « Élise prépare le goûter. », Arial 48 du poste Windows.
  La police n'est ni embarquée ni redistribuée ; seul le raster fictif est inclus.
- `cursive_fr.png` : « Bonjour les enfants. », Caveat 64. C'est une **police
  cursive synthétique**, pas une écriture produite par une personne. Le test
  vérifie le chargement et l'inférence du vrai moteur TrOCR CPU sur ce raster ;
  il ne qualifie pas la reconnaissance d'écritures humaines variées.

Caveat : [Google Fonts, révision `5571d84`](https://github.com/google/fonts/tree/5571d84c0d8c70ec1af4f64072d8c5cf1e4e9643/ofl/caveat),
fichier `Caveat[wght].ttf`, SHA-256
`0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988`.
Licence OFL fournie dans `OFL-Caveat.txt`. Aucun générateur ne télécharge de
police pendant les tests : les rasters figés sont lus directement.

Ces exemples ne contiennent aucune donnée issue d'une famille ou d'une base.
