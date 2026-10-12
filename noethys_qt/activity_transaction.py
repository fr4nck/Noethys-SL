"""Transaction partagée pour les écritures de la fiche Activité Qt.

Les repositories Qt historiques ouvrent, valident et ferment encore leur propre
connexion. Ce pont permet de les réutiliser sans dupliquer leur SQL tout en
regroupant plusieurs sauvegardes dans une seule transaction réelle.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


class _SharedConnection:
    """Proxy de connexion dont commit/rollback/close sont pilotés par l'appelant."""

    def __init__(self, connection):
        self._connection = connection

    def cursor(self, *args, **kwargs):
        return self._connection.cursor(*args, **kwargs)

    def commit(self) -> None:
        # Les repositories existants appellent commit() en fin de save().
        # Dans une transaction composée, seul le contexte externe doit valider.
        return None

    def rollback(self) -> None:
        # Même principe : une erreur remonte jusqu'au contexte externe qui
        # effectue le rollback sur la vraie connexion.
        return None

    def close(self) -> None:
        # La connexion réelle reste ouverte jusqu'à la sortie du contexte.
        return None

    def __getattr__(self, name):
        return getattr(self._connection, name)


class SharedEditorRepository:
    """Objet minimal compatible avec les repositories Qt de la fiche Activité."""

    def __init__(self, connection, placeholder: str):
        self.connection = _SharedConnection(connection)
        self.placeholder = placeholder

    def _connect(self):
        return self.connection, self.placeholder


@contextmanager
def activity_transaction(editor_repository) -> Iterator[SharedEditorRepository]:
    """Ouvre une transaction atomique SQLite ou MySQL pour la fiche Activité."""

    connection, placeholder = editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire
    shared = SharedEditorRepository(connection, placeholder)
    try:
        yield shared
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
