# Comparatif STT local — faster-whisper vs whisper.cpp vs whisper (référence OpenAI)

**Date** : 03/08/2026
**Contexte** : Luca's AI fait déjà tourner Ollama en continu sur la RTX 5080 (16 Go VRAM) du PC de Cyril — le choix du moteur STT ne se fait pas dans l'absolu, mais avec une carte graphique déjà partiellement occupée.

## Recommandation en une phrase

**Rester sur faster-whisper, en le gardant explicitement en CPU (`device="cpu"`)** — c'est déjà l'implémentation en place dans `modules/stt_engine.py`, elle est déjà calibrée (`STT_MODEL_SIZE = "small"`, mesuré par Cyril/Claude Code le 03/08/2026), et c'est la seule des trois options qui évite complètement les problèmes actuels de support GPU sur RTX 5080/Blackwell détaillés plus bas. Migrer vers whisper.cpp ou vers le GPU n'apporterait aujourd'hui aucun bénéfice qui justifie le risque ou le coût de migration.

---

## 1. Rappel du contexte déjà établi dans le projet

Trois éléments déjà actés dans `ROADMAP.md`/`config.py`, à ne pas re-décider à la légère :

- **`modules/stt_engine.py` tourne déjà sur `device="cpu"` explicitement**, pas `"auto"`. Le choix initial de `"auto"` avait provoqué un plantage réel le 02/08/2026 (`Library cublas64_12.dll is not found` — CUDA absent/mal configuré sur cette machine à ce moment-là) ; le commentaire du module documentait déjà l'intention "tourner en CPU pour ne pas se disputer la VRAM avec Ollama" avant même ce bug.
- **`STT_MODEL_SIZE` a été mesuré, pas deviné** : `"base"` donnait un WER de 0,27 à 0,42 sous bruit réaliste (SNR 5 dB, micro de téléphone), `"small"` un WER de 0,00 à 0,09 sur les deux mêmes phrases — pour un coût CPU de ~0,8 s au lieu de ~0,3 s, jugé négligeable pour un message vocal non temps réel. `STT_MODEL_SIZE` est passé à `"small"` le 03/08/2026 sur cette base.
- **La carte (RTX 5080, 16 Go) est déjà partagée** entre le modèle de chat (`qwen2.5:7b`, ~5 Go), l'embedding RAG (`nomic-embed-text` via Ollama, léger — le tableau de modèles de `CLAUDE.md` prévoyait `bge-m3`, mais l'implémentation réelle documentée dans `ROADMAP.md` utilise `nomic-embed-text`), et une vision `internvl2` (~8 Go) prévue pour la v1.1 mais actuellement désactivée (`VLM_ENABLED = False`). Si la vision est un jour réactivée, la marge VRAM libre se resserre fortement — c'est un argument qui pèse pour l'avenir, pas seulement pour aujourd'hui.

## 2. Les trois options, ce qu'elles sont réellement

| | **whisper** (référence OpenAI) | **faster-whisper** | **whisper.cpp** |
|---|---|---|---|
| Nature | Implémentation Python/PyTorch d'origine | Réimplémentation via **CTranslate2** (moteur d'inférence optimisé C++/CUDA), mêmes poids | Portage C/C++ pur (bibliothèque **ggml**), mêmes poids, zéro dépendance Python/PyTorch |
| Dépendances | PyTorch complet (lourd, adapté recherche/fine-tuning) | `faster-whisper` (pip), CUDA 12 + cuBLAS + cuDNN 9 pour le GPU ; CPU géré nativement | Binaire natif autonome, aucune dépendance Python — intégration nécessiterait un appel subprocess ou un binding (`pywhispercpp`, moins mûr) |
| Intégration actuelle dans Luca's | Aucune | **Déjà en place** (`modules/stt_engine.py`, testé, calibré) | Aucune — migration à faire de zéro |

## 3. Comparatif chiffré (vitesse, mémoire, précision)

