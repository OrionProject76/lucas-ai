# 🔬 ORIONAI — ANALYSE COMPARATIVE KIMI × CLAUDE × LENOVO AURA
## Document de synthèse pour décision Cyril
**Date :** 28 Juillet 2026  
**Documents analysés :** 3 (Claude_v1.0, Lenovo_Aura, Vidéos_YouTube)

---

## 1. SYNTHÈSE DES TROIS SOURCES

### 1.1 Document Claude (Anthropic) — Réponse à Kimi
**Ton :** Direct, pragmatique, ingénieur.  
**Message central :** "Partons d'un état des lieux honnête, pas d'un optimisme non vérifié."

**Points clés :**
- ✅ Accord de fond sur la vision Desktop Pal
- ⚠️ Tableau de statuts Kimi = trop optimiste (fichiers générés ≠ testés)
- 🔧 Recommande UNE SEULE API FastAPI (pas deux serveurs)
- 🔧 Protocole Godot minimal d'abord (state + speak), pas d'émotions avant fiabilité
- 🔧 World Model = snapshot RAM + SQLite events (pas GraphRAG, pas mood estimate)
- 🔒 Sécurité : liste blanche de fonctions prédéfinies, pas de scripts générés par LLM
- 🎯 Feature à couper si délai serré : Godot 3D complet
- 📋 Ordre de construction : Nettoyage → Mémoire → Finance → FastAPI+PWA → Godot

### 1.2 Document Lenovo/Intel Aura
**Ton :** Corporate, premium, marketing technique.  
**Concepts clés à récupérer :**
- **Smart Modes** : Attention (bloque notifs), Partage (floute données sensibles), Énergie (modèle léger)
- **Function Calling** : Llama-3.1-8B-Instruct pour déclencher actions système
- **Vision multimodale** : Phi-3-Vision pour analyse écran/caméra temps réel
- **LAM (Large Action Model)** : LangGraph pour agents autonomes planifiant tâches complexes
- **UI premium** : Glassmorphism, neomorphisme, micro-interactions, mode sombre
- **Stack suggéré** : Electron/React ou Tauri/Rust pour UI, Python pour backend

### 1.3 Document Vidéos YouTube (Lenovo Aura Edition)
**Ton :** Démonstration produit, use cases concrets.  
**Fonctionnalités observées :**
- **Shield Mode** : Sécurité proactive (détection menaces, blocage réseau)
- **Attention Mode** : Productivité (bloque distractions, focus assisté)
- **Compagnon virtuel interactif** : Interface visuelle réactive, présence permanente
- **Techniques de repro** : Python + OpenCV + modification hosts + PyQt6

---

## 2. ANALYSE COMPARATIVE — KIMI vs CLAUDE

### 2.1 Tableau comparatif point par point

| Thème | Kimi (Ma vision) | Claude (Sa vision) | Verdict |
|-------|-----------------|-------------------|---------|
| **Statut réel** | "10 modules OK" (optimiste) | "Fichiers générés ≠ testés" (honnête) | ✅ **Claude a raison** — Je sous-estimais le gap entre "fichier existe" et "fonctionne en production" |
| **Architecture serveur** | FastAPI + bridge WebSocket séparé | UNE SEULE FastAPI avec /ws + routes REST | ✅ **Claude** — Moins de code, un seul point de vérité |
| **Bridge Godot** | Protocole riche (émotions, widgets, duration) | Protocole minimal (state + speak) | ⚖️ **Compromis** — Claude a raison sur le principe (YAGNI), mais on peut prévoir l'extensibilité sans l'implémenter tout de suite |
| **World Model** | Graphe de connaissances, mood estimate | Snapshot RAM + SQLite events simples | ✅ **Claude** — Pour un débutant, gardons ça simple. Graphe = v1.2+ |
| **Sécurité OS** | Niveaux 1-4 progressifs | Liste blanche stricte, pas de scripts LLM | ✅ **Claude** — La sécurité prime. Scripts générés = danger réel |
| **Performances** | Streaming direct | Accumulation par phrase avant TTS | ✅ **Claude** — Moins saccadé, plus fluide |
| **Avatar 3D Godot** | Prioritaire (v1.0) | À couper si délai serré | ⚖️ **À discuter** — Pour Cyril, l'avatar EST le projet. Mais Claude a raison sur le risque technique |
| **Mobile** | PWA + FastAPI | PWA d'abord, confirmé | ✅ **Accord total** |
| **Finance** | Dashboards complets | Import CSV simple d'abord | ✅ **Claude** — MVP d'abord |
| **Modèle LLM** | deepseek-coder:33b | qwen2.5 (testé et fonctionnel) | ✅ **Claude** — deepseek-coder:33b n'a pas été testé réellement. qwen2.5 est le vrai modèle utilisé |

