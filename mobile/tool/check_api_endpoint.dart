// Prueba del resolvedor real sin flutter_tester (bloqueado por Windows).
import '../lib/data/api_endpoint.dart';

void main() {
  final cases = [
    (
      resolveWebSocketBase('/api',
          webSocketBase: 'https://corestream-app-api-grupo1.vercel.app/api',
          pageBase:
              Uri.parse('https://corestream-app-base-grupo1.vercel.app/')),
      'wss://corestream-app-api-grupo1.vercel.app/api'
    ),
    (
      resolveWebSocketBase('http://10.0.2.2:8000/api/'),
      'ws://10.0.2.2:8000/api'
    ),
    (
      resolveWebSocketBase('/api',
          pageBase: Uri.parse('https://example.test/')),
      'wss://example.test/api'
    ),
  ];
  for (final (actual, expected) in cases) {
    if (actual.toString() != expected) {
      throw StateError('Endpoint incorrecto: $actual; esperado: $expected');
    }
  }
  print('3 casos del resolvedor WebSocket aprobados con Dart.');
}
