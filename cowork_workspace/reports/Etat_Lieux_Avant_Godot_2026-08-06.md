# État des lieux avant le chantier Godot

**Date** : 06/08/2026, soir
**Objet** : revalidation générale en conditions réelles, avant ouverture du chantier Godot
**Nature** : vérification uniquement — **aucune construction nouvelle**

---

## ⚠️ Point encore ouvert, à trancher par Cyril

**Les 3 fichiers embarqués par erreur ce matin** attendent toujours ta décision :

```
ORION_AI_Specifications_Completes_Claude.md          381 lignes
OrionAI_Analyse_Comparative_Kimi_x_Claude_v1_0.md    341 lignes
OrionAI_Vision_Claude_v1_0.md                        114 lignes
```

État actuel : **retirés du suivi** (`git rm --cached` + `.gitignore`), **intacts sur ton disque**.
Ils restent en revanche dans le commit `38a893c`, déjà poussé — les en effacer demanderait une
réécriture d'historique + push forcé, opération destructive que je ne lance pas sans ton accord
explicite. Rien d'autre dans ce rapport n'en dépend.

---

## 1. Verdict global

> **Prêt pour la suite.**
> Aucune régression. Deux écarts trouvés, aucun n'est une régression, aucun ne bloque Godot.
> Deux points restent non vérifiables sans ton téléphone.

| | Résultat |
|---|---|
| Suite automatisée | ✅ verte, rien n'a bougé depuis hier soir |
| Sécurité (jeton, CORS) | ✅ vérifiée en réel sur le serveur en cours |
| Réseau (Tailscale + VPN, DHCP) | ✅ coexistence confirmée, adresse inchangée |
| Modèle | ✅ `gpt-oss:20b` seul, 100 % GPU, une seule instance |
| Personnalité | ✅ « Luca », tutoie, aucun script figé |
| Decision Engine | ✅ bout en bout, action journalisée |
| Audio — TTS tronqué | ✅ rejoué sous sa cause exacte |
| Audio — mute et micro | ⏸️ **nécessitent ton téléphone** |
| Finance | ✅ les 2 CSV réels réimportés sans erreur |
| Tâches planifiées | ✅ 4 tâches enregistrées et actives |
| Documentation | ✅ cohérente et synchronisée (1 renvoi mort réparé) |
| Daemon de sécurité | ⚠️ **écart — ne tourne pas depuis le 01/08** |
| `ruff format` | ⚠️ **écart connu — 95 fichiers, décision en attente** |

---

## 2. Suite automatisée — `just check` complet

```
ruff    All checks passed!
mypy    Success: no issues found in 116 source files
tests   1446 passed, 9 deselected, 88 warnings in 45.30s
couv.   TOTAL   3568 statements   0 missing   100%
```

Identique à hier soir. Rien n'a régressé. (Détail déjà rapporté : `ROADMAP.md` §5.59 à §5.65.)

---

## 3. Revalidation en conditions réelles, point par point

Tout ce qui suit interroge le **serveur qui tourne vraiment** — celui que ton téléphone joint —
pas un serveur de test monté pour l'occasion.

### 3.1 Sécurité — jeton

```
jeton actif  : empreinte a5bbf3fc7a1a (43 car.)

/system avec jeton ACTIF              -> 200
/system aucun jeton                   -> 401  REJETÉ
/system jeton FAUX (même longueur)    -> 401  REJETÉ
/system jeton actif TRONQUÉ           -> 401  REJETÉ
/system jeton actif + 1 caractère     -> 401  REJETÉ
```

