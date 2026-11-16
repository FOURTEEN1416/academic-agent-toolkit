<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · de zéro à un article complet, texte et figures compris"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[Page produit](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5 : de zéro à un article complet, texte et figures compris.**

PaperSpine5 est un AI Skill qui couvre tout le déroulé d'un article. Vous apportez un sujet de recherche, des documents existants ou des données expérimentales ; il cherche la bibliographie, organise l'argumentation, construit le plan, rédige le texte, produit les figures scientifiques, vérifie les citations, gère la relecture et les corrections, puis la mise en page, et livre des sources Word / LaTeX modifiables ainsi qu'un PDF.

Le corps du texte, les figures de données, les schémas de mécanisme et les figures de méthode sont produits dans une seule et même tâche. On le lance avec `paper-spine`, on choisit l'approche dans l'interface web, on prévisualise le texte et les figures, on laisse des demandes de correction et on télécharge les résultats. Les documents de recherche restent par défaut sur votre machine, et chaque affirmation, citation et figure s'appuie sur des sources et des preuves réelles.

## Téléchargements

- Suite Windows x64 : environ 26,4 Mo.
- Suite Linux glibc x86_64 : environ 56,2 Mo.
- Suite macOS Apple Silicon : environ 40,5 Mo.
- Suite macOS Intel x86_64 : environ 40,5 Mo.

Tous les téléchargements figurent dans la liste publique des versions et sont vérifiés par SHA-256. La version actuelle est la préversion `v0.4.0-alpha.3`.

## Installation et migration depuis les versions précédentes

Windows x64 :

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux :

```sh
sh ./install.sh --target codex --clean-legacy
```

`-CleanLegacy` archive uniquement les dossiers de découverte V3/V4 connus. Il ne supprime ni les données de tâches, ni les réglages de l'hôte, ni les fichiers inconnus. Les deux programmes d'installation vérifient le nombre d'octets, le SHA-256, l'intégrité interne de la suite et une vérification au démarrage.

## Vérifier et appliquer les mises à jour

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

Relancer le programme d’installation vérifie la version. Une nouvelle version entraîne une mise à jour réversible et une vérification au démarrage, en conservant les données. Une installation complète et à jour évite tout téléchargement ou remplacement inutile. Chaque invocation de la Skill vérifie les mises à jour et actualise la suite et son outil de mise à jour si nécessaire ; une désactivation explicite est respectée.

## Limites

- Les suites autonomes sont vérifiées sur Windows x64, Linux glibc x86_64, macOS arm64 et macOS x86_64. Linux arm64 et musl/Alpine ne sont pas déclarés pris en charge.
- Les paquets macOS ne sont ni signés ni notariés ; le premier lancement peut demander une autorisation explicite de l'utilisateur.
- Il s'agit d'une préversion alpha, sans signature cryptographique indépendante.
- La publication du produit n'autorise ni la soumission d'un manuscrit, ni l'envoi de documents privés, ni un paiement, ni une prise de contact externe.
- Le canal de soutien est volontaire, ne débloque aucune fonction et ne lit aucun état de paiement.

## Structure du dépôt public

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine` : projections par hôte.
- `dist/claude/commands/paperspine.md` : entrée de commande Claude.
- `install.ps1`, `install.sh` : limites d'installation.
- Méthodes et outils principaux : `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## Développement

`src/` contient le code source du Skill et `dist/` les projections publiques par hôte. Le dépôt public conserve le code source et les tests, mais ni tâches locales, ni données cliniques, ni caches, ni journaux d'exécution de développement.

MIT License.
