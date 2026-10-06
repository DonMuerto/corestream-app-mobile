#!/usr/bin/env bash
set -euo pipefail

# El mismo Flutter que compila el proyecto local; sin Supabase ni datos mock.
FLUTTER_VERSION=3.47.2
if [ ! -x .vercel_flutter/bin/flutter ]; then
  git clone --depth 1 --branch "$FLUTTER_VERSION" https://github.com/flutter/flutter.git .vercel_flutter
fi
.vercel_flutter/bin/flutter config --enable-web --no-analytics
.vercel_flutter/bin/flutter pub get --enforce-lockfile
.vercel_flutter/bin/flutter build web --release --dart-define=CS_API_URL=/api --dart-define=CS_WS_API_URL=https://corestream-app-api-grupo1.vercel.app/api
