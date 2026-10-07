import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/i18n.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../providers.dart';
import 'ticket_sheets.dart';
import 'widgets.dart';

class TicketDetailScreen extends ConsumerWidget {
  const TicketDetailScreen({super.key, required this.ticketId});
  final String ticketId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(ticketDetailProvider(ticketId));
    return Scaffold(
      appBar: AppBar(
        title: Text(
            detail.valueOrNull != null && detail.valueOrNull!.ticket.number > 0
                ? 'T-${detail.valueOrNull!.ticket.number}'
                : ''),
      ),
      body: AsyncView<TicketDetail>(
        value: detail,
        builder: (d) => _TicketDetailBody(d),
      ),
    );
  }
}

class _TicketDetailBody extends ConsumerStatefulWidget {
  const _TicketDetailBody(this.d);
  final TicketDetail d;

  @override
  ConsumerState<_TicketDetailBody> createState() => _TicketDetailBodyState();
}

class _TicketDetailBodyState extends ConsumerState<_TicketDetailBody> {
  Timer? _tick;
  @override
  void initState() {
    super.initState();
    // Presentation tick only; never refresh providers or make HTTP requests.
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.d;
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final lang = ref.watch(langProvider);
    final t = d.ticket;
    final p = d.permissions;
    TicketEvent? lastQuestion;
    for (final e in t.events.reversed) {
      if (e.type == 'QUESTION') {
        lastQuestion = e;
        break;
      }
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 30),
      children: [
        // breadcrumb
        Text('${d.project.name}  ›  ${d.epic.name}',
            style: TextStyle(
                fontSize: 11.5, fontWeight: FontWeight.w600, color: c.faint)),
        const SizedBox(height: 6),
        Text(t.title,
            style: const TextStyle(
                fontSize: 20, fontWeight: FontWeight.w700, height: 1.3)),
        const SizedBox(height: 10),
        Wrap(
          spacing: 7,
          runSpacing: 6,
          children: [
            StatusChip(t.status),
            if (t.archivedAt != null)
              CsChip(label: s('archived'), color: c.gray, dot: false),
            CsChip(
              label: s('p_${t.priority.wire}'),
              color: priorityColor(context, t.priority),
            ),
            if (t.isOverdue)
              CsChip(label: '⚠ ${s('overdue')}', color: c.red, dot: false),
          ],
        ),
        const SizedBox(height: 12),

        if (t.archivedAt == null &&
            (t.status == TicketStatus.inProgress ||
                t.status == TicketStatus.blocked))
          _TimerCard(ticket: t),

        if (t.status == TicketStatus.blocked && lastQuestion != null) ...[
          const SizedBox(height: 10),
          _QuoteBox(
            text: lastQuestion.text ?? '',
            author: ref
                .watch(repositoryProvider)
                .userById(lastQuestion.userId)
                ?.fullName,
            color: c.amber,
          ),
        ],

        const SizedBox(height: 12),
        CsCard(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: Column(
            children: [
              _Kv(
                s('assignee'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    UserAvatar(d.assignee, size: 22),
                    const SizedBox(width: 7),
                    Text(d.assignee?.fullName ?? s('unassigned'),
                        style: TextStyle(
                            fontWeight: FontWeight.w600,
                            color: d.assignee == null ? c.faint : c.ink)),
                  ],
                ),
              ),
              _Kv(s('due'),
                  value: t.dueDate == null ? '—' : shortDate(lang, t.dueDate!),
                  valueColor: t.isOverdue ? c.red : null),
              _Kv(s('time_spent'), value: fmtTimer(t.liveSpentSeconds)),
              if (t.liveBlockedSeconds > 0)
                _Kv(s('time_blocked'),
                    value: fmtTimer(t.liveBlockedSeconds), valueColor: c.amber),
              if (t.prLink != null)
                _Kv('PR',
                    value: t.prLink!.replaceFirst('https://', ''),
                    valueColor: c.acc),
            ],
          ),
        ),

        SectionLabel(s('description')),
        CsCard(
          child: Text(
              t.description.isEmpty ? s('empty_description') : t.description,
              style: TextStyle(fontSize: 13.5, height: 1.55, color: c.mut)),
        ),

        if (t.subtasks.isNotEmpty || p.canEditSubtasks) ...[
          SectionLabel(
              '${s('subtasks')} · ${t.subtasksDone}/${t.subtasks.length}'),
          CsCard(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
            child: Column(
              children: [
                for (final sub in t.subtasks.where((x) => x.title.isNotEmpty))
                  CheckboxListTile(
                    dense: true,
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 6),
                    value: sub.done,
                    onChanged: p.canEditSubtasks
                        ? (v) => runTicketAction(
                            context,
                            ref,
                            () => ref
                                .read(repositoryProvider)
                                .toggleSubtask(t.id, sub.id, v ?? false))
                        : null,
                    title: Text(
                      sub.title,
                      style: TextStyle(
                        fontSize: 13.5,
                        decoration:
                            sub.done ? TextDecoration.lineThrough : null,
                        color: sub.done ? c.faint : c.ink,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],

        if (t.events.isNotEmpty) ...[
          SectionLabel(s('activity')),
          CsCard(
            child: Column(
              children: [
                for (final e in t.events.reversed) _EventRow(event: e),
              ],
            ),
          ),
        ],

        const SizedBox(height: 18),
        if (p.canEditSubtasks)
          TextButton.icon(
              onPressed: () => showSubtaskSheet(context, ref, t),
              icon: const Icon(Icons.add),
              label: Text(s('new_subtask'))),
        _Actions(detail: d),
      ],
    );
  }
}

// ------------------------------------------------------------------ acciones

class _Actions extends ConsumerWidget {
  const _Actions({required this.detail});
  final TicketDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final c = cs(context);
    final t = detail.ticket;
    final p = detail.permissions;
    final repo = ref.read(repositoryProvider);

    final children = <Widget>[];

    if (p.canPause || p.canResumeTimer) {
      children.add(OutlinedButton.icon(
        icon: Icon(p.canPause ? Icons.pause : Icons.play_arrow),
        label: Text(s(p.canPause ? 'pause_work' : 'resume_work')),
        onPressed: () => runTicketAction(
            context,
            ref,
            () => p.canPause
                ? repo.pauseTicket(t.id)
                : repo.resumeTicketTimer(t.id)),
      ));
    }
    if (p.canEdit && t.archivedAt == null) {
      children.add(OutlinedButton.icon(
          icon: const Icon(Icons.drive_file_move_outline),
          label: Text(s('move_ticket')),
          onPressed: () => showMoveSheet(context, ref, detail)));
    }
    if (p.canArchive) {
      children.add(OutlinedButton.icon(
          icon: const Icon(Icons.archive_outlined),
          label: Text(s('archive')),
          onPressed: () => showArchiveConfirmation(context, ref, t)));
    }
    if (p.canRestore) {
      children.add(FilledButton.icon(
          icon: const Icon(Icons.unarchive_outlined),
          label: Text(s('restore')),
          onPressed: () =>
              runTicketAction(context, ref, () => repo.restoreTicket(t.id))));
    }

    if (p.canAssign) {
      children.add(FilledButton.icon(
        icon: const Icon(Icons.people_outline),
        label: Text(t.assigneeId == null ? s('assign') : s('reassign')),
        onPressed: () => showAssignSheet(context, ref, t),
      ));
    }
    if (p.canStart) {
      children.add(FilledButton.icon(
        icon: const Icon(Icons.play_arrow),
        label: Text(s('start')),
        onPressed: () =>
            runTicketAction(context, ref, () => repo.startTicket(t.id)),
      ));
    }
    if (p.canComplete) {
      children.add(FilledButton.icon(
        style: FilledButton.styleFrom(backgroundColor: c.green),
        icon: const Icon(Icons.check),
        label: Text(s('complete')),
        onPressed: () => showCompleteSheet(context, ref, t),
      ));
    }
    if (p.canQuestion || p.canRedirect) {
      children.add(Row(
        children: [
          if (p.canQuestion)
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(
                    backgroundColor: c.amber, foregroundColor: Colors.black87),
                icon: const Icon(Icons.help_outline),
                label: Text(s('raise_q')),
                onPressed: () => showQuestionSheet(context, ref, t),
              ),
            ),
          if (p.canQuestion && p.canRedirect) const SizedBox(width: 10),
          if (p.canRedirect)
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: c.indigo),
                icon: const Icon(Icons.swap_horiz),
                label: Text(s('redirect')),
                onPressed: () => showRedirectSheet(context, ref, t),
              ),
            ),
        ],
      ));
    }
    if (p.canResolveQuestion) {
      children.add(FilledButton.icon(
        style: FilledButton.styleFrom(backgroundColor: c.green),
        icon: const Icon(Icons.play_arrow),
        label: Text(s('resume')),
        onPressed: () => showResumeSheet(context, ref, t),
      ));
    }

    if (children.isEmpty && t.status != TicketStatus.done) {
      return EmptyState(s('view_only'), icon: Icons.visibility_outlined);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) const SizedBox(height: 10),
          children[i],
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------- timer

