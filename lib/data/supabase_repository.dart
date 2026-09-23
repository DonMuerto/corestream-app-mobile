/// Datos de la demostración persistidos en Supabase/PostgreSQL.
///
/// La selección de usuarios es sólo una simulación de sesión: no hay
/// autenticación real. Las políticas públicas son aptas únicamente para
/// datos ficticios de una demo, nunca para información de producción.
library;

import 'dart:async';

import 'package:flutter/material.dart' show Color;
import 'package:supabase_flutter/supabase_flutter.dart' hide User;

import '../models/models.dart';
import 'repository.dart';

class SupabaseRepository implements CoreStreamRepository {
  SupabaseRepository({SupabaseClient? client})
      : _client = client ?? Supabase.instance.client;

  final SupabaseClient _client;
  final _changes = StreamController<int>.broadcast();
  final _push = StreamController<AppNotification>.broadcast();
  final Map<String, User> _users = {};
  final Map<String, Project> _projects = {};
  final Map<String, Epic> _epics = {};
  final Set<String> _seenNotifications = {};
  User? _current;
  Timer? _refreshTimer;
  int _revision = 0;

  @override
  Stream<int> get changes => _changes.stream;

  @override
  Stream<AppNotification> get incomingPush => _push.stream;

  void _emit() => _changes.add(++_revision);

  List<Map<String, dynamic>> _rows(dynamic value) =>
      List<Map<String, dynamic>>.from(value as List);

  DateTime? _date(dynamic value) =>
      value == null ? null : DateTime.tryParse(value.toString());

