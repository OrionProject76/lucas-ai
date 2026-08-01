# security/ — capacité de protection de Luca's
#
# Ce paquet conditionne l'élargissement des libertés d'action de Luca's :
# voir VISION_LONG_TERME.md §4.1 et CLAUDE.md, section « Liberté conditionnée
# à la protection ». Plus ces modules sont matures et testés, plus le
# périmètre d'autonomie peut légitimement s'élargir.
#
# ─────────────────────────────────────────────────────────────────────
# NIVEAU DE MATURITÉ ACTUEL : 0 — OBSERVATION SEULE
# ─────────────────────────────────────────────────────────────────────
# Ces modules DÉTECTENT et RAPPORTENT. Ils n'agissent jamais : aucun
# process tué, aucune connexion coupée, aucun fichier mis en quarantaine.
# Donner à Luca's un pouvoir d'action défensif est une décision distincte,
# qui devra être validée explicitement par Cyril (CLAUDE.md, cas 1).
#
# Ils n'appellent aucun service externe : pas de VirusTotal, pas de base
# de signatures en ligne. Envoyer la liste des process ou des connexions
# de Cyril à un tiers serait exactement la fuite qu'on cherche à empêcher.
# Tout repose sur des heuristiques locales.
#
# Ce ne sont donc PAS un antivirus. Ce sont des capteurs qui apprennent à
# reconnaître ce qui sort de l'ordinaire, comme un humain développe sa
# vigilance avant qu'on lui confie les clés.

from security.guardian import Guardian
from security.monitor import SecurityMonitor
from security.privacy_shield import PrivacyShield
from security.ransomware_watch import RansomwareWatch
from security.types import CRITICAL, INFO, WARNING, Finding, format_report

__all__ = [
    "CRITICAL",
    "INFO",
    "WARNING",
    "Finding",
    "Guardian",
    "PrivacyShield",
    "RansomwareWatch",
    "SecurityMonitor",
    "format_report",
]