class _TimerCard extends ConsumerStatefulWidget {
  const _TimerCard({required this.ticket});
  final Ticket ticket;

  @override
  ConsumerState<_TimerCard> createState() => _TimerCardState();
}

class _TimerCardState extends ConsumerState<_TimerCard> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted &&
          (widget.ticket.runningSince != null ||
              widget.ticket.blockedSince != null)) {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final t = widget.ticket;
    final blocked = t.status == TicketStatus.blocked;
    final color = blocked ? c.amber : c.green;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: blocked ? c.amberSoft : c.raised,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: blocked ? c.amber : c.line.withOpacity(0.7)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                    blocked
                        ? s('blocked_waiting')
                        : t.runningSince == null
                            ? s('work_paused')
                            : s('time_spent'),
                    style: TextStyle(fontSize: 11.5, color: c.mut)),
                const SizedBox(height: 2),
                Text(
                    fmtTimer(
                        blocked ? t.liveBlockedSeconds : t.liveSpentSeconds),
                    style: TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.w700,
                        color: color,
                        fontFeatures: const [FontFeature.tabularFigures()])),
              ],
            ),
          ),
          Icon(blocked ? Icons.pause_circle_outline : Icons.timer_outlined,
              color: color),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ helpers

class _Kv extends StatelessWidget {
  const _Kv(this.label, {this.value, this.valueColor, this.trailing});

