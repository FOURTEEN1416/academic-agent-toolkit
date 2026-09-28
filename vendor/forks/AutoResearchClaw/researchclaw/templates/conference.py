"""Conference template definitions for NeurIPS, ICLR, and ICML.

Each template stores the LaTeX preamble, document structure, author format,
and bibliography style needed to produce a submission-ready ``.tex`` file.

Style files (``.sty``) are NOT bundled — the generated ``.tex`` references
them, and users download the official files from the conference website.
Download URLs are included as comments in the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Root directory for bundled style files
_STYLES_DIR = Path(__file__).parent / "styles"


@dataclass(frozen=True)
class ConferenceTemplate:
    """LaTeX template specification for one conference."""

    name: str
    display_name: str
    year: int
    document_class: str
    style_package: str
    style_options: str
    extra_packages: tuple[str, ...]
    author_format: str  # "neurips" | "iclr" | "icml"
    bib_style: str
    columns: int  # 1 or 2
    style_download_url: str
    preamble_extra: str = ""

    def render_preamble(
        self,
        title: str,
        authors: str,
        abstract: str,
    ) -> str:
        # Style options go on the style package when one is declared, otherwise
        # fall through to documentclass options (revtex pattern:
        # \documentclass[aps,prd,reprint]{revtex4-2}).
        options = f"[{self.style_options}]" if self.style_options else ""
        pkg_lines = "\n".join(f"\\usepackage{{{p}}}" for p in self.extra_packages)

        author_block = self._render_authors(authors)

        # Substitute __TITLE__ placeholder in preamble_extra (e.g. ICML running title)
        preamble_extra = self.preamble_extra.replace("__TITLE__", title)

        if self.style_package:
            docclass_line = f"\\documentclass{{{self.document_class}}}\n"
            style_line = f"\\usepackage{options}{{{self.style_package}}}\n"
        else:
            # No separate style package — options attach to documentclass
            # (e.g. revtex4-2 for PRD/PRL/PRX).
            docclass_line = (
                f"\\documentclass{options}{{{self.document_class}}}\n"
                if options
                else f"\\documentclass{{{self.document_class}}}\n"
            )
            style_line = ""

        style_comment = (
            f"% Style file: {self.style_download_url}\n"
            if self.style_download_url
            else ""
        )

        # BUG-51 fix: ICML's \begin{icmlauthorlist} is an environment that
        # must appear AFTER \begin{document}.  For non-ICML templates the
        # \author{} command is a preamble declaration and stays before.
        # revtex also places \author{} after \begin{document}, typically
        # before \title{} (handled via post_doc_author).
        if self.author_format == "icml":
            preamble_author = ""
            post_doc_author = f"{author_block}\n\n"
        elif self.author_format == "revtex":
            preamble_author = ""
            # revtex order: \title before \author, both after \begin{document}
            post_doc_author = (
                f"\\title{{{title}}}\n\n"
                f"{author_block}\n\n"
                f"\\date{{\\today}}\n\n"
            )
        else:
            preamble_author = f"{author_block}\n"
            post_doc_author = ""

        # revtex puts \title inside the document, others in preamble
        preamble_title = (
            "" if self.author_format == "revtex" else f"\\title{{{title}}}\n"
        )

        return (
            f"{style_comment}"
            f"{docclass_line}"
            f"{style_line}"
            f"{pkg_lines}\n"
            f"{preamble_extra}\n"
            f"\n"
            f"{preamble_title}"
            f"\n"
            f"{preamble_author}"
            f"\n"
            f"\\begin{{document}}\n"
            f"{post_doc_author}"
            f"\\begin{{abstract}}\n"
            f"{abstract}\n"
            f"\\end{{abstract}}\n"
            f"\n"
            f"\\maketitle\n"
        )

    def render_footer(self, bib_file: str = "references") -> str:
        return (
            f"\n\\bibliographystyle{{{self.bib_style}}}\n"
            f"\\bibliography{{{bib_file}}}\n"
            f"\n"
            f"\\end{{document}}\n"
        )

    def get_style_files(self) -> list[Path]:
        """Return paths to bundled ``.sty`` and ``.bst`` files for this template.

        Files are stored under ``researchclaw/templates/styles/<name>/``.
        Returns only files that exist on disk.
        """
        style_dir = _STYLES_DIR / self.name
        if not style_dir.is_dir():
            return []
        return sorted(
            p for p in style_dir.iterdir()
            if p.suffix in {".sty", ".bst", ".cls"}
        )

    def _render_authors(self, authors: str) -> str:
        if self.author_format == "icml":
            return (
                f"\\begin{{icmlauthorlist}}\n"
                f"\\icmlauthor{{{authors}}}{{aff1}}\n"
                f"\\end{{icmlauthorlist}}\n"
                f"\\icmlaffiliation{{aff1}}{{Affiliation}}"
            )
        if self.author_format == "jhep":
            return (
                f"\\author{{{authors}}}\n"
                f"\\affiliation{{Affiliation}}\n"
                f"\\emailAdd{{author@example.com}}"
            )
        if self.author_format == "revtex":
            return (
                f"\\author{{{authors}}}\n"
                f"\\affiliation{{Affiliation}}"
            )
        return f"\\author{{{authors}}}"


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

# -- Legacy (kept for backward compat) --

NEURIPS_2024 = ConferenceTemplate(
    name="neurips_2024",
    display_name="NeurIPS 2024",
    year=2024,
    document_class="article",
    style_package="neurips_2024",
    style_options="preprint",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
    ),
    author_format="neurips",
    bib_style="plainnat",
    columns=1,
    style_download_url="https://media.neurips.cc/Conferences/NeurIPS2024/Styles.zip",
    preamble_extra="\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}",
)

ICLR_2025 = ConferenceTemplate(
    name="iclr_2025",
    display_name="ICLR 2025",
    year=2025,
    document_class="article",
    style_package="iclr2025_conference",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
    ),
    author_format="iclr",
    bib_style="iclr2025_conference",
    columns=1,
    style_download_url="https://github.com/ICLR/Master-Template/raw/master/iclr2025.zip",
)

ICML_2025 = ConferenceTemplate(
    name="icml_2025",
    display_name="ICML 2025",
    year=2025,
    document_class="article",
    style_package="icml2025",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
    ),
    author_format="icml",
    bib_style="icml2025",
    columns=2,
    style_download_url="https://icml.cc/Conferences/2025/StyleAuthorInstructions",
    preamble_extra="\\icmltitlerunning{__TITLE__}",
)

# -- Current (2025/2026) --

NEURIPS_2025 = ConferenceTemplate(
    name="neurips_2025",
    display_name="NeurIPS 2025",
    year=2025,
    document_class="article",
    style_package="neurips_2025",
    style_options="preprint",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
    ),
    author_format="neurips",
    bib_style="plainnat",
    columns=1,
    style_download_url="https://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip",
    preamble_extra="\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}",
)

ICLR_2026 = ConferenceTemplate(
    name="iclr_2026",
    display_name="ICLR 2026",
    year=2026,
    document_class="article",
    style_package="iclr2026_conference",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
    ),
    author_format="iclr",
    bib_style="iclr2026_conference",
    columns=1,
    style_download_url="https://github.com/ICLR/Master-Template",
)

ICML_2026 = ConferenceTemplate(
    name="icml_2026",
    display_name="ICML 2026",
    year=2026,
    document_class="article",
    style_package="icml2026",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "nicefrac",
        "microtype",
        "graphicx",
        "natbib",
        "algorithm",
        "algorithmic",
        "adjustbox",
        "morefloats",
    ),
    author_format="icml",
    bib_style="icml2026",
    columns=2,
    style_download_url="https://icml.cc/Conferences/2026/AuthorInstructions",
    preamble_extra="\\icmltitlerunning{__TITLE__}",
)

# -- Generic (non-ML) --

# -- HEP phenomenology templates --
#
# These rely on publisher-provided classes that ship with a standard TeX Live
# install (revtex4-2, jheppub, svjour3). No .sty files are bundled.

JHEP = ConferenceTemplate(
    name="jhep",
    display_name="Journal of High Energy Physics (JHEP)",
    year=2025,
    document_class="article",
    style_package="jheppub",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "amssymb",
        "graphicx",
        "xspace",
        "slashed",
    ),
    author_format="jhep",
    bib_style="JHEP",
    columns=1,
    style_download_url="https://jhep.sissa.it/jhep/help/JHEP_TeXclass.jsp",
    preamble_extra=(
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\providecommand{\\GeV}{\\ensuremath{\\mathrm{GeV}}\\xspace}\n"
        "\\providecommand{\\TeV}{\\ensuremath{\\mathrm{TeV}}\\xspace}\n"
        "\\providecommand{\\fb}{\\ensuremath{\\mathrm{fb}}\\xspace}\n"
        "\\providecommand{\\pb}{\\ensuremath{\\mathrm{pb}}\\xspace}"
    ),
)

PRD = ConferenceTemplate(
    name="prd",
    display_name="Physical Review D (PRD)",
    year=2025,
    document_class="revtex4-2",
    style_package="",
    style_options="aps,prd,reprint,amsmath,amssymb,nofootinbib,floatfix",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "graphicx",
        "xspace",
        "slashed",
    ),
    author_format="revtex",
    bib_style="apsrev4-2",
    columns=2,
    style_download_url="https://journals.aps.org/revtex",
    preamble_extra=(
        "\\providecommand{\\GeV}{\\ensuremath{\\mathrm{GeV}}\\xspace}\n"
        "\\providecommand{\\TeV}{\\ensuremath{\\mathrm{TeV}}\\xspace}\n"
        "\\providecommand{\\fb}{\\ensuremath{\\mathrm{fb}}\\xspace}\n"
        "\\providecommand{\\pb}{\\ensuremath{\\mathrm{pb}}\\xspace}"
    ),
)

PRL = ConferenceTemplate(
    name="prl",
    display_name="Physical Review Letters (PRL)",
    year=2025,
    document_class="revtex4-2",
    style_package="",
    style_options="aps,prl,reprint,amsmath,amssymb,nofootinbib,floatfix",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "graphicx",
        "xspace",
        "slashed",
    ),
    author_format="revtex",
    bib_style="apsrev4-2",
    columns=2,
    style_download_url="https://journals.aps.org/revtex",
    preamble_extra=(
        "\\providecommand{\\GeV}{\\ensuremath{\\mathrm{GeV}}\\xspace}\n"
        "\\providecommand{\\TeV}{\\ensuremath{\\mathrm{TeV}}\\xspace}"
    ),
)

PRX = ConferenceTemplate(
    name="prx",
    display_name="Physical Review X (PRX)",
    year=2025,
    document_class="revtex4-2",
    style_package="",
    style_options="aps,prx,reprint,amsmath,amssymb,nofootinbib,floatfix",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "graphicx",
        "xspace",
        "slashed",
    ),
    author_format="revtex",
    bib_style="apsrev4-2",
    columns=2,
    style_download_url="https://journals.aps.org/revtex",
    preamble_extra=(
        "\\providecommand{\\GeV}{\\ensuremath{\\mathrm{GeV}}\\xspace}\n"
        "\\providecommand{\\TeV}{\\ensuremath{\\mathrm{TeV}}\\xspace}"
    ),
)

EPJC = ConferenceTemplate(
    name="epjc",
    display_name="European Physical Journal C (EPJC)",
    year=2025,
    document_class="article",
    style_package="",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "amssymb",
        "graphicx",
        "geometry",
        "xspace",
        "slashed",
    ),
    author_format="neurips",
    bib_style="spphys",
    columns=1,
    style_download_url="https://www.springer.com/journal/10052/submission-guidelines",
    preamble_extra=(
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\providecommand{\\GeV}{\\ensuremath{\\mathrm{GeV}}\\xspace}"
    ),
)


GENERIC = ConferenceTemplate(
    name="generic",
    display_name="Generic Academic Paper",
    year=2025,
    document_class="article",
    style_package="",
    style_options="",
    extra_packages=(
        "hyperref",
        "url",
        "booktabs",
        "amsfonts",
        "amsmath",
        "graphicx",
        "natbib",
        "geometry",
        "adjustbox",
    ),
    author_format="neurips",
    bib_style="plainnat",
    columns=1,
    style_download_url="",
    preamble_extra="\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}\n\\usepackage[margin=1in]{geometry}",
)


# ---------------------------------------------------------------------------
# Registry — short aliases point to LATEST version of each conference
# ---------------------------------------------------------------------------

CONFERENCE_REGISTRY: dict[str, ConferenceTemplate] = {
    # Latest (default aliases)
    "neurips": NEURIPS_2025,
    "iclr": ICLR_2026,
    "icml": ICML_2026,
    # Generic for non-ML domains
    "generic": GENERIC,
    "article": GENERIC,
    # Versioned keys (all versions)
    "neurips_2025": NEURIPS_2025,
    "neurips_2024": NEURIPS_2024,
    "iclr_2026": ICLR_2026,
    "iclr_2025": ICLR_2025,
    "icml_2026": ICML_2026,
    "icml_2025": ICML_2025,
    # HEP phenomenology templates
    "jhep": JHEP,
    "prd": PRD,
    "prl": PRL,
    "prx": PRX,
    "epjc": EPJC,
}


# Templates that should NOT receive the NeurIPS-style reproducibility checklist
# appended in stage 22. HEP journals, EPJC, and generic have their own norms.
ML_CHECKLIST_TEMPLATES: frozenset[str] = frozenset({
    "neurips_2024",
    "neurips_2025",
    "icml_2025",
    "icml_2026",
    "iclr_2025",
    "iclr_2026",
})


def get_template(name: str) -> ConferenceTemplate:
    """Look up a conference template by name.

    Raises ``KeyError`` if *name* is not in the registry.
    Accepts both full names (``"neurips_2024"``) and short aliases (``"neurips"``).
    """
    key = name.lower().strip().replace("-", "_").replace(" ", "_")
    if key not in CONFERENCE_REGISTRY:
        available = ", ".join(sorted({t.name for t in CONFERENCE_REGISTRY.values()}))
        raise KeyError(f"Unknown conference template: {name!r}. Available: {available}")
    return CONFERENCE_REGISTRY[key]


def list_conferences() -> list[str]:
    """Return deduplicated list of canonical template names."""
    return sorted({t.name for t in CONFERENCE_REGISTRY.values()})
