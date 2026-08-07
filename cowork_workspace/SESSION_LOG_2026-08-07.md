# SESSION_LOG — Audit avatar Godot + watchdog VRAM
**Date :** 07/08/2026
**Nature de la session :** audit complet + une seule brique d'implémentation
(watchdog VRAM), conformément au brief de session reçu. Rien d'autre n'a été
construit ni committé côté visuel (mesh, shader, HUD) — voir section 5.

---

## 1. Résultats bruts de l'audit

### 1.1 État du visage actuel

**Confirmé, en lisant `Lucas3D/scenes/face/face_root.tscn` directement** :

```
Head      -> SphereMesh (radius 2.5, échelle 1.0 / 1.08 / 0.92)
EyeLeft   -> SphereMesh (radius 0.45)
EyeRight  -> SphereMesh (radius 0.45)
Mouth     -> BoxMesh (1.4 × 0.24 × 0.18)
```

Trois sphères et un cube. Aucune autre géométrie. Le brief avait raison.

**Confirmé, en lisant `Lucas3D/scenes/hud/widget_system.gd`** : `cpu_bar`,
`ram_bar`, `gpu_bar` sont trois `ProgressBar` standard (linéaires), pas de
widget circulaire.

**Fichiers `.gd`/`.tscn` impliqués dans le rendu actuel de l'avatar** (chemins
complets, `Lucas3D/`) :

```
main.gd, main.tscn
scenes/face/face_controller.gd, scenes/face/face_root.tscn
scenes/hud/chat_message.gd, scenes/hud/chat_message.tscn
scenes/hud/hud_canvas.tscn, scenes/hud/hud_manager.gd
scenes/hud/widget_audio.gd, scenes/hud/widget_audio.tscn
scenes/hud/widget_chat.gd, scenes/hud/widget_chat.tscn
scenes/hud/widget_clock.gd, scenes/hud/widget_clock.tscn
scenes/hud/widget_system.gd, scenes/hud/widget_system.tscn
scripts/_expr.gd, scripts/audio_visualizer.gd, scripts/auto_hide.gd
scripts/global.gd, scripts/websocket_client.gd, scripts/window_manager.gd
```

### 1.2 WebSocket Godot ↔ FastAPI

**Statut réel : NON corrigé.** Lu directement dans
`Lucas3D/scripts/websocket_client.gd` (ligne 17) :

```gdscript
@export var websocket_url: String = "ws://127.0.0.1:8000/ws"
```

Aucun paramètre `?token=` n'est jamais envoyé (`send_message`,
`_send_heartbeat`, ligne 124-129 — aucune trace de jeton).

Ce n'est pas une hypothèse : `ROADMAP.md` l. 7104-7122 documente que le
serveur est passé en HTTPS avec authentification active, et que le client
Godot, resté en `ws://` sans jeton, échoue systématiquement
(`InvalidMessage`) — qualifié d'« étape 2, rien n'a été touché » le
06-07/08/2026. Seul commit touchant ce fichier depuis : le renommage
Orion→Lucas (`e9bf6c4`), qui ne change aucune logique. **La situation
décrite le 06-07/08 est donc toujours exactement celle d'aujourd'hui.**

Conséquence pratique : le chat entre Godot et l'API ne fonctionne pas
actuellement. Sans lien avec le watchdog VRAM (testé sans avoir besoin du
chat — voir section 2).

### 1.3 VRAM — mesures fraîches du jour (07/08/2026, ~12h30-12h45 UTC)

| Configuration | VRAM utilisée | VRAM libre |
|---|---|---|
| Rien chargé côté Ollama, Godot arrêté (baseline) | 3 644 – 3 662 Mo | 12 316 – 12 334 Mo |
| `gpt-oss:20b` seul chargé, Godot arrêté (3 échantillons, stable) | 15 419 – 15 427 Mo | 546 – 559 Mo |
| + Godot avatar lancé (600×600 coin, rendu actif), immédiatement après | 15 665 Mo | 313 Mo |
| Godot arrêté à nouveau (process absent, vérifié) | 15 432 Mo | ~546 – 559 Mo |
| Test de charge forcée (section 2) : `gpt-oss:20b` + Godot relancé | 15 388 Mo (mesuré par le module lui-même) | 570 – 590 Mo |

**⚠️ Écart avec la mesure du 06-07/08/2026 (marge minimale 805 Mo,
`gpt-oss:20b` + Godot actif 24 min)** : aujourd'hui, `gpt-oss:20b` **seul**,
sans même lancer Godot, laisse déjà **moins** de marge (546-590 Mo) que les
805 Mo mesurés il y a un jour avec Godot en plus. Cause probable, **non
confirmée formellement** : plus d'applications ouvertes sur ce poste
aujourd'hui (baseline à ~3 650 Mo — Chrome ×2, Edge ×3, VS Code, Claude
desktop ×2, Steam, ChatGPT Desktop, Widgets — contre une baseline non
recomparée dans les mêmes conditions le 06-07/08). **À ne pas traiter comme
un fait acquis** : à remesurer dans des conditions comparables si Cyril veut
trancher plus finement.

