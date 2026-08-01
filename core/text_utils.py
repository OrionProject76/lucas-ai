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


def normalize(text: str) -> str:
    """
    Minuscules, sans accents, apostrophes uniformisées.

    « Qu'est-ce que tu vois à l'ÉCRAN ? » et « quest ce que tu vois a
    lecran » se ramènent au même terrain de comparaison, aux tirets près.
    """
    lowered = text.lower()

    for apostrophe in APOSTROPHES:
        lowered = lowered.replace(apostrophe, "'")

    # NFD sépare les lettres de leurs accents ; on retire les accents
    # (catégorie Mn = marque non espaçante) et on garde les lettres.
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


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