**Sur « l'ancien jeton est-il toujours rejeté ? »** — je ne peux pas le rejouer, et
**c'est le bon signe** : sa valeur n'est stockée nulle part. Ni dans Git (`.env` est ignoré),
ni dans la documentation (on n'écrit pas un secret dans un fichier lisible). Le serveur ne
distingue d'ailleurs pas « ancien » de « faux » — il compare à la valeur courante en temps
constant. J'ai donc testé quatre formes invalides, dont une de longueur identique : toutes
rejetées.

⚠️ **Un faux positif de ma part, signalé pour ce qu'il enseigne** : mon premier test envoyait
l'en-tête `X-API-Token` et rendait `401` sur le jeton *actif*. J'ai failli conclure à une
régression grave. L'en-tête réel est `Authorization: Bearer` (`verify_token`, `api/server.py`).
La leçon vaut au-delà du cas : **un test de sécurité qui échoue accuse d'abord le test.**

### 3.2 Sécurité — CORS

```
https://192.168.1.12:8000    (LAN ethernet)   autorisé
https://192.168.1.14:8000    (LAN wifi)       autorisé
https://100.88.249.117:8000  (Tailscale)      autorisé
https://localhost:8000                        autorisé
https://evil.example.com     (non déclarée)   REFUSÉ
```

Les 3 origines que tu visais sont bonnes, plus localhost, et une origine étrangère est refusée.

### 3.3 Réseau — Tailscale, VPN Bitdefender, DHCP

Les deux tunnels sont **simultanément actifs** :

| Interface | Adresse | État |
|---|---|---|
| Tailscale | `100.88.249.117` | Up |
| Bitdefender (WireGuard) | `100.112.10.167` | Up |
| Ethernet | `192.168.1.12` | DHCP |
| Wi-Fi | `192.168.1.14` | DHCP |

**Split tunneling confirmé — et pas seulement par la présence des interfaces.** La route par
défaut (`0.0.0.0/0`) part par **Ethernet → 192.168.1.1**, ton routeur. Si le VPN Bitdefender
capturait tout le trafic, une route par défaut passerait par `bdvpnservice_1` avec une métrique
plus basse. Il n'y en a pas. Le VPN est allumé mais ne route que ce qui le concerne.

**Preuve fonctionnelle, VPN allumé** — les trois adresses répondent :

```
192.168.1.12    -> 200
192.168.1.14    -> 200
100.88.249.117  -> 200
```

**Réservation DHCP tenue** : l'Ethernet est toujours sur `192.168.1.12`, l'adresse déclarée
dans le CORS. Elle n'a pas bougé.

**Ton téléphone est visible sur Tailscale** : `s25-ultra-de-cyril`, état `idle`, avec du trafic
déjà échangé. Il est joignable, il ne parle simplement pas en ce moment.

### 3.4 Modèle

```
NAME           SIZE     PROCESSOR    CONTEXT
gpt-oss:20b    12 GB    100% GPU     4096

instances ollama.exe : 1
VRAM : 14766 / 16303 MiB   (1 537 MiB libres)
```

Un seul `ollama.exe`, écoutant sur `127.0.0.1:11434` uniquement. **Aucun doublon n'est
réapparu.** Le modèle est entièrement sur GPU, pas de débordement RAM. Les 1 537 Mo libres
laissent la place aux 246 Mo mesurés pour Godot (§5.56) — le chantier qui s'ouvre tient
dans la marge.

### 3.5 Personnalité — échanges réels

```
Cyril : salut
Luca  : Qu'est-ce que tu veux gérer aujourd'hui ?              [3,8 s]

Cyril : tu t'appelles comment ?
Luca  : C'est Luca.                                            [2,7 s]

Cyril : qui es-tu, en une phrase ?
Luca  : Je suis Luca, ton assistant personnel tournant en
        local sur ton PC.                                      [2,3 s]
```

**Test du script figé** — même question deux fois :

```
salut #1 -> Qu'est-ce que tu veux gérer ?
salut #2 -> Tu veux qu'on s'occupe de quoi ?
identiques : False
```

**Tutoiement** sur une réponse longue : **0 marqueur de vouvoiement, 3 de tutoiement.**

Et la réponse à « explique-moi ce que tu sais faire » décrit ses capacités **réelles** —
CSV, documents indexés, OCR à la demande, voix, applications autorisées. Pas de promesse
qu'elle ne tient pas.

⚠️ Ces échanges sont entrés dans ton historique de conversation réel. C'est le prix d'une
validation en conditions réelles, pas un défaut.

### 3.6 Decision Engine

```
action_log AVANT : 7 entrées
Cyril : ouvre le bloc-notes
Luca  : Bloc-notes ouvert sur ton PC.
action_log APRÈS : 8 entrées  (+1)

dernière entrée : {'id': 9, 'action': 'launch_notepad',
                   'source': 'chat', 'result': 'executed',
                   'created_at': '2026-08-06 17:35:38'}
```

La chaîne complète tient : chat → résolution d'`ActionSpec` → décision → journalisation →
exécution.

*Fenêtre refermée par mes soins.* Tu avais un Bloc-notes ouvert depuis 01:15 (`Nouveau Document
texte.txt`) — **celui-là n'a pas été touché**. Seule l'instance lancée par le test (19:35:38) a
été fermée.

### 3.7 Audio — les 3 correctifs du 05/08

| Bug | Où vit le correctif | Vérifié ? |
|---|---|---|
| TTS tronqué | `modules/voice_manager.py` | ✅ **rejoué sous sa cause exacte** |
| Mute peu fiable | `static/js/voice_output.js` | ⏸️ présent dans le code, **comportement non testable sans le téléphone** |
| Micro (flux réutilisé) | `static/js/audio.js` + `sw.js` | ⏸️ idem |

**Le TTS tronqué a été rejoué sous sa cause réelle, pas constaté au repos.** Le bug venait
d'une instance `VoiceManager` **partagée** écrivant sur un chemin **fixe** : deux synthèses qui
se chevauchent s'écrasaient. J'ai reproduit exactement ce chevauchement — une instance, deux
appels concurrents, textes de longueurs très différentes :

```
long   texte 164 car. -> tts_45a755…mp3   47 088 octets
court  texte   4 car. -> tts_1e0346…mp3    8 208 octets

chemins DISTINCTS : True
ratio long/court  : 5,7x       VERDICT : aucune troncature
```

**Pour mute et micro, il me faut toi.** Ce sont des correctifs JavaScript qui s'exécutent dans
le navigateur du S25 Ultra. Je peux confirmer qu'ils sont dans le code (revérifié ligne par
ligne) et que le cache de la PWA est en **v10** — donc que le téléphone les recevra. Je ne peux
pas confirmer qu'ils *fonctionnent*. Je préfère le dire plutôt que de cocher une case sur la
foi d'un `grep`.

