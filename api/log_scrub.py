# api/log_scrub.py — empêche un secret de passer en clair dans les logs.
#
# Pourquoi ce module existe
# -------------------------
# Uvicorn journalise la ligne de requête complète, query string comprise :
#
#     INFO:  192.168.1.14:59240 - "WebSocket /ws?token=<valeur réelle>" [accepted]
#
# Le jeton d'API de Luca's y arrivait donc en clair, à chaque connexion du
# téléphone, dans `data/logs/server_startup.log` — un fichier sans rotation,
# qui grossit indéfiniment. Le fichier est bien couvert par .gitignore (il ne
# part jamais dans un commit), mais « pas dans Git » n'est pas « pas en
# clair » : un log est le premier fichier qu'on copie-colle pour demander de
# l'aide, et le premier qu'on oublie en archivant un dossier.
#
# Deux défenses, pas une (elles ne se remplacent pas)
# ---------------------------------------------------
# 1. La PWA transporte désormais son jeton dans l'en-tête `Sec-WebSocket-
#    Protocol` (voir api/server.py, _token_from_subprotocols) — un en-tête
#    n'est jamais journalisé au niveau INFO, le secret ne peut donc plus
#    atteindre le log. C'est la vraie correction : le secret ne passe plus
#    par là du tout.
# 2. Ce module masque ce qui arriverait quand même par query string. Ce
#    repli reste nécessaire : les tests, `curl`, et le futur client Godot
#    peuvent poser `?token=`, et un client hors du navigateur n'a aucune
#    raison de connaître notre convention de sous-protocole.
#
# Le masquage ne remplace pas le point 1 — il couvre les chemins que le
# point 1 ne peut pas atteindre.

import logging
import re

# Noms de paramètres dont la VALEUR est masquée dans toute ligne de log.
# Volontairement un peu large : rater un nom coûte une fuite, en masquer un
# de trop coûte une ligne de log un peu moins lisible.
SENSITIVE_PARAMS = (
    "token",
    "access_token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
)

MASK = "***"

# La valeur s'arrête au premier séparateur d'URL ou d'affichage : & termine
# le paramètre, l'espace et le guillemet terminent la ligne de log d'uvicorn
# (`"WebSocket /ws?token=..." [accepted]`). Le nom du paramètre est conservé
# tel quel — savoir QU'UN jeton a été fourni reste utile pour diagnostiquer
# un 401, connaître sa valeur ne l'est jamais.
_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(SENSITIVE_PARAMS) + r")=[^&\s\"'#]*"
)


def mask_secrets(text: str) -> str:
    """
    Remplace la valeur de tout paramètre sensible par `***`.

    >>> mask_secrets('"WebSocket /ws?token=abc123" [accepted]')
    '"WebSocket /ws?token=***" [accepted]'
    """
    return _PATTERN.sub(lambda m: f"{m.group(1)}={MASK}", text)


class TokenScrubFilter(logging.Filter):
    """
    Filtre de journalisation qui masque les secrets AVANT écriture.

    Agit sur `record.msg` et sur `record.args` : uvicorn journalise avec un
    format paresseux (`'%s - "WebSocket %s" [accepted]'` + arguments), donc
    le chemin porteur du jeton vit dans les arguments, pas dans le message.
    Ne traiter que `record.msg` laisserait fuir exactement le cas qui a
    motivé ce module.

    Un filtre plutôt qu'un formateur : il s'applique quel que soit le
    handler configuré ensuite (console, fichier, redirection shell), y
    compris ceux qu'uvicorn installe lui-même.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: mask_secrets(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            else:
                record.args = tuple(
                    mask_secrets(value) if isinstance(value, str) else value
                    for value in record.args
                )

        return True  # ne filtre rien : masque, ne supprime jamais une ligne


# Loggers visés. "uvicorn.access" porte les requêtes HTTP ; "uvicorn.error"
# porte — malgré son nom — les lignes WebSocket `[accepted]`/`403`, vérifié
# dans uvicorn/protocols/websockets/websockets_impl.py. Rater le second
# aurait laissé passer précisément la fuite d'origine.
_TARGET_LOGGERS = ("uvicorn.access", "uvicorn.error")


def install(logger_names: tuple[str, ...] = _TARGET_LOGGERS) -> None:
    """
    Pose le filtre sur les loggers d'uvicorn, sans doublon si rappelée.

    Appelée à l'import de `api.server`, donc APRÈS qu'uvicorn a configuré
    sa journalisation (`Config.__init__` configure les logs, `load()`
    importe l'application ensuite). `logging.config.dictConfig` remplace
    les handlers d'un logger mais ne touche pas à ses filtres : celui-ci
    survit donc à la configuration d'uvicorn, quel que soit l'ordre.
    """
    for name in logger_names:
        logger = logging.getLogger(name)
        if any(isinstance(existing, TokenScrubFilter) for existing in logger.filters):
            continue
        logger.addFilter(TokenScrubFilter())
