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

Sécurité validée : **liste blanche et confirmation pour toute action système à risque** — pas un bridage par défaut de tout le reste. Luca's a un accès large et réel à ce dont elle a besoin pour être utile ; c'est au moment du doute ou du risque qu'elle demande, et Cyril tranche. Jamais de script généré dynamiquement par le LLM, jamais d'exécution de code auto-généré hors sandbox. Formulation de référence : `VISION_LONG_TERME.md` §4 — en cas d'écart entre les deux fichiers, c'est la vision qui fait foi.

**État de `security/` au 01/08/2026 — niveau 0, observation seule.** Guardian, Privacy Shield et Ransomware Watch existent en ébauche testée (62 tests) : ils détectent et rapportent, ils n'agissent jamais. Aucun process tué, aucune connexion coupée, aucun fichier restauré, aucun appel à un service externe. Leur donner un pouvoir d'action défensif est une décision distincte, à valider par Cyril.

La détection de rançongiciel repose sur les **métadonnées seules** (extensions connues, notes de rançon, rafale de modifications) et sur des **fichiers-appâts** déployés explicitement. Elle ne lit jamais le contenu des documents : l'analyse d'entropie serait plus fiable mais obligerait le capteur à ouvrir les fichiers personnels — décision qui revient à Cyril.

**Surveillance continue branchée sur le daemon** (01/08/2026) : `SecurityMonitor` orchestre les trois capteurs depuis `orion_daemon.py` — process et réseau toutes les 5 minutes, fichiers toutes les 15. Les signaux ne sont rapportés qu'une fois : un état persistant (`data/security_state.json`) déduplique d'un balayage à l'autre et d'un redémarrage à l'autre, et oublie un signal après 3 jours d'absence pour que son retour soit de nouveau une information. Les alertes atterrissent dans `system_events`, donc dans le contexte que Luca's injecte au LLM.

Prochains niveaux envisageables : suivi des hooks clavier (keylogger), historique des connexions pour repérer les anomalies dans la durée, analyse d'entropie du contenu des fichiers (nécessite l'accord de Cyril — le capteur ouvrirait ses documents).

**Nouveau principe acté le 01/08/2026 — la liberté est conditionnée à la protection.** Guardian et Privacy Shield (`security/`) deviennent une dépendance directe de toute extension future des libertés d'action de Luca's : plus ils sont matures et testés, plus le périmètre d'autonomie peut s'élargir. Concrètement pour le séquencement de ce fichier, aucune phase n'ouvre de nouveaux droits d'action (OS Controller, automation, exécution autonome) tant que ces deux modules ne sont pas au moins ébauchés et testés. Ils n'appartiennent donc plus au « polish » de la Phase 5 — ce sont des prérequis. Doctrine : `VISION_LONG_TERME.md` §4.1, résumé opposable : `CLAUDE.md`.

---

## 5. Points de vigilance infra (leçons du 30/07/2026)

- **Ollama en double instance** : l'appli tray Ollama relance automatiquement un serveur si on tue le process en CLI. Résultat : deux instances sur le port 11434, chacune avec un jeu de modèles différent, causant des 404 "model not found" alors que le modèle existe bel et bien. **Solution appliquée** : tuer `ollama.exe` ET `ollama app.exe`, puis relancer uniquement via `ollama serve` en CLI. **À faire avant de clore Phase 2** : vérifier dans les paramètres Ollama si le démarrage automatique avec Windows est activé, et le désactiver si besoin pour éviter que le problème revienne à chaque redémarrage du PC.
- **SQLite et threads FastAPI** : `OrionCore()` est recréé à chaque requête `/chat` plutôt que partagé en singleton, pour éviter les erreurs de thread SQLite. Fonctionne car tout l'état vit dans le fichier `.db`, pas en mémoire Python. À garder en tête si on introduit du code qui suppose un état Python persistant entre requêtes.
- **Toujours vérifier l'existence d'un backup avant suppression** : lors du nettoyage Phase 0, les vrais dossiers `core/` et `ui/` ont été supprimés par erreur (confusion avec les fantômes `Fichier core/`/`Fichier ui/`, noms très proches). Récupérés via un zip de backup antérieur (`OrionProject/OrionAI.zip` du 26/07). Réflexe à garder : zipper le dossier projet avant tout nettoyage manuel.

---

## 6. Renommage Luca's — partie visible faite le 01/08/2026

**Fait** : tout ce que Cyril voit affiche désormais « Luca's » — `SYSTEM_PROMPT`
et `WINDOW_TITLE` dans `config.py`, titre de fenêtre, libellé de l'interlocuteur
dans le chat, placeholder de saisie, infobulles TTS, message « réfléchit… »,
titres et prose de `CLAUDE.md` et `README_INSTALL.md`.

**Volontairement inchangé** : tous les noms techniques — `OrionCore`,
`core/orion_core.py`, `orion_daemon.py`, `Orion3D/`, `memory/orion_memory.db`,
le chemin `C:\OrionAI`, l'organisation GitHub `OrionProject76`. Les renommer
casserait imports et chemins pour un gain nul.

**Leçon de cette session** : une première tentative par expression régulière
sur `\borion\b` a transformé `self.orion` en `self.luca's` — erreur de syntaxe
immédiate. Un renommage se fait par remplacements exacts, chaîne par chaîne,
jamais par motif générique sur du code.

### Ce qui reste (ancien contenu de cette section)

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
