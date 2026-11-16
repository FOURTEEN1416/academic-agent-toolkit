<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · от нуля до готовой статьи с текстом и иллюстрациями"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[Страница продукта](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5: от нуля до готовой статьи с текстом и иллюстрациями.**

PaperSpine5 — это AI Skill, охватывающий весь цикл работы над научной статьёй. Вы задаёте направление исследования, имеющиеся материалы или экспериментальные данные — он ищет литературу, выстраивает аргументацию, составляет план, пишет полный текст, готовит научные иллюстрации, проверяет ссылки, проводит рецензирование и правку и выполняет вёрстку. На выходе — редактируемые исходники Word / LaTeX и PDF.

От основного текста до графиков с данными, схем механизмов и обзорных схем методов — всё делается в рамках одной задачи. Запуск выполняется командой `paper-spine`: в веб-интерфейсе вы выбираете вариант, просматриваете текст и иллюстрации, оставляете замечания и скачиваете результат. Материалы исследования по умолчанию остаются локально, а утверждения, ссылки и иллюстрации опираются на реальные источники и доказательства.

## Загрузки

- Suite для Windows x64: около 26,4 МБ.
- Suite для Linux glibc x86_64: около 56,2 МБ.
- Suite для macOS Apple Silicon: около 40,5 МБ.
- Suite для macOS Intel x86_64: около 40,5 МБ.

Все загрузки перечислены в публичном списке выпусков и проверяются по SHA-256. Текущая версия — `v0.4.0-alpha.3` (предрелиз).

## Установка и переход со старых версий

Windows x64:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux:

```sh
sh ./install.sh --target codex --clean-legacy
```

`-CleanLegacy` только архивирует известные каталоги обнаружения Skill версий V3/V4; данные задач, настройки хоста и неизвестные файлы не удаляются. Оба установщика проверяют размер в байтах, SHA-256, внутреннюю целостность suite и самопроверку при запуске.

## Проверка и установка обновлений

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

Повторный запуск установщика проверяет версию. При наличии новой версии выполняются обновление с возможностью отката и проверка запуска; данные задач сохраняются. Полная актуальная установка не загружается и не перезаписывается повторно. Каждый вызов Skill проверяет обновления и при необходимости обновляет suite и сам инструмент обновления; явное отключение автообновления учитывается.

## Границы

- Автономные suite проверены на Windows x64, Linux glibc x86_64, macOS arm64 и macOS x86_64. Поддержка Linux arm64 и musl/Alpine не заявлена.
- Пакеты для macOS не подписаны и не нотаризованы: при первом запуске может потребоваться явное разрешение пользователя.
- Это alpha-предрелиз без отдельной криптографической подписи.
- Публикация продукта не даёт разрешения на подачу статьи, загрузку приватных материалов, платежи или внешние обращения.
- Канал поддержки — добровольная поддержка сопровождения: он не открывает функции и не читает статус платежей.

## Структура публичного репозитория

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine`: проекции для хостов.
- `dist/claude/commands/paperspine.md`: вход команды Claude.
- `install.ps1`, `install.sh`: границы установки.
- Ключевые методы и инструменты: `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## Разработка

`src/` — исходный код Skill, `dist/` — публичные проекции для каждого хоста. В публичном репозитории хранятся исходный код и тесты; локальные задачи, клинические данные, кеши и журналы разработки — нет.

MIT License.
