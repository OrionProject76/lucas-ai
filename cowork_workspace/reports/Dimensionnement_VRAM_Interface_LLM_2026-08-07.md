# Dimensionnement VRAM — Interface d'abord, LLM dans la marge restante
**Date : 07/08/2026. Recherche + mesure uniquement — aucune bascule en production, aucun code d'avatar committé.**

**Condition de base, valable pour TOUTE mesure de ce rapport : le flux TV Orange était actif sur Microsoft Edge du début à la fin de cette recherche** (fenêtre « En direct - OrangeTV », process `msedge.exe` PID 32248, ouverte depuis 12h30, jamais fermée). Aucun chiffre de ce rapport n'a été pris TV éteinte.

**Aucun chiffre d'une session antérieure à aujourd'hui n'a été réutilisé tel quel** — tout ce qui suit a été mesuré dans cette session, sur cette machine.

---

## 0. Budget VRAM réel de départ

> **Budget réel retenu pour ce rapport : ~13 100 Mo sur 16 303 Mo totaux** (cas médian mesuré, TV active — détail et fourchette ci-dessous). C'est ce chiffre, pas les 16 303 Mo bruts, qui sert de point de départ à tous les calculs des sections suivantes.

**Confirmé avant chaque mesure de cette section : Ollama vide (`curl .../api/ps` → `{"models":[]}`) et aucun process Godot actif (`tasklist` vérifié)** — seule la TV (et les applications de bureau habituelles de Cyril) restait active, conformément à l'Étape 0 du brief.

### Ce qui a été mesuré, et ce qui ne l'a pas pu être

`nvidia-smi --query-compute-apps` ne rend **aucune** valeur par processus sur cette RTX 5080 (`[Insufficient Permissions]` / `[N/A]` sur toutes les entrées sans exception, y compris `msedge.exe` — vérifié deux fois). C'est une limite du pilote sur cette carte grand public, pas un oubli.

**Contournement trouvé et vérifié : le compteur de performance Windows `\GPU Process Memory(*)\Dedicated Usage`** (`Get-Counter` PowerShell, lecture seule, aucun P/Invoke) donne bien des valeurs par processus, via la comptabilité WDDM plutôt que NVML. Somme des process `msedge.exe` réels (14 process listés par `tasklist`, deux avec une charge non nulle) : **≈ 996 Mo**.

⚠️ **Ce chiffre est une estimation, pas une mesure certaine.** Croisé avec `nvidia-smi` au même instant : la somme WDDM de **tous** les process (5 053 Mo) ne correspond pas au total `nvidia-smi` (3 316 Mo) au même moment — un écart de méthode déjà connu entre comptabilité WDDM et NVML (le premier peut compter de la mémoire réservée/partagée que le second ne compte pas comme réellement occupée). Le sous-total Edge (996 Mo) hérite donc de la même marge d'erreur — à lire comme « de l'ordre de 500 Mo à 1 Go », pas comme une valeur exacte.

### Le chiffre qui compte réellement pour ce rapport

Le budget qui sert à tous les calculs ci-dessous n'est **pas** ce sous-total Edge isolé (trop incertain), mais le **total VRAM réellement utilisé mesuré par `nvidia-smi`**, TV comprise puisqu'elle n'a jamais été coupée — la même méthode par delta déjà utilisée avec succès pour tout le reste du projet (Godot, Ollama).

**⚠️ Ce total a fluctué de façon notable sur la durée de la session — de 1 484 à 3 662 Mo** — apparemment sans lien avec la TV elle-même (restée ouverte en continu), mais avec le nombre d'applications simultanément ouvertes sur ce PC (Chrome, VS Code, Claude Desktop, Steam...) et de possibles variations du flux TV lui-même (débit, publicité, scène). **Ne pas prétendre à une précision que la mesure n'a pas.**

