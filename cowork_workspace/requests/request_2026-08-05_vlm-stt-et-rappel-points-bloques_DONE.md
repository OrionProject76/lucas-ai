# Demande — Tests VLM/STT + rappel points bloqués (hors-scope Claude Code)

**Date :** 05/08/2026
**Origine :** Cyril + Claude (Anthropic)
**Priorité :** Normale — n'affecte pas la priorité actuelle (avatar Godot 3D)

---

## ⚠️ À ne PAS toucher — 5 points réservés à Cyril devant son PC

Ces points nécessitent une présence physique (réseau, matériel, tests réels) et ne doivent pas être traités en autonomie, même partiellement :

1. Réservation DHCP (Livebox) pour fixer l'IP du PC
2. Installation Tailscale côté PC
3. Rotation du jeton API (`.env`)
4. Nettoyage du doublon Ollama (deux instances sur le même port — garder celle en IPv4)
5. Calibration du barge-in (mode diagnostic déjà prêt, à tester en conditions réelles)

Si l'un de ces points bloque une tâche ci-dessous, arrête-toi et note-le dans `reports/` plutôt que d'y toucher.

## Contexte — LLM déjà réglé, pas d'action ici

`gpt-oss:20b` a déjà été testé et retenu comme modèle principal (comparaison chiffrée contre qwen3:14b, gemma3:12b, deepseek-r1:14b, qwen2.5:7b — tokens/sec, VRAM réelle sous charge partagée, function calling, 15 essais tutoiement/relance). **Ne rien changer côté LLM.** Vérifier seulement que `CLAUDE.md` (tableau des modèles) reflète bien ce choix — corriger la doc si elle mentionne encore `deepseek-coder:33b` ou `qwen2.5` comme modèle principal.

## 1. VLM (vision écran) — recherche comparative complète, pas un seul candidat

**Problème :** `llava:13b` / `internvl2` (VLM actuellement suspendu, `VLM_ENABLED=False` suite à hallucinations documentées) sont dépassés. Ne pas se limiter à un seul candidat par défaut — appliquer la même rigueur que pour le choix du LLM principal (gpt-oss:20b avait été retenu après comparaison chiffrée contre 4 autres modèles, pas pris au premier essai).

**Action demandée :**
- Rechercher l'état actuel du marché des VLM utilisables en local via Ollama (ou compatibles), en priorisant ce qui est réellement disponible et à jour à la date du test — ne pas se fier uniquement à une liste figée à l'avance. `qwen2.5-vl:7b` est un point de départ raisonnable mais **pas une conclusion** : vérifier s'il existe mieux (ex. Qwen3-VL, Gemma vision, autres) et si c'est utilisable dans Ollama sans bug bloquant à ce jour (le module vision `mmproj` de Qwen3-VL avait un bug de câblage connu début août — revérifier si corrigé).
- Sélectionner 3 à 5 candidats sérieux compatibles avec la VRAM disponible (RTX 5080 16 Go, en tenant compte de gpt-oss:20b déjà chargé en parallèle).
- Comparer sur des critères mesurés, pas ressentis : VRAM réelle sous charge partagée, vitesse, qualité OCR/lecture d'écran en français, et surtout — critère prioritaire vu l'historique — **taux d'hallucination** sur des captures d'écran réelles du projet (pas des exemples génériques).
- Vérifier spécifiquement si le problème d'hallucination déjà documenté (contamination du contexte par l'historique de refus) persiste avec le(s) modèle(s) retenu(s), ou si c'était propre à llava.
- Documenter la comparaison (comme pour le LLM) avant de conclure — pas de choix par défaut non justifié.
- Ne réactiver `VLM_ENABLED=True` qu'après validation manuelle par Cyril sur plusieurs cas réels — pas automatique, même si le modèle choisi semble meilleur sur le papier.

## 2. STT — passer à faster-whisper si pas déjà fait

**Action demandée :**
- Vérifier si `faster-whisper` (backend CTranslate2) est déjà utilisé ; sinon l'intégrer à la place de whisper.cpp (whisper.cpp cible Mac/CPU, faster-whisper est le bon choix sur RTX 5080/NVIDIA).
- Dimensionner le modèle (`small`/`medium`/`large-v3`) selon la VRAM réellement disponible une fois gpt-oss:20b chargé — mesurer, ne pas supposer.
- Point de vigilance : la calibration du barge-in (point 5 bloqué ci-dessus) dépend de ce pipeline STT — ne pas la considérer comme terminée tant que Cyril n'a pas testé en réel.

## Règles générales

- Un module à la fois (VLM, puis STT), test réel entre chaque avant de passer au suivant.
- Ne pas modifier `ROADMAP.md`/`VISION_LONG_TERME.md` dans le cadre de cette demande — seule une correction factuelle de `CLAUDE.md` (tableau modèles) est autorisée si l'écart avec gpt-oss:20b est confirmé.
- Si ambiguïté ou dépendance à un des 5 points bloqués : ne pas deviner, déposer une note de blocage dans `reports/`.
