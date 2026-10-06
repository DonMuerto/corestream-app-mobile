import 'package:corestream_mobile/data/api_event.dart';
import 'package:corestream_mobile/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> event(String type, Map<String, dynamic>? payload,
        {String at = '2026-10-06T20:00:00Z'}) =>
    {
      'event_type': type,
      'user': {'id': 'developer-uuid'},
      'created_at': at,
      'payload': payload,
    };

void main() {
  test('Official status transition is not displayed as TODO -> TODO', () {
    final parsed = parseApiTicketEvent(event('STATUS_CHANGED', {
      'from_status': 'TODO',
      'to_status': 'IN_PROGRESS',
    }));
    expect(parsed.type, 'STATUS');
    expect(parsed.userId, 'developer-uuid');
    expect(parsed.fromStatus, TicketStatus.todo);
    expect(parsed.toStatus, TicketStatus.inProgress);
  });

  test('Question and resolution use the official payload fields', () {
    final question = parseApiTicketEvent(event('QUESTION_RAISED', {
      'question': 'Confirmar persistencia del bloqueo',
      'from_status': 'IN_PROGRESS',
      'to_status': 'BLOCKED_QUESTION',
    }));
    final answer = parseApiTicketEvent(event('QUESTION_RESOLVED', {
      'resolution': 'Persistencia verificada',
    }));
    expect(question.type, 'QUESTION');
    expect(question.text, 'Confirmar persistencia del bloqueo');
    expect(question.toStatus, TicketStatus.blocked);
    expect(answer.type, 'RESOLVED');
    expect(answer.text, 'Persistencia verificada');
  });

  test('Redirection retains recipient and reason', () {
    final parsed = parseApiTicketEvent(event('REDIRECTED', {
      'to_user_id': 'recipient-uuid',
      'reason': 'Traspaso de prueba',
    }));
    expect(parsed.toUserId, 'recipient-uuid');
    expect(parsed.text, 'Traspaso de prueba');
  });

  test('CS-020 justification, recipient and assignment are displayed', () {
    final parsed = parseApiTicketEvent(event('REDIRECTED', {
      'justification': 'Traspaso con justificación oficial',
      'to_user_id': 'recipient-uuid',
      'previous_status': 'IN_PROGRESS',
      'new_status': 'TODO',
    }));
    expect(parsed.text, 'Traspaso con justificación oficial');
    expect(parsed.toUserId, 'recipient-uuid');
    expect(parsed.fromStatus, TicketStatus.inProgress);
    expect(parsed.toStatus, TicketStatus.todo);
    expect(parseApiTicketEvent(event('TICKET_ASSIGNED', {
      'to_user_id': 'recipient-uuid',
    })).type, 'ASSIGNED');
  });

  test('Imported comments and events without payload remain supported', () {
    expect(parseApiTicketEvent(event('QUESTION_RAISED', {
      'comment': 'Pregunta importada',
      'question_text': 'Pregunta importada',
    })).text, 'Pregunta importada');
    final empty = parseApiTicketEvent(event('CREATED', null));
    expect(empty.type, 'CREATED');
    expect(empty.text, isNull);
    expect(empty.fromStatus, isNull);
    expect(empty.toStatus, isNull);
  });

  test('Descending API events become chronological for latest question lookup', () {
    final parsed = parseApiTicketEvents([
      event('QUESTION_RAISED', {'question': 'La más reciente'},
          at: '2026-10-06T21:00:00Z'),
      event('QUESTION_RAISED', {'question': 'La anterior'}),
    ]);
    expect(parsed.last.text, 'La más reciente');
    expect(parsed.first.text, 'La anterior');
  });

  test('Blocked clock is independent of accumulated work time', () {
    final ticket = Ticket(
      id: 'ticket', number: 0, epicId: 'epic', title: 'QA', description: '',
      spentSeconds: 37, blockedSeconds: 20,
      blockedSince: DateTime.now().subtract(const Duration(seconds: 120)),
    );
    expect(ticket.liveSpentSeconds, 37);
    expect(ticket.liveBlockedSeconds, inInclusiveRange(140, 142));
  });

  test('A cleared block start does not keep accumulating time', () {
    final ticket = Ticket(
      id: 'ticket', number: 0, epicId: 'epic', title: 'QA', description: '',
      blockedSeconds: 30,
    );
    expect(ticket.liveBlockedSeconds, 30);
  });
}
