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
# Module non branché ailleurs dans le code au moment de la correction — voir
# ROADMAP.md, section « statut réel à clarifier ».

from __future__ import annotations

import requests


class WeatherManager:
    """Récupère la météo actuelle d'une ville via wttr.in."""

    def get_current(self, city: str) -> dict[str, str] | None:
        """
        Retourne température/condition/vent/humidité, ou None si la ville
        est invalide ou la requête échoue — jamais une exception, pour que
        `format_for_display` n'ait qu'un seul cas à gérer.
        """
        try:
            response = requests.get(f"http://wttr.in/{city}?format=3")
            data = response.text.splitlines()
            if len(data) <= 1:
                print("Erreur : Ville invalide")
                return None
            return {
                "temperature": data[0].split()[2],
                "condition": data[1].split()[0],
                "wind": data[2].split()[2],
                "humidity": data[3].split()[2],
            }
        except requests.exceptions.RequestException as exc:
            print(f"Erreur de connexion : {exc}")
            return None

    def format_for_display(self, data: dict[str, str] | None) -> str:
        if data is not None:
            return (
                f"Météo actuelle à {data['temperature']}°C, avec une condition de "
                f"{data['condition']}, un vent de {data['wind']} et une humidité "
                f"de {data['humidity']}%"
            )
        return "Erreur : ville invalide ou pas de connexion"


if __name__ == "__main__":
    weather_manager = WeatherManager()
    print(weather_manager.format_for_display(weather_manager.get_current("Paris")))