### 2.2 Ce que Kimi a bien vu (et Claude n'a pas mentionné)
- **Les 5 modes de présence** (actif/passif/discret/veille/alerte) — Claude ne les mentionne pas, mais ils sont essentiels à l'expérience Desktop Pal
- **Le concept de World Model** — Même si la structure est trop complexe, l'idée que Orion doit "cartographier mentalement" l'état du système est valide et différenciante
- **L'intégration vision écran temps réel** — Mentionnée mais pas assez priorisée par Claude
- **Le HUD dynamique** — Concept clé de l'interface premium, absent du retour de Claude

### 2.3 Ce que Claude a bien vu (et Kimi a sous-estimé)
- **L'honnêteté sur le statut réel** — C'est le point le plus important. On ne peut pas planifier sur du sable.
- **Le risque des agents autonomes** — Cursor et Aider ont généré du code non validé. C'est un vrai problème de gestion de projet.
- **La sécurité** — La génération libre de scripts par LLM est dangereuse. Liste blanche = bonne pratique.
- **Le principe YAGNI** — "You Aren't Gonna Need It" — Ne pas sur-enginerer avant d'avoir les bases solides.
- **L'ordre de construction** — Nettoyer avant de construire. C'est de l'ingénierie, pas de la magie.

---

## 3. SYNTHÈSE LENOVO AURA — CE QU'ON PEUT RÉCUPÉRER

### 3.1 Concepts directement applicables à OrionAI

| Concept Aura | Application OrionAI | Priorité |
|-------------|---------------------|----------|
| **Smart Modes** | Modes de présence enrichis : Attention (bloque notifs, focus), Gaming (optimise perf), Veille (réduit conso) | 🟡 Moyenne — S3-S4 |
| **Function Calling** | Orion déclenche des actions système via LLM structuré (pas scripts libres) | 🔴 Haute — S2 |
| **Shield Mode** | Détection anomalie système + alerte proactive | 🟡 Moyenne — S4 |
| **Glassmorphism UI** | Design premium pour l'interface PySide6 (effets flou, transparence, bordures lumineuses) | 🟢 Basse — Polish S7-S8 |
| **Vision écran temps réel** | VLM analyse écran pour contexte + assistance proactive | 🔴 Haute — S3 |
| **LAM (LangGraph)** | Agents autonomes planifiant tâches complexes | 🔵 Future — v1.2+ |

### 3.2 Ce qu'on ignore d'Aura (pas adapté à OrionAI)
- **Electron/Tauri** — On reste sur PySide6 (Python natif, pas de JS/TS à apprendre)
- **Llama-3.1-8B** — qwen2.5 fonctionne déjà, pas besoin de changer maintenant
- **Phi-3-Vision** — llava/llama3.2-vision déjà testés et fonctionnels
- **LangGraph** — Trop complexe pour v1.0. Restons sur FastAPI + endpoints simples.

---

## 4. POSITIONNEMENT DE KIMI APRÈS LECTURE DE CLAUDE

### 4.1 Ce que je reconnais avoir sous-estimé
1. **Le gap "fichier généré" vs "fonctionne réellement"** — J'ai pris les outputs de Cursor/Aider comme des acquis. C'était une erreur de ma part.
2. **La complexité de Godot 3D** — J'ai poussé pour Godot parce que la vision visuelle est forte, mais Claude a raison : c'est le plus gros risque technique pour le plus faible impact utilitaire.
3. **Le modèle LLM** — J'ai cité deepseek-coder:33b comme principal alors que qwen2.5 est le seul testé et validé.
4. **Le World Model** — Ma structure dataclass était trop ambitieuse pour un débutant. Claude a raison : snapshot RAM + events SQLite suffisent.

