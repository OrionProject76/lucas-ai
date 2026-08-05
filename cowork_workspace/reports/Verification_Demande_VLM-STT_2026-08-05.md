# Vérification — demande VLM/STT/points bloqués du 05/08/2026

**Fichier traité** : `cowork_workspace/requests/request_2026-08-05_vlm-stt-et-rappel-points-bloques.md`

## Constat

Avant d'exécuter la demande, vérification de `cowork_workspace/reports/` (règle 9 de
`CLAUDE.md`) : **les deux volets de cette demande sont déjà traités par des rapports
existants**, dont l'un daté du jour même. Rien n'est dupliqué ici — cette note se
limite à confirmer la couverture et à signaler ce qui reste ouvert.

| Volet de la demande | Déjà couvert par | Statut |
|---|---|---|
| §0 — CLAUDE.md, tableau modèles reflète gpt-oss:20b | `Comparatif_VLM_LucasAI_2026-08-05.md` §5 (correction appliquée) | ✅ Vérifié directement dans `CLAUDE.md` (ligne Principal = `gpt-oss:20b`) — aucune trace de `deepseek-coder:33b` ou `qwen2.5` en Principal aujourd'hui |
| §1 — Comparatif VLM (3-5 candidats, VRAM, hallucination, Qwen3-VL) | `Comparatif_VLM_LucasAI_2026-08-05.md` (même date) | ✅ 4 candidats comparés (qwen2.5-vl:7b, qwen3-vl, minicpm-v4.6, gemma3:4b) + 2 exclus documentés (Moondream, InternVL3). Bug mmproj Qwen3-VL revérifié : toujours ouvert |
| §2 — STT faster-whisper | `Comparatif_STT_LucasAI_2026-08-03.md` | ✅ Confirmé aujourd'hui par lecture directe de `modules/stt_engine.py` : faster-whisper est le backend prioritaire, forcé CPU (`device="cpu"`), `STT_MODEL_SIZE` piloté par `config.py` — code inchangé depuis le rapport du 03/08 |

## Ce qui reste ouvert (ni cette note ni les rapports existants ne peuvent le clore)

Le rapport VLM du 05/08 le documente déjà explicitement en §4 : une session cloud/cowork
ne peut ni charger un modèle Ollama, ni le soumettre à une vraie capture d'écran du
projet, ni mesurer un taux d'hallucination réel. Cette limite est confirmée techniquement
ici — cette session n'a pas accès à PowerShell (mode restreint), donc pas davantage la
possibilité d'exécuter `ollama pull`/`ollama run` ou de mesurer la VRAM sous charge.

Ordre de test déjà proposé par le rapport VLM (qwen2.5-vl:7b, puis minicpm-v4.6 si besoin)
reste la marche à suivre — inchangé, rien à ajouter.

## Lien avec les 5 points réservés à Cyril

Aucun des 5 points bloqués (DHCP, Tailscale, rotation token, doublon Ollama, calibration
barge-in) n'a empêché la partie documentaire de cette demande — les deux rapports
existants sont de la recherche comparée, pas des tests réels. En revanche, deux d'entre
eux conditionnent directement l'étape suivante que **Cyril seul** peut faire :

- **Point 4 (doublon Ollama)** : une mesure fiable de VRAM réelle sous charge partagée
  (demandée explicitement au §1 de la demande) suppose une seule instance Ollama active —
  à vérifier avant tout test de candidat VLM, sinon les chiffres mesurés seraient faussés.
- **Point 5 (barge-in)** : sans rapport direct avec le VLM, mais rappelé ici parce que le
  pipeline STT qu'il calibre est le même que celui déjà validé au §2 — la note du 03/08
  le signale déjà, pas de nouvelle information ici.

Aucun de ces 5 points n'a été touché par cette session, conformément à la consigne.

## Fichiers touchés par cette session

Aucun — lecture seule de `CLAUDE.md`, `requirements.txt`, `requirements_daemon.txt`,
`modules/stt_engine.py`, `modules/vision_manager.py`, `config.py` (extraits via recherche),
et des deux rapports cités. Ce fichier est la seule écriture.
