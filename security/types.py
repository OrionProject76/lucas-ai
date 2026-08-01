# security/types.py — vocabulaire commun à Guardian et Privacy Shield

from dataclasses import dataclass, field

INFO = "info"
WARNING = "warning"
CRITICAL = "critical"

# Ordre d'affichage : le plus grave d'abord.
SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}

# Champs qui bougent d'un balayage à l'autre sans que le signal change.
VOLATILE_EVIDENCE_KEYS = frozenset({
    "pid", "total", "fichiers_modifies", "distant", "exemple",
})

SEVERITY_LABELS = {
    INFO: "ℹ️  INFO",
    WARNING: "⚠️  ATTENTION",
    CRITICAL: "🚨 CRITIQUE",
}


@dataclass
class Finding:
    """
    Un signal relevé par un capteur de sécurité.

    `severity` dit à quel point c'est inhabituel, pas à quel point c'est
    malveillant : un capteur en observation seule ne conclut jamais à une
    infection, il signale ce qui mérite le regard de Cyril.

    `evidence` porte les faits bruts (chemin, PID, IP) pour que la
    décision reste vérifiable et ne repose pas sur la parole du capteur.
    """

    severity: str
    kind: str
    summary: str
    evidence: dict = field(default_factory=dict)

    def fingerprint(self) -> str:
        """
        Identité stable d'un signal, pour ne pas ré-alerter à chaque
        balayage sur la même chose.

        Les champs volatils sont exclus : un PID change à chaque
        redémarrage du programme, un compteur varie à chaque passage.
        Les inclure ferait ré-alerter en boucle sur un signal identique,
        et le rapport deviendrait du bruit qu'on cesse de lire.
        """
        stable = {k: v for k, v in self.evidence.items() if k not in VOLATILE_EVIDENCE_KEYS}
        facts = "|".join(f"{k}={v}" for k, v in sorted(stable.items()))
        return f"{self.kind}|{facts}"

    def as_event(self) -> tuple[str, str]:
        """Convertit en (event_type, details) pour MemoryManager.save_event."""
        facts = ", ".join(f"{k}={v}" for k, v in self.evidence.items())
        return f"security_{self.kind}", f"{self.summary} | {facts}"[:200]


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.kind))


def format_report(findings: list[Finding]) -> str:
    """Rapport lisible, prêt à afficher dans le chat."""
    if not findings:
        return "=== Rapport sécurité ===\nAucun signal inhabituel détecté."

    lines = ["=== Rapport sécurité ===", f"{len(findings)} signal(s) relevé(s)", ""]
    for finding in sort_findings(findings):
        label = SEVERITY_LABELS.get(finding.severity, finding.severity)
        lines.append(f"{label} — {finding.summary}")
        for key, value in finding.evidence.items():
            lines.append(f"      {key} : {value}")
    lines.append("")
    lines.append("Observation seule : aucune action n'a été prise.")
    return "\n".join(lines)
