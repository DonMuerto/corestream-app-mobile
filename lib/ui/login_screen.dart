import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config.dart';
import '../core/theme.dart';
import '../data/demo_repository.dart';
import '../providers.dart';
import 'widgets.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isSubmitting = false;
  bool _obscurePassword = true;
  String? _credentialsError;

  static final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    if (!AppConfig.isDemo) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                s('login_api_unavailable'),
                textAlign: TextAlign.center,
                style:
                    const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ),
      );
    }

    final c = cs(context);
    final demoEmails = DemoRepository.demoEmailByUserId.values.join(' · ');

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: (constraints.maxHeight - 48)
                    .clamp(0.0, double.infinity)
                    .toDouble(),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 8),
                  Center(
                    child: Container(
                      width: 60,
                      height: 60,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF4C8DFF), Color(0xFF2FBF71)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(19),
                        boxShadow: [
                          BoxShadow(
                            color:
                                const Color(0xFF4C8DFF).withValues(alpha: 0.35),
                            blurRadius: 22,
                            offset: const Offset(0, 9),
                          ),
                        ],
                      ),
                      child: const Text(
                        'C',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 27,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    s('app_name'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 27,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    s('login_sub'),
                    textAlign: TextAlign.center,
                    style:
                        TextStyle(color: c.mut, fontSize: 13.5, height: 1.45),
                  ),
                  const SizedBox(height: 18),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 13, vertical: 11),
                    decoration: BoxDecoration(
                      color: c.accSoft,
                      borderRadius: BorderRadius.circular(13),
                      border: Border.all(color: c.acc.withValues(alpha: 0.28)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.science_outlined, color: c.acc, size: 19),
                        const SizedBox(width: 9),
                        Expanded(
                          child: Text(
                            s('login_demo_banner'),
                            style: TextStyle(
                                color: c.ink, fontSize: 12.5, height: 1.4),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  Form(
                    key: _formKey,
                    autovalidateMode: AutovalidateMode.onUserInteraction,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        TextFormField(
                          key: const Key('login.email'),
                          controller: _emailController,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autofillHints: const [
                            AutofillHints.username,
                            AutofillHints.email
                          ],
                          autocorrect: false,
                          enableSuggestions: false,
                          decoration: InputDecoration(
                            labelText: s('login_email'),
                            prefixIcon: const Icon(Icons.mail_outline),
                            filled: true,
                            fillColor: c.surface,
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(13),
                            ),
                          ),
                          validator: _validateEmail,
                          onChanged: _clearCredentialsError,
                        ),
                        const SizedBox(height: 13),
                        TextFormField(
                          key: const Key('login.password'),
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          textInputAction: TextInputAction.done,
                          autofillHints: const [AutofillHints.password],
                          autocorrect: false,
                          enableSuggestions: false,
                          decoration: InputDecoration(
                            labelText: s('login_password'),
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              tooltip: s('login_toggle_password'),
                              onPressed: () => setState(
                                () => _obscurePassword = !_obscurePassword,
                              ),
                              icon: Icon(
                                _obscurePassword
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                              ),
                            ),
                            filled: true,
                            fillColor: c.surface,
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(13),
                            ),
                          ),
                          validator: (value) => value == null || value.isEmpty
                              ? s('login_password_required')
                              : null,
                          onChanged: _clearCredentialsError,
                          onFieldSubmitted: (_) => _submit(),
                        ),
                      ],
                    ),
                  ),
                  if (_credentialsError != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      key: const Key('login.credentialError'),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 10),
                      decoration: BoxDecoration(
                        color: c.redSoft,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.error_outline, color: c.red, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _credentialsError!,
                              style: TextStyle(color: c.red, fontSize: 12.5),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 17),
                  SizedBox(
                    height: 52,
                    child: FilledButton(
                      key: const Key('login.submit'),
                      onPressed: _isSubmitting ? null : _submit,
                      style: FilledButton.styleFrom(
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: _isSubmitting
                          ? Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Text(s('login_loading')),
                              ],
                            )
                          : Text(
                              s('login_submit'),
                              style:
                                  const TextStyle(fontWeight: FontWeight.w700),
                            ),
                    ),
                  ),
                  const SizedBox(height: 15),
                  CsCard(
                    padding: const EdgeInsets.all(13),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.key_outlined, color: c.acc, size: 17),
                            const SizedBox(width: 7),
                            Text(
                              s('login_demo_accounts_title'),
                              style: const TextStyle(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 7),
                        SelectableText(
                          demoEmails,
                          style: TextStyle(
                              color: c.mut, fontSize: 11.5, height: 1.45),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${s('login_demo_password')}: ${DemoRepository.demoPassword}',
                          style: TextStyle(color: c.mut, fontSize: 11.5),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    s('demo_note'),
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11.5, color: c.faint),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  String? _validateEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty) return ref.read(stringsProvider)('login_email_required');
    if (!_emailPattern.hasMatch(email)) {
      return ref.read(stringsProvider)('login_email_invalid');
    }
    return null;
  }

  void _clearCredentialsError(String _) {
    if (_credentialsError != null) {
      setState(() => _credentialsError = null);
    }
  }

  Future<void> _submit() async {
    if (_isSubmitting || !(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _isSubmitting = true;
      _credentialsError = null;
    });

    try {
      final success = await ref
          .read(authProvider.notifier)
          .loginWithDemoCredentials(
              _emailController.text, _passwordController.text);
      if (mounted && !success) {
        setState(() => _credentialsError =
            ref.read(stringsProvider)('login_invalid_credentials'));
      }
    } catch (_) {
      if (mounted) {
        setState(() =>
            _credentialsError = ref.read(stringsProvider)('login_failed'));
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }
}
