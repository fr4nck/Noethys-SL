Noethys SL
==================
Logiciel de gestion libre et gratuit de gestion multi-activités pour 
les accueils de loisirs, crèches, garderies périscolaires, cantines, 
TAP ou NAP, clubs sportifs et culturels...

Plus d'infos sur www.noethys.com


Noethys SL et versionnement
------------------

Noethys SL est la lignée de développement wxPython maintenue dans ce dépôt.
Sa numérotation publique est volontairement distincte de la numérotation
historique de Noethys. Cette séparation évite toute collision ou fausse
continuité avec la nomenclature et les numéros de version de Noethys
d'origine, créé par Ivan LUCAS, ainsi qu'avec ses évolutions ultérieures.

Le fichier `noethys/Versions.txt` conserve donc la version de compatibilité
interne historique, nécessaire notamment aux migrations de base et à certains
échanges entre composants. Cette version interne ne désigne pas la version
publique de Noethys SL.

La version publique de Noethys SL est définie dans `noethys/Identite.py` et
utilise sa propre série de versions et de tags `noethys-sl-*`.

Moteur et interfaces wx / Qt
------------------

**Noethys SL** désigne le produit, son moteur fonctionnel et les comportements
métier communs aux différentes interfaces. Lorsqu'un travail concerne
spécifiquement l'interface graphique, le toolkit doit être nommé explicitement :

- **Noethys SL wx** : interface graphique basée sur wxPython ;
- **Noethys SL Qt** : interface graphique basée sur Qt ;
- **Noethys SL** sans suffixe : fonctionnalités moteur, logique métier,
  données, règles de gestion et comportements indépendants du toolkit.

Cette convention doit être utilisée dans les branches, PR, notes de version,
tests et artefacts dès qu'un changement est propre à une interface. Un correctif
métier commun ne doit donc pas être artificiellement étiqueté wx ou Qt.

**Vanilla** reste un terme historique de travail et ne doit plus servir à
désigner le produit ni l'une des deux interfaces.


Installation sur Windows
------------------

Allez dans la rubrique Téléchargements du site www.noethys.com pour télécharger la version compilée pour Windows.


Installation sur Ubuntu 20.04
------------------

Lancez dans votre console Linux les commandes suivantes :
```
sudo apt-get install git curl libsdl2-mixer-2.0-0 libsdl2-image-2.0-0 libsdl2-2.0-0 python3-pip python3-pyscard python3-dev default-libmysqlclient-dev build-essential
pip3 install -U -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-20.04 wxPython
git clone https://github.com/Noethys/Noethys
pip3 install -r Noethys/requirements.txt
python3 Noethys/noethys/Noethys.py
```



Installation depuis les sources
------------------
Si vous rencontrez les difficultés d'installation ou souhaitez installer Noethys depuis les sources,
consultez les documents dédiés ici : https://github.com/Noethys/Noethys/tree/master/noethys/Doc

