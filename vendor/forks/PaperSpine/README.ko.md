<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · 처음부터, 그림까지 갖춘 논문을 빠르게 완성합니다"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[제품 페이지](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5: 처음부터, 그림까지 갖춘 논문을 빠르게 완성합니다.**

PaperSpine5는 논문의 전 과정을 다루는 AI Skill입니다. 연구 주제나 이미 가진 자료, 실험 데이터를 주면 문헌 검색, 논점 정리, 개요 작성, 본문 집필, 과학 그림 생성, 인용 검증, 검토와 수정, 조판까지 처리하고 편집 가능한 Word / LaTeX 원본과 PDF를 넘겨줍니다.

본문부터 데이터 그림, 메커니즘 도해, 방법 프레임워크 그림까지 한 작업 안에서 만들어집니다. `paper-spine`으로 실행하고, 웹 화면에서 방식을 고르고, 본문과 그림을 미리 보고, 수정 의견을 남기고 결과물을 내려받습니다. 연구 자료는 기본적으로 로컬에 보관하며, 주장과 인용과 그림은 모두 실제 자료와 근거에 기반합니다.

## 다운로드

- Windows x64 suite: 약 26.5 MB.
- Linux glibc x86_64 suite: 약 56.2 MB.
- macOS Apple Silicon suite: 약 40.6 MB.
- macOS Intel x86_64 suite: 약 40.5 MB.

모든 다운로드는 공개 릴리스 목록에 올라 있으며 SHA-256으로 검증됩니다. 현재 버전은 `v0.4.0-alpha.3` 프리릴리스입니다.

## 설치와 이전 버전 마이그레이션

Windows x64:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux:

```sh
sh ./install.sh --target codex --clean-legacy
```

`-CleanLegacy`는 알려진 V3/V4 Skill 검색 폴더를 백업 위치로 옮길 뿐이며, 논문 작업 데이터와 호스트 설정, 알 수 없는 파일은 삭제하지 않습니다. 두 설치 프로그램 모두 바이트 수, SHA-256, suite 내부 무결성, 첫 실행 자체 점검을 확인합니다.

## 업데이트 확인과 적용

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

설치 프로그램을 다시 실행하면 버전을 확인합니다. 새 버전이 있으면 작업 데이터를 보존한 채 되돌릴 수 있는 업데이트와 실행 점검을 진행합니다. 최신 버전이고 Skill이 온전하면 다시 다운로드하거나 덮어쓰지 않습니다. Skill을 호출할 때마다 업데이트를 확인하고 필요하면 suite와 업데이트 도구를 함께 갱신합니다. 명시적으로 자동 업데이트를 끈 설정은 존중합니다.

## 경계

- 자체 포함 suite는 Windows x64, Linux glibc x86_64, macOS arm64, macOS x86_64에서 검증했습니다. Linux arm64와 musl/Alpine은 지원 대상으로 선언하지 않습니다.
- macOS 패키지는 서명되지 않았고 공증도 거치지 않아, 첫 실행 시 사용자의 명시적 허용이 필요할 수 있습니다.
- 현재는 alpha 프리릴리스이며 별도의 암호학적 서명이 없습니다.
- 제품 공개는 논문 투고, 비공개 자료 업로드, 결제, 외부 연락을 허가하지 않습니다.
- 지원 창구는 자발적인 유지보수 후원이며 기능을 열어주지 않고 결제 정보도 읽지 않습니다.

## 공개 저장소 구조

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine`: 호스트별 투영.
- `dist/claude/commands/paperspine.md`: Claude 명령 진입점.
- `install.ps1`, `install.sh`: 설치 경계.
- 주요 메서드/도구: `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## 개발

`src/`에 Skill 소스 코드가 있고 `dist/`는 호스트별 공개 투영입니다. 공개 저장소에는 소스와 테스트만 두고, 로컬 작업, 임상 데이터, 캐시, 개발 실행 로그는 넣지 않습니다.

MIT License.
