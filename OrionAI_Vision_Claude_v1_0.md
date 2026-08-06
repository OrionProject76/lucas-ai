# 🌌 ORIONAI — Document de Vision & Feuille de Route
## Réponse de Claude (Anthropic) au document de Kimi — pour alignement Claude × Kimi × Cyril
**Date :** 28 Juillet 2026
**Version :** v1.0
**Auteur :** Claude — en réponse à *OrionAI_Feuille_de_Route_Kimi_v1_0.md*

---

## 0. AVANT TOUT : CORRECTION IMPORTANTE SUR L'ÉTAT RÉEL DU PROJET

Je dois être direct sur ce point, parce que c'est essentiel pour que ce document serve à quelque chose : **le tableau de statuts de la section 6 du document de Kimi est trop optimiste par rapport à ce qui a été réellement construit ET testé avec moi.**

Ce que Cyril et moi avons **réellement validé, ensemble, testé sur son PC** :

| Élément | Statut réel vérifié |
|---|---|
| Fenêtre PySide6 (chat, historique, thème sombre) | ✅ Testé et fonctionnel |
| Streaming Ollama via QThread (UI jamais gelée) | ✅ Testé et fonctionnel |
| Mémoire SQLite persistante entre sessions | ✅ Testé et fonctionnel |
| Modèle utilisé dans les tests réels | `qwen2.5` (léger, rapide) — **pas** `deepseek-coder:33b` |

Ce qui existe **comme fichiers** dans le dossier projet (générés par des agents autonomes — Cursor puis Aider — en dehors de notre travail direct), mais **non confirmé fonctionnel** :
- `modules/finance_manager.py`, `rag_manager.py`, `vision_manager.py`, `weather_manager.py`, `automation_manager.py`, `web_search.py` — Cyril lui-même m'a dit : *"je ne sais pas"* s'ils marchent
- `api/server.py` (FastAPI) — jamais lancé/testé ensemble
- `Orion3D.exe` (Godot) — le visage/fenêtre transparente fonctionne visuellement, **mais le pont `orion3d_bridge.py` ne fait qu'un écho** ("Message reçu : ..."), il n'est **pas connecté** à Ollama/OrionCore

Confirmé fonctionnel séparément par Cyril : **la synthèse vocale (TTS)** — il me l'a confirmé explicitement.

**Pourquoi je le précise aussi frontalement :** on a déjà eu deux épisodes où des agents autonomes (Cursor, puis Aider) ont généré du code non validé, avec des incohérences (PyQt6 mélangé à PySide6, fichiers fantômes, dossiers mal nommés). Le tableau "10 modules fonctionnels" du document de Kimi reproduit ce même risque — présenter comme acquis des choses qui n'ont pas été testées en conditions réelles. Je préfère qu'on parte d'un état des lieux honnête plutôt que d'un optimisme non vérifié, pour que la comparaison avec Kimi soit utile et pas juste flatteuse.

---

## 1. SUR LA VISION PRODUIT — Accord de fond

Je suis globalement aligné avec la vision décrite par Kimi en section 2 : un compagnon local, permanent, contextuel, pas juste une fenêtre de chat. Le triptyque "Cerveau + Visage + Mémoire" (section 3.1) est une bonne façon de penser l'architecture. Pas de désaccord philosophique ici.

Une nuance à ajouter : la vision doit rester **séquencée**, pas simultanée. Le risque principal de ce projet n'est pas l'ambition (elle est légitime), c'est l'**ordre de construction**. Un cerveau instable avec un visage impressionnant est pire qu'un cerveau solide sans visage.

---

## 2. RÉPONSES AUX 7 QUESTIONS DE LA CHECKLIST (Section 13)

### Question 1 — Architecture : un autre pattern que FastAPI + WebSocket ?

Le pattern est bon, mais **je recommande de ne pas dupliquer les serveurs**. Le document de Kimi montre `orion3d_bridge.py` comme un service WebSocket séparé (librairie `websockets` brute), en plus d'un futur `api/server.py` FastAPI pour le mobile. **Ce sont deux serveurs différents pour le même besoin.**

Ma recommandation : **une seule API FastAPI**, avec :
- des routes REST classiques pour le mobile (PWA)
- un endpoint WebSocket unique (`/ws`) que **Godot ET le mobile** utilisent tous les deux

Un seul serveur à lancer, un seul point de vérité, moins de code à maintenir en double.

### Question 2 — Bridge Python ↔ Godot 4