**Ce qu'il faudrait de ta part** : ouvrir la PWA sur le téléphone, couper le son juste après
avoir envoyé un message (avant que la voix ne démarre), et enchaîner deux enregistrements micro
d'affilée.

### 3.8 Finance

```
dossier data/finance : 2 fichier(s) CSV
[OK] 00050051060.cs ->  68 transactions
[OK] GDB_04082026.c -> 359 transactions
```

Les deux formats réels s'importent toujours sans erreur.

**Le PDF n'a pas à être vérifié : il a été évalué et écarté** le 05/08 (`ROADMAP.md` §5.23) —
la mise en colonnes visuelle n'est pas préservée par l'extraction de texte, et le CSV comptable
de la même banque porte la même donnée sous une forme fiable.

*Note de méthode* : aucun contenu de ces fichiers n'est affiché ici — ni ligne, ni nom de
colonne, ni montant, ni solde. Uniquement des faits structurels, et en cas d'échec la
**catégorie** de l'erreur, jamais son message (règle `CLAUDE.md` du 04/08). La catégorisation
LLM était désactivée pour ce contrôle : c'est l'import qui est mesuré, pas la qualité du
classement.

### 3.9 Tâches planifiées

| Tâche | État | Déclencheur | Dernier résultat |
|---|---|---|---|
| `LucasAPIServer` | Ready | à l'ouverture de session | 0 (succès) |
| `LucasOllamaServer` | Ready | à l'ouverture de session | 0 (succès) |
| `LucasCoworkRequests` | Ready | quotidien 22:00 | 0 (succès) |
| `LucasVeilleModeles` | Ready | **hebdo, lundi 09:00** | jamais exécutée |

Les quatre existent toujours dans le Planificateur, activées.

**Sur la veille** : `LastTaskResult = 267011` est le code Windows « la tâche n'a pas encore été
exécutée » (`0x41303`), pas une erreur. Sa première exécution automatique est le
**lundi 10/08/2026 à 09:00**, récurrence hebdomadaire (`WeeksInterval = 1`, `DaysOfWeek = 2`).
Ses deux fichiers sont en place (`veille_modeles_runner.ps1`, 252 lignes ;
`start_veille_modeles_hidden.vbs`), et les trois garde-fous mécaniques (restauration de
`config.py`, suppression de tout modèle apparu, arrêt de Godot s'il apparaît) sont toujours
dans le script, ainsi que l'interdiction de relancer Godot.

Le serveur API tourne bien : uvicorn en HTTPS sur `0.0.0.0:8000`
(`--ssl-certfile data/cert.pem`).

### 3.10 Documentation

**Synchronisation `cowork_workspace/` ↔ racine** : les 4 fichiers sont **identiques**
(ROADMAP, CLAUDE, IDEAS, VISION_LONG_TERME).

**Cohérence des renvois** : j'ai vérifié automatiquement que chaque `§X` cité dans les 4
documents et dans les rapports pointe sur une section qui existe. **Un seul renvoi mort** :
le rapport de session promettait `§5.65`, que je n'avais jamais écrite.

*(Le contrôle a aussi signalé `§4.1` dans trois fichiers — fausse alerte : mon script validait
tous les `§` contre les seules sections de `ROADMAP.md`, alors que ces trois-là renvoient
explicitement à `VISION_LONG_TERME.md` §4.1, qui existe bien. Vérifié à la main.)*

**Réparé** — `ROADMAP.md` §5.65 (campagne de mutation finale) et §5.66 (cette revalidation)
sont maintenant écrites. C'est la **seule modification** de cette passe.

⚠️ **Et l'ironie mérite d'être dite** : en écrivant §5.66, j'ai posé trois renvois
croisés — **deux étaient faux** (`§5.60` au lieu de `§5.59`, et un `§5.x` jamais résolu).
Je les ai rattrapés en les vérifiant un par un. Une référence écrite de mémoire rate
silencieusement, et le contrôle qui les a attrapées était un **script jetable** : aucun garde
permanent n'existe contre une référence morte. En faire un est une piste, pas un acquis —
cette passe était de vérification seule.

---

## 4. Les deux écarts

### Écart 1 — Le daemon de sécurité ne tourne pas

```
get_status() -> active=False
                last_scan_at='2026-08-01T13:59:36'
                findings_24h=0
```

**Dernier balayage : il y a 5 jours.** Aucun process `lucas_daemon.py`, **aucune tâche
planifiée** pour le lancer.

**Ce n'est pas une régression** : le daemon était prévu en service Windows via NSSM (`ROADMAP.md`
§4), et cette installation n'a jamais eu lieu. Il n'a tourné que lancé à la main, le 01/08.

