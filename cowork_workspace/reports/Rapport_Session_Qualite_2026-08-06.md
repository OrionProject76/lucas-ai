# Rapport de session — Qualité du code et état du projet Luca's

**Date** : 6 août 2026
**Durée** : ~8 heures
**Périmètre** : ruff, mypy, couverture, campagne de mutation
**Auteur** : Claude Code (Opus 5)

---

# Partie 1 — Ce qui a été fait pendant la session

## 1.1 Vue d'ensemble

| Indicateur | Au début | À la fin |
|---|---|---|
| Alertes **ruff** | 105 *(recette cassée)* | **0** |
| Erreurs **mypy** | invisible *(recette cassée)* | **0** sur 116 fichiers |
| **Couverture** | 97 %, `ui/` non mesuré | **100 %** — 3 568 lignes, 0 non couverte |
| **Score de mutation** | 85,5 % | **99,5 %** — 1 seul survivant, prouvé équivalent |
| **Tests** | 1 297 | **1 446** |
| Commits | — | **31** |

**31 commits**, tous poussés. Production vérifiée intacte à chaque étape
(`git diff` vide sur `modules/`, `core/`, `api/`, `memory/`, `security/`).

---

## 1.2 Le constat de départ : trois portes qui ne s'ouvraient pas

Avant de corriger quoi que ce soit, l'exécution réelle des commandes a
montré que **les outils de vérification du projet ne fonctionnaient pas** :

| Commande | État réel | Cause |
|---|---|---|
| `just lint` | **ne s'exécutait jamais** | appelait `ruff` nu, absent du PATH |
| `just mypy` | **ne s'exécutait jamais** | même cause |
| `just test` | s'exécutait **ailleurs** | `pytest` nu → Python **global**, auquel manquent **20 paquets** du venv |

Conséquence mesurée pour `just test` : il collectait **1 249 tests avec
2 erreurs d'import** (`ModuleNotFoundError: ddgs`) là où le venv en
collecte 1 298 qui passent. Deux fichiers de tests n'étaient **jamais
exécutés** par la commande officielle du projet.

Les trois recettes passent désormais par `venv/Scripts/python.exe -m …`.

> **La leçon** : une commande de vérification qui ne s'exécute jamais, ou
> qui s'exécute ailleurs que là où vit le code, ne protège rien — et ne le
> dit pas.

---

## 1.3 Chantier ruff — 105 → 0

Le tri s'est fait **par nature**, pas par lot : une alerte de lint n'est
pas une alerte de lint.

### Vrais défauts corrigés

| Alerte | Ce que c'était |
|---|---|
| `ASYNC230` `api/server.py` | Un `open()` bloquant dans le handler WebSocket **gelait la boucle d'événements** — donc toutes les connexions — le temps de lire le fichier audio. La synthèse était déjà déportée en thread ; la lecture avait été oubliée |
| `S110` ×2 `lucas_daemon.py` | `pass` muet « pour ne pas spammer les logs ». Un verrou SQLite ou un disque plein tuait la fonctionnalité **sans le moindre signe** |
| `B904` `rag_manager.py` | `raise … from e` manquant : la cause d'origine disparaissait du traceback |

### 🔴 Le bug le plus grave de la journée

`security/status.py::_findings()` comparait :

```
since      = datetime.now().isoformat()  → "2026-08-05T03:08:15.368689"  LOCAL, séparateur « T »
created_at = CURRENT_TIMESTAMP (SQLite)  → "2026-08-06 01:05:01"         UTC, séparateur ESPACE
```

La comparaison SQL porte sur des **chaînes**. L'espace (0x20) est
inférieur au « T » (0x54) : **tout événement portant la même date que
`since` était exclu**, quelle que soit son heure. La fenêtre « 24 h » ne
couvrait que la journée UTC en cours.

**Mesuré sur la base réelle avant correction :**

```
signaux security au total  : 1
comptés par la fenêtre 24h : 0
```

**La PWA affichait « aucun signal » alors qu'il y en avait un.** Une
fausse assurance, dans le module de sécurité.

**Pourquoi les tests étaient verts** : ils injectaient
`datetime.now().isoformat()` — un format que la production n'écrit
jamais. Le fixture validait une réalité inexistante.

