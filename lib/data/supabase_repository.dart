/// Repositorio híbrido para la demostración académica de Ficha Avance 02.
///
/// Proyectos, épicas y tickets se leen y escriben en PostgreSQL mediante
/// Supabase. El resto de las pantallas conserva los datos demo para no ampliar
/// el alcance de esta entrega universitaria.
library;

import 'dart:async';

import 'package:flutter/material.dart' show Color;
import 'package:supabase_flutter/supabase_flutter.dart' hide User;

import '../models/models.dart';
import 'demo_repository.dart';
import 'repository.dart';

class SupabaseRepository extends DemoRepository {
  SupabaseRepository({SupabaseClient? client})
      : _client = client ?? Supabase.instance.client {
    _demoChangesSubscription = super.changes.listen(_forwardChange);
  }

  final SupabaseClient _client;
  final _databaseChanges = StreamController<int>.broadcast();
  StreamSubscription<int>? _demoChangesSubscription;
  int _revision = 0;
  User? _currentUser;
  final Map<String, Project> _projectCache = {};
  final Map<String, Epic> _epicCache = {};

  void _forwardChange(int _) => _databaseChanges.add(++_revision);
  void _emitDatabaseChange() => _databaseChanges.add(++_revision);

  @override
  Stream<int> get changes => _databaseChanges.stream;

  @override
  Future<User> login(User user) async {
    _currentUser = await super.login(user);
    return _currentUser!;
  }

  @override
  Future<void> logout() async {
    _currentUser = null;
    await super.logout();
  }

  @override
  Future<List<ProjectSummary>> fetchProjects() async {
    final appRows =
        _rows(await _client.from('applications').select().order('name'));
    final epicRows = _rows(await _client.from('epics').select());
    final ticketRows = _rows(await _client.from('tickets').select());

    final projects = appRows.map(_projectFromRow).toList();
    final epics = epicRows.map(_epicFromRow).toList();
    final tickets = ticketRows.map(_ticketFromRow).toList();

    return [
      for (final project in projects)
        ProjectSummary(
          project: project,
          epicsCount: epics.where((e) => e.projectId == project.id).length,
          ticketsTotal: tickets
              .where((t) => _epicCache[t.epicId]?.projectId == project.id)
              .length,
          ticketsDone: tickets
              .where((t) =>
                  _epicCache[t.epicId]?.projectId == project.id &&
                  t.status == TicketStatus.done)
              .length,
          overdue: tickets
              .where((t) =>
                  _epicCache[t.epicId]?.projectId == project.id && t.isOverdue)
              .length,
        ),
    ];
  }

  @override
  Future<Board> fetchBoard(String projectId) async {
    final projectRows = _rows(
      await _client.from('applications').select().eq('id', projectId).limit(1),
    );
    if (projectRows.isEmpty) {
      throw StateError('No se encontró la aplicación solicitada.');
    }
    final project = _projectFromRow(projectRows.first);
    final epicRows = _rows(
      await _client
          .from('epics')
          .select()
          .eq('application_id', projectId)
          .order('order_index'),
    );
    final epics = epicRows.map(_epicFromRow).toList();
    final epicIds = epics.map((e) => e.id).toList();
    final ticketRows = epicIds.isEmpty
        ? const <Map<String, dynamic>>[]
        : _rows(await _client
            .from('tickets')
            .select()
            .inFilter('epic_id', epicIds)
            .order('number'));
    final tickets = ticketRows.map(_ticketFromRow).toList();

    return Board(
      project: project,
      epics: [
        for (final epic in epics)
          EpicBoard(
            epic: epic,
            tickets:
                tickets.where((ticket) => ticket.epicId == epic.id).toList(),
          ),
      ],
    );
  }

