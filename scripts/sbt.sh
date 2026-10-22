#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
mkdir -p "$WAYEB_PROJECT_ROOT/.tools" "$WAYEB_PROJECT_ROOT/artifacts"
SBT_LAUNCH="$WAYEB_PROJECT_ROOT/.tools/sbt-launch-1.9.9.jar"
if [[ ! -f "$SBT_LAUNCH" ]]; then
  curl -fL --retry 3 --connect-timeout 20 \
    https://repo.maven.apache.org/maven2/org/scala-sbt/sbt-launch/1.9.9/sbt-launch-1.9.9.jar \
    -o "$SBT_LAUNCH.tmp"
  mv "$SBT_LAUNCH.tmp" "$SBT_LAUNCH"
fi
python3 - "$SBT_LAUNCH" <<'PY'
import hashlib, sys
actual = hashlib.sha1(open(sys.argv[1], 'rb').read()).hexdigest()
expected = '2cf01b9cbc25a7a21f5e79bc9e591e8ec8e79bed'
if actual != expected:
    raise SystemExit('sbt launcher checksum mismatch: ' + actual)
PY
cd "$WAYEB_PROJECT_ROOT/build"
exec "$WAYEB_JAVA" -Xms256m -Xmx3g -XX:ActiveProcessorCount=4 \
  -Dsbt.override.build.repos=true \
  -Dsbt.repository.config="$WAYEB_PROJECT_ROOT/build/repositories" \
  -Dsbt.supershell=false -Dsbt.log.noformat=true \
  -Dlogback.configurationFile="$WAYEB_PROJECT_ROOT/configs/logback.xml" \
  -jar "$SBT_LAUNCH" "$@"

