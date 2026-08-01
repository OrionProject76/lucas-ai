# MISSION 02 : system_watcher.py

## Contexte
Couche Perception (Layer 1). Doit surveiller l'état du système Windows en temps réel.

## Objectif
Créer `perception/system_watcher.py` + `tests/test_system_watcher.py`

## Spécifications
- [ ] Thread séparé, non-bloquant
- [ ] Liste des processus actifs avec CPU/RAM (`psutil`)
- [ ] Fenêtre active + titre (`pywin32` + `win32gui`)
- [ ] URL active du navigateur (Chrome/Edge/Firefox via `pywinauto` ou accessibility)
- [ ] Envoi WebSocket JSON toutes les 2 secondes
- [ ] Filtrage des processus système non pertinents
- [ ] Tests pytest avec mock processus

## Format de sortie WebSocket
```json
{
  "type": "system_update",
  "timestamp": "2026-07-29T08:30:00",
  "data": {
    "active_window": "Visual Studio Code",
    "window_title": "main.py - OrionAI",
    "browser_url": "https://github.com/...",
    "top_processes": [
      {"name": "code.exe", "cpu": 12.5, "ram_mb": 450},
      {"name": "chrome.exe", "cpu": 8.3, "ram_mb": 1200}
    ],
    "system": {
      "cpu_percent": 25.0,
      "ram_percent": 45.0,
      "disk_percent": 60.0
    }
  }
}
```

## Dépendances
- `psutil`, `pywin32`, `pywinauto`

## Validation
```bash
pytest tests/test_system_watcher.py -v
```

## Notes
- Pour l'URL du navigateur, privilégier l'accessibility API Windows
- Filtrer les processus Windows système (svchost, csrss, etc.)
- Ne pas envoyer si aucun changement depuis la dernière capture
