/// Configuración de la app.
///
/// Modo de datos:
///   - `api` (por defecto): backend FastAPI real, sin selector de usuarios mock.
///   - `demo`: referencia original en memoria, solo con CS_DEMO=true.
/// Para usar el backend local desde el emulador Android:
///
///       flutter run --dart-define=CS_API_URL=http://10.0.2.2:8000/api
///
///     (10.0.2.2 es localhost visto desde el emulador Android).
library;

class AppConfig {
  AppConfig._();

  /// URL base del backend. El modo demo requiere CS_DEMO=true explícito.
  static const String apiBaseUrl = String.fromEnvironment(
    'CS_API_URL',
    defaultValue: 'https://corestream-app-api-grupo1.vercel.app/api',
  );

  static const bool isDemo =
      bool.fromEnvironment('CS_DEMO', defaultValue: false);

  /// Vacía usa el mismo backend HTTP. En Web evita el proxy para el socket.
  static const String webSocketApiBaseUrl =
      String.fromEnvironment('CS_WS_API_URL', defaultValue: '');

  /// Intervalo de la simulación de eventos del equipo en modo demo.
  static const Duration demoEventInterval = Duration(seconds: 20);
}
