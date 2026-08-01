# MISSION 10 : voice/stt_engine.py

## Contexte
Couche 4 — Voice Engine. Speech-to-Text avec Whisper local.

## Objectif
Créer `voice/stt_engine.py` + `tests/test_stt_engine.py`

## Spécifications
- [ ] Classe `STTEngine`
- [ ] Whisper local (`openai-whisper`, modèle "base" ou "small")
- [ ] Transcription audio buffer (numpy array) → texte
- [ ] Détection langue auto (fr/en)
- [ ] Confidence score par transcription
- [ ] API simple : `transcribe(audio_buffer) -> TranscriptResult`
- [ ] Tests pytest avec mock audio

## Format de sortie
```python
@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    segments: List[Segment]
    duration_seconds: float
```

## Dépendances
- `openai-whisper`, `numpy`, `torch`

## Validation
```bash
pytest tests/test_stt_engine.py -v
```

## Notes
- Modèle "base" = ~150 Mo, rapide, suffisant pour la v1.0
- Modèle "small" = ~500 Mo, plus précis, pour v1.1
- Cache des transcriptions récentes (éviter re-transcrire identique)
- Gérer le chargement GPU/CPU selon disponibilité
