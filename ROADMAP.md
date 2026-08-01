# ROADMAP.md — Plan d'action Luca's AI (ex-OrionAI)

Référence croisée : voir `IDEAS.md` pour le détail complet de chaque fonctionnalité citée ici.

> **Mise à jour du 30/07/2026** : S1 (Cerveau solide — FastAPI unique) est officiellement validé de bout en bout. Prochaine étape : S2 (Mémoire enrichie, RAG, TTS, Finance CSV).
>
> **Renommage acté** : le projet s'appelle désormais **Luca's** (ex-Orion). Le renommage technique complet (titre fenêtre, prompts système, nom de dossier) est différé — pas urgent, sera fait une fois le socle S2-S3 stabilisé. Voir section 6.

---

## 1. État actuel (au 30/07/2026)

### ✅ Modules validés et testés en conditions réelles
1. Chat avec streaming QThread (UI PySide6)
2. Mémoire persistante SQLite (`memory/orion_memory.db`) — confirmée comme seule source de vérité
3. FastAPI unique (`api/server.py` v0.2) — **testé de bout en bout aujourd'hui** :
   - `GET /status` ✅
   - `GET /system` ✅ (World Model v1 : CPU, RAM, fenêtre active via psutil + pywin32)
   - `POST /chat` ✅ (connecté à `OrionCore.ask()` → Ollama → réponse réelle, plus de stub)
   - `WS /ws` — endpoint créé, protocole minimal état/parole, **pas encore testé avec un vrai client** (Godot/mobile viendront en S6/S5)
4. Modèle LLM confirmé en usage réel : `qwen2.5:7b` (via Ollama)
5. Avatar 2D QPainter (v2)

### ⚠️ Statut réel à clarifier (non re-testés depuis l'audit initial)
- `modules/finance_manager.py`, `rag_manager.py`, `vision_manager.py`, `weather_manager.py`, `automation_manager.py`, `web_search.py` — à tester lors de S2/S3
- `Orion3D.exe` (Godot) — visage/fenêtre transparente fonctionne visuellement, mais `orion3d_bridge.py` fait uniquement écho, pas connecté à Ollama/OrionCore

### 🟡 Godot 4 — toujours en branche expérimentale (non bloquant)
Reclassé en Phase 6 (S5-S6), branche `experimental/godot-avatar`. Ne bloque pas la release.

---

## 2. Étape immédiate — Phase 2 : Mémoire enrichie & Finance (S2)

**Objectif : enrichir le cerveau maintenant qu'il répond correctement.**

| Tâche | Détail |
|---|---|
| Mémoire enrichie | Contexte conversation + events système (World Model) injectés dans le prompt |
| RAG documents personnels | Ingestion de documents, recherche vectorielle (ChromaDB déjà présent dans `data/`) |
| TTS intégré au chat | Bouton + lecture auto dans l'UI PySide6, brancher `modules/voice_manager.py` (à re-tester) |
| Finance CSV | Import + catégorisation, dashboard simple (MVP, pas d'API bancaire — règle actée) |

**Prérequis avant de commencer S2 :** vérifier qu'Ollama tourne sans doublon de process (voir section 5 — point de vigilance infra).

---

## 3. Jalons futurs

| Phase | Semaine | Focus | Statut |
|---|---|---|---|
| **Phase 0 — Audit** | S0 | Nettoyage, inventaire | ✅ Fait (avec incident de suppression accidentelle résolu — voir CLAUDE.md) |
| **Phase 1 — Cerveau solide** | S1 | FastAPI unique + World Model | ✅ **Fait et validé aujourd'hui** |
| **Phase 2 — Mémoire & Finance** | S2 | RAG, TTS, Finance CSV | 🔴 Priorité actuelle |
| **Phase 3 — Vision & Voix** | S3-S4 | VLM écran, STT, Avatar QPainter V3, 5 modes de présence | À venir |
| **Phase 4 — Expansion** | S5-S6 | PWA mobile, sync, Godot 4 V1 (branche expérimentale) | À venir |
| **Phase 5 — Polish** | S7-S8 | Sécurité finale, packaging, release v1.0 | À venir |

---

## 4. Principe directeur

> **"Cerveau solide d'abord, visage beau ensuite. Mais le visage ne part jamais."**

Architecture serveur validée aujourd'hui : une seule API FastAPI, `/ws` unique partagé par Godot et mobile (futur), routes REST classiques. Pas de serveur dupliqué.

Sécurité validée : liste blanche stricte pour toute action système. Jamais de script généré dynamiquement par le LLM.

---

## 5. Points de vigilance infra (leçons du 30/07/2026)

- **Ollama en double instance** : l'appli tray Ollama relance automatiquement un serveur si on tue le process en CLI. Résultat : deux instances sur le port 11434, chacune avec un jeu de modèles différent, causant des 404 "model not found" alors que le modèle existe bel et bien. **Solution appliquée** : tuer `ollama.exe` ET `ollama app.exe`, puis relancer uniquement via `ollama serve` en CLI. **À faire avant de clore Phase 2** : vérifier dans les paramètres Ollama si le démarrage automatique avec Windows est activé, et le désactiver si besoin pour éviter que le problème revienne à chaque redémarrage du PC.
- **SQLite et threads FastAPI** : `OrionCore()` est recréé à chaque requête `/chat` plutôt que partagé en singleton, pour éviter les erreurs de thread SQLite. Fonctionne car tout l'état vit dans le fichier `.db`, pas en mémoire Python. À garder en tête si on introduit du code qui suppose un état Python persistant entre requêtes.
- **Toujours vérifier l'existence d'un backup avant suppression** : lors du nettoyage Phase 0, les vrais dossiers `core/` et `ui/` ont été supprimés par erreur (confusion avec les fantômes `Fichier core/`/`Fichier ui/`, noms très proches). Récupérés via un zip de backup antérieur (`OrionProject/OrionAI.zip` du 26/07). Réflexe à garder : zipper le dossier projet avant tout nettoyage manuel.

---

## 6. Renommage Luca's — différé, pas oublié

Renommage acté par Cyril le 29-30/07/2026. À faire une fois S2 stabilisé :
- Titre fenêtre PySide6, prompts système du LLM, messages TTS
- Éventuellement le nom du dossier projet (`C:\OrionAI` → autre chose) — optionnel
- Mise à jour de `CLAUDE.md`, `ROADMAP.md`, `IDEAS.md` (remplacement des mentions "Orion"/"OrionAI")

Ne pas faire ce renommage avant S2 pour éviter de casser des chemins/imports en plein travail sur la mémoire enrichie.

---

## 7. Règles de mise à jour de ce fichier

- Après chaque brique validée : déplacer l'élément vers "État actuel ✅", repréciser la nouvelle étape immédiate.
- Ne jamais sauter une phase pour une fonctionnalité "fun" tant que le socle n'est pas stable.
- Toute nouvelle idée émergente va dans `IDEAS.md`, pas ici.
