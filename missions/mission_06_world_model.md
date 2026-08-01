# MISSION 06 : world_model/manager.py

## Contexte
Couche 2 — World Model OS. Agrège toutes les données de perception en un modèle mental temps réel.

## Objectif
Créer `world_model/manager.py` + `tests/test_world_model.py`

## Spécifications
- [ ] Classe `WorldModelManager` singleton
- [ ] Reçoit les mises à jour WebSocket des 5 watchers
- [ ] Maintient un état temps réel du système (fenêtre active, processus, émotion, etc.)
- [ ] Détection de causalité simple : "Chrome ouvert → recherche probable"
- [ ] Détection de temporalité : historique des 24h en mémoire
- [ ] Persistance SQLite des événements importants
- [ ] API pour que les autres modules interrogent l'état
- [ ] Tests pytest

## Structure de l'état
```python
@dataclass
class WorldState:
    timestamp: datetime
    active_window: str
    active_url: Optional[str]
    top_processes: List[ProcessInfo]
    screen_text: str
    audio_transcript: Optional[str]
    emotion: str
    input_pattern: str
    system_load: SystemLoad
    inferred_intent: Optional[str]  # "working", "browsing", "gaming", etc.
```

## Dépendances
- `websockets`, `sqlite3`, `dataclasses`, `typing`

## Validation
```bash
pytest tests/test_world_model.py -v
```

## Notes
- Utiliser `asyncio` pour le serveur WebSocket
- Buffer circulaire en mémoire pour les 100 derniers états
- SQLite pour persistance long terme
- Intent inference : règles simples (regex sur fenêtre active)
