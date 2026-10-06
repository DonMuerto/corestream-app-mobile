import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import 'widgets.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final options = AppConfig.isDemo ? ref.watch(loginOptionsProvider) : null;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
            child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 56),
              Container(
                width: 64,
                height: 64,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF4C8DFF), Color(0xFF2FBF71)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                        color: const Color(0xFF4C8DFF).withOpacity(0.45),
                        blurRadius: 26,
                        offset: const Offset(0, 12)),
                  ],
                ),
                child: const Text('C',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w800)),
              ),
              const SizedBox(height: 16),
              Text(s('app_name'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 27,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.5)),
              const SizedBox(height: 8),
              Text(
                  AppConfig.isDemo
                      ? s('login_sub')
                      : 'Conéctate con tu cuenta de CoreStream App',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: c.mut, fontSize: 13.5, height: 1.5)),
              const SizedBox(height: 26),
              if (!AppConfig.isDemo) const _CredentialForm(),
              if (AppConfig.isDemo)
                AsyncView<List<User>>(
                  value: options!,
                  builder: (users) => Column(
                    children: [
                      for (final u in users) ...[
                        _RoleCard(
                            user: u,
                            onTap: () =>
                                ref.read(authProvider.notifier).loginAs(u)),
                        const SizedBox(height: 10),
                      ],
                    ],
                  ),
                ),
              const SizedBox(height: 48),
              Text(
                AppConfig.isDemo ? s('demo_note') : s('api_mode'),
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 11.5, color: c.faint),
              ),
              const SizedBox(height: 12),
            ],
          ),
        )),
      ),
    );
  }
}

class _CredentialForm extends ConsumerStatefulWidget {
  const _CredentialForm();

  @override
  ConsumerState<_CredentialForm> createState() => _CredentialFormState();
}

class _CredentialFormState extends ConsumerState<_CredentialForm> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _login() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(authProvider.notifier).loginWithCredentials(
            _email.text.trim(),
            _password.text,
          );
    } catch (_) {
      if (mounted)
        setState(() {
          _error =
              'No se pudo iniciar sesión. Revisa tus credenciales y la conexión.';
        });
    } finally {
      if (mounted)
        setState(() {
          _busy = false;
        });
    }
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(children: [
        TextField(
            controller: _email,
            enabled: !_busy,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.username],
            decoration: const InputDecoration(
                labelText: 'Correo', prefixIcon: Icon(Icons.email_outlined))),
        const SizedBox(height: 12),
        TextField(
            controller: _password,
            enabled: !_busy,
            obscureText: true,
            autofillHints: const [AutofillHints.password],
            onSubmitted: (_) => _login(),
            decoration: const InputDecoration(
                labelText: 'Contraseña', prefixIcon: Icon(Icons.lock_outline))),
        if (_error != null)
          Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_error!,
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 18),
        SizedBox(
            width: double.infinity,
            child: FilledButton(
                onPressed: _busy ? null : _login,
                child: Text(_busy ? 'Conectando…' : 'Iniciar sesión'))),
      ]);
}

final loginOptionsProvider = FutureProvider<List<User>>(
  (ref) => ref.watch(repositoryProvider).loginOptions(),
);

class _RoleCard extends ConsumerWidget {
  const _RoleCard({required this.user, required this.onTap});

  final User user;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = cs(context);
    final s = ref.watch(stringsProvider);
    final roleColor = switch (user.role) {
      UserRole.admin => c.acc,
      UserRole.groupLeader => c.indigo,
      UserRole.developer => c.green,
    };
    return CsCard(
      onTap: onTap,
      child: Row(
        children: [
          UserAvatar(user, size: 46),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(user.fullName,
                    style: const TextStyle(
                        fontSize: 15.5, fontWeight: FontWeight.w700)),
                if (user.specialty != null)
                  Text(user.specialty!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 12.5, color: c.mut)),
                const SizedBox(height: 5),
                CsChip(
                    label: s('role_${user.role.wire}'),
                    color: roleColor,
                    dot: false),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: c.faint),
        ],
      ),
    );
  }
}
