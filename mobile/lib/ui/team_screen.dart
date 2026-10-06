import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../data/repository.dart';
import '../models/models.dart';
import '../providers.dart';
import 'widgets.dart';

class TeamScreen extends ConsumerWidget {
  const TeamScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final team = ref.watch(teamWorkloadProvider);

    return AsyncView<List<MemberLoad>>(
      value: team,
      builder: (members) => RefreshIndicator(
        onRefresh: () => ref.refresh(teamWorkloadProvider.future),
        child: ListView.separated(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          itemCount: members.length,
          separatorBuilder: (_, __) => const SizedBox(height: 10),
          itemBuilder: (_, i) {
            final m = members[i];
            final roleColor = switch (m.user.role) {
              UserRole.admin => c.acc,
              UserRole.groupLeader => c.indigo,
              UserRole.developer => c.green,
            };
            return CsCard(
              child: Row(
                children: [
                  UserAvatar(m.user, size: 42),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(m.user.fullName,
                            style: const TextStyle(
                                fontSize: 14.5, fontWeight: FontWeight.w700)),
                        if (m.user.specialty != null)
                          Text(m.user.specialty!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 12, color: c.mut)),
                        const SizedBox(height: 5),
                        CsChip(
                            label: s('role_${m.user.role.wire}'),
                            color: roleColor,
                            dot: false),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('${m.activeTickets}',
                          style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: m.blocked > 0 ? c.amber : c.ink)),
                      Text('${s('tickets')} ${s('active_t')}',
                          style: TextStyle(fontSize: 10.5, color: c.faint)),
                      if (m.blocked > 0)
                        Text('${m.blocked} ${s('st_blocked').toLowerCase()}',
                            style: TextStyle(
                                fontSize: 10.5,
                                color: c.amber,
                                fontWeight: FontWeight.w700)),
                    ],
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
