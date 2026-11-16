#!/usr/bin/env sh
set -eu

VERSION="0.4.0-alpha.3"
MANIFEST_PATH=""
MANIFEST_URL="https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/website/downloads/manifest.json"
MIRROR_MANIFEST_URL="https://wubing2023.github.io/PaperSpine/v5/downloads/manifest.json"
TARGET="codex"
CLEAN_LEGACY=0
CHECK_ONLY=0
BUNDLE_PATH=""
PROFILE_ROOT="${HOME}/.paperspine5/profiles/default"
CODEX_SKILLS_ROOT="${CODEX_SKILLS_ROOT:-${HOME}/.codex/skills}"
CLAUDE_SKILLS_ROOT="${CLAUDE_SKILLS_ROOT:-${HOME}/.claude/skills}"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--target codex|claude-code|both] [--clean-legacy]
                    [--check-only] [--manifest PATH] [--bundle PATH] [--profile-root PATH]

Downloads and verifies the self-contained PaperSpine5 suite for this POSIX host,
archives an existing canonical paper-spine Skill, activates the profile, and
runs first-start health. Unknown folders and paper task data are never deleted.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target) TARGET=${2:?missing --target value}; shift 2 ;;
    --clean-legacy) CLEAN_LEGACY=1; shift ;;
    --check-only) CHECK_ONLY=1; shift ;;
    --manifest|--manifest-path) MANIFEST_PATH=${2:?missing --manifest value}; shift 2 ;;
    --bundle) BUNDLE_PATH=${2:?missing --bundle value}; shift 2 ;;
    --profile-root) PROFILE_ROOT=${2:?missing --profile-root value}; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
