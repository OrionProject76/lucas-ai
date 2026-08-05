# core/text_utils.py — normalisation du texte avant comparaison
#
# ── Pourquoi ce module existe ─────────────────────────────────────────
#
# Tous les routages de Luca's reposent sur des listes de mots-clés :
# sensibilité, RAG, vision, cloud, recherche web. La comparaison se
# faisait sur le texte brut, ce qui rendait ces gardes contournables
# sans le vouloir :
#
#   « analyse mes dépenses du mois »  → sensible → LOCAL   ✅
#   « analyse mes depenses du mois »  → non détecté → CLOUD ❌
#
# Taper vite, sans accents, suffisait donc à envoyer une question
# financière au cloud. Ce n'est pas un défaut cosmétique : c'est la
# règle 3 de CLAUDE.md rendue inopérante par une faute de frappe.
#
# Même cause pour la vision : l'apostrophe typographique « ’ » que
# produisent Windows et la plupart des correcteurs ne correspond pas à
# l'apostrophe droite « ' » des mots-clés, donc « qu’est-ce que tu vois
# à l’écran » ne déclenchait rien.
#
# Toute comparaison de mots-clés doit passer par normalize().

import unicodedata

# Variantes d'apostrophe rencontrées selon le clavier, l'OS et les
# correcteurs automatiques. Toutes ramenées à l'apostrophe droite.
APOSTROPHES = "’‘ʼ´`"

# Caractères qui RESSEMBLENT à un tiret sans appartenir à la catégorie
# Unicode des tirets (Pd), et que le repli par catégorie rate donc.
#
# U+2212 est le signe moins mathématique : catégorie Sm (symbole math),
# visuellement identique à un tiret. Élargir le repli à toute la
# catégorie Sm serait pire que le mal — « + », « = » et « < » y sont
# aussi, et deviendraient des tirets.
#
# ⚠️ Cette liste est l'aveu que le repli par catégorie ne suffit pas
# TOUJOURS. Elle doit rester courte : chaque ajout signale un caractère
# rencontré en vrai, jamais une précaution imaginée.
TIRETS_HORS_CATEGORIE = "−"


def normalize(text: str) -> str:
    """
    Minuscules, sans accents, apostrophes et ponctuation uniformisées.

    « Qu'est-ce que tu vois à l'ÉCRAN ? » et « quest ce que tu vois a
    lecran » se ramènent au même terrain de comparaison.

    ── ⚠️ Espaces et tirets typographiques (ajouté le 05/08/2026) ──────

    C'est une CORRECTION DE SÉCURITÉ, pas un raffinement cosmétique.

    En passant à gpt-oss:20b, un fait nouveau est apparu : ce modèle écrit
    avec de la vraie typographie française — espace fine insécable avant
    les « ! » et « ? » (U+202F), trait d'union insécable dans « Bloc‑notes »
    (U+2011). Ces caractères ne sont ni l'espace ASCII ni le tiret ASCII.

    Conséquence mesurée AVANT correctif :

        is_sensitive("mon compte bancaire")            -> True
        is_sensitive("mon compte\\u202fbancaire")       -> False   ⚠️
        route_voice("Ton compte\\u202fbancaire : 3200") -> "cloud" ⚠️

    Autrement dit : une réponse contenant une donnée bancaire, écrite avec
    une espace fine, **partait chez Microsoft** (edge_tts) au lieu de
    rester sur la machine avec Piper. `route_voice()` analyse la RÉPONSE
    du modèle — c'est donc le modèle lui-même qui pouvait, par sa seule
    typographie, faire sortir un contenu sensible.

    Le repli se fait par CATÉGORIE Unicode plutôt que par liste :
    - `Zs` (séparateurs d'espace) → espace ASCII
    - `Pd` (tirets, tous) → tiret ASCII

    Une liste nommant U+202F et U+2011 aurait corrigé ces deux cas et
    laissé passer le suivant. La catégorie couvre aussi ceux qu'on n'a pas
    encore rencontrés — ce qui est exactement le problème : on ne sait pas
    à l'avance quelle typographie le prochain modèle emploiera.
    """
    lowered = text.lower()

    for apostrophe in APOSTROPHES:
        lowered = lowered.replace(apostrophe, "'")

    # NFD sépare les lettres de leurs accents ; on retire les accents
    # (catégorie Mn = marque non espaçante) et on garde les lettres.
    decomposed = unicodedata.normalize("NFD", lowered)

    resultat = []
    for caractere in decomposed:
        categorie = unicodedata.category(caractere)
        if categorie == "Mn":
            continue          # accent détaché par la décomposition NFD
        if categorie == "Zs":
            resultat.append(" ")
        elif categorie == "Pd" or caractere in TIRETS_HORS_CATEGORIE:
            resultat.append("-")
        else:
            resultat.append(caractere)
    return "".join(resultat)


def fold_separators(text: str) -> str:
    """
    Replie les espaces et tirets typographiques, SANS toucher au reste.

    ⚠️ À ne pas confondre avec `normalize()`, et la distinction compte
    (posée le 05/08/2026) :

    - `normalize()` sert à COMPARER. Il met en minuscules et retire les
      accents, ce qui détruit de l'information — acceptable quand on
      cherche seulement à savoir si deux textes se ressemblent.
    - `fold_separators()` sert à EXTRAIRE. La valeur trouvée est réutilisée
      telle quelle : un nom de ville part vers le service météo et
      s'affiche à Cyril, une expression arithmétique est évaluée. Les
      passer par `normalize()` rendrait « Saint-Étienne » en
      « saint-etienne » — techniquement exploitable, mais on abîmerait la
      donnée pour corriger un problème de séparateur.

    Ce que cette fonction corrige, mesuré le 05/08/2026 :

        extract_city("météo à Saint‑Étienne")   -> "Saint"  (tiret U+2011)
        extract_calculation("1 234 + 5 678")    -> expression inévaluable
        extract_periods("12 / 07 / 2025")       -> mois perdu

    Les trois viennent de la même cause : un séparateur typographique là
    où le code attend un caractère ASCII. Le cas des dates n'est pas
    théorique — les bulletins de paie en PDF emploient couramment des
    espaces insécables, et c'est précisément sur eux que la recherche
    documentaire datée a été construite.
    """
    resultat = []
    for caractere in text:
        categorie = unicodedata.category(caractere)
        if categorie == "Zs":
            resultat.append(" ")
        elif categorie == "Pd" or caractere in TIRETS_HORS_CATEGORIE:
            resultat.append("-")
        else:
            resultat.append(caractere)
    return "".join(resultat)


def contains_any(text: str, keywords) -> bool:
    """
    Vrai si l'un des mots-clés apparaît dans le texte, comparaison
    normalisée des deux côtés.

    Normaliser les mots-clés aussi est indispensable : ils contiennent
    eux-mêmes des accents (« stratégie », « relevé », « à l'écran »), et
    comparer du texte normalisé à des mots-clés accentués ne matcherait
    plus rien du tout.
    """
    normalized_text = normalize(text)
    return any(normalize(keyword) in normalized_text for keyword in keywords)
