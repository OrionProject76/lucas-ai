# SESSION_LOG — Fix pont WebSocket Godot ↔ FastAPI
**Date :** 07/08/2026
**Nature de la session :** un seul correctif, gaté par un test de bout en
bout réel. Hors scope respecté : ni mesh/shader/HUD, ni seuil du watchdog
VRAM n'ont été touchés.

---

## 1. Résultats bruts de l'audit

### 1.1 État exact du client Godot

Confirmé en relisant `websocket_client.gd` en entier : `@export var
websocket_url: String = "ws://127.0.0.1:8000/ws"` (ligne 17). Aucun jeton
n'était jamais envoyé — ni en query string, ni ailleurs. Rien dans le
fichier n'allait chercher de valeur de jeton nulle part (aucune variable
d'environnement, aucun fichier de config, rien en dur) : le mécanisme
n'existait tout simplement pas côté Godot.

### 1.2 Configuration réelle du serveur FastAPI

**Le serveur tourne bien en TLS aujourd'hui — vérifié, pas supposé.**
Deux façons de le lancer coexistent dans le dépôt :

| Lanceur | Schéma |
|---|---|
| `just serve` / `just all` | HTTPS (`--ssl-certfile data/cert.pem --ssl-keyfile data/key.pem`) |
| `just serve-http` | HTTP nu, 127.0.0.1 uniquement — étiqueté « dépannage local, sans certificat » |
| Tâche planifiée **`LucasAPIServer`** (déclencheur : connexion utilisateur, celle qui tournait réellement pendant cette session) | HTTPS — `start_server_hidden.vbs` lance exactement la même commande que `just serve` |

Testé en direct sur le serveur réellement actif (PID 9112 au moment de
l'audit) : `https://127.0.0.1:8000/status` répond, `http://127.0.0.1:8000/status`
ne répond rien du tout. **Le serveur ne parle pas en clair aujourd'hui,
quel que soit le canal.** `wss://` est donc le bon choix, pas une
supposition tirée du brief.

**Mécanisme d'auth confirmé en lisant `api/server.py`** (`websocket_endpoint`,
l. 450-484) : le jeton est cherché d'abord dans les sous-protocoles
WebSocket (`_token_from_subprotocols`, préfixe `lucas-token.`), avec repli
sur la query string `?token=` si absent. `WS_SUBPROTOCOL = "lucas.v1"`,
`WS_TOKEN_SUBPROTOCOL_PREFIX = "lucas-token."`. Un jeton absent/invalide
ferme la connexion avant `accept()` (code 1008).

**⚠️ Écart trouvé avec la documentation existante** : le commentaire
au-dessus de `_token_is_valid` affirmait « API_TOKEN est vide par défaut,
SANS EFFET aujourd'hui ». Vérifié sur le vrai `.env` du poste (sans
afficher sa valeur, uniquement sa longueur — règle CLAUDE.md sur les
données personnelles) : **43 caractères présents, pas vide.**
L'authentification WebSocket est donc réellement active, contrairement à
ce que ce commentaire affirmait. Corrigé au passage (commentaire seul,
aucun changement de comportement) — même logique que le commentaire
similaire déjà corrigé côté `websocket_client.gd`.

**Accès distant** : `cowork_workspace/PROCEDURE_TAILSCALE.md` (05/08)
confirme explicitement « rien n'est installé, rien n'est configuré ».
Reconfirmé aujourd'hui : le serveur n'est joignable que sur le réseau
local de ce PC. Le canal Tailscale n'entre donc pas en jeu dans ce
correctif — la question du brief (« le choix peut différer LAN vs
Tailscale ») ne se pose pas encore en pratique, mais le raisonnement tenu
ici (le schéma suit le serveur, pas un choix arbitraire du client) reste
valable le jour où Tailscale sera activé : `wss://` restera correct, seul
le nom d'hôte/l'IP changera.

### 1.3 Pourquoi ça n'avait jamais été corrigé

`git log --follow` et `git blame` sur `websocket_client.gd` : **un seul
commit de contenu** existe sur ce fichier avant cette session
(`a14736f8`, 01/08/2026, création — `ws://127.0.0.1:8000/ws`, commentaire
« sans authentification »), plus un commit de reformatage (tabulations,
`ff295840`) et le renommage Orion→Lucas (`e9bf6c4`, aucun changement de
logique). **Aucune tentative de correctif n'a jamais existé ni été
annulée — littéralement rien**, pas une régression au sens propre : le
fichier n'a simplement jamais suivi la bascule HTTPS + jeton du serveur,
posée après sa création.

---

## 2. Correctif appliqué

### Schéma : `wss://`, argumenté par l'audit, pas par défaut

Conforme à la règle 3 du brief : le serveur ne sert QUE du HTTPS
aujourd'hui (1.2), donc `ws://` ne peut physiquement pas fonctionner —
ce n'est pas un choix esthétique entre deux options valides.

### Jeton : réutilisation stricte du mécanisme existant

- Sous-protocoles `["lucas.v1", "lucas-token.<jeton>"]` — exactement le
  mécanisme déjà utilisé par `static/js/websocket.js` et attendu par
  `api/server.py`. Aucun système parallèle.
- Le jeton est lu dans **le même `.env`** que `config.py` (aucun nouveau
  fichier de secret) : `Lucas3D/scripts/websocket_client.gd` lit
  directement `C:/OrionAI/.env` via `FileAccess`, cherche la ligne
  `API_TOKEN=`. Il ne réapparaît jamais dans l'URL ni dans un log.

### TLS : épinglage sur la CA racine mkcert — pas sur le certificat serveur