case "$PROFILE_ROOT" in /*) ;; *) PROFILE_ROOT="$(pwd -P)/$PROFILE_ROOT" ;; esac

case "$TARGET" in codex|claude-code|both) ;; *) echo "Invalid target: $TARGET" >&2; exit 2 ;; esac

machine=$(uname -m)
os=$(uname -s)
case "$os/$machine" in
  Linux/x86_64|Linux/amd64)
    PLATFORM="linux-x86_64"
    # The published Linux interpreter is glibc-only, never guess on musl.
    getconf GNU_LIBC_VERSION >/dev/null 2>&1 || { echo "Unsupported Linux C library: the suite requires glibc." >&2; exit 2; }
    ;;
  Darwin/arm64|Darwin/aarch64) PLATFORM="macos-arm64" ;;
  Darwin/x86_64|Darwin/amd64) PLATFORM="macos-x86_64" ;;
  *) echo "Unsupported PaperSpine5 suite platform: $os/$machine" >&2; exit 2 ;;
esac

# Parse only JSON data; never source/eval manifest text. This keeps clean installs
# independent of a system Python or jq. Ambiguous keys and malformed data fail.
manifest_fields() {
  awk -v platform="$PLATFORM" '
  function fail() { bad=1; print "Invalid or ambiguous suite manifest." > "/dev/stderr"; exit 2 }
  function token(    c,j,e,h) {
    while (substr(text,pos,1) ~ /[ \t\r\n]/ && pos<=length(text)) pos++
    c=substr(text,pos,1); tok=c; val=c
    if(c=="\"") {
      j=++pos
      while(pos<=length(text)) {
        c=substr(text,pos,1)
        if(c=="\"") { val=substr(text,j,pos-j); pos++; tok="string"; return }
        if(c ~ /[[:cntrl:]]/) fail()
        if(c=="\\") {
          pos++;e=substr(text,pos,1)
          if(e=="u") { h=substr(text,pos+1,4);if(length(h)!=4 || h ~ /[^a-fA-F0-9]/) fail();pos+=4 }
          else if(index("\"\\/bfnrt",e)==0 || e=="") fail()
        }
        pos++
      }
      fail()
    }
    if(c ~ /[{}\[\]:,]/ && c!="") {pos++;return}
    if(match(substr(text,pos),/^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?/)) {
      val=substr(text,pos,RLENGTH);tok="number";pos+=RLENGTH;return
    }
    if(match(substr(text,pos),/^(true|false|null)/)) {val=substr(text,pos,RLENGTH);tok="literal";pos+=RLENGTH;return}
    if(c=="") {tok="end";return}
    fail()
  }
  function parse(p,    key,idx) {
    if(tok=="{") {
      token();if(tok=="}"){token();return}
      while(1) {
        if(tok!="string" || val !~ /^[A-Za-z_][A-Za-z0-9_]*$/) fail()
        key=val;if((p SUBSEP key) in keys) fail();keys[p SUBSEP key]=1
        token();if(tok!=":")fail();token();parse(p "." key)
        if(tok=="}"){token();return} if(tok!=",")fail();token()
      }
    }
    if(tok=="[") {
      token();idx=0
      if(tok=="]"){counts[p]=0;token();return}
      while(1) {parse(p "." idx);idx++;if(tok=="]"){counts[p]=idx;token();return}if(tok!=",")fail();token()}
    }
    if(tok!="string" && tok!="number" && tok!="literal")fail()
    values[p]=val;types[p]=tok;token()
  }
  { text=text $0 "\n" }
  END {
    if(bad)exit 2
    pos=1;token();if(tok!="{")fail();parse("root");if(tok!="end")fail()
    found=0
    for(i=0;i<counts["root.artifacts"];i++) {
      p="root.artifacts." i
      if(values[p ".platform"]==platform && (values[p ".kind"]=="suite" || values[p ".kind"]=="suite-" platform)) {selected=p;found++}
    }
    if(found!=1)fail()
    version=values["root.version"];file=values[selected ".file"];bytes=values[selected ".bytes"]
    sha=values[selected ".sha256"];build=values[selected ".build_id"];url=values[selected ".download_url"]
    gsub(/\\\//,"/",url)
    if(types["root.version"]!="string" || types[selected ".file"]!="string" || types[selected ".bytes"]!="number" || types[selected ".sha256"]!="string" || types[selected ".build_id"]!="string" || types[selected ".download_url"]!="string")fail()
    if(version !~ /^[A-Za-z0-9][A-Za-z0-9._-]*$/ || build !~ /^[A-Za-z0-9][A-Za-z0-9._-]*$/ || file !~ /^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$/ || bytes !~ /^[1-9][0-9]*$/ || length(sha)!=64 || sha ~ /[^a-fA-F0-9]/)fail()
    if(url !~ /^https:\/\/github\.com\/WUBING2023\/PaperSpine\/releases\/download\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\.zip$/)fail()
    parts=split(url,urlparts,"/");if(urlparts[parts]!=file)fail()
    print version;print file;print bytes;print tolower(sha);print build;print url
  }' "$1"
}

work=$(mktemp -d "${TMPDIR:-/tmp}/paperspine5-v5.XXXXXX")
work=$(CDPATH= cd -- "$work" && pwd -P)
work_parent=$(dirname -- "$work")
cleanup() {
  # Delete only the exact mktemp child, never a re-pointed directory/link.
  if [ -d "$work" ] && [ ! -L "$work" ] && [ "$(dirname -- "$work")" = "$work_parent" ]; then
    case "$(basename -- "$work")" in paperspine5-v5.??????) rm -rf -- "$work" ;; *) echo "Refusing unexpected temporary path." >&2 ;; esac
  fi
}
trap cleanup EXIT HUP INT TERM
if [ -n "$MANIFEST_PATH" ]; then
  manifest="$MANIFEST_PATH"
else
  command -v curl >/dev/null 2>&1 || { echo "curl is required to read the latest manifest." >&2; exit 2; }
  manifest="$work/manifest.json"
  if ! curl --fail --location --retry 2 "$MANIFEST_URL" --output "$manifest"; then
    curl --fail --location --retry 2 "$MIRROR_MANIFEST_URL" --output "$manifest"
  fi
fi
manifest_fields "$manifest" > "$work/selected.txt"
{ IFS= read -r VERSION; IFS= read -r FILE; IFS= read -r BYTES; IFS= read -r SHA256; IFS= read -r BUILD_ID; IFS= read -r DOWNLOAD_URL; } < "$work/selected.txt"
state="$PROFILE_ROOT/.paperspine5-lifecycle/profile-state.json"
current=""
if [ -f "$state" ]; then
  current=$(sed -n 's/.*"active_build_id"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9._-]*\)".*/\1/p' "$state" | head -n 1)