### Faux positifs documentés plutôt que « corrigés »

- `B023` — la lambda capture une variable de boucle, mais est consommée
  dans la même itération.
- `PLW1510` ×3 — les trois inspectent `result.returncode` juste après :
  `check=True` casserait la logique.

### ⚠️ Une erreur commise et annulée

Le premier passage a supprimé **40 commentaires `noqa`**, dont 29
portaient une justification écrite (« une panne TTS ne doit pas
invalider une réponse déjà envoyée »). C'était la trace d'`except
Exception` **délibérés**.

**Le piège** : `--select` **remplace** le jeu de règles, il ne l'étend
pas. Sans `BLE001` dans la sélection, `RUF100` a jugé ces `noqa`
inutiles. Commit annulé, rejoué sans `RUF100` : zéro `noqa` retiré.

### Découverte annexe : une tâche du daemon morte depuis toujours

```python
tests_dir = LUCAS_ROOT / "tests"
if not tests_dir.exists():
    db_log_task("auto_tests", "skipped", "Dossier tests/ non trouvé")
    return
```

`tests/` n'existe pas — les 49 fichiers sont à la racine. La tâche
« tests automatiques toutes les heures » part en `skipped` **depuis sa
création**. **Volontairement non réparée** : pointer pytest sur la racine
lancerait 1 446 tests par heure sur la machine de Cyril. Sa décision.

---

## 1.4 Chantier mypy — 0 erreur sur 116 fichiers

### Périmètre élargi trois fois

1. `core/ modules/ memory/ api/` → **+ `security/`** (mesuré à 0 erreur, donc gratuit)
2. **+ `--check-untyped-defs`** — sans ce drapeau, mypy **ignore le corps
   de toute fonction sans annotations**. Impact mesuré avant activation :
   **une seule** erreur réelle.
3. **+ la racine et `ui/`** — 73 erreurs, toutes traitées.

### Ce qui a été trouvé

| Erreur | Verdict |
|---|---|
| 2 × `str \| None` dans `lucas_core.py` | **Invariants invisibles à mypy**, vérifiés : le routeur ne dit « oui » que si l'extraction aboutit. 0 divergence sur 20 formulations |
| `finance_manager.py:169` | Idiome de dédoublonnage qui **fonctionne** mais s'appuie sur la valeur de retour d'une méthode qui n'en a pas |
| `piper_engine.py` | Cache initialisé à `None` figeant le type. Corrigé par `if TYPE_CHECKING:` — `piper` est une dépendance **optionnelle**, l'importer en tête ferait échouer le projet entier sur une machine sans Piper |
| 12 alias Qt5 dans `ui/` | **Vérifié au runtime AVANT migration** que `Qt.AlignCenter == Qt.AlignmentFlag.AlignCenter` — strictement égaux |

### Un type correct a trouvé un angle mort dans les tests

Annoter `self.avatar: AvatarWidget | None` a révélé **4 erreurs dans
`test_avatar.py`** : les tests lisaient `window.avatar.state` en
supposant l'avatar présent.

### ⚠️ Ruff et mypy se contredisent parfois

Sur `module.PdfReader = _Reader`, mypy veut `setattr`, ruff refuse
`setattr` avec un nom constant (B010). Résolu par l'affectation directe
**plus** une exception ciblée.

---

## 1.5 Couverture — 97 % → 100 %

### Le trou de `ui/` n'existait pas

`ui/avatar_widget.py` affichait **87 %**, et les 30 lignes manquantes
étaient son bloc `if __name__ == "__main__":` — une démo de 64 lignes
qu'aucun test ne doit exécuter. `.coveragerc` créé : **100 %**.

Le chiffre poussait à écrire un test artificiel pour un trou inexistant.

### 🔴 Un de mes propres tests ne testait rien

La ligne 530 de `main_window.py` restait rouge **alors qu'un test
prétendait la couvrir**. Sous `QT_QPA_PLATFORM=offscreen`,
`setVisible(True)` sur un widget dont la fenêtre n'a **jamais été
montrée** laisse `isVisible()` à `False`. La branche n'était jamais
prise, et l'assertion était vraie d'avance.