  @override
  Future<TicketDetail> fetchTicketDetail(String ticketId) async {
    final ticketRows = _rows(
      await _client.from('tickets').select().eq('id', ticketId).limit(1),
    );
    if (ticketRows.isEmpty) throw StateError('No se encontró el ticket.');
    final ticket = _ticketFromRow(ticketRows.first);

    final epicRows = _rows(
      await _client.from('epics').select().eq('id', ticket.epicId).limit(1),
    );
    final epic = _epicFromRow(epicRows.first);
    final projectRows = _rows(await _client
        .from('applications')
        .select()
        .eq('id', epic.projectId)
        .limit(1));
    final project = _projectFromRow(projectRows.first);
    final me = _currentUser;
    if (me == null) throw StateError('Debes iniciar sesión.');

    return TicketDetail(
      ticket: ticket,
      epic: epic,
      project: project,
      assignee: userById(ticket.assigneeId),
      createdBy: userById(ticket.createdById),
      permissions: TicketPermissions.compute(
        role: me.role,
        userId: me.id,
        status: ticket.status,
        assigneeId: ticket.assigneeId,
      ),
    );
  }

  @override
  Future<void> createTicket({
    required String epicId,
    required String title,
    required TicketPriority priority,
    String? assigneeId,
  }) async {
    final cleanTitle = title.trim();
    if (cleanTitle.length < 5 || cleanTitle.length > 120) {
      throw ArgumentError('El título debe tener entre 5 y 120 caracteres.');
    }
    final me = _currentUser;
    if (me == null || !me.isLead) {
      throw StateError('Sólo un administrador o líder puede crear tickets.');
    }

    await _client.from('tickets').insert({
      'epic_id': epicId,
      'title': cleanTitle,
      'description': cleanTitle,
      'status': TicketStatus.todo.wire,
      'priority': priority.wire,
      'assignee_id': assigneeId,
      'created_by_id': me.id,
      'due_date': DateTime.now().add(const Duration(days: 7)).toIso8601String(),
    });
    _emitDatabaseChange();
  }

  @override
  Project? projectOfTicket(Ticket t) {
    final epic = _epicCache[t.epicId];
    return epic == null ? null : _projectCache[epic.projectId];
  }

  List<Map<String, dynamic>> _rows(dynamic value) =>
      List<Map<String, dynamic>>.from(value as List);

  Project _projectFromRow(Map<String, dynamic> row) {
    final project = Project(
      id: row['id'] as String,
      name: row['name'] as String,
      code: row['code'] as String,
      color: _parseColor(row['color_hex'] as String?),
    );
    _projectCache[project.id] = project;
    return project;
  }

  Epic _epicFromRow(Map<String, dynamic> row) {
    final epic = Epic(
      id: row['id'] as String,
      projectId: row['application_id'] as String,
      name: row['name'] as String,
      orderIndex: (row['order_index'] as num?)?.toInt() ?? 0,
    );
    _epicCache[epic.id] = epic;
    return epic;
  }

  Ticket _ticketFromRow(Map<String, dynamic> row) => Ticket(
        id: row['id'].toString(),
        number: (row['number'] as num).toInt(),
        epicId: row['epic_id'] as String,
        title: row['title'] as String,
        description: (row['description'] as String?) ?? '',
        status: TicketStatusWire.parse((row['status'] as String?) ?? 'TODO'),
        priority:
            TicketPriorityWire.parse((row['priority'] as String?) ?? 'MEDIUM'),
        assigneeId: row['assignee_id'] as String?,
        createdById: row['created_by_id'] as String?,
        dueDate: DateTime.tryParse((row['due_date'] as String?) ?? ''),
      );

  Color _parseColor(String? hex) {
    final normalized = (hex ?? '#4C8DFF').replaceFirst('#', '');
    final value = int.tryParse('FF$normalized', radix: 16) ?? 0xFF4C8DFF;
    return Color(value);
  }

  @override
  void dispose() {
    _demoChangesSubscription?.cancel();
    _databaseChanges.close();
    super.dispose();
  }
}
