# MISSION 09 : voice/tts_engine.py

## Contexte
Couche 4 — Voice Engine. Text-to-Speech avec prosodie émotionnelle.

## Objectif
Créer `voice/tts_engine.py` + `tests/test_tts_engine.py`

## Spécifications
- [ ] Classe `TTSEngine`
- [ ] Support **Piper** (local, rapide, français) et **Kokoro** (fallback)
- [ ] File d'attente audio (queue) pour parler en continu
- [ ] Prosodie émotionnelle : vitesse, pitch selon l'état émotionnel de Luca's
- [ ] Interruption possible (stop la parole en cours)
- [ ] WebSocket endpoint pour recevoir du texte à prononcer
- [ ] Tests pytest avec mock audio

## Format d'entrée WebSocket
```json
{
  "type": "speak",
  "text": "Bonjour, je suis Luca's.",
  "emotion": "happy",
  "speed": 1.0,
  "priority": "normal"
}
```

## Dépendances
- `piper-tts`, `pyaudio`, `numpy`, `websockets`

## Validation
```bash
pytest tests/test_tts_engine.py -v
```

## Notes
- Piper : télécharger le modèle fr_FR via `piper-download`
- Queue thread-safe (`queue.Queue`)
- Émotions : "neutral", "happy", "sad", "excited", "calm", "urgent"
- Vitesse : 0.8 (lent) à 1.5 (rapide)
- Jouer l'audio via `pyaudio` ou `sounddevice`