| | VRAM totale utilisée | Budget réel (16 303 − ce chiffre) |
|---|---|---|
| **Cas favorable** (mesuré, TV + rien d'autre de lourd) | 1 484 Mo | **14 819 Mo** |
| **Cas médian** (mesuré à plusieurs reprises dans la session) | ~3 200 Mo | **~13 100 Mo** |
| **Cas le plus chargé mesuré** | 3 662 Mo | **12 641 Mo** |

**Le calcul des paliers ci-dessous utilise le cas médian (~13 100 Mo) comme référence**, avec le cas le plus chargé (12 641 Mo) donné en regard à chaque fois qu'il change la conclusion.

---

## 1. Coût VRAM de l'interface, par palier (TV active à chaque mesure)

Mesuré sur le projet Godot **réellement lancé** (scripts vivants, pas le binaire figé), en modifiant temporairement `FENETRE_TAILLE` et l'appel à `_masquer_hud()` — **tous les changements ont été intégralement annulés après mesure** (`git status` vérifié propre, aucun résidu committé).

| Palier | Configuration | VRAM avant | VRAM avec | **Coût avatar** |
|---|---|---|---|---|
| **1 — minimal** | 600×600, sphères + shader hologramme (l'existant réel — pas de mesh de tête, voir §1bis) | 3 167 Mo | 3 421 Mo | **+254 Mo** |
| **2 — intermédiaire** | 1400×900, HUD actuel visible (proxy le plus proche d'un « HUD partiel » — le projet n'a pas de mode d'affichage sélectif des widgets) | 3 172 Mo | 3 521 Mo | **+349 Mo** |
| **3 — maximal** | 3840×2160 (plein écran), sans HUD (« rendu nul ») | 3 203 Mo | 4 087 Mo | **+884 Mo** |
| **3 — maximal, avec contenu** | 3840×2160, HUD actuel visible | 3 211 Mo | 4 094 Mo | **+883 Mo** |

**Trouvaille nette** : le contenu du HUD (jauges, panneaux, texte) ne coûte quasiment rien (883 vs 884 Mo, dans le bruit de mesure) — **le coût est presque entièrement celui de la résolution/du framebuffer**, pas du contenu affiché dessus. Attendu que des cadrans circulaires remplaceraient les `ProgressBar` linéaires actuelles pour un JARVIS complet coûteraient un peu plus (un shader radial n'est pas gratuit), mais rien qui change l'ordre de grandeur mesuré ici.

### §1bis — Ce qui n'a pas pu être mesuré, et pourquoi

Le « palier minimal » du brief (« mesh de tête + shader hologramme ») **n'existe pas encore** — `face_root.tscn` reste trois `SphereMesh` et un `BoxMesh` (`cowork_workspace/REFERENCE_VISUELLE_AVATAR.md` §1bis). Le shader hologramme, lui, **est déjà appliqué** sur cette géométrie primitive. Le chiffre du tableau (+254 Mo) est donc une mesure réelle du shader + d'une géométrie simple, pas d'un vrai mesh de tête — mais la différence attendue est faible : un mesh de tête low-poly reste de l'ordre de quelques centaines à quelques milliers de sommets, un volume de données négligeable en VRAM face aux textures et au framebuffer. **Non mesuré formellement, mais l'ordre de grandeur (quelques dizaines de Mo, pas plus) est cohérent avec ce que coûte n'importe quelle géométrie de cette taille.**

### ⚠️ Le palier maximal reste bloqué par DEUX verrous indépendants, la VRAM n'étant que l'un des deux

1. **Click-through.** Un HUD plein écran capte tous les clics du bureau tant que la GDExtension `WS_EX_TRANSPARENT` (`IDEAS.md` #95) n'existe pas — mesuré et documenté début du projet (Godot 4.7/GDScript pur ne peut pas faire les deux à la fois). C'est pour cette raison précise que la fenêtre 600×600 repositionnable existe aujourd'hui.
2. **VRAM** (chiffrée ci-dessus).

**Même avec une marge VRAM confortable (et c'est le cas — voir §4), le palier maximal reste bloqué tant que le verrou n°1 n'est pas levé.** Le chiffrer ici sert à la décision future, pas à annoncer qu'il est débloqué.

---

## 2. Candidats LLM testés — méthode

### Recherche de modèles récents

Recherche web ciblée sur les sorties récentes compatibles Ollama, 7B à 14B et variantes quantifiées. Retenus pour test réel : deux modèles **jamais testés dans ce projet** (`ministral-3:8b` — famille Ministral 3, vision + agentique, sorti récemment ; `granite4.1:8b` — déjà évoqué mais jamais mesuré ici), plus `gemma4:latest` (variante 8B, différente du `gemma4:26b` déjà écarté en RAM le 05/08), en plus des candidats déjà installés (`gpt-oss:20b`, `qwen3:14b`, `gemma3:12b`). Un candidat 36B MoE (`qwen3.6:latest`) a été vérifié pour mémoire (voir §5) — trop gros pour être un candidat sérieux, confirmé plutôt que supposé.

**Sources** : [ComputingForGeeks — Open Source LLM Comparison 2026](https://computingforgeeks.com/open-source-llm-comparison/), [Hugging Face — Best Open Source LLMs to Run Locally 2026](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally), [Ollama library — ministral-3](https://ollama.com/library/ministral-3), [Ollama library — qwen3](https://ollama.com/library/qwen3).

⚠️ **Nuance sur la « récence »** : la recherche donne des dates de sortie précises pour les familles (Qwen3, Ministral 3), mais pas pour le tag Ollama exact testé — un seul repère trouvé (page Ollama de `ministral-3:8b` : « mis à jour il y a 7 mois », soit début 2026) suggère que ce tag précis est moins récent que « dernières semaines » au sens strict, même si la famille elle-même est catégorisée comme actuelle par les sources consultées. `granite4.1:8b` et `gemma4:latest` n'ont pas de date de tag confirmée non plus. **Ces trois candidats sont nouveaux pour CE PROJET** (jamais mesurés ici avant aujourd'hui), ce qui n'est pas rigoureusement la même chose que « nouveaux sur le marché ».

### Harnais de mesure

Script jetable (non committé), **appelant Ollama directement** avec le vrai `config.SYSTEM_PROMPT` du projet — **délibérément sans passer par `LucasCore`/`MemoryManager`**, pour ne jamais écrire dans `memory/lucas_memory.db` (l'incident déjà documenté, ROADMAP.md §5.32, où une campagne de mesure avait écrit par erreur dans la vraie base de Cyril). **Vérifié après coup : `memory/lucas_memory.db` contient toujours exactement 100 conversations, dernière entrée à 13h23 — avant le début de cette recherche. Aucune pollution.**

15 questions réalistes, avec un historique simulé vouvoyé (la condition la plus dure, établie par les campagnes précédentes) : suivi tutoiement, absence de relance de guichet, plus deux questions de contrôle factuel (HNSW) et grammatical (subjonctif imparfait « qu'il résolût »).

**Détecteur de guichet validé AVANT mesure** (même méthode que le 05/08, où un détecteur fautif avait faussé un comparatif) : 6 positifs connus (« Comment puis-je t'aider aujourd'hui ? », etc.) tous détectés, 5 négatifs connus (dont le piège déjà repéré « Salut Cyril ! Comment vas-tu ? », qui n'est PAS du guichet) tous rejetés — 11/11 avant de mesurer quoi que ce soit.

### ⚠️ Incident de mesure trouvé et corrigé en cours de route

Les trois premiers modèles 8B testés (`gemma4:latest`, `ministral-3:8b`, `granite4.1:8b`) ont montré une VRAM croissante de façon incohérente (7 188 → 13 642 → 15 466 Mo). Cause trouvée : **Ollama garde plusieurs petits modèles chargés simultanément** quand leur somme tient sous 16 Go — il n'évince que lorsque c'est nécessaire. `curl .../api/ps` a confirmé les trois modèles résidents en même temps au moment de la troisième mesure. **Toutes les mesures VRAM ont été reprises individuellement**, chaque modèle isolé explicitement (`keep_alive: 0` sur les autres, `api/ps` vérifié vide avant chaque nouveau test) — ce sont les chiffres du tableau §3, pas les premiers relevés contaminés. Les scores de guichet/vitesse, eux, n'étaient pas affectés (un seul modèle calcule à la fois même si plusieurs restent résidents) et n'ont pas eu besoin d'être repris.

---

## 3. Tableau des candidats — mesures réelles, TV active, modèles isolés

| Modèle | VRAM propre (delta) | tok/s (moy/15) | 1er token (s) | Guichet | Vouvoiement | Remarque |
|---|---|---|---|---|---|---|
| **`gpt-oss:20b`** *(actuel)* | **12 549 Mo** | **170,0** | 0,16 | **0/15** | **0/15** | Voir note ⚠️ sous le tableau — ce chiffre n'est PAS directement comparable aux « ~15,3 Go » cités comme référence |
| `qwen3:14b` | 9 486 Mo | 87,8 | 0,38 | 0/15 | 0/15 | HNSW correct ; sujonctif « résolve » (pas la forme classique) |
| `gemma3:12b` | 9 032 Mo | 91,6 | 0,37 | 0/15 | 1/15 | 1 vouvoiement réel confirmé (« vos emails ») |
| `granite4.1:8b` | 5 878 Mo | 136,9 | 0,21 | 0/15 | 3/15 | Vouvoiements réels confirmés ; **récite `[Contexte]` littéralement** malgré l'interdiction explicite du prompt |
| `ministral-3:8b` | 6 447 Mo | 138,1 | 0,17 | 0/15 | 1/15 | **Seul candidat correct sur le subjonctif classique** (« résolût », avec nuance) — un seul tirage, pas confirmé sur plusieurs |
| `gemma4:latest` (8B) | 4 457 Mo | 155,7 | 0,23 | 0/15 | 0/15 | Le plus rapide des 8B et le plus propre — mais **refuse la question HNSW** (« sujet trop général »), une prudence excessive pour un assistant généraliste |

**Tous les six tiennent 0/15 au test de guichet** — c'est la consigne de style qui pèse le plus dans le prompt système actuel (répétée en exemples littéraux), pas une propriété rare d'un seul modèle. La différence entre candidats se joue sur le vouvoiement résiduel et la justesse factuelle/grammaticale, pas sur le guichet.

⚠️ **Aucun n'est « parfait »** : `gpt-oss:20b` gagne sur la vitesse et le zéro-défaut strict, mais coûte 2 à 3× la VRAM des candidats 8B pour un score de guichet qu'ils atteignent déjà tous. `ministral-3:8b` est le seul juste sur la grammaire la plus fine, sur un tirage unique — à confirmer, pas à généraliser sur cette seule mesure.

### ⚠️ 12 549 Mo (`gpt-oss:20b` seul) vs « ~15,3 Go » cité comme référence — deux mesures différentes, pas une contradiction

Le brief cite `gpt-oss:20b` à « VRAM ~15,3 Go » comme référence à reconfirmer. **Les deux chiffres sont réels, mais ne mesurent pas la même chose :**

- **12 549 Mo (ce rapport)** = le coût **isolé** du modèle seul, mesuré par delta (`nvidia-smi` avant/après chargement, Ollama vide sinon). Cohérent avec ce qu'Ollama rapporte lui-même comme poids du modèle en VRAM (`size_vram` via `/api/ps`, 12 148-12 736 Mo selon l'instant de mesure dans cette même session) et avec `CLAUDE.md` (12 501 Mo, §5.56) — écart de 48 Mo, dans le bruit.
- **~15,3 Go (référence du brief, ROADMAP historique)** = le **total système** mesuré quand `gpt-oss:20b` tourne, baseline (OS + apps ouvertes) comprise — dans des sessions antérieures où cette baseline était plus élevée (~2,8-3,7 Go selon le moment, voir §0). **Ce rapport a mesuré ce même total aujourd'hui : 14 633 Mo** (12 549 + baseline 2 084 Mo de cette mesure précise) — dans la fourchette basse de ce qui a été observé au fil des sessions (14,3 à 15,3 Go selon la charge du poste au moment du test, y compris une mesure à 15 638 Mo plus tôt dans la journée), pas une divergence.

**Le modèle lui-même n'a pas changé.** C'est la baseline (tout ce qui n'est pas Luca's) qui fait varier le total de 1 à 2 Go selon le moment — exactement le phénomène déjà documenté en §0. Le tableau ci-dessus utilise le coût **isolé** (12 549 Mo) parce que c'est lui qui est directement comparable aux autres candidats et directement soustractible du budget par palier (§4) — pas parce que le total historique était faux.

### Déchargement partiel CPU — mesuré sur `gpt-oss:20b` (24 couches)

| Configuration | VRAM propre | tok/s | Coût |
|---|---|---|---|
| 100 % GPU (24/24) | 12 549 Mo | **170,0** | référence |
| 75 % GPU (18/24, 6 couches sur CPU) | 9 424 Mo | **51,7** | **≈−25 % VRAM, −70 % vitesse** |
| 50 % GPU (12/24, 12 couches sur CPU) | 6 632 Mo | **30,2** | **−47 % VRAM, −82 % vitesse** |

**Le levier CPU est disproportionné sur ce matériel** : décharger un quart des couches ne fait gagner qu'un quart de VRAM mais divise la vitesse par plus de trois. Le Ryzen 9800X3D est rapide *pour un CPU*, mais l'alternance CPU/GPU par couche a un coût de sérialisation qui écrase le gain. **Ce n'est pas un levier praticable pour un usage conversationnel temps réel** sur cette machine — utile à savoir avant de le proposer comme solution à un futur manque de VRAM.

---

## 4. Tableau final par palier — le compromis réel

Budget cas médian : **~13 100 Mo**. Cas le plus chargé mesuré : **12 641 Mo** (colonne entre parenthèses, uniquement quand la conclusion change).

| Palier | Coût avatar | VRAM restante (médian) | Meilleur LLM atteignable | Marge après LLM | Marge **confortable** ? |
|---|---|---|---|---|---|
| **1 — minimal** | 254 Mo | 12 846 Mo (12 387) | **`gpt-oss:20b`** (12 549 Mo) | **~297 Mo** (−162 dans le cas le plus chargé) | **Non** — mince, négative dans le pire cas mesuré |
| **2 — intermédiaire** | 349 Mo | 12 751 Mo (12 292) | **`gpt-oss:20b`** (12 549 Mo) | **~202 Mo** (−257 dans le cas le plus chargé) | **Non** — mince, négative dans le pire cas mesuré |
| **3 — maximal** (VRAM seule — voir verrou click-through §1) | 884 Mo | 12 216 Mo (11 757) | **`qwen3:14b`** (9 486 Mo) — `gpt-oss:20b` (12 549) ne tient plus | **~2 730 Mo** avec qwen3:14b (2 271 dans le cas le plus chargé) | **Oui** — large dans les deux scénarios |

**Lecture honnête** : `gpt-oss:20b` — le modèle déjà en production, sans aucune bascule — **tient dans les paliers 1 et 2 avec une marge réelle mais mince** (200-300 Mo dans le cas médian, **négative dans le cas le plus chargé mesuré cette session**). Ce n'est pas un verdict figé : ça dépend de ce que Cyril a d'autre d'ouvert au moment où ça compte. **Au palier 3, `gpt-oss:20b` ne tient plus** avec la même marge de sécurité — `qwen3:14b` prend le relais avec une marge large (2,7 Go), au prix d'un débit deux fois moindre (87,8 contre 170 tok/s) et d'un subjonctif moins soigné.

**Aucun modèle testé n'est disqualifiant en dessous de 300 Mo de marge** dans l'absolu — mais une marge de 200 Mo mesurée dans une session où la VRAM a déjà varié de 2 200 Mo (§0) n'est pas une marge sur laquelle construire une garantie.

---

## 5. Le candidat trop gros — vérifié, pas supposé

`qwen3.6:latest` (36B, MoE, déjà installé) : chargé et interrogé une fois (pas de test guichet complet, coût jugé disproportionné pour un candidat déjà hors budget). **Charge malgré tout** — Ollama répartit automatiquement une partie sur RAM système — mais consomme **13 386 Mo** (VRAM propre) pour une réponse de 194 tokens en **23,6 secondes**, soit environ 8 tok/s — **20× plus lent que `gpt-oss:20b`** et très inférieur à tous les candidats du tableau §3.

**Ce qui le disqualifie réellement, c'est la latence, pas la VRAM seule** : en VRAM stricte, 13 386 Mo tiendrait numériquement au palier 1 dans le cas le plus favorable mesuré en §0 (marge ~1 179 Mo), mais pas dans le cas médian (dépassement d'environ 540 Mo) ni a fortiori dans le cas le plus chargé. C'est donc un ajustement **à la limite et inconsistant selon le moment**, avant même de considérer la vitesse — et une fois la vitesse prise en compte (23,6 s pour une réponse courte, un tirage unique mais un écart trop large pour être du bruit), ce candidat n'est réaliste pour aucun usage conversationnel, quel que soit le palier.

---

## 6. Étape 4 — Le routage dynamique est-il encore nécessaire ?

**Lecture honnête, sans trancher à la place de Cyril :**

**Aux paliers 1 et 2, un seul modèle statique (`gpt-oss:20b`, déjà en production) couvre déjà le besoin** — 0/15 guichet, la meilleure vitesse mesurée, et une marge VRAM positive dans les conditions médianes de cette session. **Mais cette marge est mince (200-300 Mo) et devient négative dans le pire cas mesuré aujourd'hui** (3 662 Mo d'occupation hors-Luca's, observé une fois cette session). Un seul modèle statique fonctionne donc **la plupart du temps**, pas **tout le temps** — c'est précisément le genre de situation qu'un `vram_watchdog.py` déjà en place (bascule vers l'avatar 2D sous un seuil) sait absorber sans routage LLM : la marge fine touche l'avatar avant de toucher le modèle.

**Au palier 3, l'écart est net** : `gpt-oss:20b` ne tient plus avec une marge confortable, `qwen3:14b` prend le relais mais coûte la moitié du débit. Router entre les deux selon la complexité de la requête aurait un sens si ce palier devient réel — **mais il reste bloqué par le verrou click-through indépendamment de la VRAM (§1)**, donc cette tension ne s'exprime pas encore dans l'usage réel.

**Conclusion factuelle, pas une recommandation** : dans l'état actuel du produit (paliers 1-2 seuls atteignables aujourd'hui, palier 3 gelé par un verrou non-VRAM), **la marge est trop fine pour dire que le statu quo est confortablement acquis, mais pas assez tendue pour dire qu'un routeur multi-modèle résout un problème qui existe aujourd'hui.** Le watchdog VRAM déjà construit couvre le cas de marge fine sans qu'un routage LLM soit nécessaire pour ça spécifiquement. Le routage ne deviendrait clairement justifié que si/quand le palier 3 (HUD immersif) devient réellement construit — et sa VRAM (884 Mo, mesurée) n'est de toute façon pas ce qui le bloque aujourd'hui.

---

## 7. Ce qui n'a pas été fait, à dire clairement

- **Aucune bascule en production.** `config.MODEL_NAME` reste `gpt-oss:20b`.
- **Aucun code d'avatar committé** — les changements temporaires de fenêtre/HUD ont été entièrement annulés (`git status` vérifié propre).
- **Le sous-total VRAM d'Edge isolé (996 Mo) est une estimation**, pas une mesure certaine — la méthode fiable (delta total `nvidia-smi`) a servi de référence à la place.
- **Le palier "mesh de tête réel" n'a pas pu être mesuré** — le mesh n'existe pas, construire dessus était hors scope de cette session.
- **`ministral-3:8b` n'a été testé qu'une fois** sur le test grammatical le plus fin (subjonctif) — pas confirmé sur plusieurs tirages, à ne pas généraliser en "le meilleur en français" sur cette seule donnée.
- **`qwen3.6:latest` n'a pas eu de test guichet complet** — jugé hors budget avant de le justifier par 15 tirages coûteux.
- **Les six mesures VRAM « propres » du tableau §3** viennent de lectures directes prises pendant la reprise après l'incident de contamination (§2) — consignées après coup dans `result_clean_vram_summary.json` (répertoire de travail) pour traçabilité, mais aucun fichier brut n'existait au moment même de chaque mesure individuelle. Les chiffres eux-mêmes sont cohérents entre plusieurs recoupements (Ollama `size_vram`, `CLAUDE.md` pour `gpt-oss:20b`) — mais ce n'est pas la même rigueur de preuve que les fichiers `result_*.json` du test de guichet, générés automatiquement par le script.

---

*Rapport rédigé le 07/08/2026, vérifié par relecture croisée indépendante (exactitude numérique, honnêteté, complétude vs brief) avant finalisation — deux erreurs mineures corrigées (arrondi de pourcentage, référence de section), un écart de fond clarifié (12,5 Go isolé vs 15,3 Go total historique, §3). Données brutes (JSON par modèle) conservées dans le répertoire de travail de la session, non committées.*
