# modules/weather_manager.py — météo actuelle via wttr.in
#
# ⚠️ Corrigé le 02/08/2026 (audit de fiabilité avant renommage) : ce fichier
# exécutait un appel réseau réel dès l'import (bloc de test en bas de fichier,
# sans garde `if __name__ == "__main__"`), ce qui faisait planter l'import du
# module dès que la machine n'a pas accès à internet — découvert en essayant
# d'importer chaque module du dépôt. Le bloc de test est déplacé sous une
# garde, et l'exception `ValueError("Ville invalide")` — qui n'était pas
# rattrapée par le `except requests.exceptions.RequestException` — est
# maintenant traitée comme n'importe quel autre échec.
#
# ⚠️ BUG RÉEL PLUS GRAVE, trouvé le 04/08/2026 en câblant ce module dans le
# chat (jamais détecté avant faute d'avoir testé contre le vrai service) :
# `?format=3` rend en réalité UNE SEULE ligne (« Paris: ☀️  +23°C »), pas
# quatre. `len(data) <= 1` était donc TOUJOURS vrai, même pour une ville
# valide — ce module n'avait jamais correctement lu une réponse réelle.
# Remplacé par le format personnalisé wttr.in `%l|%C|%t|%w|%h` (délimité par
# des barres, chaque champ sur une position fixe) — bien plus fiable à
# analyser que le format d'affichage terminal, pensé pour un humain, pas un
# programme. Une ville invalide rend un code HTTP 500 (vérifié en réel :
# « location not found: upstream error... »), désormais détecté par le code
# de statut plutôt que par un nombre de lignes qui ne voulait rien dire.

from __future__ import annotations

import requests

# Champs demandés à wttr.in, dans cet ordre, séparés par « | » — un format
# personnalisé plutôt que le format d'affichage (`?format=3/4`), conçu pour un
# terminal humain (emoji, espacement variable) et donc fragile à analyser.
_WTTR_FORMAT = "%l|%C|%t|%w|%h"


class WeatherManager:
    """Récupère la météo actuelle d'une ville via wttr.in."""

    def get_current(self, city: str) -> dict[str, str] | None:
        """
        Retourne température/condition/vent/humidité, ou None si la ville
        est invalide ou la requête échoue — jamais une exception, pour que
        `format_for_display` n'ait qu'un seul cas à gérer.
        """
        try:
            # https, pas http (corrigé le 04/08/2026) : le nom de ville tapé
            # par Cyril partait en clair.
            response = requests.get(
                f"https://wttr.in/{city}", params={"format": _WTTR_FORMAT}
            )
            if response.status_code != 200:
                print(f"Erreur : Ville invalide (statut {response.status_code})")
                return None

            parts = response.text.strip().split("|")
            if len(parts) < 5 or not parts[0].strip():
                print("Erreur : Ville invalide")
                return None

            return {
                "temperature": parts[2].strip(),
                "condition": parts[1].strip(),
                "wind": parts[3].strip(),
                "humidity": parts[4].strip(),
            }
        except requests.exceptions.RequestException as exc:
            print(f"Erreur de connexion : {exc}")
            return None

    def format_for_display(self, data: dict[str, str] | None) -> str:
        """
        ⚠️ `temperature` et `humidity` embarquent déjà leur unité
        (« +23°C », « 70% ») — le format wttr.in les rend ainsi. Les
        réaccoler ici (« {temperature}°C ») doublait l'unité, second bug
        trouvé en même temps que le premier (corrigé le 04/08/2026).
        """
        if data is not None:
            return (
                f"Météo actuelle : {data['temperature']}, {data['condition']}, "
                f"vent {data['wind']}, humidité {data['humidity']}"
            )
        return "Erreur : ville invalide ou pas de connexion"


if __name__ == "__main__":
    weather_manager = WeatherManager()
    print(weather_manager.format_for_display(weather_manager.get_current("Paris")))
