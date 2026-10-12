# -*- coding: utf-8 -*-
"""Lecture CSV avec l'API de unicodecsv (fichier binaire + encoding) sous Python 3.

unicodecsv n'est ni dans requirements.txt ni dans le paquet Windows, et son
repli Outils/unicodecsvpy2 est du Python 2 (itertools.izip) : sans ce module,
les imports CSV de familles/individus et de badgeage ne s'ouvraient pas.
"""
import csv
import io


def reader(fichier, encoding="utf-8", **options):
    """Comme unicodecsv.reader : accepte un fichier ouvert en binaire."""
    if isinstance(fichier, io.TextIOBase):
        flux = fichier
    else:
        flux = io.TextIOWrapper(fichier, encoding=encoding, newline="")
    return csv.reader(flux, **options)
