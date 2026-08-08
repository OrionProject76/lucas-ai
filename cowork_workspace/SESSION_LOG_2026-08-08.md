# SESSION_LOG — Noyau minimal, les 4 briques
**Date :** 08/08/2026
**Nature de la session :** implémentation complète du brief de session
reçu de Cyril (« noyau minimal utilisable au quotidien »), les 4 briques
dans l'ordre demandé — mémoire → OS Controller → routeur hybride → avatar.
Détail complet, décisions, mesures : `ROADMAP.md` §5.68-5.71.

---

## 1. Ce qui a été livré

| Brique | Contenu | Commit |
|---|---|---|
| 3 — Mémoire | `remember()`/`recall()`/`forget()`, 5 types (IDEAS.md #2), table dédiée avec provenance vérifiable (`source_type`/`source_id`) | `bf02354` |
| 2 — OS Controller | `core/os_controller.py` (déplacer/renommer/capturer/volume/presse-papiers), dossiers autorisés, confirmation destructive Qt thread-safe | `1938a75` |
| 1 — Routeur hybride | `core/cloud_llm.py` (API Anthropic réelle, claude-opus-5), plafond mensuel, provenance affichée | `a3d5a93` |
| 4 — Avatar | 7 états (THINKING_DEEP, OBSERVING), clignement non périodique | `de1fa39` |

Suite complète : **1520/1520 tests**, `ruff`/`mypy` propres. Base réelle de
Cyril vérifiée intacte à chaque étape (comptage de lignes, jamais contenu).

---

## 2. Incident réel trouvé et corrigé en cours de route (Brique 3)

En lançant la suite complète (pas seulement les nouveaux tests), un fichier
`memory/lucas_memory.db.bak-20260808-153905` est apparu à côté de la vraie
base — le nouveau mécanisme de backup automatique s'était déclenché sur
`memory/lucas_memory.db` elle-même.

Cause trouvée en deux couches, corrigées avant de continuer :
1. Trois tests UI construisaient un vrai `MainWindow()` sans isoler
   `LucasCore` — même piège déjà corrigé une fois le 04/08 dans
   `test_ui_workers.py`, retombé dedans trois fois ailleurs.
2. Plus profond : `save_event_from_any_thread()` (et deux fonctions que
   j'ai écrites ensuite) appelaient `MemoryManager()` nu — un défaut de
   paramètre figé À LA DÉFINITION de la fonction, qui rend tout
   `monkeypatch` de `DB_PATH` inopérant. Même famille de bug que
   l'incident des ~56 messages perdus du 05/08 (ROADMAP §5.32).

Vérifié par comptage stable sur deux relances complètes de la suite après
correctif — aucune perte de données constatée. Serveur live arrêté (à ta
demande) pour la suite de la session ; à relancer manuellement quand tu
veux (commande dans ROADMAP §5.68).

---

## 3. Points de clarification tranchés par toi avant le plan

- Clé API cloud : `keyring` (Gestionnaire d'identification Windows), pas
  `.env`, pas de chiffrement maison.
- Confirmation destructive OS Controller : `QMessageBox` minimale,
  attention explicite au threading Qt (que j'ai vérifiée réellement avant
  d'écrire le test définitif — voir §4).
- Mémoire : table `memories` dédiée, provenance vérifiable
  (`source_type`/`source_id`), pas un texte libre.
- Avatar : 7 constantes (IDLE + les 6 labels du brief).

---

## 4. Ce qui a été vérifié réellement, pas supposé

- API pycaw (volume) : `AudioUtilities.GetSpeakers().EndpointVolume`, pas
  `.Activate()` comme le suggéraient d'anciens tutoriels — l'API a changé,
  testé sur cette machine avant d'écrire le code.
- Pont de confirmation Qt cross-thread : reproduit d'abord dans un script
  séparé (un `BlockingQueuedConnection` depuis le thread GUI lui-même fait
  un deadlock ; `worker.wait()` ne pompe pas la file d'événements du thread
  appelant) avant d'écrire le test définitif contre un VRAI `QThread`.
- Budget CPU de l'avatar (< 2 % annoncé au brief) : mesuré à **2,6-2,8 %**
  avec `demos/demo_avatar_cpu.py` — **au-dessus** de la cible. Signalé tel
  quel, pas masqué. Mesure sous `QT_QPA_PLATFORM=offscreen`, un rendu
  desktop réel n'a pas été comparé.

---

## 5. Ce qui attend Cyril en conditions réelles

1. **V1 (routeur cloud)** — aucune clé Anthropic disponible dans cette
   session. Enregistrer la clé (`python scripts/set_anthropic_key.py`)
   puis poser une vraie question complexe pour valider en conditions
   réelles.
2. **V5 (OS Controller)** — la boîte de dialogue de confirmation n'a pas
   été cliquée par toi (session sans écran interactif) ; seule la
   plomberie complète (thread, blocage, retour de valeur) est vérifiée,
   avec `QMessageBox.question` mocké.
3. **Budget CPU avatar** — 2,6-2,8 % mesuré, au-dessus de 2 %. Pas corrigé
   sous pression de terminer la session : optimiser le rendu est un
   chantier distinct (fréquence, respiration permanente, particules), à
   ouvrir séparément si tu le juges prioritaire.
4. **Serveur live** — arrêté (`taskkill` sur PID 31972/35480) à ta
   demande explicite pendant cette session. Commande de relance dans
   ROADMAP §5.68.

Rien de tout ceci n'est un blocage — chaque point est un test en
conditions réelles qui n'a pas pu se faire sans toi devant l'écran, pas un
défaut de conception trouvé et laissé sans réponse.