**Incohérence interne notée, pas lissée** : le delta immédiat au lancement
de Godot (+27 Mo, 15 638→15 665) ne correspond pas au delta observé après
son arrêt (-233 Mo, 15 665→15 432). Cohérent avec la réserve déjà posée dans
`ROADMAP.md` (« nvidia-smi ne rend qu'un delta global sur ce pilote, et
d'autres applications bougent sur ce GPU ») — pas un défaut du dispositif de
mesure de cette session, mais une limite connue de `nvidia-smi` sur cette
machine.

**Conséquence directe pour le watchdog** : le seuil suggéré par le brief
(1,5 Go) est **déjà franchi par le simple chargement du modèle principal**,
sans même lancer Godot. Avec ce seuil tel quel, Godot ne pourrait quasiment
jamais rester actif dans les conditions mesurées aujourd'hui. Le seuil a été
implémenté à la valeur suggérée (configurable), avec ce constat documenté en
commentaire dans `config.py` — **pas corrigé silencieusement**. Décision
laissée à Cyril.

### 1.4 Testé par Cyril vs généré sans validation

| Élément | Statut |
|---|---|
| Fenêtre 600×600 coin bas-droit, Gestionnaire des tâches accessible | **Validé par Cyril** (`ROADMAP.md`, étape 1, 06-07/08) — seul élément visuel avec validation humaine explicite trouvée dans l'historique |
| Palette « bleu glacier » désaturée + hiérarchie de luminosité (tête 0,12, traits 0,26-0,30) | **Généré, non validé.** `ROADMAP.md` l. 374-376 : « décisions prises seul, réversibles, à valider » — aucune trace de validation ultérieure |
| Correctifs bouche/yeux/inclinaison (02/08) | **Généré, non validé** — mêmes conditions que ci-dessus (mesurés, corrigés, jamais revus par Cyril en rendu) |
| `websocket_client.gd` (wss + jeton) | **Ni corrigé, ni testé, ni validé** — confirmé cassé aujourd'hui encore (section 1.2) |
| `demos/arreter_lucas3d.bat` | **Testé par Claude Code** (3 essais, 2 échecs réels révélant des bugs CRLF/faux-positif, corrigés, 3e réussi et vérifié indépendamment). **Pas testé par Cyril** — `ROADMAP.md` le dit explicitement : il a fermé par la croix |
| `demos/lancer_lucas3d.ps1` | Utilisé et fonctionnel dans **cette** session (2 lancements + 2 arrêts propres). Pas de trace d'utilisation par Cyril lui-même |
| HUD (`hud_canvas.tscn` + 5 widgets) | **Masqué** depuis le 07/08 (`_masquer_hud()`). Le seul aperçu que Cyril en a eu était un écart de périmètre accidentel avant le masquage — jamais montré intentionnellement dans son état actuel |

### 1.5 Intégrité de `REFERENCE_VISUELLE_AVATAR.md`

**Vérifié : le fichier est complet, seul le message de commit était
tronqué.** `git show --stat 0d4ac4c` confirme que le texte du message de
commit s'arrête bien en plein mot (« C' »). Mais le contenu du fichier
lui-même (357 lignes) est intact et se termine proprement par « *Consolidé
le 07/08/2026...* ». Aucune perte de contenu réelle — seule la description
du commit est coupée, ce qui n'affecte pas la lecture du document.

---

## 2. Statut du watchdog VRAM

**Implémenté** : `modules/vram_watchdog.py` (142 lignes), réglages dans
`config.py` (`VRAM_WATCHDOG_THRESHOLD_MB = 1536`, `VRAM_WATCHDOG_POLL_SECONDS
= 12.0`).

- Poll la VRAM libre via `GPUtil` (déjà une dépendance du projet, réutilisée
  telle quelle depuis `core/world_model.py` — pas de nouvelle dépendance).
- Sous le seuil : arrête `Lucas3D.exe` via `taskkill /F` (même méthode que
  `demos/arreter_lucas3d.bat`, pas de P/Invoke).
- Au-dessus du seuil, après un repli : journalise que le retour à Godot est
  **possible**, mais ne relance **rien automatiquement** — un compagnon de
  bureau ne se relance pas seul sans Cyril devant l'écran. Choix documenté
  en commentaire dans le module.
- Chaque bascule journalisée dans `system_events` (table déjà existante,
  `memory/lucas_memory.db`, via `save_event_from_any_thread` — aucun nouveau
  système de stockage), avec horodatage et VRAM libre au moment du switch.

**Testé comment** :

