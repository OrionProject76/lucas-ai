# MISSION 03 : audio_watcher.py

## Contexte
Couche Perception (Layer 1). Doit capturer l'audio du micro et détecter la parole.

## Objectif
Créer `perception/audio_watcher.py` + `tests/test_audio_watcher.py`

## Spécifications
- [ ] Thread séparé, non-bloquant
- [ ] Capture audio micro avec `pyaudio` (chunk 1024, rate 16000)
- [ ] Voice Activity Detection (VAD) avec `webrtcvad` ou `silero-vad`
- [ ] Quand parole détectée → buffer audio → transcription STT Whisper local
- [ ] Envoi WebSocket JSON vers World Model
- [ ] Gestion bruit ambiant (seuil adaptatif)
- [ ] Tests pytest avec mock audio

## Format de sortie WebSocket
```json
{
  "type": "audio_transcript",
  "timestamp": "2026-07-29T08:30:00",
  "data": {
    "transcript": "Luca's, quelle heure est-il ?",
    "confidence": 0.92,
    "language": "fr",
    "duration_seconds": 2.5
  }
}
```

## Dépendances
- `pyaudio`, `numpy`, `openai-whisper` (local), `webrtcvad`

## Validation
```bash
pytest tests/test_audio_watcher.py -v
```

## Notes
- Whisper local via `whisper.load_model("base")` (téléchargement auto)
- VAD pour éviter de transcrire le silence
- Buffer circulaire de 30 secondes max
- Ne pas envoyer si transcript < 3 caractères
