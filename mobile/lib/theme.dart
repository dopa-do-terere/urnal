import 'package:flutter/material.dart';

/// Cores próprias do app, acessíveis com `context.colors`.
@immutable
class FinanceColors extends ThemeExtension<FinanceColors> {
  const FinanceColors({
    required this.background,
    required this.card,
    required this.ink,
    required this.ink2,
    required this.muted,
    required this.line,
    required this.field,
    required this.positive,
    required this.negative,
    required this.warning,
    required this.warningBg,
    required this.focus,
  });

  final Color background;
  final Color card;
  final Color ink;
  final Color ink2;
  final Color muted;
  final Color line;
  final Color field;
  final Color positive;
  final Color negative;
  final Color warning;
  final Color warningBg;
  final Color focus;

  static const brand = Color(0xFF0F3D34);
  static const brand2 = Color(0xFF155E4F);
  static const lime = Color(0xFFD9F99D);

  static const light = FinanceColors(
    background: Color(0xFFF4F3EE),
    card: Color(0xFFFFFFFF),
    ink: Color(0xFF17201D),
    ink2: Color(0xFF3B4541),
    muted: Color(0xFF737B77),
    line: Color(0xFFE7E5DD),
    field: Color(0xFFF7F6F2),
    positive: Color(0xFF12805C),
    negative: Color(0xFFB42318),
    warning: Color(0xFF9A5B07),
    warningBg: Color(0xFFFBF3E2),
    focus: Color(0xFF2F8F76),
  );

  static const dark = FinanceColors(
    background: Color(0xFF0C100F),
    card: Color(0xFF141A18),
    ink: Color(0xFFE9EEEC),
    ink2: Color(0xFFC3CBC7),
    muted: Color(0xFF8A9490),
    line: Color(0xFF232B28),
    field: Color(0xFF101513),
    positive: Color(0xFF5FD3A5),
    negative: Color(0xFFFF8A7A),
    warning: Color(0xFFF2C063),
    warningBg: Color(0xFF2A2110),
    focus: Color(0xFF5FD3A5),
  );

  @override
  FinanceColors copyWith() => this;

  @override
  FinanceColors lerp(ThemeExtension<FinanceColors>? other, double t) {
    if (other is! FinanceColors) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return FinanceColors(
      background: l(background, other.background),
      card: l(card, other.card),
      ink: l(ink, other.ink),
      ink2: l(ink2, other.ink2),
      muted: l(muted, other.muted),
      line: l(line, other.line),
      field: l(field, other.field),
      positive: l(positive, other.positive),
      negative: l(negative, other.negative),
      warning: l(warning, other.warning),
      warningBg: l(warningBg, other.warningBg),
      focus: l(focus, other.focus),
    );
  }
}

extension FinanceTheme on BuildContext {
  FinanceColors get colors => Theme.of(this).extension<FinanceColors>()!;
}

/// Fonte serifada dos números grandes e títulos.
TextStyle serif({double size = 22, FontWeight weight = FontWeight.w500, Color? color, double? height}) {
  return TextStyle(
    fontFamily: 'Fraunces',
    fontSize: size,
    fontWeight: weight,
    color: color,
    height: height,
    letterSpacing: -0.4,
    fontFeatures: const [FontFeature.tabularFigures()],
  );
}

ThemeData buildTheme(Brightness brightness) {
  final c = brightness == Brightness.dark ? FinanceColors.dark : FinanceColors.light;
  final scheme = ColorScheme(
    brightness: brightness,
    primary: brightness == Brightness.dark ? FinanceColors.lime : FinanceColors.brand,
    onPrimary: brightness == Brightness.dark ? FinanceColors.brand : const Color(0xFFF2FBE4),
    secondary: c.focus,
    onSecondary: Colors.white,
    error: c.negative,
    onError: Colors.white,
    surface: c.card,
    onSurface: c.ink,
    surfaceContainerHighest: c.field,
    outline: c.line,
    outlineVariant: c.line,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: brightness, fontFamily: 'Inter');
  final text = base.textTheme.apply(fontFamily: 'Inter', bodyColor: c.ink, displayColor: c.ink);
  final fieldBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: BorderSide(color: c.line),
  );

  return base.copyWith(
    scaffoldBackgroundColor: c.background,
    textTheme: text,
    extensions: [c],
    splashFactory: InkSparkle.splashFactory,
    appBarTheme: AppBarTheme(
      backgroundColor: c.background,
      surfaceTintColor: Colors.transparent,
      foregroundColor: c.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: serif(size: 22, weight: FontWeight.w600, color: c.ink),
    ),
    cardTheme: CardThemeData(
      color: c.card,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: c.line),
      ),
    ),
    dividerTheme: DividerThemeData(color: c.line, space: 1, thickness: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: c.field,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: fieldBorder,
      enabledBorder: fieldBorder,
      focusedBorder: fieldBorder.copyWith(borderSide: BorderSide(color: c.focus, width: 1.5)),
      errorBorder: fieldBorder.copyWith(borderSide: BorderSide(color: c.negative)),
      labelStyle: TextStyle(color: c.muted),
      hintStyle: TextStyle(color: c.muted),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 48),
        foregroundColor: c.ink,
        side: BorderSide(color: c.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 14),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: brightness == Brightness.dark ? c.positive : FinanceColors.brand2,
        textStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: c.card,
      surfaceTintColor: Colors.transparent,
      indicatorColor: brightness == Brightness.dark ? const Color(0xFF1E3A33) : const Color(0xFFE3F2DA),
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontFamily: 'Inter',
          fontSize: 12,
          fontWeight: states.contains(WidgetState.selected) ? FontWeight.w600 : FontWeight.w500,
          color: states.contains(WidgetState.selected) ? c.ink : c.muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(color: states.contains(WidgetState.selected) ? c.ink : c.muted),
      ),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: c.card,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      dragHandleColor: c.line,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: c.ink,
      contentTextStyle: TextStyle(fontFamily: 'Inter', color: c.background, fontSize: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        backgroundColor: c.field,
        selectedBackgroundColor: c.card,
        selectedForegroundColor: c.ink,
        foregroundColor: c.muted,
        side: BorderSide(color: c.line),
        textStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 13),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: c.card,
      selectedColor: brightness == Brightness.dark ? const Color(0xFF1E3A33) : const Color(0xFFE3F2DA),
      side: BorderSide(color: c.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      labelStyle: TextStyle(fontFamily: 'Inter', fontSize: 13, fontWeight: FontWeight.w600, color: c.ink2),
      showCheckmark: false,
    ),
  );
}