  Color _color(String? hex) => Color(
      int.tryParse('FF${(hex ?? '#4C8DFF').replaceFirst('#', '')}', radix: 16) ??
          0xFF4C8DFF);

  User _user(Map<String, dynamic> row) {
    final user = User(
      id: row['id'] as String,
      fullName: row['full_name'] as String,
      role: UserRoleWire.parse(row['role'] as String),
      specialty: row['specialty'] as String?,
      avatarColor: _color(row['avatar_color_hex'] as String?),
      isActive: row['is_active'] as bool? ?? true,
    );
    _users[user.id] = user;
    return user;
  }

  Project _project(Map<String, dynamic> row) {
    final project = Project(
      id: row['id'] as String,
      name: row['name'] as String,
      code: row['code'] as String,
      color: _color(row['color_hex'] as String?),
    );
    _projects[project.id] = project;
    return project;
  }

  Epic _epic(Map<String, dynamic> row) {
    final epic = Epic(
      id: row['id'] as String,
      projectId: row['application_id'] as String,
      name: row['name'] as String,
      orderIndex: (row['order_index'] as num?)?.toInt() ?? 0,
    );
    _epics[epic.id] = epic;
    return epic;
  }

  TicketEvent _event(Map<String, dynamic> row) => TicketEvent(
        type: row['type'] as String,
        userId: row['user_id'] as String,
        ts: _date(row['created_at']) ?? DateTime.now(),
        text: row['text'] as String?,
        toUserId: row['to_user_id'] as String?,
        fromStatus: row['from_status'] == null
            ? null
            : TicketStatusWire.parse(row['from_status'] as String),
        toStatus: row['to_status'] == null
            ? null
            : TicketStatusWire.parse(row['to_status'] as String),
      );

  Ticket _ticket(Map<String, dynamic> row,
      List<Map<String, dynamic>> subtasks,
      List<Map<String, dynamic>> events) =>
      Ticket(
        id: row['id'].toString(),
        number: (row['number'] as num).toInt(),
        epicId: row['epic_id'] as String,
        title: row['title'] as String,
        description: row['description'] as String? ?? '',
        status: TicketStatusWire.parse(row['status'] as String? ?? 'TODO'),
        priority: TicketPriorityWire.parse(row['priority'] as String? ?? 'MEDIUM'),
        assigneeId: row['assignee_id'] as String?,
        createdById: row['created_by_id'] as String?,
        dueDate: _date(row['due_date']),
        spentSeconds: (row['spent_seconds'] as num?)?.toInt() ?? 0,
        blockedSeconds: (row['blocked_seconds'] as num?)?.toInt() ?? 0,
        runningSince: _date(row['running_since']),
        prLink: row['pr_link'] as String?,
        subtasks: [
          for (final s in subtasks.where((s) => s['ticket_id'] == row['id']))
            Subtask(
              id: s['id'].toString(),
              title: s['title'] as String,
              done: s['done'] as bool? ?? false,
            ),
        ],
        events: [
          for (final e in events.where((e) => e['ticket_id'] == row['id']))
            _event(e),
        ],
      );

  Incident _incident(Map<String, dynamic> row,
      List<Map<String, dynamic>> comments) =>
      Incident(
        id: row['id'].toString(),
        number: (row['number'] as num).toInt(),
        projectId: row['application_id'] as String,
        title: row['title'] as String,
        description: row['description'] as String? ?? '',
        category: IncidentCategoryWire.parse(row['category'] as String),
        severity: IncidentSeverityWire.parse(row['severity'] as String),
        status: IncidentStatusWire.parse(row['status'] as String),
        reporterId: row['reporter_id'] as String,
        assigneeId: row['assignee_id'] as String?,
        createdAt: _date(row['created_at']) ?? DateTime.now(),
        comments: [
          for (final c in comments.where((c) => c['incident_id'] == row['id']))
            IncidentComment(
              userId: c['user_id'] as String,
              text: c['text'] as String,
              ts: _date(c['created_at']) ?? DateTime.now(),
            ),
        ],
      );

  Future<_Store> _load() async {
    final results = await Future.wait([
      _client.from('demo_users').select().order('id'),
      _client.from('applications').select().order('name'),
      _client.from('epics').select().order('order_index'),
      _client.from('tickets').select().isFilter('deleted_at', null).order('number'),
      _client.from('ticket_subtasks').select().order('order_index'),
      _client.from('ticket_events').select().order('created_at'),
      _client.from('demo_incidents').select().isFilter('deleted_at', null).order('created_at'),
      _client.from('demo_incident_comments').select().order('created_at'),
    ]);
    final users = _rows(results[0]).map(_user).toList();
    final projects = _rows(results[1]).map(_project).toList();
    final epics = _rows(results[2]).map(_epic).toList();
    final subtasks = _rows(results[4]);
    final events = _rows(results[5]);
    final comments = _rows(results[7]);
    return _Store(
      users: users,
      projects: projects,
      epics: epics,
      tickets: [for (final row in _rows(results[3])) _ticket(row, subtasks, events)],
      incidents: [for (final row in _rows(results[6])) _incident(row, comments)],
    );
  }

  User get _me => _current ?? (throw StateError('Selecciona un usuario demo.'));

  @override
  Future<List<User>> loginOptions() async {
    final rows = _rows(await _client
        .from('demo_users')
        .select()
        .eq('is_login_option', true)
        .order('id'));
    return rows.map(_user).toList();
  }

  @override
  Future<User> login(User user) async {
    _current = user;
    _seenNotifications.clear();
    for (final n in await fetchNotifications()) {
      _seenNotifications.add(n.id);
    }
    _refreshTimer?.cancel();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) async {
      try {
        for (final notification in await fetchNotifications()) {
          if (_seenNotifications.add(notification.id) && !notification.read) {
            _push.add(notification);
          }
        }
        _emit();
      } catch (_) {
        // La siguiente lectura de pantalla muestra el error de conexión.
      }
    });
    return user;
  }

  @override
  Future<void> logout() async {
    _refreshTimer?.cancel();
    _refreshTimer = null;
    _current = null;
  }

  ProjectSummary _summary(Project project, _Store store) {
    final epicIds = store.epics
        .where((epic) => epic.projectId == project.id)
        .map((epic) => epic.id)
        .toSet();
    final tickets = store.tickets.where((t) => epicIds.contains(t.epicId)).toList();
    return ProjectSummary(
      project: project,
      epicsCount: epicIds.length,
      ticketsTotal: tickets.length,
      ticketsDone: tickets.where((t) => t.status == TicketStatus.done).length,
      overdue: tickets.where((t) => t.isOverdue).length,
    );
  }

  @override
  Future<Dashboard> fetchDashboard() async {
    final me = _me;
    final store = await _load();
    if (me.isLead) {
      final open = store.tickets.where((t) => t.status != TicketStatus.done).toList();
      final blocked = open.where((t) => t.status == TicketStatus.blocked).toList();
      final late = open.where((t) => t.isOverdue).toList();
      final attention = <AttentionItem>[
        for (final t in {...blocked, ...late})
          AttentionItem.ticket(t, projectOfTicket(t)?.name ?? ''),
        for (final i in store.incidents.where((i) =>
            (i.status == IncidentStatus.open || i.status == IncidentStatus.reopened) &&
            (i.severity == IncidentSeverity.critical || i.severity == IncidentSeverity.high)))
          AttentionItem.incident(i, _projects[i.projectId]?.name ?? ''),
      ];
      return Dashboard(
        role: me.role,
        stats: {
          'apps': store.projects.length,
          'open': open.length,
          'blocked': blocked.length,
          'late': late.length,
        },
        projects: [for (final p in store.projects) _summary(p, store)],
        attention: attention.take(10).toList(),
      );
    }
    final mine = store.tickets
        .where((t) => t.assigneeId == me.id && t.status != TicketStatus.done)
        .toList()
      ..sort((a, b) => (a.dueDate ?? DateTime(2100))
          .compareTo(b.dueDate ?? DateTime(2100)));
    final myIncidents = store.incidents
        .where((i) => i.assigneeId == me.id && i.isOpen)
        .toList();
    final weekAgo = DateTime.now().subtract(const Duration(days: 7));
    return Dashboard(
      role: me.role,
      stats: {
        'mine': mine.length,
        'prog': mine.where((t) => t.status == TicketStatus.inProgress).length,
        'doneWeek': store.tickets.where((t) =>
            t.assigneeId == me.id && t.status == TicketStatus.done &&
            t.events.any((e) => e.type == 'COMPLETED' && e.ts.isAfter(weekAgo))).length,
        'incidents': myIncidents.length,
      },
      myTickets: mine,
      myIncidents: myIncidents,
    );
  }

  @override
  Future<List<ProjectSummary>> fetchProjects() async {
    final store = await _load();
    return [for (final p in store.projects) _summary(p, store)];
  }

  @override
  Future<Board> fetchBoard(String projectId) async {
    final store = await _load();
    final project = _projects[projectId];
    if (project == null) throw StateError('No se encontró la aplicación.');
    return Board(
      project: project,
      epics: [
        for (final epic in store.epics.where((e) => e.projectId == projectId))
          EpicBoard(
            epic: epic,
            tickets: store.tickets.where((t) => t.epicId == epic.id).toList(),
          ),
      ],
    );
  }

  @override
  Future<TicketDetail> fetchTicketDetail(String ticketId) async {
    final store = await _load();
    final ticket = store.tickets.where((t) => t.id == ticketId).firstOrNull;
    if (ticket == null) throw StateError('No se encontró el ticket.');
    final epic = _epics[ticket.epicId]!;
    return TicketDetail(
      ticket: ticket,
      epic: epic,
      project: _projects[epic.projectId]!,
      assignee: userById(ticket.assigneeId),
      createdBy: userById(ticket.createdById),
      permissions: TicketPermissions.compute(
        role: _me.role,
        userId: _me.id,
        status: ticket.status,
        assigneeId: ticket.assigneeId,
      ),
    );
  }

  @override
  Future<List<Incident>> fetchIncidents() async {
    final store = await _load();
    final list = _me.isLead
        ? store.incidents
        : store.incidents.where((i) =>
            i.assigneeId == _me.id || i.reporterId == _me.id || i.assigneeId == null).toList();
    return [...list]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  @override
  Future<Incident> fetchIncident(String incidentId) async {
    final store = await _load();
    return store.incidents.firstWhere((i) => i.id == incidentId);
  }

  @override
  Future<List<MemberLoad>> fetchTeamWorkload() async {
    final store = await _load();
    final weekAgo = DateTime.now().subtract(const Duration(days: 7));
    return [
      for (final u in store.users)
        MemberLoad(
          user: u,
          activeTickets: store.tickets.where((t) =>
              t.assigneeId == u.id && t.status != TicketStatus.done).length,
          inProgress: store.tickets.where((t) =>
              t.assigneeId == u.id && t.status == TicketStatus.inProgress).length,
          blocked: store.tickets.where((t) =>
              t.assigneeId == u.id && t.status == TicketStatus.blocked).length,
          doneLast7d: store.tickets.where((t) =>
              t.assigneeId == u.id && t.status == TicketStatus.done &&
              t.events.any((e) => e.type == 'COMPLETED' && e.ts.isAfter(weekAgo))).length,
          openIncidents: store.incidents.where((i) =>
              i.assigneeId == u.id && i.isOpen).length,
        ),
    ];
  }

  AppNotification _notification(Map<String, dynamic> row) => AppNotification(
        id: row['id'].toString(),
        kind: NotificationKindWire.parse(row['kind'] as String),
        message: row['message'] as String,
        ts: _date(row['created_at']) ?? DateTime.now(),
        read: row['is_read'] as bool? ?? false,
        ticketId: row['ticket_id'] as String?,
        incidentId: row['incident_id'] as String?,
      );

  @override
  Future<List<AppNotification>> fetchNotifications() async {
    if (_current == null) return [];
    final rows = _rows(await _client
        .from('demo_notifications')
        .select()
        .eq('user_id', _me.id)
        .order('created_at', ascending: false));
    return rows.map(_notification).toList();
  }

  @override
  Future<int> unreadCount() async =>
      (await fetchNotifications()).where((n) => !n.read).length;

  @override
  Future<List<User>> fetchUsers() async {
    final rows = _rows(await _client.from('demo_users').select().order('id'));
    return rows.map(_user).toList();
  }

  @override
  User? userById(String? id) => id == null ? null : _users[id];

  @override
  Project? projectOfTicket(Ticket ticket) =>
      _projects[_epics[ticket.epicId]?.projectId];

  Future<Map<String, dynamic>> _ticketRow(String ticketId) async {
    final rows = _rows(await _client.from('tickets').select()
        .eq('id', ticketId).isFilter('deleted_at', null).limit(1));
    if (rows.isEmpty) throw StateError('No se encontró el ticket.');
    return rows.first;
  }

  TicketPermissions _permissions(Map<String, dynamic> row) =>
      TicketPermissions.compute(
        role: _me.role,
        userId: _me.id,
        status: TicketStatusWire.parse(row['status'] as String),
        assigneeId: row['assignee_id'] as String?,
      );

  void _require(bool allowed) {
    if (!allowed) throw StateError('El usuario seleccionado no puede realizar esta acción.');
  }

  Future<void> _log(String ticketId, String type, {
    String? text,
    String? toUserId,
    TicketStatus? from,
    TicketStatus? to,
  }) async {
    await _client.from('ticket_events').insert({
      'ticket_id': ticketId,
      'type': type,
      'user_id': _me.id,
      'to_user_id': toUserId,
      'text': text,
      'from_status': from?.wire,
      'to_status': to?.wire,
    });
  }

  Future<void> _notify(Iterable<String> userIds, NotificationKind kind,
      String message, {String? ticketId, String? incidentId}) async {
    final ids = userIds.where((id) => id != _me.id).toSet();
    if (ids.isEmpty) return;
    await _client.from('demo_notifications').insert([
      for (final id in ids)
        {
          'user_id': id,
          'kind': kind.name.toUpperCase(),
          'message': message,
          'ticket_id': ticketId,
          'incident_id': incidentId,
        },
    ]);
  }

  Iterable<String> get _leadIds => _users.values
      .where((u) => u.isLead)
      .map((u) => u.id);

  Map<String, dynamic> _settle(Map<String, dynamic> row) {
    final since = _date(row['running_since']);
    final elapsed = since == null ? 0 : DateTime.now().difference(since).inSeconds;
    return {
      'spent_seconds': (row['spent_seconds'] as num? ?? 0).toInt() +
          (elapsed < 0 ? 0 : elapsed),
      'running_since': null,
    };
  }

  @override
  Future<void> assignTicket(String ticketId, String assigneeId,
      {String? comment}) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canAssign && _users.containsKey(assigneeId));
    await _client.from('tickets').update({
      'assignee_id': assigneeId,
      if (row['status'] == 'REDIRECTED') 'status': 'TODO',
    }).eq('id', ticketId);
    await _log(ticketId, 'ASSIGNED', toUserId: assigneeId, text: comment);
    await _notify([assigneeId], NotificationKind.assignment,
        '${_me.fullName} te asignó: “${row['title']}”', ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> startTicket(String ticketId) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canStart);
    await _client.from('tickets').update({
      'status': 'IN_PROGRESS',
      'running_since': DateTime.now().toUtc().toIso8601String(),
    }).eq('id', ticketId);
    await _log(ticketId, 'STATUS',
        from: TicketStatusWire.parse(row['status'] as String),
        to: TicketStatus.inProgress);
    _emit();
  }

  @override
  Future<void> completeTicket(String ticketId, String prLink) async {
    if (!prLinkPattern.hasMatch(prLink)) throw ArgumentError('pr_invalid');
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canComplete);
    await _client.from('tickets').update({
      ..._settle(row), 'status': 'DONE', 'pr_link': prLink,
    }).eq('id', ticketId);
    await _log(ticketId, 'COMPLETED');
    await _notify(_leadIds, NotificationKind.completion,
        '${_me.fullName} completó: “${row['title']}”', ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> raiseQuestion(String ticketId, String question) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canQuestion && question.trim().length >= 10);
    await _client.from('tickets').update({
      ..._settle(row),
      'status': 'BLOCKED',
      'blocked_since': DateTime.now().toUtc().toIso8601String(),
    }).eq('id', ticketId);
    await _log(ticketId, 'QUESTION', text: question.trim());
    await _notify(_leadIds, NotificationKind.question,
        '${_me.fullName} planteó una pregunta en: “${row['title']}”',
        ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> resolveQuestion(String ticketId, String resolution) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canResolveQuestion && resolution.trim().isNotEmpty);
    final since = _date(row['blocked_since']);
    final elapsed = since == null ? 0 : DateTime.now().difference(since).inSeconds;
    await _client.from('tickets').update({
      'status': 'IN_PROGRESS',
      'blocked_seconds': (row['blocked_seconds'] as num? ?? 0).toInt() +
          (elapsed < 0 ? 0 : elapsed),
      'blocked_since': null,
      'running_since': DateTime.now().toUtc().toIso8601String(),
    }).eq('id', ticketId);
    await _log(ticketId, 'RESOLVED', text: resolution.trim());
    await _notify([if (row['assignee_id'] != null) row['assignee_id'] as String],
        NotificationKind.system, '${_me.fullName} resolvió la pregunta: “${row['title']}”',
        ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> redirectTicket(String ticketId, String toUserId, String reason) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canRedirect &&
        _users.containsKey(toUserId) && toUserId != _me.id &&
        reason.trim().length >= 10);
    await _client.from('tickets').update({
      ..._settle(row), 'status': 'REDIRECTED', 'assignee_id': toUserId,
    }).eq('id', ticketId);
    await _log(ticketId, 'REDIRECTED', toUserId: toUserId, text: reason.trim());
    await _notify([toUserId, ..._leadIds], NotificationKind.redirect,
        '${_me.fullName} redirigió: “${row['title']}”', ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> toggleSubtask(String ticketId, String subtaskId, bool done) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canEditSubtasks);
    await _client.from('ticket_subtasks').update({'done': done})
        .eq('id', subtaskId).eq('ticket_id', ticketId);
    _emit();
  }

  @override
  Future<void> createTicket({
    required String epicId,
    required String title,
    required TicketPriority priority,
    String? assigneeId,
    String? description,
    DateTime? dueDate,
  }) async {
    _require(_me.isLead);
    final cleanTitle = title.trim();
    if (cleanTitle.length < 5 || cleanTitle.length > 120) {
      throw ArgumentError('El título debe tener entre 5 y 120 caracteres.');
    }
    if (assigneeId != null && !_users.containsKey(assigneeId)) {
      throw ArgumentError('El responsable no existe.');
    }
    final inserted = await _client.from('tickets').insert({
      'epic_id': epicId,
      'title': cleanTitle,
      'description': description?.trim().isNotEmpty == true
          ? description!.trim() : cleanTitle,
      'status': 'TODO',
      'priority': priority.wire,
      'assignee_id': assigneeId,
      'created_by_id': _me.id,
      'due_date': dueDate?.toUtc().toIso8601String(),
    }).select('id').single();
    final ticketId = inserted['id'].toString();
    await _log(ticketId, 'CREATED');
    if (assigneeId != null) {
      await _log(ticketId, 'ASSIGNED', toUserId: assigneeId);
      await _notify([assigneeId], NotificationKind.assignment,
          '${_me.fullName} te asignó: “$cleanTitle”', ticketId: ticketId);
    }
    await _notify(_leadIds, NotificationKind.system,
        '${_me.fullName} creó: “$cleanTitle”', ticketId: ticketId);
    _emit();
  }

  @override
  Future<void> deleteTicket(String ticketId) async {
    final row = await _ticketRow(ticketId);
    _require(_permissions(row).canDelete);
    await _client.from('tickets').update({
      'deleted_at': DateTime.now().toUtc().toIso8601String(),
      'deleted_by_id': _me.id,
      ..._settle(row),
    }).eq('id', ticketId);
    await _log(ticketId, 'DELETED');
    _emit();
  }

  @override
  Future<void> takeIncident(String incidentId) async {
    await _client.from('demo_incidents').update({
      'assignee_id': _me.id, 'status': 'IN_PROGRESS',
    }).eq('id', incidentId);
    _emit();
  }

  @override
  Future<void> assignIncident(String incidentId, String assigneeId) async {
    _require(_me.isLead && _users.containsKey(assigneeId));
    await _client.from('demo_incidents').update({
      'assignee_id': assigneeId, 'status': 'IN_PROGRESS',
    }).eq('id', incidentId);
    await _notify([assigneeId], NotificationKind.assignment,
        '${_me.fullName} te asignó una incidencia.', incidentId: incidentId);
    _emit();
  }

  @override
  Future<void> setIncidentStatus(String incidentId, IncidentStatus status) async {
    await _client.from('demo_incidents').update({'status': status.wire})
        .eq('id', incidentId);
    _emit();
  }

  @override
  Future<void> markNotificationRead(String id) async {
    await _client.from('demo_notifications').update({'is_read': true})
        .eq('id', id).eq('user_id', _me.id);
    _emit();
  }

  @override
  Future<void> markAllNotificationsRead() async {
    await _client.from('demo_notifications').update({'is_read': true})
        .eq('user_id', _me.id).eq('is_read', false);
    _emit();
  }

  @override
  Future<void> registerDevice(String fcmToken, String platform) async {}

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _changes.close();
    _push.close();
  }
}

class _Store {
  const _Store({
    required this.users,
    required this.projects,
    required this.epics,
    required this.tickets,
    required this.incidents,
  });

  final List<User> users;
  final List<Project> projects;
  final List<Epic> epics;
  final List<Ticket> tickets;
  final List<Incident> incidents;
}
