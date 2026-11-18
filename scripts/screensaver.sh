#!/usr/bin/env bash
# Turns on the screensaver built into dumbtv home and puts its images on the TV from this
# computer. The images cross-fade with a slow zoom under a clock; a file named
# "Category - Title - 1.jpg" is captioned "CATEGORY" over "Title". No app is added: the
# screensaver is a service of dumbtv home, which still has no internet access.
# The images go to the launcher's media folder, the one adb can write on every Fire OS.
# Usage: ./scripts/screensaver.sh [options] [image|folder ...]
#   --replace     remove the images already on the TV first
#   --minutes N   idle minutes before it starts (Fire OS: screen_off_timeout)
#   --off         give the screensaver back to the TV's own (Amazon's, or Android's)
#   --dry-run  -y
# With no image, only the screensaver setting is changed.
# ./scripts/screensaver-images.py downloads series, anime and film backdrops to use.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PKG=tv.dumbtv.home
DREAM=$PKG/.Screensaver
DIR=/sdcard/Android/media/$PKG/screensaver
REPLACE=0 OFF=0 MINUTES=""
args=() images=()
value() { [[ $# -ge 2 && -n $2 && $2 != -* ]] || die "$1 needs a value"; }
while [[ $# -gt 0 ]]; do
  case $1 in
    --replace) REPLACE=1 ;;
    --off) OFF=1 ;;
    --minutes) value "$@"; MINUTES=$2; shift ;;
    --dry-run|-y|--yes) args+=("$1") ;;
    -*) die "unknown flag: $1" ;;
    *) images+=("$1") ;;
  esac
  shift
done
parse_flags "${args[@]+"${args[@]}"}"

case $MINUTES in ''|[1-9]|[1-9][0-9]|1[0-9][0-9]) ;; *) die "--minutes takes 1 to 199" ;; esac

# A folder stands for the images in it.
files=()
for a in "${images[@]+"${images[@]}"}"; do
  if [[ -d $a ]]; then
    for f in "$a"/*; do
      [[ -f $f ]] || continue
      case $(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z') in jpg|jpeg|png|webp) files+=("$f") ;; esac
    done
  elif [[ -f $a ]]; then
    case $(printf '%s' "${a##*.}" | tr 'A-Z' 'a-z') in
      jpg|jpeg|png|webp) files+=("$a") ;;
      *) die "$a: the screensaver reads .jpg, .jpeg, .png and .webp" ;;
    esac
  else
    die "not a file or folder: $a"
  fi
done
[[ ${#images[@]} -gt 0 && ${#files[@]} -eq 0 ]] && die "no .jpg, .jpeg, .png or .webp in: ${images[*]}"

need_device
current=$(dev1 settings get secure screensaver_components)

if [[ $OFF == 1 ]]; then
  step "screensaver off"
  want=$(dev1 settings get secure screensaver_default_component)
  case $want in ''|null) want=$AOSP_DREAM ;; esac
  if [[ $current != "$DREAM" ]]; then
    note "the TV does not use the dumbtv screensaver (it uses ${current:-none}): unchanged"
    exit 0
  fi
  acmd settings put secure screensaver_components "$want" >/dev/null
  note "screensaver is now $want; the images stay in $DIR"
  exit 0
fi

present $PKG || die "dumbtv home is not installed: ./scripts/launcher.sh first"
dev "dumpsys package $PKG" | grep -q 'tv.dumbtv.home/.Screensaver' ||
  die "this dumbtv home has no screensaver; build and install this fork's launcher: ./launcher/build.sh && ./launcher/install.sh"

step "plan"
note "screensaver  $DREAM (now: ${current:-none})"
[[ ${#files[@]} -gt 0 ]] && note "images       ${#files[@]}, into $DIR"
[[ $REPLACE == 1 ]] && note "replace      the images already on the TV are removed first"
[[ -n $MINUTES ]] && note "starts after $MINUTES idle minutes"
if [[ $DRY_RUN == 0 ]]; then confirm "Use the dumbtv screensaver on $SERIAL?" || die "cancelled"; fi

if [[ ${#files[@]} -gt 0 || $REPLACE == 1 ]]; then
  step "images"
  acmd "mkdir -p '$DIR'" >/dev/null
  [[ $REPLACE == 1 ]] && acmd "rm -f '$DIR'/*" >/dev/null
  n=0
  for f in "${files[@]+"${files[@]}"}"; do
    n=$((n + 1))
    if [[ $DRY_RUN == 1 ]]; then
      note "[dry-run] push $(basename "$f")"
      continue
    fi
    # Git Bash leaves a path with a quote in it (Journey's End) unconverted, and adb.exe
    # cannot read /c/...: hand it the Windows path itself.
    src=$f
    if command -v cygpath >/dev/null 2>&1; then src=$(cygpath -w "$f"); fi
    out=$("$ADB" -s "$SERIAL" push "$src" "$DIR/$(basename "$f")" 2>&1) ||
      die "push of $(basename "$f") failed: $out"
  done
  note "$n pushed"
  on_tv=$(dev "ls '$DIR' 2>/dev/null" | tr -d '\r' | grep -ciE '\.(jpe?g|png|webp)$')
  note "${on_tv:-0} images on the TV"
fi

step "setting"
acmd settings put secure screensaver_components "$DREAM" >/dev/null
note "screensaver_components  $DREAM"
if [[ -n $MINUTES ]]; then
  acmd settings put system screen_off_timeout "$((MINUTES * 60000))" >/dev/null
  note "screen_off_timeout      $((MINUTES * 60000)) ms"
fi
note "done: ./scripts/screensaver.sh --off gives the TV's own screensaver back"
