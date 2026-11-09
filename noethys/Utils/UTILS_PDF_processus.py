# -*- coding: utf-8 -*-
"""UI-432K : moteur PDF Noedoc dans un processus Windows separe.

La voie historique reste par defaut : la bascule est une qualification
explicite, avant toute activation dans un executable PyInstaller. Aucune
donnee ni secret n'est ecrit dans des fichiers de communication.
"""
import datetime
import decimal
import multiprocessing
import os


def _primitif(valeur):
    """Copie les donnees de rendu sans transporter d'objets natifs wx."""
    try:
        import wx
        if isinstance(valeur, wx.Colour):
            return (valeur.Red(), valeur.Green(), valeur.Blue())
    except ImportError:
        pass
    if valeur is None or isinstance(
            valeur, (str, bytes, bool, int, float, decimal.Decimal,
                     datetime.date, datetime.datetime)):
        return valeur
    if isinstance(valeur, (list, tuple)):
        return type(valeur)(_primitif(x) for x in valeur)
    if isinstance(valeur, dict):
        return {_primitif(k): _primitif(v) for k, v in valeur.items()}
    raise TypeError("Donnee non qualifiee pour rendu PDF isole : %s" %
                    type(valeur).__name__)


def Preparer(comptes, options):
    """Capture les wx.Colour sur le thread GUI avant le lancement du worker."""
    return _primitif(comptes), _primitif(options)


def _nom_base(source, suffixe):
    """Derive DATA ou PHOTOS sans lire le profil ou une autre base."""
    if suffixe in (None, "DATA"):
        return source
    if suffixe != "PHOTOS":
        raise ValueError("Base secondaire non qualifiee pour le rendu")
    racine, extension = os.path.splitext(source)
    if racine.lower().endswith("_data"):
        return racine[:-5] + "_PHOTOS" + extension
    raise ValueError("Base PHOTOS introuvable pour la source fournie")


def _processus(conn, source, comptes, options, modele, chemin):
    """Point d'entree enfant : tous les objets wx naissent dans CE processus."""
    app = None
    original = None
    try:
        if os.environ.get("NOETHYS_SL_PDF_TEST_ISOLE") == "1":
            import _garde_reseau  # noqa: F401  guard inherited by child
        import wx
        import GestionDB
        original = GestionDB.DB
        app = wx.GetApp() or wx.App(False)
        # Aucun dialogue modal enfant ne peut demander une interaction
        # utilisateur invisible pendant un rendu distant.
        def refuser_dialogue(*args, **kwargs):
            raise RuntimeError("Dialogue interactif interdit dans le rendu PDF")
        wx.MessageDialog = refuser_dialogue

        class DBSource(original):
            def __init__(self, suffixe="DATA", nomFichier="", modeCreation=False,
                         IDconnexion=None, pooling=True):
                if not nomFichier:
                    nomFichier = _nom_base(source, suffixe)
                    suffixe = None
                original.__init__(
                    self, suffixe=suffixe, nomFichier=nomFichier,
                    modeCreation=modeCreation, IDconnexion=IDconnexion,
                    pooling=False)

        GestionDB.DB = DBSource
        from Utils import UTILS_Impression_facture
        UTILS_Impression_facture.Impression(
            comptes, options, IDmodele=modele,
            ouverture=False, nomFichier=chemin)
        conn.send(("ok",))
    except BaseException as erreur:
        try:
            module = (getattr(erreur, "name", None)
                      if isinstance(erreur, ImportError) else None)
            if (module is None and isinstance(erreur, ImportError)
                    and os.environ.get("NOETHYS_SL_PDF_TEST_ISOLE") == "1"):
                # Message uniquement en banc fictif, sans chemin absolu.
                module = str(erreur).split(" (", 1)[0].split("\\n", 1)[0][:160]
            conn.send(("error", type(erreur).__name__, module))
        except Exception:
            pass
    finally:
        if original is not None:
            try:
                GestionDB.DB = original
            except Exception:
                pass
        if app is not None:
            try:
                app.Destroy()
            except Exception:
                pass
        conn.close()


def Generer(comptes, options, modele, chemin, source_db, delai=180, donnees_pretes=False):
    """Bloquant uniquement pour le thread d'orchestration, jamais pour wx.

    Doit etre appele depuis un TravailFond d'UTILS_Etapes_ui. Le fichier
    temporaire est possede/nettoye par UTILS_PDF_securise.Generer.
    """
    if not isinstance(source_db, str) or not source_db or "\x00" in source_db:
        raise ValueError("Source SQL explicite requise pour le processus")
    if not isinstance(chemin, str) or not chemin:
        raise ValueError("Chemin PDF manquant")
    if delai <= 0:
        raise ValueError("Delai de rendu invalide")

    if donnees_pretes:
        donnees, reglages = comptes, options
    else:
        donnees, reglages = Preparer(comptes, options)
    ctx = multiprocessing.get_context("spawn")
    lecture, ecriture = ctx.Pipe(duplex=False)
    processus = ctx.Process(
        target=_processus,
        args=(ecriture, source_db, donnees, reglages, modele, chemin),
        name="Noethys-PDF-UI432K", daemon=True)
    try:
        processus.start()
        ecriture.close()
        if not lecture.poll(delai):
            processus.terminate()
            processus.join(timeout=5)
            raise TimeoutError("Rendu PDF isole hors delai")
        verdict = lecture.recv()
        processus.join(timeout=5)
        if processus.is_alive():
            processus.terminate()
            processus.join(timeout=5)
            raise RuntimeError("Processus PDF impossible a fermer")
        if processus.exitcode != 0 or verdict != ("ok",):
            typ = verdict[1] if len(verdict) > 1 else "ProcessusInconnu"
            module = verdict[2] if len(verdict) > 2 else None
            if module and isinstance(module, str):
                raise RuntimeError(
                    "Rendu PDF isole refuse : %s (module %s)" %
                    (typ, module[:100]))
            raise RuntimeError("Rendu PDF isole refuse : %s" % typ)
        return chemin
    finally:
        lecture.close()
        ecriture.close()
        if processus.is_alive():
            processus.terminate()
            processus.join(timeout=5)
        processus.close()
