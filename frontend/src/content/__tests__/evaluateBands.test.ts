import { describe, it, expect } from 'vitest';
import { evaluateBands, evaluateCondition } from '../evaluateBands';
import type { ValueInterpretation } from '../evaluateBands';
import fixture from '../__fixtures__/bands-cases.json';

/**
 * PARITY CONTRACT: this suite and backend/tests/test_education_bands.py
 * consume the SAME fixture (bands-cases.json). Any behavioral divergence
 * between the TS and Python evaluators fails one of these suites.
 */

describe('evaluateCondition', () => {
  const cases: Array<[string, string, boolean]> = [
    ['value > 10', '15', true],
    ['value >= 10', '10', true],
    ['value > 10', '9.99', false],
    ["value == 'bullish'", 'Bullish', true],
    ["value != 'bearish'", 'neutral', true],
    ['value < 0', '-1', true],
    ['garbage', '5', false],
    ["value == 'x", 'x', false], // unterminated quote
  ];
  for (const [cond, val, expected] of cases) {
    it(`${cond} vs ${val} → ${expected}`, () => {
      expect(evaluateCondition(cond, val)).toBe(expected);
    });
  }
});

describe('evaluateBands — shared fixture parity', () => {
  const typed = fixture as {
    cases: Array<{
      name: string;
      value: string;
      expected: string;
      interpretation: ValueInterpretation;
    }>;
  };

  for (const c of typed.cases) {
    it(`${c.name}: ${c.value} → "${c.expected}"`, () => {
      expect(evaluateBands(c.interpretation, c.value)).toBe(c.expected);
    });
  }
});

describe('evaluateBands — multi-band first-match ordering', () => {
  const interp: ValueInterpretation = {
    type: 'bands',
    bands: [
      { if: 'value > 70', text: 'overbought at ${value}' },
      { if: 'value > 30', text: 'mid-range ${value}' },
      { if: 'value >= 0', text: 'oversold ${value}' },
      { if: "value != ''", text: 'unparseable' },
    ],
  };

  it('picks first matching band only', () => {
    expect(evaluateBands(interp, '85')).toBe('overbought at 85');
    expect(evaluateBands(interp, '50')).toBe('mid-range 50');
    expect(evaluateBands(interp, '12')).toBe('oversold 12');
  });

  it('falls through to last band for junk values', () => {
    expect(evaluateBands(interp, 'N/A')).toBe('unparseable');
  });
});

describe('evaluateBands — transforms applied to interpolated value', () => {
  it('percent', () => {
    expect(
      evaluateBands(
        { type: 'bands', transform: 'percent', bands: [{ if: 'value > 20', text: 'strong at ${value}' }] },
        '24.6'
      )
    ).toBe('strong at 24.6%');
  });

  it('ratio', () => {
    expect(
      evaluateBands(
        { type: 'bands', transform: 'ratio', bands: [{ if: 'value > 1', text: '${value} of average' }] },
        '1.7777'
      )
    ).toBe('1.78x of average');
  });

  it('compactNumber', () => {
    expect(
      evaluateBands(
        { type: 'bands', transform: 'compactNumber', bands: [{ if: 'value > 0', text: '${value} shares/day' }] },
        '2500000'
      )
    ).toBe('2.5M shares/day');
  });

  it('money', () => {
    expect(
      evaluateBands(
        { type: 'bands', transform: 'money', bands: [{ if: 'value > 100', text: 'cap ${value}' }] },
        '1250.5'
      )
    ).toBe('cap $1,250.50');
  });
});