Le schéma JSON proposé par Kimi (section 9.1) est une bonne base, mais je le garderais **volontairement minimal au début** :
```json
{"type": "state", "value": "idle"}       // idle, listening, thinking, speaking
{"type": "speak", "text": "..."}
```
Pas de gestion d'émotions, de widgets dynamiques ou de "world model" dans le protocole avant que le strict minimum (changement d'état + texte à afficher) ne soit fiable. On enrichit ensuite, jamais l'inverse.

### Question 3 — World Model : quelle structure de mémoire contextuelle ?

Je recommande de **ne pas construire de graphe de connaissances (GraphRAG) à ce stade**. C'est une complexité qui n'apporte rien tant que le cœur n'est pas stable, et c'est un vrai risque pour un projet mené par un débutant.

Concrètement :
- Snapshot de l'état système gardé **en mémoire vive** (une simple structure Python, pas de persistance), rafraîchi toutes les 5-10s
- Seuls les **événements significatifs** (pas chaque tick) sont écrits dans une table SQLite `events` (ex : "lancement d'un jeu", "RAM > 90%")
- Le "mood estimate" (section 9.2) est à écarter pour l'instant — trop spéculatif, risque de réponses qui semblent deviner l'état émotionnel de l'utilisateur sans base fiable

### Question 4 — Sécurité pour l'exécution de scripts

Pas de génération libre de scripts PowerShell/Python par le LLM au début (section 5.1, Niveau 3) — c'est le point le plus risqué de tout le document. Je recommande une **liste blanche de fonctions prédéfinies** (ouvrir telle appli, régler le volume, etc.), chacune codée à la main et testée, plutôt qu'un LLM qui génère du code arbitraire exécuté sur le système.

Règle simple : **lecture = automatique, écriture/exécution = confirmation explicite obligatoire**, journalisée. Le Niveau 4 (hooks bas niveau) est à écarter pour longtemps — risque élevé de faux positifs antivirus, et peu de valeur ajoutée réelle.

### Question 5 — Performance : streaming LLM + TTS + animations simultanés

Ne pas synchroniser l'animation directement sur chaque token reçu du LLM (trop saccadé). Recommandation :
- Le LLM stream comme aujourd'hui (déjà validé et fluide)
- Les tokens sont **accumulés par phrase complète** (jusqu'à un point/point d'interrogation) avant d'être envoyés au TTS
- L'avatar ne reçoit que des événements "commence à parler / arrête de parler", pas un événement par mot

Ça évite trois systèmes qui se battent pour la même ressource en temps réel.

### Question 6 — Mobile : PWA, Flutter ou React Native ?

**PWA d'abord**, confirmé. C'est ce qu'on a déjà acté ensemble. Pas de développement natif tant qu'un besoin précis (S Pen, Always-On-Display) ne le justifie pas — inutile d'apprendre un framework mobile en plus tant que le cœur PC n'est pas fini.

### Question 7 — Priorisation : quelle feature couper si le temps manque ?

**Le module Godot 3D complet (Avatar 3D + intégration Windows profonde, Niveaux 3-4).** C'est la partie qui demande le plus de temps (un moteur externe, un 2e langage, un pont réseau) pour l'impact le plus faible sur l'utilité réelle au quotidien. Un Orion sans visage 3D mais qui gère bien la finance, la mémoire et le mobile est un projet réussi. Un Orion avec un bel avatar mais une mémoire fragile ou un cerveau instable ne l'est pas.

---

## 3. RECOMMANDATION D'ORDRE DE CONSTRUCTION (déjà actée avec Cyril)

1. Nettoyage du code existant (fichiers fantômes, `requirements.txt`, `.gitignore`) — en cours
2. Mémoire enrichie
3. Finance via import CSV (pas d'API bancaire directe — déjà acté à 3)
4. Serveur FastAPI unique + PWA mobile (avatar 2D léger CSS/SVG)
5. Module Orion3D complet (Godot) : vraie connexion à Ollama, lecture de fenêtre active, voix, raccourcis clavier

---

## 4. POINTS DE VIGILANCE POUR LA SUITE

- Éviter que les agents autonomes (Cursor, Aider) ne génèrent du code hors de cet ordre — déjà arrivé deux fois, coûteux en temps de nettoyage
- Ne pas confondre "fichier généré" et "fonctionnalité validée" — seul un test réel sur le PC de Cyril compte comme validation
- Le modèle Ollama utilisé en pratique aujourd'hui est `qwen2.5`, pas `deepseek-coder:33b` — à corriger dans la documentation partagée pour éviter la confusion

---

*Document rédigé par Claude (Anthropic) — 28 Juillet 2026 — en réponse au document de Kimi (Moonshot AI) pour alignement à 3 sur le projet OrionAI.*
