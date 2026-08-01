# MISSION 04 : webcam_watcher.py

## Contexte
Couche Perception (Layer 1). Doit capturer l'émotion et l'attention via la webcam.

## Objectif
Créer `perception/webcam_watcher.py` + `tests/test_webcam_watcher.py`

## Spécifications
- [ ] Thread séparé, non-bloquant
- [ ] Capture webcam avec `opencv-python` (frame toutes les 5 secondes)
- [ ] Détection visage avec `opencv` Haar Cascade ou DNN
- [ ] Analyse émotion basique (luminosité + mouvement = proxy fatigue/attention)
- [ ] Envoi WebSocket JSON vers World Model
- [ ] Gestion webcam non disponible (graceful degradation)
- [ ] Tests pytest avec mock frame

## Format de sortie WebSocket
```json
{
  "type": "webcam_analysis",
  "timestamp": "2026-07-29T08:30:00",
  "data": {
    "face_detected": true,
    "brightness": 120.5,
    "motion_score": 0.15,
    "attention_proxy": "focused",
    "fatigue_proxy": "low"
  }
}
```

## Dépendances
- `opencv-python`, `numpy`

## Validation
```bash
pytest tests/test_webcam_watcher.py -v
```

## Notes
- v1.0 : proxy simple (luminosité + mouvement)
- v1.1 : intégrer `deepface` ou modèle ONNX pour émotions réelles
- Toujours libérer la webcam (`cap.release()`)
- Ne pas bloquer si webcam occupée par autre app
