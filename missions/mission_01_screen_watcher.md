# MISSION 01 : screen_watcher.py

## Contexte
Couche Perception (Layer 1). Doit capturer l'écran et extraire le texte via OCR pour alimenter le World Model.

## Objectif
Créer `perception/screen_watcher.py` + `tests/test_screen_watcher.py`

## Spécifications
- [ ] Thread séparé (`threading.Thread`), non-bloquant pour l'UI
- [ ] Capture d'écran toutes les 5 secondes **uniquement si changement détecté**
- [ ] OCR avec `easyocr` (français + anglais)
- [ ] Détection fenêtre active avec `pywin32` (`win32gui`)
- [ ] Envoi WebSocket JSON vers `world_model/manager.py` (structure à définir)
- [ ] Gestion d'erreurs : écran verrouillé, OCR vide, texte illisible
- [ ] Tests pytest avec mock écran (`pytest-mock`, `PIL.Image` mock)

## Format de sortie WebSocket
```json
{
  "type": "screen_update",
  "timestamp": "2026-07-29T08:30:00",
  "data": {
    "text": "texte extrait par OCR...",
    "app_active": "Visual Studio Code",
    "window_title": "main.py - Luca's",
    "screen_hash": "abc123..."
  }
}
```

## Dépendances
- `Pillow`, `easyocr`, `pywin32`, `websockets`

## Validation
```bash
pytest tests/test_screen_watcher.py -v
```

## Notes
- Ne pas bloquer l'UI principale (thread daemon)
- Utiliser `hashlib` pour détecter les changements d'écran (comparer hash)
- Limiter la taille du texte envoyé (max 2000 caractères)
- Logger les erreurs sans crasher le thread
