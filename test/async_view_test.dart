import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:corestream_mobile/providers.dart';
import 'package:corestream_mobile/ui/widgets.dart';

void main() {
  testWidgets('conserva la pantalla durante una recarga y un error temporal',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    Widget app(AsyncValue<int> value) => ProviderScope(
          overrides: [prefsProvider.overrideWithValue(prefs)],
          child: MaterialApp(
            home: Scaffold(
              body: AsyncView<int>(
                value: value,
                builder: (number) => Text('Dato $number'),
              ),
            ),
          ),
        );

    await tester.pumpWidget(app(const AsyncData(42)));
    expect(find.text('Dato 42'), findsOneWidget);

    await tester.pumpWidget(app(
      const AsyncLoading<int>()
          .copyWithPrevious(const AsyncData(42), isRefresh: false),
    ));
    expect(find.text('Dato 42'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);

    await tester.pumpWidget(app(
      AsyncError<int>(StateError('Sin conexión'), StackTrace.current)
          .copyWithPrevious(const AsyncData(42)),
    ));
    expect(find.text('Dato 42'), findsOneWidget);
  });
}
