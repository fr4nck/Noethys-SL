# -*- coding: utf-8 -*-
"""Lot B RC10.5 : contrôles physiques minimaux d'un PDF avant envoi.

Ne prétend pas valider la structure PDF complète ou la signature. Evite
simplement de traiter une absence, un fichier vide, un faux PDF ou un PDF
manifestement tronqué comme un reçu envoyé. Lecture seule, coût constant.
"""
import os
import re

_ENTETE_PDF = re.compile(br"%PDF-1\.[0-9]")
_FIN_PDF = re.compile(br"%%EOF(?:\s*)\Z")


def PDFPretPourEnvoi(chemin):
    """Vrai si l'attachement ressemble à un PDF généré complet.

    Ne lit que l'en-tête et 2048 derniers octets. Le flux est fermé dans
    tous les cas ; aucun appel réseau, aucune mutation ni sortie de secret.
    """
    try:
        if not chemin or not isinstance(chemin, (str, os.PathLike)):
            return False
        with open(chemin, "rb") as pdf:
            taille = os.fstat(pdf.fileno()).st_size
            if taille < 16 or _ENTETE_PDF.match(pdf.read(8)) is None:
                return False
            pdf.seek(max(0, taille - 2048))
            fin = pdf.read().rstrip()
            position = fin.rfind(b"%%EOF")
            if position == -1:
                return False
            return _FIN_PDF.fullmatch(fin[position:]) is not None
    except (OSError, ValueError, TypeError):
        return False