### 4.2 Ce que je maintiens comme important (et où je diverge légèrement de Claude)
1. **L'avatar n'est PAS optionnel** — Pour Cyril, l'avatar 3D/2D est le cœur de l'expérience. Pas question de le couper. MAIS on peut le faire évoluer : QPainter V3 d'abord (stable), Godot en parallèle (expérimental).
2. **Les modes de présence** — C'est ce qui différencie Orion d'un simple chatbot. Claude ne les mentionne pas assez. Ils doivent être dans la roadmap.
3. **Le HUD dynamique** — Concept clé de l'interface premium. À intégrer dès QPainter V3.
4. **La vision écran** — C'est la fonctionnalité "wow" qui justifie le local. Prioritaire dès S3.

---

## 5. RECOMMANDATION CONSOLIDÉE — LA VOIE DU MILIEU

### 5.1 Principe directeur
> **"Cerveau solide d'abord, visage beau ensuite. Mais le visage ne part jamais."**

On ne coupe PAS l'avatar. On le stabilise en QPainter V3 (ce qui marche déjà) pendant qu'on consolide le backend. Godot reste en exploration parallèle mais ne bloque pas les releases.

### 5.2 Architecture validée à 3 (Kimi + Claude + Cyril)

```
┌─────────────────────────────────────────────────────────────┐
│              ARCHITECTURE ORIONAI v1.0 CONSOLIDÉE          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FRONTEND (Stable)          BACKEND (Cerveau)              │
│  ┌─────────────────┐        ┌──────────────────────────┐   │
│  │ Avatar QPainter │◄──────►│ FastAPI (UN SEUL)        │   │
│  │  • V3 polish    │  WS    │  • /ws → Godot + Mobile  │   │
│  │  • HUD dynamique│        │  • /api → REST classique │   │
│  │  • 5 modes      │        │  • LLM Manager (qwen2.5) │   │
│  │  • Glassmorphism│        │  • Memory (SQLite + RAG) │   │
│  └─────────────────┘        │  • World Model (RAM+SQL) │   │
│           ▲                 │  • OS Actions (whitelist)│   │
│           │                 │  • TTS (Kokoro)          │   │
│  ┌────────┴────────┐        └──────────────────────────┘   │
│  │  Godot 4 (Expé) │        ┌──────────────────────────┐   │
│  │  • V1 test      │◄──────►│  Mobile PWA (S5+)        │   │
│  │  • Non bloquant │  WS    │  • CSS/SVG avatar léger  │   │
│  │  • Fallback QPainter    │  • Chat + sync           │   │
│  └─────────────────┘        └──────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Feuille de route révisée (8 semaines — réaliste)

#### Phase 0 — AUDIT & NETTOYAGE (S0 — Semaine 0, avant S1)
**Objectif :** Partir sur des bases propres. C'est la leçon de Claude.

| Jour | Tâche | Validation |
|------|-------|------------|
| J1 | Inventaire exact des fichiers existants | Liste avec ✅ testé / ⚠️ généré non testé / ❌ fantôme |
| J2 | Suppression fichiers fantômes, fusion doublons | `git status` propre |
| J3 | requirements.txt à jour, venv recréé | `pip install -r requirements.txt` OK |
| J4 | Test end-to-end : chat → LLM → réponse | Capture d'écran de l'UI fonctionnelle |
| J5 | Documenter CE QUI MARCHE réellement | README.md à jour avec statuts réels |

**Livrable :** Base de code propre, connue, testée. Pas de magie.

#### Phase 1 — CERVEAU SOLIDE (S1-S2)
**Objectif :** Backend fiable, mémoire enrichie, actions système sécurisées

| Semaine | Tâches | Livrable |
|---------|--------|----------|
| **S1** | • FastAPI unique (fusion bridge + API) <br>• Endpoints : /chat, /memory, /system <br>• World Model v1 (psutil + fenêtre active) <br>• OS Actions whitelist (volume, brightness, lancer app) | v0.2 — Cerveau fiable + actions basiques |
| **S2** | • Mémoire enrichie (contexte conversation + events système) <br>• RAG documents personnels <br>• TTS intégré au chat (bouton + auto) <br>• Finance CSV import + dashboard simple | v0.3 — Mémoire + Finance + TTS |

#### Phase 2 — VISION & VOIX (S3-S4)
**Objectif :** Orion voit et entend

| Semaine | Tâches | Livrable |
|---------|--------|----------|
| **S3** | • VLM écran temps réel (screenshot + analyse) <br>• STT commandes vocales (whisper local) <br>• Avatar QPainter V3 (sans wireframe, glassmorphism) <br>• HUD dynamique (CPU/RAM/horloge + ajout/suppression) | v0.5 — Vision + Voix + Avatar V3 |
| **S4** | • 5 modes de présence (actif/passif/discret/veille/alerte) <br>• Proactivité (alertes intelligentes basées sur World Model) <br>• Smart Modes v1 (Attention, Gaming) <br>• Click-through + auto-hide | v0.7 — Orion est "vivant" |

#### Phase 3 — EXPANSION (S5-S6)
**Objectif :** Multi-device + Godot

| Semaine | Tâches | Livrable |
|---------|--------|----------|
| **S5** | • PWA mobile S25 Ultra <br>• Sync PC ↔ Mobile <br>• Notifications push <br>• Avatar mobile CSS/SVG | v0.8 — Mobile + Sync |
| **S6** | • Godot 4 V1 (visage low-poly + shaders néon) <br>• Bridge Godot ↔ FastAPI (protocole minimal) <br>• Test A/B : QPainter vs Godot <br>• Optimisation performances | v0.9 — Godot testable |

#### Phase 4 — POLISH (S7-S8)
**Objectif :** Version installable

| Semaine | Tâches | Livrable |
|---------|--------|----------|
| **S7** | • Choix final avatar (QPainter ou Godot) <br>• Sécurité (sandbox, audit log) <br>• Glassmorphism final polish <br>• Stress test | v0.95 — Prêt pour packaging |
| **S8** | • Installateur Windows (.exe) <br>• Démarrage auto <br>• Documentation <br>• Bugfix final | **v1.0 — OrionAI Essentiel** |

### 5.4 Protocole WebSocket consolidé (Kimi + Claude)

```python
# PHASE 1 — Minimal (Claude a raison, on commence là)
# Backend → Frontend
{
    "type": "avatar_state",
    "state": "speaking",     # idle, listening, thinking, speaking, alert, sleep
    "text": "Bonjour Cyril !"  # Optionnel, seulement si state=speaking
}

