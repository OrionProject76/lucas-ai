# Comparatif VLM (vision écran) — candidats 2026 pour remplacer llava/internvl2

**Date** : 05/08/2026
**Contexte** : `VLM_ENABLED = False` depuis le 01/08/2026 (llava fabriquait du contenu inexistant). Cette note recherche et compare 3 à 5 candidats sérieux pour une éventuelle réactivation — **elle ne réactive rien** : la décision reste entièrement à Cyril, après ses propres tests sur des cas réels (point 5 des règles de la demande).

## Recommandation en une phrase

**Tester `qwen2.5-vl:7b` en premier** (hallucination mesurée la plus basse des candidats trouvés dans un benchmark public — 0,33 %, OCR fort, aucun bug bloquant connu sur Ollama/CUDA aujourd'hui), avec **`minicpm-v4.6` en second candidat sérieux** si l'usage penche vers de la lecture de document dense plutôt que de la description de scène — et **exclure `Qwen3-VL` pour l'instant**, malgré son classement supérieur sur le papier, à cause d'un bug de bascule GPU encore ouvert sur les GPU NVIDIA récents (RTX 50-series comprise).

---

## 1. Ce qui change tout le calcul VRAM : ce n'est plus une cohabitation, c'est une bascule

**Trouvé en croisant `ROADMAP.md` §5.44-5.45 (lecture seule), pas supposé.** Depuis la bascule sur `gpt-oss:20b` comme modèle principal (validée par Cyril, en production), la contrainte VRAM pour la vision n'est **plus** « quel VLM tient dans la marge restante » — elle est mesurée et documentée noir sur blanc :

- `gpt-oss:20b` (chat + RAG) consomme **15 291 Mo** sur les 16 Go de la RTX 5080 → **1 093 Mo de marge**.
- `llava` (~4,7 Go) **ne tient pas** dans cette marge — confirmé explicitement dans `ROADMAP.md` §5.44, point 2.
- §5.45 point 2 est encore plus net : réactiver `VLM_ENABLED` avec gpt-oss **ne produira aucune erreur** — Ollama déchargera le modèle de chat pour charger le VLM, puis l'inverse, à chaque analyse d'écran, pour un coût mesuré d'**environ 3 s par aller-retour**. Ce chiffre a été mesuré avec `llava` ; il donne un ordre de grandeur, pas une promesse pour un autre modèle — à revérifier une fois le candidat choisi.

**Conséquence directe sur cette comparaison** : aucun des candidats sérieux ci-dessous (2 à 8 Go) ne pose de problème de taille — ils tiennent tous largement seuls dans 16 Go pendant leur fenêtre de bascule. Le critère qui distingue les candidats n'est donc **pas** la VRAM brute, mais : le taux d'hallucination (priorité explicite de Cyril), la qualité OCR, et — nouveau, absent de la demande initiale mais découvert en recherchant — **la présence ou non d'un bug de fonctionnement connu sur Ollama aujourd'hui**, qui peut à lui seul disqualifier un candidat malgré de meilleurs chiffres sur le papier.

## 2. Deux problèmes distincts déjà documentés dans le projet — à ne pas confondre

La demande initiale les nomme comme un seul sujet (« le problème d'hallucination déjà documenté — contamination du contexte par l'historique de refus »). En relisant `ROADMAP.md`, ce sont en réalité **deux bugs différents, à deux endroits différents de la chaîne** :

| | **Fabrication par le VLM** (`VLM_ENABLED=False`, décision du 01/08/2026) | **Auto-imitation de refus** (§Aspect 2, corrigé le 03/08/2026) |
|---|---|---|
| Où | Dans le modèle de vision lui-même (llava) | Dans le modèle de **chat** (qwen2.5:7b à l'époque), après que la vision a fonctionné |
| Symptôme | Invente des erreurs techniques inexistantes à l'écran : une erreur `docker.sock`, un `mount /dev/sda6`, un traceback Python complet avec numéro de ligne — rien de tout ça n'était affiché | Le modèle **répond quand même** « je n'ai pas accès à l'écran », alors que l'OCR a bien lu l'écran et que le bloc vision est bien injecté — il imite ses propres refus récents dans l'historique de conversation |
| Cause | Le modèle vision fabrique du contenu plausible mais faux (comportement propre à llava, documenté sur 4 captures réelles) | Un problème d'historique/orchestration (`core/lucas_core.py`), sans rapport avec la fidélité du VLM |
| État | Cause du `VLM_ENABLED=False` actuel — **c'est le sujet de cette note** | Corrigé par un filtre heuristique (`is_vision_refusal()`), **explicitement « pas une solution définitive »** — 2 refus sur 3 ont encore échappé au filtre lors de la revalidation du 03/08, malgré une réponse finale correcte cette fois-là |

**Ce que ça implique pour le choix du VLM** : le second problème (auto-imitation) ne dépend pas du VLM choisi — c'est un problème d'historique de conversation, désormais côté `gpt-oss:20b`, et le filtre actuel a été construit sur les formulations observées avec qwen2.5:7b, pas avec gpt-oss. **Hors scope de cette demande** (« ne rien changer côté LLM »), mais un point à garder à l'esprit si Cyril observe encore des refus de vision après la bascule — ce ne serait pas un signe que le nouveau VLM hallucine, mais que le filtre doit être revalidé sur le nouveau style de formulation de gpt-oss. Le premier problème (fabrication), lui, dépend entièrement du modèle de vision — c'est ce que compare cette note.

## 3. Les candidats

Recherche du marché actuel (août 2026), pas d'une liste figée à l'avance. `llava:13b` et `internvl2` sont exclus d'office : le premier est la cause documentée du `VLM_ENABLED=False`, le second n'a jamais été testé en réel dans le projet et appartient à la même génération que llava.

### 3.1 `qwen2.5-vl:7b` — le point de départ, confirmé sérieux

- **Statut Ollama** : modèle officiel, disponible directement (`ollama pull qwen2.5-vl:7b` sur Ollama ≥ 0.7.0).
- **VRAM** : ~6-8 Go en Q4 — tient seul largement dans 16 Go.
- **Hallucination mesurée** (benchmark indépendant PhotoPrism, pas un chiffre marketing) : **0,33 %** sur la variante 7B, la plus basse mesurée parmi les modèles testés dans cette source — contre 2 % pour Gemma 3 4B dans le même test.
- **OCR** : décrit comme fort en reconnaissance de texte, âge/genre de sujet, lieux, points de repère.
- **Limite trouvée** : le même benchmark note que la précision OCR reste la plus haute sur du texte anglais net — **aucune donnée chiffrée trouvée spécifiquement sur le français**, à vérifier par Cyril sur ses propres captures.
- **Bug bloquant connu ?** Aucun trouvé à ce jour pour cette version (contrairement à Qwen3-VL, voir 3.2).

### 3.2 `qwen3-vl` — supérieur sur le papier, **exclu pour l'instant**

C'est le candidat que la demande soupçonnait déjà (« bug de câblage connu début août — revérifier si corrigé »). **Vérifié : toujours pas corrigé.**

- **Scores publics** (déclaratifs, source commerciale, à prendre avec prudence) : MMMU 69,6, DocVQA 96,1 pour la variante 8B — supérieur à Qwen2.5-VL sur le papier.
- **Bug 1 — toujours ouvert** : [ollama/ollama#16264](https://github.com/ollama/ollama/issues/16264) — le modèle s'enregistre comme compatible vision mais **plante dès la première requête image** (`exit status 2`, « model runner has unexpectedly stopped »). Signalé sur Apple Silicon, sans assigné ni correctif en vue au moment de la recherche.
- **Bug 2 — toujours ouvert, et plus inquiétant pour la config de Cyril** : [ollama/ollama#14548](https://github.com/ollama/ollama/issues/14548) — sur **RTX 5090** (même génération Blackwell que la RTX 5080 de Cyril), le traitement d'une seule image de 512×375 prend **33 secondes**, malgré flash attention activé et les couches bien envoyées sur le GPU — la partie vision semble mal déchargée sur le GPU. Aucune donnée spécifique RTX 5080 trouvée, mais l'architecture est la même famille que celle déjà identifiée comme fragile pour faster-whisper (voir rapport STT du 03/08).
- **Conclusion** : ne pas installer Qwen3-VL en production tant que ces deux tickets restent ouverts — un modèle qui plante ou qui prend 30+ secondes par image serait pire que la situation actuelle (OCR seul, sans VLM). À resurveiller : les deux bugs évoluent vite selon leur propre historique de commentaires.

### 3.3 `minicpm-v4.6` (ou 4.5) — spécialiste OCR/document, sérieux

- **Statut Ollama** : présent dans la bibliothèque officielle (`ollama.com/library/minicpm-v4.6`), tag standard ~1,6 Go (existe aussi en variante 8B pleine, ~5-6 Go en Q4_K_M selon la source).
- **Spécialité** : conçu prioritairement pour l'OCR et la compréhension de documents, gère bien la haute résolution et le texte dense — plusieurs sources indépendantes le décrivent comme *« the best all-around local document-OCR model for normal hardware »*.
- **Scores** : élevés sur OCRBench et OmniDocBench (bancs publics spécialisés OCR).
- **Pas de bug bloquant trouvé** à ce jour.
- **Pourquoi second et pas premier** : moins de données d'hallucination chiffrées trouvées (contrairement à Qwen2.5-VL, pas de mesure indépendante équivalente au test PhotoPrism) — sa force documentée est la précision OCR, pas spécifiquement la résistance à la fabrication de contenu. À tester en second, en particulier si Qwen2.5-VL déçoit sur de la lecture d'écran dense (tableaux, code, texte petit).

### 3.4 `gemma3:4b` (vision) — le repli léger, pas le premier choix

- **VRAM** : ~3 Go en Q4, le plus léger des candidats sérieux, donc la bascule GPU la plus rapide.
- **Intégration** : « jour-un » dans Ollama, la meilleure compatibilité runtime des candidats testés.
- **Hallucination mesurée** (même source PhotoPrism que Qwen2.5-VL, donc comparable) : **2 %**, taux d'erreur global ~25 % — nettement au-dessus du 0,33 % de Qwen2.5-VL 7B.
- **Conclusion** : candidat de repli si la latence de bascule (§1) s'avère gênante en usage réel et qu'un modèle plus léger devient nécessaire — mais avec le critère prioritaire de Cyril (hallucination), ce n'est pas le premier choix. Gemma 4 (12B/27B, sorti courant 2026) a été regardé aussi : VRAM 6,6 Go / 14,9 Go en Q4 — trop récent, aucune donnée d'hallucination indépendante trouvée, aucune preuve de disponibilité vision stable au moment de la recherche. Pas retenu pour l'instant, à resurveiller.

### 3.5 Exclus explicitement, avec la raison

- **Moondream (2/3)** : très léger (~1,5-2 Go), rapide, mais les sources le décrivent explicitement comme *non adapté aux documents denses* — utile pour des légendes courtes, pas pour lire un écran chargé (fenêtres, menus, paragraphes). Écarté pour l'usage principal de Luca's.
- **InternVL3** : n'existe sur Ollama que via un tag communautaire non-officiel (`blaifa/InternVL3`), pas la bibliothèque Ollama elle-même — risque d'intégration/maintenance plus élevé, à l'image du choix déjà fait pour faster-whisper (intégration native préférée à un binding tiers moins mûr). Écarté pour cette raison, indépendamment de sa qualité.

## 4. Ce qui reste à faire — et qui ne peut PAS être fait depuis cette session

Cette note est une recherche documentaire, sourcée sur le marché actuel et sur les données déjà mesurées dans le projet — **elle ne mesure rien sur les vraies captures d'écran de Cyril**, ce qui était le critère prioritaire de la demande. Concrètement, ni cette session cloud ni cette note ne peuvent :

- Charger un modèle Ollama et lui soumettre une vraie capture d'écran du projet.
- Mesurer un taux d'hallucination réel sur plusieurs cas réels, comme l'exige le point 5 des règles (validation manuelle par Cyril avant toute réactivation).
- Vérifier la qualité OCR en français sur des cas concrets — aucune donnée publique chiffrée trouvée sur ce point précis pour aucun candidat.
- Mesurer la latence de bascule réelle (§1) avec un modèle autre que llava.

**Proposition d'ordre de test, une fois Cyril devant son PC** : `qwen2.5-vl:7b` d'abord (meilleur compromis hallucination/OCR/maturité), puis `minicpm-v4.6` si le premier déçoit sur du texte dense, en laissant `VLM_ENABLED=False` jusqu'à validation explicite sur plusieurs cas réels — conformément au point 5 de la demande.

## 5. CLAUDE.md — correction factuelle appliquée

Le tableau des modèles de `CLAUDE.md` mentionnait encore `deepseek-coder:33b` comme modèle **Principal**, alors que `gpt-oss:20b` est en production depuis le 05/08/2026 (`ROADMAP.md` §5.45 : *« Cyril a validé l'option A. `MODEL_NAME = "gpt-oss:20b"`, en production »*). Écart confirmé → **corrigé**, uniquement cette ligne :

- Avant : `| Principal | deepseek-coder:33b | ~20 Go | Raisonnement, code, chat |`
- Après : `| Principal | gpt-oss:20b | ~15,3 Go (mesuré, chat+RAG — ROADMAP.md §5.44) | Raisonnement, code, chat |`

Les autres lignes du tableau (Vision, Rapide, Créatif, Memory) n'ont **pas** été touchées — hors du périmètre explicitement autorisé par la demande. Deux écarts supplémentaires remarqués en chemin, notés ici sans être corrigés :
- La ligne **Vision** (`internvl2 / llava:13b`) est précisément le sujet non tranché de cette note — à mettre à jour seulement après le choix réel de Cyril.
- La ligne **Rapide** (`qwen2.5:7b`) pourrait être obsolète : `ROADMAP.md` §5.45 indique que `INTENT_MODEL` a été aligné sur `MODEL_NAME` (gpt-oss:20b), donc qu'il n'y a plus de modèle « rapide » séparé pour le routage — mais ce n'était pas dans le périmètre autorisé par cette demande (limité explicitement à l'écart gpt-oss:20b), donc non corrigé ; à signaler à Cyril pour une future demande dédiée.

---

## Sources

- [GPT-OSS 20B VRAM Requirements (12.8GB Q4_K_M) — Will It Run AI](https://willitrunai.com/models/gpt-oss-20b)
- [GPT-OSS:20B running almost entirely on CPU · Issue #11731 · ollama/ollama](https://github.com/ollama/ollama/issues/11731)
- [The Best Local Vision Language Models in 2026 — TinyWeights.dev](https://tinyweights.dev/posts/best-local-vision-language-models-2026/)
- [Best Ollama Vision Models 2026: Tested & Ranked — Serverman](https://www.serverman.co.uk/ai/ollama/best-ollama-models-for-vision/)
- [Local Vision-Language OCR Benchmark — nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- [Qwen3-VL-8B GGUF + mmproj crashes on first image request · Issue #16264 · ollama/ollama](https://github.com/ollama/ollama/issues/16264)
- [Qwen3-VL slow on RTX 5090 · Issue #14548 · ollama/ollama](https://github.com/ollama/ollama/issues/14548)
- [How to Run Qwen 3 VL Models Locally with Ollama — Apidog](https://apidog.com/blog/how-to-run-qwen-3-vl-locally-with-ollama/)
- [Vision Model Comparison — PhotoPrism developer docs](https://docs.photoprism.app/developer-guide/vision/model-comparison/)
- [minicpm-v4.6 — Ollama library](https://ollama.com/library/minicpm-v4.6)
- [Best Local Vision Model for OCR — MyLocalAI](https://mylocalai.org/blog/best-local-vision-model-ocr)
- [Gemma 4 VRAM Requirements: 12B, 27B & E4B on Ollama (2026) — RunAIatHome](https://runaiathome.com/blog/gemma-4-local-setup-guide/)
- [GeForce RTX 50XX cuBLAS failed with status CUBLAS_STATUS_NOT_SUPPORTED · Issue #1865 · OpenNMT/CTranslate2](https://github.com/OpenNMT/CTranslate2/issues/1865)

*Croisé avec `ROADMAP.md` §5.44, §5.45 et §Aspect 2 (mesures réelles du projet) et `CLAUDE.md` (tableau des modèles, corrigé sur la seule ligne Principal) — lus/modifiés sur `C:\OrionAI` via le pont bureau, aucun autre fichier touché. `ROADMAP.md` et `VISION_LONG_TERME.md` non modifiés, conformément aux règles de la demande.*