**Trouvaille en testant, pas en supposant** : la première tentative
épinglait `TLSOptions.client()` directement sur `data/cert.pem` (le
certificat du serveur), en pensant que ce serait *plus* strict. **Godot
l'a refusé** — `mbedtls error: returned -0x2700` / `TLS handshake error:
-9984`, reproduit deux fois. mbedTLS valide une chaîne jusqu'à une
autorité reconnue ; lui donner la feuille comme « chaîne de confiance »
ne lui fournit aucune autorité pour vérifier sa propre signature.
**Correction : épinglage sur la CA racine mkcert**
(`C:\Users\PC\AppData\Local\mkcert\rootCA.pem`, obtenue via `tools\mkcert.exe
-CAROOT`) — testée, connexion établie sans erreur (voir section 3).

### Fichiers modifiés

- `Lucas3D/scripts/websocket_client.gd` — schéma, lecture du jeton,
  options TLS, log horodaté de chaque `avatar_state` reçu.
- `api/server.py` — commentaire seul, corrigé pour refléter que
  `API_TOKEN` est réellement configuré (aucun changement de comportement).

---

## 3. Résultat du test de bout en bout — observé, pas supposé

Serveur réel (tâche planifiée `LucasAPIServer`, PID 9112) + projet Godot
lancé en direct (`Godot_v4.7.1-stable_win64_console.exe --path Lucas3D`,
scripts vivants, pas de réexport nécessaire).

**Connexion** : log Godot, aucune erreur —

```
WebSocket pret sur wss://127.0.0.1:8000/ws
Connecte a Lucas Backend
[15:16:57] avatar_state recu : idle
```

**Déclenchement d'un vrai événement backend** : un message `chat` réel a
été envoyé par la connexion Godot elle-même (scaffold de test temporaire,
retiré après la mesure — voir section 5), provoquant un vrai appel
`LucasCore.ask()` (chargement de `gpt-oss:20b`, génération réelle). Reçu
et journalisé par Godot, horodaté :

```
[15:17:14] avatar_state recu : thinking
[15:17:14] avatar_state recu : speaking
[15:17:14] avatar_state recu : idle
```

Trois états reçus dans l'ordre attendu, sur la connexion de Godot
elle-même — pas une connexion de test séparée. C'est la preuve demandée :
un changement d'état réel, backend, traverse effectivement le pont.

**Coupure serveur en cours de route** — process serveur (PID 9112 et son
parent lanceur venv 8420, tués ensemble après vérification de l'arbre
parent-enfant) :

```
mbedtls error: returned -0x6c00

Deconnecte
Reconnexion...
Connexion en cours...
```

**Aucun crash** (process Godot toujours vivant, vérifié `tasklist`),
déconnexion journalisée proprement, reconnexion automatique enclenchée
comme prévu — comportement déjà attendu ailleurs dans le projet, pas une
nouvelle exigence.

**Serveur relancé** (via la tâche planifiée `LucasAPIServer`, la même
méthode que sa mise en route normale) — reconnexion automatique de Godot
confirmée dans la foulée, cycle complet rejoué avec succès :

```
Connecte a Lucas Backend
[15:19:01] avatar_state recu : idle
[15:19:08] avatar_state recu : thinking
[15:19:08] avatar_state recu : speaking
[15:19:08] avatar_state recu : idle
```

**Cette brique peut donc être marquée « fait, vérifié en conditions
réelles »**, pas seulement « corrigé ».

---

## 4. Mise à jour de `ROADMAP.md`

Uniquement la ligne concernant ce pont WebSocket — rien d'autre touché
(mesh/HUD toujours en attente, seuil du watchdog VRAM non rouvert).

---

## 5. État final du poste, signalé explicitement

- Le scaffold de test (`send_message({"type": "chat", ...})` déclenché à
  la connexion) a été **retiré** après la mesure — ce n'était pas une
  fonctionnalité demandée par ce brief (Godot n'a toujours pas de moyen
  d'envoyer un message de chat en usage normal, ce qui est hors scope
  ici).
- Ce test a laissé **deux échanges réels** dans l'historique de
  conversation (`memory/lucas_memory.db`) — contenu anodin (« Mesure de
  connexion en direct, ignore ce message. »), signalé plutôt que tu.
- L'instance de test de Godot (lancée directement depuis le projet, pas
  le binaire exporté) a été arrêtée proprement — aucun process Godot ne
  reste actif.
- Le serveur API a été **coupé puis relancé** pendant le test (section
  3) — remis dans l'état où il a été trouvé (tâche planifiée
  `LucasAPIServer`, HTTPS, port 8000, `0.0.0.0`). Vérifié réécoute avant
  de conclure la session.
- **Le binaire exporté (`build/Lucas3D.exe`) a été régénéré et
  revérifié.** Le premier test de bout en bout (section 3) tournait sur
  le projet lancé en direct depuis les scripts sources — utile pour
  itérer vite, mais ce n'est pas ce que Cyril lance réellement
  (`demos/lancer_lucas3d.ps1` pointe sur `build/Lucas3D.exe`). Réexporté
  (`Godot.exe --headless --path Lucas3D --export-release "Windows
  Desktop" ../build/Lucas3D.exe`, aucune erreur), puis relancé
  directement : connexion `wss://` établie, jeton accepté, premier état
  `avatar_state: idle` reçu — **le binaire que Cyril lancera réellement
  fonctionne, pas seulement les scripts sources.** Arrêté ensuite via
  `demos/arreter_lucas3d.bat` (`[OK] Lucas3D a ete arrete` / `[OK]
  Verifie`).

Aucune décision d'architecture réseau n'a été prise seul : le canal reste
LAN local uniquement, comme avant. Rien n'a été ouvert vers l'extérieur.
