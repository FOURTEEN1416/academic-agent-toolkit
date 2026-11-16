<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · de cero a un artículo completo con texto y figuras"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[Página del producto](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5: de cero a un artículo completo con texto y figuras.**

PaperSpine5 es un AI Skill que cubre todo el proceso de un artículo. Tú aportas la dirección de investigación, los materiales que ya tengas o los datos experimentales; él busca la bibliografía, ordena los argumentos, arma el esquema, redacta el texto completo, genera las figuras científicas, verifica las citas, pasa por revisión y corrección y se ocupa de la maquetación, y al final entrega fuentes editables de Word / LaTeX y un PDF.

El cuerpo del texto, las figuras de datos, los esquemas de mecanismo y los diagramas de método se producen dentro de la misma tarea. Se inicia con `paper-spine`, eliges el enfoque en la página web, previsualizas texto y figuras, dejas comentarios de revisión y descargas los resultados. Los materiales de investigación se guardan por defecto en tu equipo, y cada afirmación, cita y figura se apoya en fuentes y evidencias reales.

## Descargas

- Suite para Windows x64: unos 26.5 MB.
- Suite para Linux glibc x86_64: unos 56.2 MB.
- Suite para macOS Apple Silicon: unos 40.6 MB.
- Suite para macOS Intel x86_64: unos 40.5 MB.

Todas las descargas figuran en la lista pública de lanzamientos y se verifican con SHA-256. La versión actual es la versión preliminar `v0.4.0-alpha.3`.

## Instalación y migración desde versiones anteriores

Windows x64:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux:

```sh
sh ./install.sh --target codex --clean-legacy
```

`-CleanLegacy` solo archiva las carpetas conocidas de descubrimiento de Skills V3/V4. No borra datos de tareas, ajustes del host ni archivos desconocidos. Ambos instaladores verifican el número de bytes, el SHA-256, la integridad interna de la suite y una comprobación al arrancar.

## Comprobar y aplicar actualizaciones

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

Al ejecutar de nuevo el instalador se comprueba la versión. Si hay una nueva, se actualiza de forma reversible y se comprueba el arranque, conservando los datos. Una instalación completa y actual no se vuelve a descargar ni sobrescribir. Cada invocación de la Skill busca actualizaciones y actualiza la suite y el actualizador cuando es necesario; se respeta la desactivación explícita.

## Límites

- Las suites autocontenidas están verificadas en Windows x64, Linux glibc x86_64, macOS arm64 y macOS x86_64. Linux arm64 y musl/Alpine no se declaran compatibles.
- Los paquetes de macOS no están firmados ni notarizados; el primer arranque puede requerir una autorización explícita del usuario.
- Es una versión preliminar alpha sin firma criptográfica independiente.
- Publicar el producto no autoriza el envío de manuscritos, la subida de material privado, pagos ni contacto externo.
- El canal de apoyo es voluntario, no desbloquea funciones y no lee el estado de pago.

## Estructura del repositorio público

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine`: proyecciones por host.
- `dist/claude/commands/paperspine.md`: entrada de comando de Claude.
- `install.ps1`, `install.sh`: límites de instalación.
- Métodos y herramientas principales: `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## Desarrollo

`src/` contiene el código fuente del Skill y `dist/` las proyecciones públicas por host. El repositorio público conserva el código y las pruebas, no tareas locales, datos clínicos, cachés ni registros de ejecución de desarrollo.

MIT License.
