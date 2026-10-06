import 'package:corestream_mobile/data/api_endpoint.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Web: el socket utiliza la API directa aunque HTTP use /api', () {
    expect(
        resolveWebSocketBase('/api',
            webSocketBase: 'https://corestream-app-api-grupo1.vercel.app/api',
            pageBase:
                Uri.parse('https://corestream-app-base-grupo1.vercel.app/')),
        Uri.parse('wss://corestream-app-api-grupo1.vercel.app/api'));
  });
  test('Android local conserva su backend HTTP sin override', () {
    expect(resolveWebSocketBase('http://10.0.2.2:8000/api/'),
        Uri.parse('ws://10.0.2.2:8000/api'));
  });
  test('Una ruta relativa sin override mantiene el mismo origen', () {
    expect(
        resolveWebSocketBase('/api',
            pageBase: Uri.parse('https://example.test/')),
        Uri.parse('wss://example.test/api'));
  });
}
