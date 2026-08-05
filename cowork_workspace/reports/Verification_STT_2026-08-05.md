# STT — vérification de l'existant (pas de nouvelle décision)

**Date** : 05/08/2026
**Objet** : la demande du jour redemandait de vérifier si `faster-whisper` était déjà en place à la place de `whisper.cpp`. Réponse courte : **oui, déjà fait**, mesuré et calibré le 03/08/2026 (`reports/Comparatif_STT_LucasAI_2026-08-03.md`, `modules/stt_engine.py`). Cette note ne relance pas la comparaison — elle confirme qu'elle reste valide deux jours plus tard, et ajoute un seul élément nouveau trouvé en revérifiant.

## Ce qui est déjà acquis (rappel, non retesté ici)

- `modules/stt_engine.py` tourne en `device="cpu"` explicitement, `STT_MODEL_SIZE = "small"` — choix mesuré (WER 0,00-0,09 en "small" contre 0,27-0,42 en "base" sous bruit réaliste), pas deviné.
- Le choix CPU n'est pas qu'un contournement d'un bug GPU ponctuel : il évite aussi la contention VRAM avec Ollama — argument renforcé, pas affaibli, par la bascule sur `gpt-oss:20b` (qui laisse encore moins de marge VRAM que `qwen2.5:7b` à l'époque du rapport du 03/08 — voir `Comparatif_VLM_LucasAI_2026-08-05.md` §1).

## Le seul point revérifié aujourd'hui

Le rapport du 03/08 notait que le correctif du bug cuBLAS Blackwell (RTX 50-series) dans CTranslate2 était *"déjà fusionné en amont... mais les binaires distribués n'ont pas encore tous été republiés"* — donc pas garanti disponible. Revérifié ce jour : l'issue amont ([OpenNMT/CTranslate2#1865](https://github.com/OpenNMT/CTranslate2/issues/1865)) est bien **fermée, liée à la pull request #1937** — le correctif est confirmé mergé.

**Sans effet sur la recommandation** : la décision de rester en CPU ne repose pas sur ce bug précis (il ne concerne que le mode GPU), mais sur la contention VRAM avec Ollama, qui reste valable — et s'est même renforcée avec `gpt-oss:20b`. Aucun changement à apporter.

## Ce qui n'a pas été retouché

Conformément aux règles de la demande : aucune modification de `modules/stt_engine.py`, `config.py`, `ROADMAP.md` ou `VISION_LONG_TERME.md`. Le point de calibration du barge-in (point 5 des points bloqués) reste, comme prévu, à tester par Cyril en conditions réelles — non traité ici.

---

*Lecture seule sur `ROADMAP.md`, `reports/Comparatif_STT_LucasAI_2026-08-03.md`, `modules/stt_engine.py` (vérification de configuration uniquement) — aucun fichier source modifié.*
