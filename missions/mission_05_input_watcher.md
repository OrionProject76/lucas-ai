# MISSION 05 : input_watcher.py

## Contexte
Couche Perception (Layer 1). Doit surveiller les patterns d'usage clavier/souris.

## Objectif
Créer `perception/input_watcher.py` + `tests/test_input_watcher.py`

## Spécifications
- [ ] Thread séparé, non-bloquant
- [ ] Hook clavier global avec `pynput` (sans bloquer le système)
- [ ] Hook souris global avec `pynput` (clics, mouvements)
- [ ] Calcul rythme de frappe (WPM), pauses, patterns
- [ ] Détection inactivité (pas d'input depuis X secondes)
- [ ] Envoi WebSocket JSON toutes les 10 secondes (agrégé)
- [ ] Tests pytest avec mock input

## Format de sortie WebSocket
```json
{
  "type": "input_stats",
  "timestamp": "2026-07-29T08:30:00",
  "data": {
    "wpm": 45.2,
    "keys_last_10s": 23,
    "clicks_last_10s": 3,
    "mouse_distance_px": 450,
    "idle_seconds": 0,
    "pattern": "typing_burst"
  }
}
```

## Dépendances
- `pynput`

## Validation
```bash
pytest tests/test_input_watcher.py -v
```

## Notes
- `pynput` fonctionne en thread séparé avec listener
- Ne pas logger les touches exactes (privacy) — uniquement stats agrégées
- Pattern detection : "typing_burst", "slow_typing", "idle", "clicking"
- Gérer les permissions Windows (run as admin si nécessaire)
