#!/usr/bin/env bash
set -euo pipefail

git clone --depth 1 --branch 3.47.2 https://github.com/flutter/flutter.git .vercel_flutter
./.vercel_flutter/bin/flutter config --enable-web --no-analytics
./.vercel_flutter/bin/flutter pub get
./.vercel_flutter/bin/flutter build web --release \
  --dart-define="SUPABASE_URL=${SUPABASE_URL:-}" \
  --dart-define="SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}"
