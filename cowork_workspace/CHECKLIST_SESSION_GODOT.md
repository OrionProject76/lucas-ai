# Checklist — ouverture de la session Godot supervisée

**Préparé le 05/08/2026 en session autonome. Aucun code Godot écrit, aucun
test Godot lancé** — le chantier est gelé jusqu'à ce que Cyril supervise en
direct (`ROADMAP.md` §3, décision du 02/08/2026 : « Ne pas relancer Godot
pour des tests automatisés sans lui tant que ce point n'est pas rouvert »).

Ce document sert à ne pas repartir de zéro le jour où la session s'ouvre :
ce qui est acquis, ce qui bloquait, et ce qu'il faudra trancher **avec Cyril
devant l'écran**.

---

## 1. Ce qui fonctionne déjà (à re-vérifier, pas à reconstruire)

| Élément | État connu | À revérifier en ouverture |
|---|---|---|
| Fenêtre transparente + visage | Fonctionne visuellement | Se lance encore après le renommage `Orion3D/` → `Lucas3D/` ? |
| `WS /ws` côté serveur | Endpoint unique, partagé PWA/Godot | Godot s'y connecte-t-il toujours ? **Voir point 4** |
| Vocabulaire de protocole | `api/protocol.py`, partagé | Inchangé |
| Renommage interne | `Global.orion_state` → `lucas_*` fait | Aucun reste de `orion_` dans les scripts ? |

⚠️ Le pont `orion3d_bridge.py` faisait **uniquement écho**, jamais connecté
au cœur — il a été supprimé. Godot doit passer par `/ws` comme la PWA, il
n'y a plus de chemin parallèle.

---

## 2. Les deux blocages réels, dans l'ordre où ils comptent

### 🔴 Blocage 1 — Godot se ferme ou gèle spontanément (cause NON identifiée)

Quatre occurrences observées le 02/08/2026, **sans aucune trace** : rien
dans le journal d'événements Windows, ni « Application Error » ni
« Application Hang ». Une fois disparition silencieuse du processus, une
fois gel visible tué à la main.

C'est le vrai sujet de la session. Tant qu'il n'est pas compris, tout ce
qu'on construit dessus est bâti sur du sable.

**Pistes à explorer AVEC Cyril présent** (aucune n'a été testée) :
- lancer depuis l'éditeur vs binaire exporté — les 4 cas étaient en éditeur
- RTX 5080 partagée avec Ollama : un pic VRAM pendant un chargement de
  modèle coïncide-t-il avec les fermetures ? (Le GPU est déjà relevé dans
  `get_snapshot()`, on peut corréler.)
- pilote graphique / mode de rendu Godot (Forward+ vs Compatibility)
- exécuter avec `--verbose` et capturer la sortie dans un fichier, ce qui
  n'a jamais été fait sur les 4 occurrences

### ⛔ Blocage 2 — Click-through impossible sur Windows (limite de Godot 4.7)

Documenté, **pas un bug à corriger** : une limite de la version. L'état
retenu par Cyril est le comportement le plus sûr — fenêtre invisible qui ne
bloque jamais le bureau (`_appliquer_passthrough_total()`).

À trancher ensemble : accepter cette limite pour la v1.0, ou changer
d'approche (overlay non-plein-écran, fenêtre déplaçable, HUD en coin).

---

## 3. Décisions à prendre avec Cyril — aucune ne se tranche seul

1. **Éditeur ou binaire exporté** comme cible de référence pour les tests.
2. **Périmètre v1.0 de l'avatar** : visage animé seul, ou visage + HUD
   (jauges CPU/RAM/GPU) ? Le HUD existait dans les scènes.
3. **Comportement fenêtre** : plein écran transparent, ou fenêtre en coin
   d'écran ? Conditionne la question du click-through.
4. **Que fait l'avatar quand Luca ne parle pas** — présent en permanence,
   ou apparaît à l'interaction ? Décision d'identité produit, pas technique
   (cf. `CLAUDE.md` : un changement esthétique de fond se discute).
5. **Godot consomme-t-il les nouveaux messages `activity`** (console de
   flux) et `security` ? Ils n'existaient pas quand le client Godot a été
   écrit.

---

## 4. Ce qui a changé côté serveur DEPUIS la mise en pause de Godot

À vérifier en priorité : le client Godot a été écrit avant tout ceci.

- **Authentification WebSocket** (05/08/2026, `ROADMAP.md` §5.30) : le
  jeton passe désormais par le sous-protocole `lucas-token.<jeton>`. **La
  query string `?token=` reste acceptée en repli**, précisément pour que
  Godot continue de fonctionner sans modification — mais si le client Godot
  n'envoie aucun jeton et que `API_TOKEN` est renseigné, il sera **fermé en
  1008**. À tester en premier.
- **Nouveaux types de messages** : `activity` (console de flux) et
  `security`. Un client qui les ignore ne casse pas, mais n'en profite pas.
- **`allow_screen_capture`** : le serveur distingue les clients. Godot est
  identifié « pc » par défaut, donc la capture d'écran lui reste autorisée
  — comportement inchangé, mais désormais explicite.
- **Snapshot enrichi** : `active_process` s'ajoute à `active_window` dans
  `/system` (05/08/2026). Un HUD qui affiche le snapshot brut verra un
  champ de plus.

---

## 5. Préparation matérielle de la session

- **Un seul Ollama** — et au 05/08/2026 ce n'est PAS le cas : `ollama
  app.exe` est relancée à l'ouverture de session par `explorer.exe`, et le
  serveur ne voit que 2 modèles sur 9 (`ROADMAP.md` §5.36). **À régler
  avant** : Godot et Ollama se partagent la RTX 5080, et un doublon fausse
  toute corrélation VRAM ↔ fermeture de Godot (piste du blocage 1).
- **Fenêtres du bureau** : prévoir de minimiser ce qui gêne — autorisé
  (`CLAUDE.md`, 02/08/2026), sauf le terminal Claude Code lui-même.
- **Jamais de P/Invoke Win32** pour manipuler des fenêtres pendant les
  tests (`CLAUDE.md`, 04/08/2026). Capture d'écran standard uniquement.
- **Cyril doit être devant l'écran** : les 4 fermetures n'ont laissé
  aucune trace, seule l'observation directe a permis de distinguer
  « disparu » de « gelé ».

---

## 6. Ordre suggéré pour la session

1. Régler le doublon Ollama (§5.36) — préalable, pas optionnel.
2. Lancer Godot avec `--verbose` redirigé vers un fichier, le laisser
   tourner, observer. Objectif : **capturer une trace** de la fermeture,
   pas encore la corriger.
3. Pendant ce temps, tester la connexion `/ws` (point 4) — indépendant.
4. Trancher les décisions du point 3 pendant que la trace s'accumule.
5. Seulement ensuite : toucher au rendu.
