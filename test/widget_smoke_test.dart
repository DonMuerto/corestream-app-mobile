// Smoke tests del login demo, navegación por rol y cierre de sesión.

import 'package:flutter/material.dart' show Key, TextFormField;
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:corestream_mobile/data/demo_repository.dart';
import 'package:corestream_mobile/main.dart';
import 'package:corestream_mobile/models/models.dart';
import 'package:corestream_mobile/providers.dart';

const _emailField = Key('login.email');
const _passwordField = Key('login.password');
const _submitButton = Key('login.submit');

Future<ProviderContainer> _pumpDemoApp(WidgetTester tester) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(overrides: [
    prefsProvider.overrideWithValue(prefs),
  ]);
  addTearDown(container.dispose);

  // Evita temporizadores pendientes durante los tests de widgets.
  final repo = container.read(repositoryProvider) as DemoRepository;
  repo.simulationEnabled = false;

  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const CoreStreamApp(),
  ));
  await tester.pumpAndSettle();
  return container;
}

void main() {
  testWidgets(
      'las tres cuentas abren su dashboard y logout limpia el formulario',
      (tester) async {
    final container = await _pumpDemoApp(tester);

    expect(find.text('CoreStream'), findsOneWidget);
    expect(find.textContaining('DEMO'), findsOneWidget);

    const accounts = [
      (
        email: 'ana@demo.corestream.local',
        firstName: 'Ana',
        role: UserRole.admin
      ),
      (
        email: 'luis@demo.corestream.local',
        firstName: 'Luis',
        role: UserRole.groupLeader
      ),
      (
        email: 'diego@demo.corestream.local',
        firstName: 'Diego',
        role: UserRole.developer
      ),
    ];

    for (final account in accounts) {
      await tester.enterText(find.byKey(_emailField), account.email);
      await tester.enterText(
          find.byKey(_passwordField), DemoRepository.demoPassword);
      await tester.tap(find.byKey(_submitButton));
      await tester.pumpAndSettle();

      expect(find.textContaining('Hola, ${account.firstName}'), findsOneWidget);
      expect(container.read(authProvider)?.role, account.role);
      expect(find.text('Portal Clientes'), findsWidgets);

      await container.read(authProvider.notifier).logout();
      await tester.pumpAndSettle();
      expect(find.byKey(_emailField), findsOneWidget);
      expect(
        tester.widget<TextFormField>(find.byKey(_emailField)).controller?.text,
        isEmpty,
      );
      expect(
        tester
            .widget<TextFormField>(find.byKey(_passwordField))
            .controller
            ?.text,
        isEmpty,
      );
    }
  });

  testWidgets('valida campos, correo y credenciales sin iniciar sesión',
      (tester) async {
    final container = await _pumpDemoApp(tester);

    await tester.ensureVisible(find.byKey(_submitButton));
    await tester.tap(find.byKey(_submitButton));
    await tester.pumpAndSettle();
    expect(find.text('Ingresa tu correo electrónico.'), findsOneWidget);
    expect(find.text('Ingresa tu contraseña.'), findsOneWidget);
    expect(container.read(authProvider), isNull);

    await tester.enterText(find.byKey(_emailField), 'no-es-un-correo');
    await tester.enterText(
        find.byKey(_passwordField), DemoRepository.demoPassword);
    await tester.ensureVisible(find.byKey(_submitButton));
    await tester.tap(find.byKey(_submitButton));
    await tester.pumpAndSettle();
    expect(find.text('Ingresa un correo electrónico válido.'), findsOneWidget);
    expect(container.read(authProvider), isNull);

    await tester.enterText(
        find.byKey(_emailField), 'desconocido@demo.corestream.local');
    await tester.ensureVisible(find.byKey(_submitButton));
    await tester.tap(find.byKey(_submitButton));
    await tester.pumpAndSettle();
    expect(find.text('Correo o contraseña demo incorrectos'), findsOneWidget);
    expect(container.read(authProvider), isNull);

    await tester.enterText(
        find.byKey(_emailField), 'ana@demo.corestream.local');
    await tester.pump();
    expect(find.text('Correo o contraseña demo incorrectos'), findsNothing);

    await tester.enterText(find.byKey(_passwordField), 'incorrecta');
    await tester.ensureVisible(find.byKey(_submitButton));
    await tester.tap(find.byKey(_submitButton));
    await tester.pumpAndSettle();
    expect(find.text('Correo o contraseña demo incorrectos'), findsOneWidget);
    expect(container.read(authProvider), isNull);
  });
}