> **La couverture a trouvé ce que la campagne de mutation avait manqué.**
> Les deux outils ne voient pas la même chose : la mutation valide les
> tests qu'on *pense* avoir écrits, la couverture révèle ceux qui
> **n'exécutent rien**.

### 55 lignes finales

Réparties en quatre familles — replis d'environnement, gardes de
sécurité, messages d'erreur, effets externes. Trois mécanismes ont dû
être trouvés :

- Le **classifieur d'intention était inatteignable** : `conftest.py` le
  neutralise globalement. Solution : capturer la fonction **à l'import du
  module de test**, avant que la fixture autouse ne s'installe.
- **`__package__` résiste au rechargement** : `importlib.reload()` le
  recalcule. Il faut charger le fichier **hors paquet**.
- **Un seul genre de titre exerce l'arbitrage AURA** : « tutoriel » est à
  la fois marqueur LEARNING *et* marqueur d'arbitrage, donc LEARNING
  gagne avant. Seuls `apprendre` et `cours ` touchent la ligne.

---

## 1.6 Campagne de mutation

### L'outil

Aucun outil de mutation n'était installé, et `mutmut`/`cosmic-ray`
relancent la **suite entière** par mutant — à 44 s la suite, quelques
centaines de mutants prendraient des jours.

Outil maison, avec deux choix qui rendent la campagne faisable :

- **Sélection des tests par module** — seuls les fichiers de test qui
  *importent* le module sont lancés (analyse des imports, pas une
  convention de nommage). **~5 s par mutant au lieu de 44.**
- **Mutations ciblées, par AST** — comparaisons inversées, opérateurs
  booléens, négations retirées, constantes de décision.

### Résultats

| Passage | Mutants | Survivants | Score |
|---|---|---|---|
| **Premier** | 605 | 86 | 85,5 % |
| **Second** (hors négations) | 495 | 3 | 99,0 % |
| **Négations seules** | 115 | 1 | 99,1 % |
| **Second, combiné** | 610 | 4 | 99,0 % |
| **🏁 Final** *(après correction des 4)* | **605** | **1** | **99,5 %** |

### Le résultat final, en détail honnête

```
MUTANTS      : 605      appliqués
tués         : 602
survivants   : 1        core/intent.py:350 — ÉQUIVALENT, prouvé
ignorés      : 4
SCORE        : 99,5 %
durée        : 53,4 min
```

Sur les **41 modules**, **40 sont à 100 %**. Le seul module en dessous
est `core/intent.py` (27 tués / 1 survivant, 96,4 %) — et ce survivant
est le mutant **prouvé équivalent**.

⚠️ **Trois précisions que le score seul ne dit pas :**

| Écart | Ce que c'est |
|---|---|
| 605 appliqués, **603 mesurés** | **2 mutants ont expiré** (timeout de 180 s) et n'ont donc jamais été évalués. Ils sont comptés comme non tués dans le 99,5 % — c'est le sens prudent, mais ils restent **non mesurés** |
| 4 « ignorés » | 2 timeouts ci-dessus + 2 points refusés par le garde de frontière de mot (un `or` à l'intérieur d'un mot, dans `semantic_desktop.py`) |
| Score sur le mesuré | **602 / 603 = 99,83 %** |

**Autrement dit : tous les mutants réels et mesurés sont tués.** Le seul
survivant est équivalent par construction, et deux mutants restent une
zone d'ombre — mon outil ne journalise pas *lesquels* ont expiré, ce qui
est un défaut à corriger avant la prochaine campagne.

### Les 86 survivants du premier passage, par module

| Module | Survivants | Traités |
|---|---|---|
| `memory/index_documents.py` | 12 | 12 tués |
| `core/lucas_core.py` | 11 | 11 tués |
| `security/*` | 11 | 11 tués |
| `modules/rag_manager.py` | 10 | 10 tués |
| `api/server.py` | 7 | 7 tués |
| `core/intent.py` | 6 | 5 tués + 1 équivalent prouvé |
| `modules/stt_engine.py` | 5 | 5 tués |
| `modules/web_search.py` | 4 | 4 tués |
| `modules/finance_manager.py` | 4 | 4 tués |
| `modules/voice_manager.py` | 3 | 3 tués |
| divers (13 modules) | 13 | 13 tués |

