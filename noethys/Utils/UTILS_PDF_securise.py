# -*- coding: utf-8 -*-
"""UI-432K : ecriture PDF temporaire atomique et non concurrente.

Le rendu reste sur le thread appelant. Ce module ne rend PAS ReportLab
asynchrone ; il evite uniquement de transmettre un PDF incomplet au Mailer.
"""
import os
import tempfile


def Generer(chemin_final, rendu):
    """Commit d'un PDF uniquement apres fermeture et validation minimale.

    Le fichier intermediaire est cree dans le meme repertoire pour conserver
    l'atomicite de os.replace sur le meme volume. Seul ce fichier appartient
    au traitement et peut etre supprime en cas d'exception.
    """
    if not isinstance(chemin_final, str) or not chemin_final:
        raise ValueError("Destination PDF absente")
    cible = os.path.abspath(chemin_final)
    dossier = os.path.dirname(cible)
    descripteur, temporaire = tempfile.mkstemp(
        prefix=".noethys-pdf-", suffix=".pdf", dir=dossier)
    os.close(descripteur)
    try:
        rendu(temporaire)
        with open(temporaire, "rb") as fichier:
            fichier.seek(0, os.SEEK_END)
            taille = fichier.tell()
            if taille < 20:
                raise ValueError("PDF incomplet : fichier trop court")
            fichier.seek(0)
            entete = fichier.read(5)
            fichier.seek(max(0, taille - 2048))
            fin = fichier.read()
        if entete != b"%PDF-" or b"%%EOF" not in fin:
            raise ValueError("PDF incomplet : signature ou fin manquante")
        os.replace(temporaire, cible)
        return chemin_final
    finally:
        if os.path.exists(temporaire):
            os.remove(temporaire)
