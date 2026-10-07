import '../models/models.dart';

/// The mobile BFF exposes the official audit JSONB as `payload`.
/// Keep domain events chronological: the UI reverses them for newest first.
List<TicketEvent> parseApiTicketEvents(Iterable<dynamic> rows) {
  final events = [
    for (final row in rows)
      parseApiTicketEvent((row as Map).cast<String, dynamic>()),
  ];
  events.sort((a, b) => a.ts.compareTo(b.ts));
  return events;
}

TicketEvent parseApiTicketEvent(Map<String, dynamic> row) {
  final payload = row['payload'] is Map
      ? (row['payload'] as Map).cast<String, dynamic>()
      : <String, dynamic>{};
  final user = row['user'];
  final wire =
      (payload['action'] == 'ARCHIVED' || payload['action'] == 'RESTORED')
          ? payload['action'].toString()
          : (row['event_type'] ?? '').toString();
  final from = _firstText([payload['from_status'], payload['previous_status']]);
  final to = _firstText([payload['to_status'], payload['new_status']]);
  return TicketEvent(
    type: switch (wire) {
      'STATUS_CHANGED' => 'STATUS',
      'QUESTION_RAISED' => 'QUESTION',
      'QUESTION_RESOLVED' => 'RESOLVED',
      'TICKET_ASSIGNED' => 'ASSIGNED',
      _ => wire,
    },
    userId: user is Map ? (user['id'] ?? '').toString() : '',
    ts: DateTime.tryParse((row['created_at'] ?? '').toString()) ??
        DateTime.now(),
    text: _firstText([
      payload['comment'],
      payload['question_text'],
      payload['question'],
      payload['resolution'],
      payload['reason'],
      payload['justification'],
      payload['message'],
    ]),
    toUserId: _firstText([payload['to_user_id'], payload['assignee_id']]),
    fromStatus: from == null ? null : TicketStatusWire.parse(from),
    toStatus: to == null ? null : TicketStatusWire.parse(to),
  );
}

String? _firstText(Iterable<dynamic> values) {
  for (final value in values) {
    if (value != null && value.toString().trim().isNotEmpty) {
      return value.toString();
    }
  }
  return null;
}