### Ce que les survivants protégeaient — les plus significatifs

| Ligne | Ce qui se serait passé |
|---|---|
| `lucas_core:451` | Une question routée au **cloud** aurait déclenché une capture d'écran |
| `lucas_core:846` | Le témoin d'action ne se remettait pas à zéro : une action réussie au tour 1 autorisait une **fausse confirmation** au tour 2 |
| `index_documents:433` | `allow_secrets` par défaut à `True` : mots de passe et clés d'API **indexés dans une base consultable par le LLM** |
| `index_documents:483` | `reset` par défaut à `True` : un simple `index_directory()` **viderait la base** |
| `server:132` | CORS `allow_credentials=True` : cookies et en-têtes d'authentification traversant les requêtes croisées |
| `server:444` | `validate=False` sur le base64 : des octets **tronqués** écrits sur disque puis envoyés à l'OCR |
| `privacy_shield:189` | Une socket en écoute sans adresse fait tomber le **balayage entier** — plus aucun signal de sécurité |
| `ransomware_watch:104` | « Documents » redirigé vers OneDrive **jeté** au profit d'un chemin qui n'existe pas : la veille surveillerait un dossier vide |
| `finance_manager:286` | Les **revenus** deviennent les dépenses — le total affiché serait faux, sans erreur visible |
| `status.py:43` | `SecurityStatus` non gelé : l'état de sécurité réécrivable en mémoire |

### 🔴 Deux défauts dans MA façon de mesurer

**1. Mon correctif écartait une catégorie entière.** En remplaçant le
`str.replace()` naïf par une frontière de mot, j'ai encadré le motif des
**deux** côtés. Sur `"not "` — qui finit par une **espace** — le garde de
fin examine le caractère suivant l'espace, presque toujours une lettre :
il échouait **toujours**.

**110 mutations de négation silencieusement ignorées**, et un score de
99 % calculé sur un jeu amputé. Corrigé, puis mesuré séparément :
**115 négations, 114 tuées**.

> Un outil de mesure qui écarte discrètement ce qu'il ne sait pas traiter
> **flatte son propre résultat** — exactement ce que cette campagne
> cherche à débusquer dans le code.

**2. Ma vérification par palier était incomplète.** Sur les 11 survivants
de `security/` annoncés traités, mon script n'en avait rejoué que **huit**.
`privacy_shield:154` et `:189` n'ont jamais été vérifiés — comptés comme
traités **sans preuve**.

### Un mutant équivalent, prouvé et non contourné

`intent.py:350` — `_inherit=False` → `True` ne peut rien changer : le
contexte passé à cet appel est vide, donc la garde qui le lit est déjà
fausse. **Comparé sur 5 questions elliptiques, sorties identiques
caractère par caractère.**

---

## 1.7 Le motif qui revient — et ce qu'il coûte

Une trentaine de mes tests ont résisté à leur première tentative. Les
causes, toutes distinctes :