fi
if [ "$TARGET" = "both" ]; then targets="codex claude-code"; else targets="$TARGET"; fi
skills_ready=true
for target in $targets; do
  if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
  pointer="$root/paper-spine/references/installed-suite.json"
  installed="$PROFILE_ROOT/.paperspine5-lifecycle/installs/$BUILD_ID"
  if [ ! -f "$root/paper-spine/SKILL.md" ] || [ ! -f "$pointer" ] ||
     [ ! -x "$installed/runtime_vendor/python/bin/python3" ] ||
     ! "$installed/runtime_vendor/python/bin/python3" -I -B -c 'import json,sys; p=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if p.get("build_id")==sys.argv[2] and p.get("suite_root")==sys.argv[3] else 1)' "$pointer" "$BUILD_ID" "$installed"; then
    skills_ready=false
  fi
done
if [ -z "$current" ]; then status="not_installed"; elif [ "$current" = "$BUILD_ID" ]; then status="up_to_date"; else status="update_available"; fi
if [ "$CHECK_ONLY" -eq 1 ]; then
  printf '{"status":"%s","platform":"%s","current_build_id":"%s","available_build_id":"%s","version":"%s","skills_ready":%s}\n' "$status" "$PLATFORM" "$current" "$BUILD_ID" "$VERSION" "$skills_ready"
  exit 0
fi
if [ "$status" = "up_to_date" ] && [ "$skills_ready" = "true" ]; then
  if [ "$CLEAN_LEGACY" -eq 1 ]; then
    installed="$PROFILE_ROOT/.paperspine5-lifecycle/installs/$BUILD_ID"
    "$installed/paperspine" verify-bundle --bundle "$installed" >/dev/null
    set -- "$installed/runtime_vendor/python/bin/python3" -I -B "$installed/standalone/paper-spine/scripts/skill_discovery_migration.py" preview --archive-root "$HOME/.paperspine5/legacy-migrations" --operation-id "v5-preview-$(date -u +%Y%m%d-%H%M%S)"
    for target in $targets; do
      if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
      set -- "$@" --skills-root "$target=$root"
    done
    "$@" > "$work/legacy-preview.json"
    if ! grep -Eq '"item_count"[[:space:]]*:[[:space:]]*0([,}])' "$work/legacy-preview.json"; then
      set -- "$installed/runtime_vendor/python/bin/python3" -I -B "$installed/standalone/paper-spine/scripts/skill_discovery_migration.py" migrate --archive-root "$HOME/.paperspine5/legacy-migrations" --operation-id "v5-clean-$(date -u +%Y%m%d-%H%M%S)"
      for target in $targets; do
        if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
        set -- "$@" --skills-root "$target=$root"
      done
      "$@" >/dev/null
    fi
  fi
  printf 'PaperSpine5 %s is up to date for %s. Existing profile and Skills retained; no suite download required.\n' "$VERSION" "$PLATFORM"
  exit 0