# Frontend → Backend
{
    "type": "system_state",
    "mouse_pos": [1200, 800],
    "window_active": "chrome.exe",
    "screen_resolution": [2560, 1440],
    "mode": "passive"        # actif, passif, discret, veille
}

# PHASE 2 — Enrichi (quand Phase 1 est fiable)
# Backend → Frontend
{
    "type": "avatar_state",
    "state": "speaking",
    "text": "Ta RAM est à 92%",
    "emotion": "concerned",   # happy, neutral, concerned, excited
    "hud_widgets": ["cpu", "ram", "alert"],
    "tts_duration": 2.5
}
```

### 5.5 World Model consolidé (Kimi + Claude)

```python
# En RAM (rafraîchi toutes les 5s) — Claude a raison, pas de persistance inutile
@dataclass
class WorldState:
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    active_window: str
    active_processes: List[str]  # Juste les noms, pas les objets complets
    user_idle_time: int  # secondes

# En SQLite (événements significatifs uniquement) — Claude a raison
class SystemEvent(Base):
    __tablename__ = "system_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    event_type = Column(String)  # "app_launched", "ram_alert", "mode_change"
    details = Column(String)     # JSON simple

# Pas de mood estimate pour l'instant — Claude a raison, trop spéculatif
# Pas de GraphRAG pour l'instant — Claude a raison, trop complexe
```

### 5.6 Sécurité consolidée (Kimi + Claude)

```python
# LISTE BLANCHE — Claude a raison, pas de scripts générés par LLM
ALLOWED_ACTIONS = {
    "volume_up": lambda: os.system("nircmd.exe changesysvolume +5000"),
    "volume_down": lambda: os.system("nircmd.exe changesysvolume -5000"),
    "launch_app": lambda app: subprocess.Popen([app]),
    "screenshot": lambda: pyautogui.screenshot(),
    "clipboard_get": lambda: pyperclip.paste(),
    "clipboard_set": lambda text: pyperclip.copy(text),
}

