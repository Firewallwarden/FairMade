import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeAnswer, decodeTurn } from '../src/services/assistant-contract.ts'

test('old answers are withheld when current evidence no longer matches', () => {
  const turn = decodeTurn({
    id: 'turn',
    revision: 1,
    request_id: 'request',
    question: 'Why?',
    answer_status: 'evidence_changed',
    answer: { sensitive_old_answer: true },
    created_at: '2026-11-11T12:00:00Z',
  })
  assert.equal(turn.answer, null)
  assert.throws(() =>
    decodeTurn({ ...turn, answer_status: 'available', answer: null }),
  )
})

test('model prose and authoritative facts retain distinct citations', () => {
  const answer = decodeAnswer({
    assistant_version: 'fairmade-assistant-v1',
    provider: 'ollama_local',
    model: 'qwen3:8b',
    generated_at: '2026-11-11T12:00:00Z',
    facts: [{ text: 'USD 8.00', evidence_keys: ['e1'] }],
    paragraphs: [
      { text: 'Seller reported, unverified.', evidence_keys: ['e1'] },
    ],
    evidence: [
      {
        key: 'e1',
        title: 'Approved Passport',
        basis: 'seller_reported_unverified',
        data: { price: '8.00' },
      },
    ],
    notices: ['No fairness certification.'],
  })
  assert.equal(answer.facts[0].text, 'USD 8.00')
  assert.equal(answer.paragraphs[0].text, 'Seller reported, unverified.')
  assert.deepEqual(answer.paragraphs[0].evidence_keys, ['e1'])
  assert.throws(() => decodeAnswer({ ...answer, provider: 'unapproved_cloud' }))
})
