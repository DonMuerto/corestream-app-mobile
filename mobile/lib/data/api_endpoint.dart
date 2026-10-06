/// HTTP puede usar el proxy Web; el socket puede apuntar a la API directamente.
Uri resolveWebSocketBase(String httpBase,
    {String? webSocketBase, Uri? pageBase}) {
  final endpoint = (pageBase ?? Uri.base).resolve(webSocketBase ?? httpBase);
  return endpoint.replace(
      scheme: endpoint.scheme == 'https' ? 'wss' : 'ws',
      path: endpoint.path.replaceFirst(RegExp(r'/$'), ''));
}