| Critère | whisper (référence) | faster-whisper | whisper.cpp |
|---|---|---|---|
| Vitesse GPU (large-v3, carte NVIDIA récente type RTX 4070) | ~1× temps réel (référence, la plus lente) | **~12× temps réel** (int8) — jusqu'à 4× plus rapide que la référence | ~8× temps réel (pas d'accélération NVIDIA aussi mature que CTranslate2) |
| Vitesse CPU (modèle `base`) | Très lente, non conçue pour le CPU | **~20× temps réel** | ~15× temps réel |
| VRAM (modèle `large`, GPU) | ~10 Go (fp16/fp32 PyTorch) | **~2,5-2,9 Go** (int8 quantifié) | ~3-3,9 Go |
| RAM (CPU, par taille de modèle) | Élevée, peu optimisée | `tiny`/`base` ~1 Go, `small` ~2 Go, `medium` ~5 Go, `large-v3` ~10 Go (comparable entre faster-whisper et whisper.cpp, les deux quantifient) | idem faster-whisper |
| Précision (WER) | Référence — même poids que les deux autres | **Identique** à la référence (quantification int8 = perte négligeable) | **Identique** à la référence (ggml quantifié = perte négligeable) |
| Overhead CUDA fixe par process (si GPU) | ~300-800 Mo (contexte CUDA), payé une fois pour toutes par process, indépendamment de la taille du modèle | idem | idem |

Les trois donnent la même précision de transcription puisqu'ils partent des mêmes poids Whisper — la différence se joue entièrement sur la vitesse et l'empreinte mémoire, pas sur la qualité.

## 4. Le point qui change tout pour Luca's : RTX 5080 = Blackwell, architecture très récente

C'est l'élément le plus important trouvé en recherchant spécifiquement pour ce PC, et il n'est documenté nulle part dans le projet actuellement :

