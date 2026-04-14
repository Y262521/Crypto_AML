import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_PAGE,
  buildPathForPage,
  getGraphAddressFromSearch,
  getPageFromPathname,
} from '../src/utils/navigation.js'

test('maps known pathnames to pages', () => {
  assert.equal(getPageFromPathname('/'), 'feed')
  assert.equal(getPageFromPathname('/analytics'), 'analytics')
  assert.equal(getPageFromPathname('/clusters/'), 'clusters')
  assert.equal(getPageFromPathname('/graph'), 'graph')
})

test('falls back to the default page for unknown routes', () => {
  assert.equal(getPageFromPathname('/does-not-exist'), DEFAULT_PAGE)
})

test('builds graph URLs with an address query string', () => {
  assert.equal(
    buildPathForPage('graph', '0xabc'),
    '/graph?address=0xabc',
  )
})

test('extracts the graph address from the current search string', () => {
  assert.equal(
    getGraphAddressFromSearch('?address=0xdef'),
    '0xdef',
  )
  assert.equal(getGraphAddressFromSearch(''), '')
})