  final String label;
  final String? value;
  final Color? valueColor;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = cs(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          Text(label, style: TextStyle(fontSize: 13.5, color: c.mut)),
          const Spacer(),
          trailing ??
              Text(value ?? '',
                  style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: valueColor ?? c.ink)),
        ],
      ),
    );
  }
}

class _QuoteBox extends StatelessWidget {
  const _QuoteBox({required this.text, this.author, required this.color});

  final String text;
  final String? author;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: const BorderRadius.horizontal(right: Radius.circular(10)),
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Text(
        author == null ? '“$text”' : '“$text” — $author',
        style: TextStyle(fontSize: 12.5, color: color, height: 1.45),
      ),
    );
  }
}

class _EventRow extends ConsumerWidget {
  const _EventRow({required this.event});
  final TicketEvent event;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final repo = ref.watch(repositoryProvider);
    final user = repo.userById(event.userId);

    final (icon, color, label) = switch (event.type) {
      'CREATED' => (Icons.add_circle_outline, c.green, s('ev_created')),
      'ASSIGNED' => (
          Icons.assignment_ind_outlined,
          c.acc,
          '${s('ev_assigned_to')} ${repo.userById(event.toUserId)?.fullName ?? ''}'
        ),
      'STATUS' => (
          Icons.swap_vert,
          c.gray,
          '${s('s_${(event.fromStatus ?? TicketStatus.todo).wire}')} → ${s('s_${(event.toStatus ?? TicketStatus.todo).wire}')}'
        ),
      'QUESTION' => (Icons.help_outline, c.amber, s('n_QUESTION')),
      'RESOLVED' => (Icons.check_circle_outline, c.green, s('ev_resolved')),
      'REDIRECTED' => (
          Icons.swap_horiz,
          c.indigo,
          '${s('ev_redirected_to')} ${repo.userById(event.toUserId)?.fullName ?? ''}'
        ),
      'COMPLETED' => (Icons.celebration_outlined, c.green, s('n_COMPLETION')),
      'ARCHIVED' => (Icons.archive_outlined, c.gray, s('ev_archived')),
      'RESTORED' => (Icons.unarchive_outlined, c.green, s('ev_restored')),
      'TIMER_START' => (Icons.play_arrow, c.green, s('ev_timer_start')),
      'TIMER_PAUSE' => (Icons.pause, c.amber, s('ev_timer_pause')),
      'MOVED' => (Icons.drive_file_move_outline, c.acc, s('ev_moved')),
      'SUBTASK_CREATED' => (Icons.add_task, c.acc, s('ev_subtask_created')),
      'SUBTASK_COMPLETED' => (
          Icons.task_alt,
          c.green,
          s('ev_subtask_completed')
        ),
      _ => (Icons.chat_bubble_outline, c.gray, ''),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
                color: color.withOpacity(0.14), shape: BoxShape.circle),
            child: Icon(icon, size: 15, color: color),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(children: [
                    TextSpan(
                        text: user?.fullName ?? '¿?',
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    TextSpan(text: '  $label', style: TextStyle(color: c.mut)),
                  ]),
                  style: const TextStyle(fontSize: 13, height: 1.4),
                ),
                if (event.text != null && event.text!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 5),
                    child: _QuoteBox(text: event.text!, color: c.gray),
                  ),
                const SizedBox(height: 2),
                Text(relativeTime(s, event.ts),
                    style: TextStyle(fontSize: 11.5, color: c.faint)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
