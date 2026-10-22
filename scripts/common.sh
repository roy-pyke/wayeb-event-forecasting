#!/usr/bin/env bash
set -euo pipefail
WAYEB_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WAYEB_PROJECT_ROOT
if [[ -n "${WAYEB_JAVA_HOME:-}" ]]; then
  WAYEB_JAVA="$WAYEB_JAVA_HOME/bin/java"
elif [[ -x /usr/libexec/java_home ]] && WAYEB_JAVA_HOME="$(/usr/libexec/java_home -v 11 2>/dev/null)"; then
  WAYEB_JAVA="$WAYEB_JAVA_HOME/bin/java"
elif [[ -n "${JAVA_HOME:-}" ]]; then
  WAYEB_JAVA="$JAVA_HOME/bin/java"
else
  WAYEB_JAVA="$(command -v java)"
fi
if ! "$WAYEB_JAVA" -version 2>&1 | head -n 1 | grep -q 'version "11\.'; then
  echo 'This deployment requires JDK 11. Set WAYEB_JAVA_HOME to its directory.' >&2
  exit 1
fi
export WAYEB_JAVA
export WAYEB_HOME="$WAYEB_PROJECT_ROOT/upstream/Wayeb"