# RÈGLES — Lecture auto, Écriture confirmée, Exécution journalisée
PERMISSION_RULES = {
    "read": ["screenshot", "process_list", "resources"],      # Auto
    "write": ["volume", "brightness", "clipboard"],           # Confirmation UI
    "execute": ["launch_app", "run_script"],                   # Confirmation + log
}
```

---

## 6. DÉCISIONS À PRENDRE PAR CYRIL

### 6.1 Questions ouvertes (choix à faire)

| # | Question | Option A (Kimi) | Option B (Claude) | Recommandation |
|---|----------|----------------|-------------------|----------------|
| 1 | **Avatar principal** | QPainter V3 stable + Godot parallèle | QPainter seul, Godot reporté v1.2 | **Compromis** : QPainter V3 pour v1.0, Godot en branche expérimentale |
| 2 | **STT modèle** | whisper base (précision) | whisper tiny (rapidité) | **whisper base** — Le PC de Cyril (RTX 5080) peut le gérer |
| 3 | **Smart Modes** | Intégrer dès S4 | Reporté v1.2 | **S4** — C'est un différenciateur clé vs assistants classiques |
| 4 | **Function Calling** | Via qwen2.5 natif | Via parsing manuel des réponses | **qwen2.5 natif** — Simplifie le code, plus fiable |
| 5 | **Mobile** | PWA full feature | PWA chat seul d'abord | **PWA chat + sync** — Le S25 Ultra mérite mieux que "chat seul" |

### 6.2 Ce qui ne se discute plus (accord à 3)
- ✅ Python + PySide6 + Ollama + SQLite
- ✅ qwen2.5 comme modèle principal (testé et fonctionnel)
- ✅ Une seule API FastAPI
- ✅ Pas de scripts générés par LLM (liste blanche)
- ✅ PWA pour mobile
- ✅ CSV pour finance (pas d'API bancaires)
- ✅ Pas de hooks clavier/souris bas niveau (Niveau 4)

---

## 7. PLAN D'ACTION IMMÉDIAT

### Cette semaine (S0 — Audit)
1. **Cyril** : Faire l'inventaire exact des fichiers avec `tree /F` dans C:\OrionAI
2. **Cyril** : Tester chaque fichier "module" et noter ✅/⚠️/❌
3. **Kimi** : Aider à nettoyer et documenter
4. **Claude** : Valider le nettoyage

### Semaine prochaine (S1 — Cerveau)
1. **Kimi** : Fournir le code FastAPI unique consolidé
2. **Claude** : Valider la structure et la sécurité
3. **Cyril** : Tester end-to-end sur son PC

---

## 8. CONCLUSION

### Ce que Claude a apporté (et que Kimi reconnaît)
- **Honnêteté sur le statut réel** — Le point le plus important. On ne peut pas construire sur du sable.
- **Pragmatisme** — YAGNI, un seul serveur, protocole minimal, liste blanche.
- **Sécurité** — La génération libre de scripts est un risque réel qu'il faut écarter.
- **Ordre de construction** — Nettoyer avant de construire. C'est de l'ingénierie.

### Ce que Kimi apporte (et que Claude sous-estime)
- **L'expérience utilisateur** — Les modes de présence, le HUD, la vision écran. C'est ce qui fait qu'Orion n'est pas "juste un chatbot local".
- **La vision premium** — Glassmorphism, Smart Modes, réactivité contextuelle. C'est ce qui justifie le "haut de gamme".
- **L'ambition contrôlée** — On ne rêve pas trop grand, on rêve juste assez pour que ça vaille le coup.

### La voie du milieu
> **"Un cerveau solide avec un visage beau, pas un cerveau fragile avec un visage spectaculaire. Mais un cerveau solide sans visage, c'est juste un terminal."**

**OrionAI v1.0 = QPainter V3 (stable, beau, fonctionnel) + FastAPI unique (fiable, sécurisé) + Mémoire enrichie + Vision + Voix + Mobile PWA.**

Godot 3D reste en exploration parallèle (branche `experimental/godot-avatar`) mais ne bloque aucune release.

---

> *"Le meilleur code est celui qu'on peut mainteneur. Le meilleur projet est celui qu'on peut finir."*
>
> **— Synthèse Kimi × Claude, 28 Juillet 2026**

---

*Document d'analyse comparative rédigé par Kimi (Moonshot AI)*  
*Basé sur les documents de Claude (Anthropic), Lenovo Aura, et analyses vidéo YouTube*