- **faster-whisper (CTranslate2) plante sur RTX 50-series avec `CUBLAS_STATUS_NOT_SUPPORTED`** dès qu'on utilise la quantification int8 par défaut — les tenseurs INT8 de Blackwell exigent un padding que les anciennes versions de CTranslate2 ne posent pas. Contournement connu : forcer `compute_type="float16"` au lieu de laisser l'int8 par défaut. Le correctif est déjà fusionné en amont dans CTranslate2, mais les binaires distribués n'ont pas encore tous été republiés avec — donc pas garanti disponible aujourd'hui selon la version installée.
- **whisper.cpp ne compile pas nativement son backend CUDA sur RTX 5080** : `nvcc` échoue avec `Unsupported gpu architecture 'compute_120'` (Blackwell). Contournement trouvé par un utilisateur : forcer `-DCMAKE_CUDA_ARCHITECTURES="86"` (cible l'architecture Ada, plus ancienne) — ça compile, mais ça tourne alors en couche de compatibilité, pas optimisé pour la carte réelle.
- **whisper (référence OpenAI/PyTorch)** dépend de PyTorch, dont le support officiel de `sm_120` (Blackwell) fait aussi l'objet de tickets ouverts récents — même famille de friction.

**Autrement dit : les trois options ont actuellement un accroc connu sur GPU Blackwell.** Ce n'est pas rédhibitoire (des contournements existent), mais ça confirme que le GPU n'est, pour l'instant, un terrain confortable pour aucun des trois sur cette carte précise — un argument de plus pour ne pas y toucher tant que ce n'est pas nécessaire.

## 5. Le facteur décisif : la VRAM ne se partage jamais gratuitement

Indépendamment du bug Blackwell ci-dessus, la contrainte de fond reste la même : **chaque process qui touche le GPU paie un contexte CUDA fixe (environ 300 à 800 Mo selon le driver et le framework), et ce coût est payé indépendamment par chaque process** — Ollama ne le mutualise pas avec un second process STT qui viendrait s'ajouter. Sur une carte de 16 Go déjà occupée par `qwen2.5:7b` (~5 Go) et vouée à accueillir `internvl2` (~8 Go) en v1.1, ajouter un second contexte CUDA pour une tâche aussi ponctuelle qu'un message vocal (quelques secondes, pas du temps réel continu) n'a pas de sens : le gain de vitesse (CPU "small" ≈ 0,8 s, largement sous le seuil de perception pour un message vocal) ne compense pas le risque de contention, de fragmentation VRAM, ou simplement de future casse le jour où la vision sera réactivée.

## 6. Pourquoi ne pas migrer vers whisper.cpp malgré ses qualités

whisper.cpp reste un choix légitime dans l'absolu (aucune dépendance Python/PyTorch, empreinte très légère, très répandu sur edge/mobile) — mais pour Luca's aujourd'hui :

- Le module `modules/stt_engine.py` est **déjà écrit, testé (WER mesuré, faux positifs éliminés méthodiquement) et calibré** sur faster-whisper — migrer signifierait tout rejouer (mesures WER, intégration à `api/server.py`, tests) pour un gain non démontré, puisque la précision est identique entre les deux et que faster-whisper reste la référence la plus rapide en CPU également.
- L'intégration Python de faster-whisper est native (`pip install faster-whisper`) ; whisper.cpp exigerait soit un appel à un binaire externe (subprocess, moins propre dans une architecture FastAPI), soit un binding Python tiers moins mature.
- Le seul avantage réel de whisper.cpp pour Luca's serait le streaming temps réel bas niveau (utile pour une future transcription continue) — non pertinent aujourd'hui puisque le besoin actuel est la transcription d'un message vocal ponctuel, pas un flux continu.

## 7. Pourquoi exclure whisper (implémentation de référence OpenAI)

Aucun avantage identifié pour ce projet : plus lente que faster-whisper aussi bien sur GPU (jusqu'à 4× plus lent) que sur CPU (non optimisée pour ce cas d'usage), dépendance PyTorch complète et lourde pour un gain de précision nul (mêmes poids que les deux autres). Pertinent uniquement pour du fine-tuning ou de la recherche — pas pour de l'inférence en production locale.

## 8. Ce qui pourrait faire changer d'avis plus tard

- Si un vrai besoin de **transcription continue/temps réel** apparaît (écoute ambiante contextuelle "maison", `IDEAS.md` #71, actuellement en pause) : whisper.cpp (mode streaming) deviendrait le candidat naturel à réévaluer — mais uniquement en CPU pour les mêmes raisons de VRAM, ou après un arbitrage GPU explicite avec Cyril si le besoin de latence l'exigeait vraiment.
- Si Cyril décide un jour d'ouvrir la vision (`internvl2`) **et** de vouloir un STT GPU simultanément : revérifier à ce moment-là l'état du support Blackwell dans CTranslate2/whisper.cpp (les deux évoluent vite, les correctifs cités ci-dessus sont très récents) plutôt que de se fier à cette note.
- `distil-whisper` ou `large-v3-turbo` (variantes accélérées, compatibles CTranslate2/faster-whisper) pourraient être une piste si jamais la précision de `"small"` devenait insuffisante sans vouloir payer le coût CPU de `"medium"` — non nécessaire aujourd'hui vu les WER déjà mesurés.

---

## Sources

- [faster-whisper vs whisper.cpp vs OpenAI Whisper (2026) — Codersera](https://codersera.com/blog/faster-whisper-vs-whisper-cpp-speech-to-text-2026/)
- [Whisper.cpp vs faster-whisper 2026: STT Speed Test — PromptQuorum](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
- [Faster Whisper crashes on RTX 50-series (cuBLAS NOT_SUPPORTED) unless using float16 — SubtitleEdit #10180](https://github.com/SubtitleEdit/subtitleedit/issues/10180)
- [Compiling Error Ubuntu RTX 5080: nvcc fatal : Unsupported gpu architecture 'compute_120' — whisper.cpp #3030](https://github.com/ggml-org/whisper.cpp/issues/3030)
- [Running Multiple Local Models: Memory Management Strategies — SitePoint](https://www.sitepoint.com/multiple-local-models-memory-management/)
- [Ollama VRAM Requirements: Complete 2026 Guide — LocalLLM.in](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)
- [faster-whisper — CTranslate2-Optimized OpenAI Whisper for GPU Production — VexaScribe](https://vexascribe.com/faster-whisper)
- [Faster-Whisper Setup Guide (2026): 4x Faster Local Speech-to-Text — Local AI Master](https://localaimaster.com/blog/faster-whisper-guide)

*Croisé avec `ROADMAP.md` §5.4 (mesures WER réelles du 03/08/2026) et `config.py`/`modules/stt_engine.py` (implémentation actuelle) — lus en lecture seule sur `C:\OrionAI`, aucun fichier source modifié.*
