export async function getLatestTransactions({ limit = 200, offset = 0, sortBy = 'amount_desc', chain = 'all' } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset), sort_by: sortBy })
  if (chain && chain !== 'all') params.set('chain', chain)

  const res = await fetch(`/api/transactions?${params.toString()}`)
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`Failed to fetch transactions: ${res.status} ${txt}`)
  }
  return res.json()
}
