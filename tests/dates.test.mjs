import test from 'node:test'
import assert from 'node:assert/strict'
import { isCalendarDate, formatDate, formatDraftDate, beijingDate } from '../src/lib/dates.ts'

test('native date input intermediate values never crash the draft label', () => {
  for (const value of ['10000-01-01', '202610-10-10', '2026-02-30', '2025-02-29', '2026-', '', '0000-01-01', null, undefined, 2026]) {
    assert.equal(isCalendarDate(value), false)
    assert.equal(formatDraftDate(value), '日期待修改')
  }
  assert.equal(formatDate('10000-01-01T00:00:00+08:00'), '日期待修改')
  assert.equal(formatDate('invalid'), '日期待修改')
})

test('valid dates retain calendar meaning including leap years and date limits', () => {
  for (const value of ['0001-01-01', '0099-12-31', '2012-02-29', '2026-10-10', '9999-12-31']) assert.ok(isCalendarDate(value))
  assert.equal(formatDraftDate('2012-02-29'), '2012年2月29日')
  assert.equal(formatDate('2026-10-10T16:01:00Z'), '2026年10月11日')
  assert.equal(beijingDate(new Date('2026-10-10T16:01:00Z')), '2026-10-11')
})
