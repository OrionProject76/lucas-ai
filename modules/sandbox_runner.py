# modules/sandbox_runner.py — bootstrap exécuté DANS le sous-processus isolé
#
# Invoqué par modules/sandbox_manager.py : `python sandbox_runner.py <fichier>`,
# avec cwd déjà fixé sur sandbox_workspace/ par l'appelant (Popen(cwd=...)).
# Fichier de CONFIANCE — jamais écrit ni modifié par le code sandboxé
# lui-même, contrairement au fichier passé en argument.
#
# Doctrine : VISION_LONG_TERME.md §4 — « Aucune exécution de code
# auto-généré hors sandbox ». Brief : cowork_workspace/BRIEF_WORKSPACE_E3_SANDBOX.md.
#
# ⚠️ Sandbox LOGICIELLE (niveau Python), pas une isolation OS (pas de
# conteneur, pas de VM, pas d'AppContainer Windows, pas de compte
# restreint). Les gardes ci-dessous interceptent les chemins normaux
# (réseau via `socket`, accès fichiers via `open`/`os.*`, lancement de
# processus externe) — un code qui contournerait ces API via `ctypes` ou
# un appel Win32 direct n'est PAS arrêté. Honnête sur ce que ça couvre
# (RT-2, CLAUDE.md) : suffisant pour des scripts d'analyse/outils
# maladroits, pas une défense contre un adversaire qui écrit du code
# spécifiquement pour s'évader. Durcissement futur : IDEAS.md.

from __future__ import annotations

import builtins
import io
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path

# Chemins : vérifiés par résolution réelle (symlinks compris), pas par
# préfixe de chaîne — un `..` ou un lien ne doit pas pouvoir passer sous
# le radar d'une simple comparaison textuelle.
_PATH_MUTATORS_SINGLE = (
    "remove", "unlink", "mkdir", "makedirs", "rmdir", "removedirs",
    "chmod", "truncate", "listdir", "scandir", "chdir",
)
_PATH_MUTATORS_DOUBLE = ("rename", "replace", "renames")
_PATH_MUTATORS_LINK = ("symlink", "link")

_PROCESS_SPAWNERS = (
    "system", "popen", "posix_spawn",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe",
)


def _network_blocked(*_args, **_kwargs):
    raise PermissionError(
        "Accès réseau bloqué dans la sandbox (VISION_LONG_TERME.md §4)."
    )


def _process_blocked(*_args, **_kwargs):
    raise PermissionError(
        "Lancement de processus externe bloqué dans la sandbox — "
        "contourner le blocage réseau/fichiers par un sous-processus "
        "n'est pas autorisé."
    )


def _check_contained(root: Path, path: str | bytes | os.PathLike | int) -> None:
    """Lève PermissionError si `path` résout hors de `root`."""
    if isinstance(path, int):
        return  # descripteur déjà ouvert (dup2...) : rien à vérifier
    # fsdecode, pas fspath : un chemin en bytes (valide pour open()/os.open()
    # sur ce projet Windows) doit rester vérifiable — Path() n'accepte pas
    # bytes, fsdecode() ramène tout à str sans perdre le cas bytes.
    resolved = Path(os.fsdecode(path)).resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError(
            f"Accès fichier hors de sandbox_workspace/ refusé : {path!r}"
        )


def _wrap_path_fn(root: Path, real_fn, arg_indices: tuple[int, ...]):
    def wrapped(*args, **kwargs):
        for i in arg_indices:
            if i < len(args):
                _check_contained(root, args[i])
        return real_fn(*args, **kwargs)

    return wrapped


def install_guards(root: Path) -> None:
    """
    Applique tous les garde-fous. Doit être appelé UNE FOIS, avant
    d'exécuter le code proposé — jamais après, sinon la fenêtre entre
    l'exec et la pose des gardes serait un accès libre.
    """
    # Réseau — bloque le point d'entrée commun à socket, requests,
    # urllib, http.client (tous construisent un socket.socket en interne).
    socket.socket = _network_blocked  # type: ignore[misc, assignment]
    socket.create_connection = _network_blocked  # type: ignore[assignment]

    # Fichiers — open()/io.open()/os.open() couvrent lecture ET écriture,
    # y compris via pathlib (Path.open()/read_text()/write_text() délèguent
    # à io.open ; Path.unlink()/rename()/mkdir() délèguent aux fonctions
    # os.* patchées ci-dessous, jamais à une copie figée à l'import).
    _real_open = builtins.open

    def _guarded_open(file, *args, **kwargs):
        _check_contained(root, file)
        return _real_open(file, *args, **kwargs)

    builtins.open = _guarded_open
    io.open = _guarded_open  # séparé de builtins.open dans l'implémentation CPython

    for name in _PATH_MUTATORS_SINGLE:
        if hasattr(os, name):
            setattr(os, name, _wrap_path_fn(root, getattr(os, name), (0,)))
    for name in _PATH_MUTATORS_DOUBLE:
        if hasattr(os, name):
            setattr(os, name, _wrap_path_fn(root, getattr(os, name), (0, 1)))
    for name in _PATH_MUTATORS_LINK:
        if hasattr(os, name):
            setattr(os, name, _wrap_path_fn(root, getattr(os, name), (0, 1)))
    if hasattr(os, "open"):
        os.open = _wrap_path_fn(root, os.open, (0,))  # type: ignore[assignment]

    # Processus — ferme la porte de contournement la plus directe : un
    # script qui shell-out (curl.exe, powershell...) rendrait les deux
    # gardes ci-dessus inutiles, puisqu'un processus externe n'hérite
    # d'aucun des patchs posés dans CE process Python.
    subprocess.Popen.__init__ = _process_blocked  # type: ignore[method-assign]
    for name in _PROCESS_SPAWNERS:
        if hasattr(os, name):
            setattr(os, name, _process_blocked)
    if hasattr(os, "startfile"):
        os.startfile = _process_blocked  # type: ignore[attr-defined]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage : sandbox_runner.py <fichier_a_executer>", file=sys.stderr)
        return 2

    script_path = Path(sys.argv[1])
    root = Path.cwd().resolve()
    install_guards(root)

    try:
        code = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Impossible de lire la proposition sandbox : {exc}", file=sys.stderr)
        return 1

    try:
        # exec() du code PROPOSÉ est la raison d'être de ce fichier — les
        # gardes ci-dessus (install_guards) sont ce qui rend cet exec sûr,
        # pas une absence d'exec. except BaseException (pas Exception) :
        # une proposition qui appelle sys.exit()/lève SystemExit doit
        # quand même remonter comme un résultat propre au parent
        # (modules/sandbox_manager.py), jamais comme un crash de ce runner.
        exec(compile(code, str(script_path), "exec"), {"__name__": "__sandbox__"})  # noqa: S102
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
