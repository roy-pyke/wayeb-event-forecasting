#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
KAFKA_ARCHIVE="$WAYEB_PROJECT_ROOT/.tools/kafka_2.13-3.4.0.tgz"
mkdir -p "$WAYEB_PROJECT_ROOT/.tools"
if [[ ! -f "$KAFKA_ARCHIVE" ]]; then
  curl -fL --retry 3 --connect-timeout 20 \
    https://archive.apache.org/dist/kafka/3.4.0/kafka_2.13-3.4.0.tgz \
    -o "$KAFKA_ARCHIVE.tmp"
  mv "$KAFKA_ARCHIVE.tmp" "$KAFKA_ARCHIVE"
fi
python3 - "$KAFKA_ARCHIVE" <<'PY'
import hashlib, sys
expected = '2c405149c065627ce2125088dfcce0a4dc23aebaa72c1157736d5829cb5cbef273c0915ec55d2d8ba38e5e0524f0720f43e07d7d677439cd2ac7bea618caa65b'
actual = hashlib.sha512(open(sys.argv[1], 'rb').read()).hexdigest()
if actual != expected:
    raise SystemExit('Kafka archive checksum mismatch: ' + actual)
print('Verified Kafka 3.4.0 archive SHA-512')
PY
if [[ ! -d "$WAYEB_PROJECT_ROOT/.tools/kafka_2.13-3.4.0" ]]; then
  tar -xzf "$KAFKA_ARCHIVE" -C "$WAYEB_PROJECT_ROOT/.tools"
fi