1. **7 tests unitaires** (`test_vram_watchdog.py`), tout mocké (`GPUtil`,
   `tasklist`, `taskkill`, l'écriture en base) — logique de seuil, non-
   répétition de la bascule, restauration. Tous passent, ainsi que la suite
   complète du dépôt (**1453 passed**, aucune régression).
2. **Test de charge forcée réel, en conditions réelles** (gate demandée par
   le brief) :
   - Godot relancé réellement (`demos/lancer_lucas3d.ps1`), `gpt-oss:20b`
     chargé réellement dans Ollama.
   - VRAM libre mesurée par le module lui-même : **570-590 Mo**, sous le
     seuil de 1 536 Mo.
   - `VramWatchdog().check_once()` exécuté **sans aucun mock** : a bien
     détecté `Lucas3D.exe` actif, l'a arrêté réellement — confirmé absent
     ensuite via `tasklist`.
   - Événement `vram_watchdog_fallback` retrouvé **dans la vraie base**
     (`memory/lucas_memory.db`, `system_events`, id 616) : *« VRAM libre 570
     Mo < seuil 1536 Mo — Lucas3D.exe arrêté, repli sur l'avatar 2D »*.
   - Trajet retour testé aussi : modèle déchargé (`keep_alive: 0`), VRAM
     remontée à 13 262 Mo libres, second `check_once()` réel a bien basculé
     `in_fallback` à `False` et journalisé `vram_watchdog_restore` (id 617)
     dans la vraie base.
3. **Lint/typage** : `ruff check` propre (2 avertissements `PLW1510`
   corrigés — `check=False` explicite sur les deux appels `subprocess.run`).
   `mypy` : un seul avertissement, l'absence de stubs pour `GPUtil` —
   **préexistant**, identique à celui déjà présent sur
   `core/world_model.py`, pas une régression introduite ici.

**État final du poste, signalé explicitement** : `Lucas3D.exe` arrêté,
`gpt-oss:20b` déchargé d'Ollama (déchargé volontairement pendant le test du
trajet retour). VRAM libre en fin de session : ~13 260 Mo. Rien n'a été
laissé allumé qui ne l'était pas avant la session.

---

## 3. Anomalies et incohérences trouvées

- **Écart de marge VRAM significatif** entre la mesure d'aujourd'hui et
  celle du 06-07/08 — détaillé en section 1.3. Signalé, pas lissé.
- **`websocket_client.gd` toujours cassé** — pas une anomalie nouvelle, mais
  confirmation que « l'étape 2 » citée le 06-07/08 n'a toujours pas été
  traitée, malgré plusieurs commits de documentation depuis.
- **`demos/arreter_lucas3d.bat` invoqué via `cmd.exe /c` depuis l'outil Bash
  (Git Bash) de cette session a échoué silencieusement** — aucune erreur
  retournée, mais le process Lucas3D restait actif. Le même script, invoqué
  via PowerShell, a fonctionné correctement (`[OK] Lucas3D a ete arrete` /
  `[OK] Verifie`). Cause non creusée plus loin (pas nécessaire pour la
  session), mais à noter : **utiliser PowerShell, pas `cmd.exe /c` depuis
  Git Bash, pour ce script** — première observation de ce genre, jamais
  documentée avant.
- **Ollama a déchargé `gpt-oss:20b` tout seul** (`keep_alive` par défaut de
  5 minutes) pendant l'audit, entre deux mesures VRAM — découvert en
  retrouvant un chiffre incohérent avec la mesure précédente. Pas un
  problème du projet, mais un facteur opérationnel à connaître : la marge
  VRAM va varier automatiquement au fil des expirations Ollama, sans
  rapport avec Godot.
- Aucune trace du code Three.js « fourni par Cyril » ni de la maquette
  interactive citée dans le brief d'origine du 07/08 (recherché dans tout le
  dépôt, y compris `cowork_workspace/`) — déjà signalé dans
  `REFERENCE_VISUELLE_AVATAR.md` §0, reconfirmé ici : rien à récupérer.

---

## 4. Mise à jour de `ROADMAP.md`

Watchdog VRAM déplacé vers « fait », en nouvelle section datée du
07/08/2026, insérée avant « ## 6. Renommage Luca's ». **Aucune section
mesh/HUD n'a été touchée** — elles restent explicitement en attente.

---

## 5. Ce qui n'a PAS été exécuté cette session (rappel)

Conformément au brief : mesh de tête définitif, shader hologramme, jauges
circulaires, HUD plein écran — **rien importé, rien committé**. Ces pistes
restent documentées dans `cowork_workspace/REFERENCE_VISUELLE_AVATAR.md`
§5.1-5.4, prêtes à être lancées sur validation explicite de Cyril, une fois
ses références visuelles complémentaires transmises.

Aucune supposition n'est faite ici sur ce que Cyril voudra pour le visuel —
ce point se tranche avec lui.
