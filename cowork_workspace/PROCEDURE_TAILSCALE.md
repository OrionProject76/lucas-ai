# Procédure Tailscale — accéder à Luca depuis l'extérieur

**Préparé le 05/08/2026. Rien n'est installé, rien n'est configuré** —
ouvrir un accès distant à Luca est une décision de sécurité qui revient à
Cyril (`CLAUDE.md`, Autonomie d'exécution, cas 1 : accès réseau externe).

Contexte : Cyril a tranché pour Tailscale le 03/08/2026, plutôt que
WireGuard brut — simplicité pour un débutant, gestion automatique de l'IP
dynamique, chiffrement de bout en bout conservé. La décision est prise
depuis deux jours ; seule l'exécution attendait.

---

## 1. Ce qui est déjà prêt — rien à recoder

Audité le 03/08/2026, revérifié aujourd'hui :

| | |
|---|---|
| `API_HOST` | `0.0.0.0` — écoute déjà sur toutes les interfaces, Tailscale comprise |
| PWA | construit son URL depuis `location.host` — aucune adresse en dur |
| Jeton d'API | construit et fonctionnel, transporté par sous-protocole WebSocket |
| CORS | `allow_origins=["*"]` — à resserrer, voir §4 |
| Certificat HTTPS | à régénérer, commande prête : `just cert-tailscale <IP>` |

Autrement dit : **le code n'a pas besoin d'une seule modification.** Ce
qui reste est de l'installation et un certificat.

---

## 2. Les deux étapes que Cyril seul peut faire

Installer un logiciel et se connecter à un compte sortent de ce qu'un
agent autonome peut faire à sa place.

### Sur le PC

1. Télécharger Tailscale pour Windows : <https://tailscale.com/download>
2. Installer, puis lancer.
3. Se connecter — un compte Google/Microsoft/GitHub suffit, pas besoin
   d'en créer un dédié.
4. Relever l'adresse attribuée : elle commence par **`100.`**
   (`tailscale ip -4` en ligne de commande, ou dans l'interface).

### Sur le S25 Ultra

1. Installer Tailscale depuis le Play Store.
2. Se connecter **avec le même compte** — c'est ce qui met les deux
   appareils sur le même réseau privé.
3. Vérifier que le PC apparaît dans la liste des machines.

⚠️ **Garder le Wi-Fi/données mobiles actif** : Tailscale ne remplace pas
la connexion Internet, il crée un tunnel par-dessus.

---

## 3. Ce que je fais dès que tu me donnes l'adresse `100.x.y.z`

Une seule commande, déjà écrite et testée :

```
just cert-tailscale 100.x.y.z
```

Elle régénère le certificat en **conservant les adresses existantes**
(`192.168.1.12`, `192.168.1.14`, `127.0.0.1`, `localhost`).

⚠️ Ce détail n'est pas cosmétique : sans les anciennes adresses, Luca
deviendrait injoignable **à la maison** en gagnant l'accès à distance.
Une régression qu'on ne découvrirait que le soir venu.

Puis relancer le serveur pour qu'il charge le nouveau certificat.

L'adresse à utiliser sur le téléphone devient alors :

```
https://100.x.y.z:8000/app/?token=<ton jeton>
```

Le téléphone redemandera d'accepter le certificat — une fois, parce
qu'il a changé.

---

## 4. ⚠️ La revue de sécurité — à lire avant de dire oui

C'est la partie qui mérite ton attention, pas les clics.

### Ce que le tunnel expose réellement

Aujourd'hui, Luca n'est joignable que depuis ton salon. Avec Tailscale,
elle devient joignable **depuis n'importe quel appareil connecté à ton
compte Tailscale**, où qu'il soit. Ce qui devient atteignable :

- `GET /history` — **tout ton historique de conversation**
- `GET /documents` — la liste de tes documents indexés
- `GET /finance/summary` — le résumé de tes relevés bancaires
- `POST /chat` — poser des questions en ton nom, avec accès au RAG
- Le lancement d'applications sur ton PC (liste blanche)

**Le jeton d'API est la seule barrière.** Il est en place et fonctionne —
mais c'est le moment de le régénérer, parce qu'il a séjourné en clair
dans `data/logs/server_startup.log` avant le correctif de cette nuit
(ROADMAP.md §5.30). Ce point était déjà ouvert ; il devient beaucoup plus
important avec un accès distant.

### Ce que Tailscale voit, et ne voit pas

Le chiffrement est de bout en bout : le contenu de tes échanges avec Luca
ne passe **jamais** en clair par leurs serveurs. Ce qui transite chez eux,
ce sont les **métadonnées de coordination** — quels appareils existent,
quand ils se connectent, leurs adresses. C'est le compromis que tu as
accepté le 03/08 en le préférant à WireGuard brut, et il reste juste.

### Trois choses à faire pendant qu'on y est

1. **Régénérer `API_TOKEN` dans `.env`** — voir ci-dessus. Ça t'obligera
   à réappairer le téléphone, autant le faire en même temps que le reste.
2. **Resserrer `allow_origins`** dans `api/server.py` : actuellement
   `["*"]`, annoté dans le code comme provisoire. Une fois l'origine
   Tailscale connue, je peux la restreindre — je le ferai avec toi, pas
   tout seul.
3. **Décider pour les ACL Tailscale** : par défaut, tous tes appareils se
   voient. Si tu ajoutes un jour un appareil moins fiable (une machine de
   travail, celle d'un proche), il aura accès à Luca. Tailscale permet de
   restreindre ça ; ce n'est pas urgent à deux appareils, mais c'est à
   savoir avant d'en ajouter un troisième.

### Ce que ça ne change pas

La règle 3 de `CLAUDE.md` reste entière : **le tunnel change QUI peut
joindre Luca, jamais ce qu'elle envoie dehors.** Le routage local/cloud,
le refus d'envoyer une donnée sensible, le TTS local sur contenu
sensible — tout cela est décidé côté serveur et ne dépend pas du chemin
d'accès. C'est d'ailleurs exactement ce que dit `VISION_LONG_TERME.md`
§4 : « la sécurité vient du contrôle de *ce qui* est envoyé et *quand*,
pas du canal utilisé. »

---

## 5. Ordre suggéré

1. **Réservation DHCP sur la Livebox** (en cours) — indépendant, utile
   dans tous les cas.
2. Installer Tailscale sur le PC, relever l'adresse `100.x.y.z`.
3. Me la donner → je régénère le certificat.
4. Installer Tailscale sur le téléphone, même compte.
5. Régénérer le jeton, réappairer le téléphone avec la nouvelle adresse.
6. Resserrer `allow_origins` ensemble.

Les étapes 1 et 2 peuvent se faire en parallèle ; les suivantes
s'enchaînent en quelques minutes.
