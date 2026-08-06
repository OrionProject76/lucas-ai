# test_log_scrub.py — le jeton ne doit jamais atteindre un fichier de log.
#
# Le cas d'origine (data/logs/server_startup.log, 05/08/2026) :
#     INFO:  192.168.1.14:59240 - "WebSocket /ws?token=<valeur réelle>" [accepted]
#
# uvicorn journalise en format paresseux — le chemin porteur du jeton vit
# dans record.args, pas dans record.msg. Un filtre qui ne regarderait que
# le message laisserait passer exactement cette ligne : d'où le test
# `test_masks_the_uvicorn_websocket_line`, qui reproduit l'appel réel.

import logging

import pytest

from api.log_scrub import MASK, TokenScrubFilter, install, mask_secrets

# ── mask_secrets : la valeur part, le nom reste ────────────────────────


def test_masks_a_token_in_a_query_string() -> None:
    assert mask_secrets("/ws?token=abc123") == f"/ws?token={MASK}"


def test_keeps_the_parameter_name() -> None:
    """
    Savoir QU'UN jeton a été fourni reste utile pour diagnostiquer un 401 ;
    connaître sa valeur ne l'est jamais.
    """
    assert "token=" in mask_secrets("/ws?token=abc123")


def test_masks_the_uvicorn_websocket_line() -> None:
    ligne = '192.168.1.14:59240 - "WebSocket /ws?token=xHCdilkq_9X54jW0fk1f" [accepted]'
    masque = mask_secrets(ligne)
    assert "xHCdilkq_9X54jW0fk1f" not in masque
    assert masque.endswith('[accepted]')  # le reste de la ligne survit


def test_stops_at_the_next_parameter() -> None:
    """Un & termine la valeur — le paramètre suivant reste lisible."""
    assert mask_secrets("/ws?token=abc&client=pwa") == f"/ws?token={MASK}&client=pwa"


def test_masks_several_sensitive_parameters() -> None:
    masque = mask_secrets("?api_key=aaa&password=bbb&secret=ccc")
    for valeur in ("aaa", "bbb", "ccc"):
        assert valeur not in masque


def test_is_case_insensitive() -> None:
    assert mask_secrets("?TOKEN=abc123") == f"?TOKEN={MASK}"


def test_leaves_an_ordinary_line_untouched() -> None:
    ligne = '127.0.0.1:1234 - "GET /app/ HTTP/1.1" 200'
    assert mask_secrets(ligne) == ligne


def test_does_not_mask_a_word_merely_containing_token() -> None:
    """
    `mytoken=` n'est pas `token=` : la frontière de mot (\\b) évite de
    masquer un paramètre sans rapport. Le préfixe reste visible.
    """
    assert mask_secrets("?mytoken=abc") == "?mytoken=abc"


def test_handles_an_empty_value() -> None:
    assert mask_secrets("?token=") == f"?token={MASK}"


# ── TokenScrubFilter : msg ET args ─────────────────────────────────────


def _record(msg: str, args=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_filter_masks_the_message() -> None:
    record = _record("connexion /ws?token=abc123")
    TokenScrubFilter().filter(record)
    assert "abc123" not in record.getMessage()


def test_filter_masks_lazy_arguments() -> None:
    """
    Le cas réel d'uvicorn : format paresseux, jeton dans les arguments.
    C'est ce test qui protège contre la régression d'origine.
    """
    record = _record(
        '%s - "WebSocket %s" [accepted]',
        ("192.168.1.14:59240", "/ws?token=abc123"),
    )
    TokenScrubFilter().filter(record)
    assert "abc123" not in record.getMessage()
    assert "192.168.1.14:59240" in record.getMessage()


def test_filter_masks_dict_arguments() -> None:
    # Passé en 1-uplet, comme le fait `logger.info(msg, {...})` : LogRecord
    # déballe le mapping et le pose tel quel dans record.args.
    record = _record("%(path)s", ({"path": "/ws?token=abc123"},))
    TokenScrubFilter().filter(record)
    assert "abc123" not in record.getMessage()


def test_filter_never_drops_a_line() -> None:
    """Masquer, jamais supprimer : un log muet cacherait aussi les pannes."""
    assert TokenScrubFilter().filter(_record("/ws?token=abc")) is True


def test_filter_tolerates_non_string_arguments() -> None:
    record = _record("%s %d", ("/ws?token=abc", 42))
    TokenScrubFilter().filter(record)
    assert "abc" not in record.getMessage()
    assert "42" in record.getMessage()


# ── install : idempotence et couverture réelle ─────────────────────────


def test_install_is_idempotent() -> None:
    logger = logging.getLogger("test_log_scrub.idempotence")
    logger.filters = []
    install(("test_log_scrub.idempotence",))
    install(("test_log_scrub.idempotence",))
    poses = [f for f in logger.filters if isinstance(f, TokenScrubFilter)]
    assert len(poses) == 1


def test_install_covers_the_uvicorn_websocket_logger() -> None:
    """
    Les lignes WebSocket sortent sur `uvicorn.error`, pas `uvicorn.access`
    malgré leur nature d'accès (vérifié dans uvicorn/protocols/websockets/
    websockets_impl.py). Rater ce logger-là aurait laissé la fuite entière.
    """
    import api.server  # noqa: F401  — l'import pose le filtre

    filtres = logging.getLogger("uvicorn.error").filters
    assert any(isinstance(f, TokenScrubFilter) for f in filtres)


def test_a_real_handler_writes_the_masked_value(tmp_path) -> None:
    """
    Bout en bout : ce qui atteint le FICHIER est masqué, pas seulement ce
    que le filtre retourne. C'est le fichier qui a fui, c'est lui qu'on
    vérifie.
    """
    fichier = tmp_path / "acces.log"
    logger = logging.getLogger("test_log_scrub.fichier")
    logger.filters = []
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(fichier, encoding="utf-8")
    logger.addHandler(handler)
    install(("test_log_scrub.fichier",))

    logger.info('%s - "WebSocket %s" [accepted]', "192.168.1.14:1", "/ws?token=abc123")
    handler.close()

    contenu = fichier.read_text(encoding="utf-8")
    assert "abc123" not in contenu
    assert MASK in contenu


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
