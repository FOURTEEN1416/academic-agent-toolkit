<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · von null zu einer vollständigen Arbeit mit Text und Abbildungen"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[Produktseite](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5: von null zu einer vollständigen Arbeit mit Text und Abbildungen.**

PaperSpine5 ist ein AI Skill, der den gesamten Ablauf einer wissenschaftlichen Arbeit abdeckt. Sie geben eine Forschungsrichtung, vorhandenes Material oder experimentelle Daten vor; er sucht die Literatur, ordnet die Argumente, baut die Gliederung, schreibt den Volltext, erstellt die wissenschaftlichen Abbildungen, prüft die Zitate, führt durch Review und Überarbeitung und übernimmt das Layout. Am Ende stehen bearbeitbare Word- / LaTeX-Quellen und ein PDF.

Vom Fließtext über Datenabbildungen und Mechanismus-Skizzen bis zu Methodenübersichten entsteht alles in einer einzigen Aufgabe. Gestartet wird mit `paper-spine`; in der Weboberfläche wählen Sie den Ansatz, sehen Text und Abbildungen als Vorschau, hinterlassen Änderungswünsche und laden die Ergebnisse herunter. Forschungsmaterial bleibt standardmäßig lokal, und jede Aussage, jedes Zitat und jede Abbildung stützt sich auf echte Quellen und Belege.

## Downloads

- Suite für Windows x64: etwa 26,4 MB.
- Suite für Linux glibc x86_64: etwa 56,2 MB.
- Suite für macOS Apple Silicon: etwa 40,5 MB.
- Suite für macOS Intel x86_64: etwa 40,5 MB.

Alle Downloads stehen in der öffentlichen Release-Liste und sind per SHA-256 abgesichert. Aktuelle Version: `v0.4.0-alpha.3` (Vorabversion).

## Installation und Migration von älteren Versionen

Windows x64:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux:

```sh
sh ./install.sh --target codex --clean-legacy
```

`-CleanLegacy` archiviert nur bekannte V3/V4-Skill-Verzeichnisse. Aufgaben­daten, Host-Einstellungen und unbekannte Dateien werden nicht gelöscht. Beide Installer prüfen Byteanzahl, SHA-256, die interne Integrität der Suite und einen Selbsttest beim Start.

## Updates prüfen und einspielen

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex
```

```sh
# macOS / Linux
sh ./install.sh --check-only
sh ./install.sh --target codex
```

Ein erneuter Installer-Aufruf prüft die Version. Bei einer neuen Version erfolgt ein rückgängigfähiges Update mit Startprüfung; Aufgabendaten bleiben erhalten. Eine vollständige aktuelle Installation wird weder erneut heruntergeladen noch überschrieben. Bei jedem Skill-Aufruf wird auf Updates geprüft; bei Bedarf werden Suite und Updater aktualisiert. Eine ausdrücklich deaktivierte automatische Aktualisierung wird respektiert.

## Grenzen

- Die selbstständigen Suites sind auf Windows x64, Linux glibc x86_64, macOS arm64 und macOS x86_64 geprüft. Linux arm64 und musl/Alpine werden nicht zugesichert.
- Die macOS-Pakete sind weder signiert noch notarisiert; beim ersten Start kann eine ausdrückliche Freigabe nötig sein.
- Es handelt sich um eine Alpha-Vorabversion ohne eigenständige kryptografische Signatur.
- Die Veröffentlichung des Produkts erlaubt weder Einreichung von Manuskripten noch das Hochladen privater Materialien, Zahlungen oder externe Kontaktaufnahme.
- Der Support-Kanal ist freiwillig, schaltet keine Funktionen frei und liest keinen Zahlungsstatus.

## Aufbau des öffentlichen Repositories

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine`: Projektionen je Host.
- `dist/claude/commands/paperspine.md`: Claude-Befehlseingang.
- `install.ps1`, `install.sh`: Installationsgrenzen.
- Zentrale Methoden und Werkzeuge: `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## Entwicklung

`src/` enthält den Quellcode des Skills, `dist/` die öffentlichen Projektionen je Host. Das öffentliche Repository enthält Quellcode und Tests, aber keine lokalen Aufgaben, klinischen Daten, Caches oder Entwicklungsprotokolle.

MIT License.
