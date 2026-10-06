#!/usr/bin/env bash
set -euo pipefail

# Keep LF line endings: Vercel runs this file with Bash.
FLUTTER_VERSION=3.47.2
if [ ! -x .vercel_flutter/bin/flutter ]; then
  git clone --depth 1 --branch "$FLUTTER_VERSION" https://github.com/flutter/flutter.git .vercel_flutter
fi
.vercel_flutter/bin/flutter config --enable-web --no-analytics
.vercel_flutter/bin/flutter pub get --enforce-lockfile
.vercel_flutter/bin/flutter test test/api_endpoint_test.dart test/api_event_test.dart --reporter expanded
.vercel_flutter/bin/flutter build web --release --dart-define=CS_API_URL=/api --dart-define=CS_WS_API_URL=https://corestream-app-api-grupo1.vercel.app/api
