// Lean unit tests for pure logic (without the map's platform channels).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:heritage_at_risk/theme.dart';

void main() {
  test('threat colour follows the inverted traffic-light ramp', () {
    expect(AppColors.forThreatLevel('high'), AppColors.threatHigh);
    expect(AppColors.forThreatLevel('medium'), AppColors.threatMedium);
    expect(AppColors.forThreatLevel('low'), AppColors.threatLow);
    // An unknown level falls back to "low".
    expect(AppColors.forThreatLevel('unknown'), AppColors.threatLow);
  });

  test('threat label maps level keys to English', () {
    expect(AppColors.threatLabel('high'), 'high');
    expect(AppColors.threatLabel('medium'), 'medium');
    expect(AppColors.threatLabel('low'), 'low');
    expect(AppColors.threatLabel('unknown'), 'low');
  });

  test('themes build without error', () {
    expect(AppTheme.light().brightness, Brightness.light);
    expect(AppTheme.dark().brightness, Brightness.dark);
  });
}