**Ce que ça veut dire concrètement** : la sécurité niveau 1 est **construite et testée**
(5 capteurs, 94 tests) mais **n'observe rien**. Aucun balayage process/réseau/fichiers ne tourne
en ce moment.

**Ce qui va bien quand même** : le panneau le dit **honnêtement** — `active=False`. Le correctif
de la fenêtre 24 h (§5.59) fait exactement son travail : la vérification croisée en SQL direct
donne 1 signal au total, daté du 01/08, donc 0 sur 24 h. Le panneau et la base sont d'accord.
Avant le correctif, il aurait affiché « 0 signal » **même s'il y en avait eu un**.

**À trancher par toi** : installer le service (NSSM ou une tâche planifiée comme pour l'API),
ou assumer que le niveau 1 reste dormant jusqu'à une étape ultérieure. Je n'ai rien installé —
c'est un service qui tourne en permanence sur ta machine, pas une décision d'implémentation
mineure.

### Écart 2 — `ruff format` n'a jamais été appliqué

```
ruff format --check .  ->  95 files would be reformatted, 55 already formatted
```

**État délibéré, pas une dette cachée.** `format` a été **séparé** de `lint` dans le justfile
(§5.59) précisément pour qu'un reformatage massif ne se déclenche jamais en effet de bord d'un
`just lint`. `just check` = `lint` + `test` + `mypy`, sans `format-check`.

**Ce que ça coûterait de le faire** : un diff sur 95 fichiers, qui rendrait illisible tout
`git blame` et toute comparaison avec l'état d'avant. **Ce que ça rapporterait** : un style
uniforme, et la possibilité d'ajouter `format-check` à `just check`.

**À trancher par toi.** Mon avis : à faire en un commit isolé, étiqueté comme tel, à un moment
où aucun chantier n'est en cours — donc **pas maintenant**, juste avant d'ouvrir Godot.

---

## 5. Ce qui attend une action de toi

| # | Quoi | Pourquoi toi |
|---|---|---|
| 1 | **Les 3 fichiers** — suivis ou non, historique réécrit ou non | Push forcé = destructif |
| 2 | **Mute et micro sur le téléphone** — 2 gestes, 1 minute | Seul le S25 Ultra peut le dire |
| 3 | **Daemon de sécurité** — l'installer en service ou l'assumer dormant | Service permanent sur ta machine |
| 4 | **`ruff format`** — l'appliquer ou pas | 95 fichiers, `git blame` impacté |

---

## 6. État des clients à la fin de cette passe

Comme convenu (règle `CLAUDE.md` du 02/08) :

- **Serveur API** : toujours en marche, **jamais redémarré** pendant cette passe — aucune de tes
  connexions n'a été coupée.
- **Ollama** : en marche, une seule instance, `gpt-oss:20b` chargé (se déchargera seul après
  ~30 min d'inactivité).
- **Ton téléphone** : connecté à Tailscale, `idle`. Je n'ai rien fait qui le déconnecte.
- **Ton Bloc-notes de 01:15** : toujours ouvert, intact.
- **Godot** : **pas lancé** — ni pour mesurer, ni pour vérifier.
- **Ajouté à ton historique de conversation** : **8 messages de contrôle** — vérifié en base,
  pas estimé. Quatre « salut » (le premier essai a bien reçu sa réponse avant de planter à
  l'affichage, côté script uniquement), « tu t'appelles comment ? », « qui es-tu, en une
  phrase ? », « explique-moi en trois phrases ce que tu sais faire », « ouvre le bloc-notes ».

---

*Généré le 06/08/2026. Traçabilité : `ROADMAP.md` §5.65 et §5.66.*