fi
command -v unzip >/dev/null 2>&1 || { echo "unzip is required to install the suite." >&2; exit 2; }
zip="$work/$FILE"
if [ -n "$BUNDLE_PATH" ]; then cp "$BUNDLE_PATH" "$zip"; else curl --fail --location --retry 3 "$DOWNLOAD_URL" --output "$zip"; fi
actual_bytes=$(wc -c < "$zip" | tr -d '[:space:]')
if [ "$actual_bytes" != "$BYTES" ]; then echo "Byte-size mismatch for $FILE" >&2; exit 1; fi
if command -v sha256sum >/dev/null 2>&1; then actual_sha=$(sha256sum "$zip" | awk '{print $1}'); else actual_sha=$(shasum -a 256 "$zip" | awk '{print $1}'); fi
if [ "$actual_sha" != "$SHA256" ]; then echo "SHA-256 mismatch for $FILE" >&2; exit 1; fi
extract="$work/suite"
mkdir -p "$extract"
unzip -q "$zip" -d "$extract"
chmod +x "$extract/paperspine" "$extract/release/stable-update" "$extract/runtime_vendor/python/bin/python3"
"$extract/paperspine" verify-bundle --bundle "$zip" >/dev/null

stamp=$(date -u +%Y%m%d-%H%M%S)
operation="v5-${PLATFORM}-${stamp}"
backup_root="$HOME/.paperspine5/backups/v5-install/$stamp"
archive_root="$HOME/.paperspine5/legacy-migrations"
if [ "$TARGET" = "both" ]; then targets="codex claude-code"; else targets="$TARGET"; fi
if [ "$CLEAN_LEGACY" -eq 1 ]; then
  set -- "$extract/runtime_vendor/python/bin/python3" -I -B "$extract/standalone/paper-spine/scripts/skill_discovery_migration.py" preview --archive-root "$archive_root" --operation-id "$operation"
  for target in $targets; do
    if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
    set -- "$@" --skills-root "$target=$root"
  done
  "$@" > "$work/legacy-preview.json"
  if ! grep -Eq '"item_count"[[:space:]]*:[[:space:]]*0([,}])' "$work/legacy-preview.json"; then
    set -- "$extract/runtime_vendor/python/bin/python3" -I -B "$extract/standalone/paper-spine/scripts/skill_discovery_migration.py" migrate --archive-root "$archive_root" --operation-id "$operation"
    for target in $targets; do
      if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
      set -- "$@" --skills-root "$target=$root"
    done
    "$@" >/dev/null
  fi
fi
mkdir -p "$PROFILE_ROOT"
if [ "$status" = "up_to_date" ]; then
  echo "Current profile retained; installed only missing target Skills."
elif [ -f "$state" ]; then
  "$extract/paperspine" update --profile-root "$PROFILE_ROOT" --bundle "$zip" --operation-id "$operation" --confirm
else
  "$extract/paperspine" install --profile-root "$PROFILE_ROOT" --bundle "$zip" --operation-id "$operation"
fi
"$extract/paperspine" first-start --profile-root "$PROFILE_ROOT"
installed="$PROFILE_ROOT/.paperspine5-lifecycle/installs/$BUILD_ID"
for target in $targets; do
  if [ "$target" = "codex" ]; then root="$CODEX_SKILLS_ROOT"; else root="$CLAUDE_SKILLS_ROOT"; fi
  destination="$root/paper-spine"
  if [ "$status" = "up_to_date" ] && [ "$skills_ready" = "true" ]; then continue; fi
  prepared="$work/prepared-skill-$target"
  "$extract/runtime_vendor/python/bin/python3" -I -B "$extract/release/install_skill.py" --archive "$zip" --installed-root "$installed" --prepared-root "$prepared" >/dev/null
  mkdir -p "$root"
  if [ -e "$destination" ]; then
    mkdir -p "$backup_root/$target"
    mv "$destination" "$backup_root/$target/paper-spine"
  fi
  mv "$prepared" "$destination"
  printf 'Installed V5 paper-spine Skill for %s: %s\n' "$target" "$destination"
done
printf 'PaperSpine5 %s installed for %s. Restart the host before invoking paper-spine.\n' "$VERSION" "$PLATFORM"
printf 'Profile: %s\nBackup root: %s\n' "$PROFILE_ROOT" "$backup_root"