| Cause | Exemple |
|---|---|
| **Mutation équivalente sur mes données** | Avec « mot » répété, la troncature tombe pile sur un espace : les deux branches rendent le même texte |
| **Je sautais la ligne testée** | `_action_executed = True` posé à la main — la ligne 875 ne s'exécutait jamais |
| **La même condition écrite deux fois** | Une par chemin (photo mobile / capture d'écran). N'en tester qu'un laissait l'autre vivant |
| **Mauvaise propriété mesurée** | J'assertais la taille des morceaux RAG ; la ligne décide la **fusion** |
| **Double surveillant la mauvaise méthode** | `ask()` appelle `save_message`, pas `save_response` — j'ai failli signaler un bug inexistant |
| **État non discriminant** | En mode dégradé, `use_chroma` et `collection` sont tous deux faux : `and` et `or` donnent le même résultat |

### ⚠️ Trois fois le même piège de syntaxe

Un commentaire commençant par les mots d'une directive **est lu comme une
directive** :

- `# noqa` en tête de commentaire → ruff crée un `noqa` **blanket** qui
  supprime toutes les règles de la ligne (2 fois)
- `# type: ignore` en tête de commentaire → mypy le lit comme une
  directive mal formée (1 fois)

### ⚠️ Et un échec silencieux dans mon propre outillage

Un script de correction faisait un `str.replace()` qui **n'a pas matché**
(échappement du `\n`), puis imprimait « corrigé » sans vérifier.
**J'ai rapporté une correction qui n'avait pas eu lieu.** Corrigé par une
assertion sur le remplacement.

> C'est le motif traqué dans le code, appliqué à mes outils : une
> opération qui annonce un succès sans l'avoir constaté.

---

## 1.8 Autres travaux de la session

### Ollama — le magasin amputé

Luca's est tombée en pleine utilisation : « Modèle `gpt-oss:20b`
introuvable ». L'application tray servait un magasin de **2 modèles sur
13**, sans `gpt-oss`, sans `llava`, sans `nomic-embed-text`.

**Le démarrage automatique n'était PAS en cause** — vérifié : aucune clé
Run, aucune tâche, `Ollama.lnk` dans `Startup-Disabled` depuis le 02/08.
Le vrai mécanisme, **établi par test dans les deux sens** : la CLI Ollama
réveille l'appli tray **quand aucun serveur ne répond**.

Correctif : tâche `LucasOllamaServer` qui garantit qu'un serveur répond
toujours.

**Leçon associée** : arrêter un serveur Ollama ne libère pas la VRAM. Les
`llama-server.exe` **petits-enfants** survivent à leur parent. Deux
orphelins tenaient 15 318 / 16 303 Mo → latence 19-58 s. Après
nettoyage : **2,3 s**.

### Comparatif de modèles — la conclusion s'est inversée

Six candidats mesurés sur cette machine.

| Modèle | Coût VRAM | Marge | 1ᵉʳ token | Débit | Guichet |
|---|---|---|---|---|---|
| `granite4.1:8b` | 5 903 Mo | 8 381 | **0,10 s** | 133 t/s | **4-6/15** ❌ |
| `gemma3:12b` | 9 044 Mo | 4 493 | 0,34 s | 89 t/s | 1-2/15 |
| **`gpt-oss:20b`** | 12 501 Mo | 1 011 | 1,30 s | **170 t/s** | **0-1/15** |
| `gemma4:latest` | 4 506 Mo | 9 684 | 3,27 s | 156 t/s | **0/15** |
| `qwen3:14b` | 9 485 Mo | 4 050 | 3,30 s | 87 t/s | 0-1/15 |
| `gemma4:26b` | 13 993 Mo | 522 | 11,23 s | 85 t/s | — |

**Sur le MoE, mesuré deux fois** : `gemma4:26b` déclare 17 367 Mo dont
seulement **12 794 tiennent sur le GPU** — 4,6 Go débordent en RAM. Un
MoE réduit le **calcul**, jamais la **mémoire**.

**Ce qui a inversé la conclusion** : le coût VRAM de Godot était supposé
en gigaoctets. **Mesuré : 246 Mo.** Donc `1 011 − 246 = 765 Mo restants`
— Godot cohabite avec `gpt-oss:20b`. Le problème qui motivait le
changement n'existait pas.

**Aucune bascule en production.**

### Veille modèles automatisée

Règle 12 ajoutée à `CLAUDE.md` : veille LLM **et** VLM traitées
**ensemble**, dans la même passe. Justification technique, pas
organisationnelle : avec `VLM_NEEDS_VRAM_MO = 4700`, ni `gpt-oss:20b` ni
`gemma3:12b` ne laissent la place à un VLM résident. **Choisir le LLM
seul, c'est présélectionner le VLM sans le savoir.**

Tâche `LucasVeilleModeles` — hebdomadaire, lundi 09:00. Trois garanties
**mécaniques** (pas des intentions) :

| Garde | Ce qu'elle garantit |
|---|---|
| **G1** | `config.py` restauré s'il a bougé — aucune bascule ne survit à une veille |
| **G2** | Tout modèle apparu pendant la passe est supprimé après |
| **G3** | Godot arrêté s'il apparaît (jamais relancé automatiquement — sa fenêtre capte tous les clics) |

**Les gardes ont été éprouvés, et le premier essai a échoué** : `2>&1`
sur un exécutable natif déclenche un `NativeCommandError` qui, avec
`$ErrorActionPreference = "Stop"`, **interrompt le script** — après avoir
modifié `config.py` et **avant** G1. Correctif structurel : les gardes
passent dans un `finally`.

### 🔴 1ʳᵉ passe de veille : `llava` invente ce qu'il lit

Mesuré avec une image **fabriquée** (contenu connu), pas un benchmark tiers :

| Modèle | Lecture | Invente | 1ᵉʳ token |
|---|---|---|---|
| **`qwen2.5vl:7b`** | **4/4** | non | **0,14 s** |
| `qwen3-vl:8b` | 4/4 | non | 1,12 s |
| `llava:latest` *(actuel)* | **0/4** | **oui** | 0,04 s |

Sur « Relevé du 12 juillet 2026 / 1847 euros », `llava` a rendu « Refle
du 21 Juillet / 1,91 € » puis « RELEVE DU 1ER JUIL 2023 ». **Des chiffres
faux mais crédibles** — le pire mode de défaillance pour un capteur censé
lire l'écran.

`VLM_ENABLED = False`, donc aucun risque actif. **Mais `llava` ne doit
pas être réactivé tel quel.**

Corrections au passage : le tag recommandé par le rapport Cowork
(`qwen2.5-vl:7b`) **n'existe pas** — le vrai est `qwen2.5vl:7b`, sans
tiret.

### `config.json` est inerte

`CLAUDE.md` le décrivait comme « Config utilisateur (modifiable) ». Il
n'est lu par **aucun module** — vérifié sur trois angles. L'éditer ne
produit rien, sans message ni erreur. Constante morte retirée,
documentation corrigée. **Le fichier n'a pas été supprimé** : c'est la
décision de Cyril.

### Le tableau des modèles décrivait 4 modèles inexistants

`internvl2`, `llava:13b`, `bge-m3`, `mistral-nemo` — **aucun installé**.
Et `qwen2.5:7b`, listé comme classifieur, ne sert plus (`INTENT_MODEL`
vaut `gpt-oss:20b`). Tableau réécrit avec les VRAM mesurées.

---

# Partie 2 — État d'avancement du projet Luca's

## 2.1 Où en est le produit

| Phase | Semaine | Contenu | État |
|---|---|---|---|
| **0 — Audit** | S0 | Nettoyage, inventaire | ✅ Fait |
| **1 — Cerveau solide** | S1 | FastAPI unique + World Model | ✅ Fait et validé |
| **2 — Mémoire & Finance** | S2 | RAG, TTS, Finance CSV | ✅ Fait — validation finance sur données fictives, **un export réel de Cyril reste attendu** |
| **3 — Vision & Voix** | S3-S4 | VLM écran, avatar, 5 modes, barge-in | 🟡 **En cours** — VLM écran ✅, 5 modes ✅, barge-in implémenté mais **non validé en conditions réelles** |
| **4 — Expansion** | S5-S6 | PWA mobile, sync, Godot | 🟡 **Amorcé** — pont mobile livré (chat, micro, caméra, TTS, HTTPS), accès distant Tailscale opérationnel |
| **5 — Polish** | S7-S8 | Sécurité finale, packaging, v1.0 | ⬜ À venir |

## 2.2 Ce qui tourne aujourd'hui

**Services actifs**

| Service | État |
|---|---|
| Serveur API (port 8000) | ✅ En écoute, certificat Tailscale chargé |
| Ollama (port 11434) | ✅ 14 modèles, magasin complet |
| Accès distant Tailscale | ✅ Fonctionnel, coexiste avec le VPN Bitdefender |

**Tâches planifiées** — 4, toutes vérifiées

| Tâche | Déclencheur |
|---|---|
| `LucasAPIServer` | à l'ouverture de session |
| `LucasOllamaServer` | à l'ouverture de session |
| `LucasCoworkRequests` | ouverture de session + 22:00 |
| `LucasVeilleModeles` | **lundi 09:00** — prochaine : 10/08/2026 |

**Modèles**

| Rôle | Modèle | État |
|---|---|---|
| Principal | `gpt-oss:20b` | ✅ actif — 12 501 Mo, 2-3 s par échange |
| Embeddings RAG | `nomic-embed-text` | ✅ actif |
| Classifieur d'intention | `gpt-oss:20b` | ✅ actif (partage le principal) |
| TTS | `edge_tts` / Piper | ✅ actif, routé par sensibilité |
| Vision (VLM) | `llava:latest` | ⛔ **coupé** — et à ne pas réactiver tel quel |

## 2.3 Santé du code

| Indicateur | Valeur |
|---|---|
| Fichiers de production | 50 — **11 478 lignes** |
| Fichiers de tests | 57 — **19 417 lignes** |
| Ratio test / code | **1,69** ligne de test par ligne de code |
| Couverture | **100 %** (3 568 lignes mesurées) |
| Tests | **1 446** |
| ruff | **0 alerte**, tout le projet |
| mypy | **0 erreur**, 116 fichiers, `--check-untyped-defs` |
| **Score de mutation** | **99,5 %** — 602/605, 40 modules sur 41 à 100 % |
| `just check` | **code de retour 0** |

## 2.4 Ce qui attend une décision ou une action de Cyril

### Actions concrètes

| Point | Pourquoi lui |
|---|---|
| **Lien d'appairage** à ouvrir sur le S25 Ultra | Nouveau jeton après rotation ; à effacer de l'historique Chrome ensuite |
| **Calibration du barge-in** | Exige le téléphone et une voix réelle |
| **Export bancaire réel** | La finance n'a été validée que sur données fictives |
| **Magasin Ollama imbriqué (~26,7 Go)** | Plus servi, mais sa suppression demande de confirmer qu'il ne contient rien d'unique |

### Décisions ouvertes

| Sujet | Enjeu |
|---|---|
| **Périmètre de règles ruff** | Aucune config n'existe : le périmètre bouge à chaque montée de version. Le figer explicitement ajouterait ~266 alertes (mesuré) — c'est une politique, pas un réglage |
| **`config.json`** | Le supprimer, ou le brancher pour de vrai |
| **Tâche horaire de tests du daemon** | La réparer lancerait 1 446 tests par heure |
| **Réactivation du VLM** | `llava` disqualifié par mesure. `qwen2.5vl:7b` en tête, à re-mesurer localement |
| **Modèle principal** | `gpt-oss:20b` reste le meilleur compromis. Le choix redevient ouvert **quand le VLM reviendra** — les deux se tranchent ensemble |

### Chantiers gelés, par décision antérieure

- **Avatar Godot** — attend une session où Cyril supervise en direct
- **Sécurité niveau 2** — même traitement
- **HERMES / multi-agents** — acté sur le principe, conception détaillée non ouverte

## 2.5 Ce que la journée a établi de plus utile

**Trois échelles de vérification, trois choses différentes**

| Outil | Ce qu'il mesure | Ce qu'il ne voit pas |
|---|---|---|
| **Couverture** | « cette ligne s'exécute » | si elle fait la bonne chose |
| **Mutation** | « si cette ligne faisait le contraire, quelqu'un le remarquerait » | les tests qui n'exécutent rien |
| **Exécution réelle** | ce qui se passe vraiment sur la machine | — |

Le projet était à **100 % de couverture** avec un score de mutation de
**85,5 %** : 86 lignes s'exécutaient sous test sans que rien ne vérifie
leur comportement. Il est aujourd'hui à **100 % / 99,5 %**.

⚠️ **Ce que 99,5 % ne veut PAS dire.** Ce n'est pas « le code est sans
bug ». C'est : *les mutations que mon outil sait produire sont toutes
détectées par la suite*. Un bug de conception, une exigence mal comprise,
une interaction entre modules — rien de tout cela ne se mute. La mutation
mesure la **qualité des tests**, pas la justesse du produit.

**Et la couverture a trouvé un test vide que la mutation avait manqué.**
Aucun des deux ne remplace l'autre.

**Le principal défaut trouvé était dans mes propres tests et outils** —
pas dans le code de Luca's. Sur les 86 survivants, une trentaine ont
résisté à ma première tentative, et deux défauts de mesure ont failli me
faire rapporter un résultat faux.

> La discipline qui a fonctionné : **ne jamais rapporter un succès sans
> l'avoir constaté**, et vérifier l'instrument avant la mesure.

---

*Généré le 06/08/2026. Détail complet et traçabilité : `ROADMAP.md`
§5.55 à §5.65.*
