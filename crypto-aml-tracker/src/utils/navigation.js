export const PAGE_ROUTES = Object.freeze({
  feed: '/',
  analytics: '/analytics',
  clusters: '/clusters',
  graph: '/graph',
})

export const DEFAULT_PAGE = 'feed'

export const normalizePage = (page) => (
  Object.prototype.hasOwnProperty.call(PAGE_ROUTES, page) ? page : DEFAULT_PAGE
)

export const getPageFromPathname = (pathname = '/') => {
  const normalizedPath = pathname === '/'
    ? pathname
    : pathname.replace(/\/+$/, '')

  for (const [page, route] of Object.entries(PAGE_ROUTES)) {
    if (route === normalizedPath) {
      return page
    }
  }

  return DEFAULT_PAGE
}

export const getGraphAddressFromSearch = (search = '') => (
  new URLSearchParams(search).get('address') || ''
)

export const buildPathForPage = (page, address = '') => {
  const nextPage = normalizePage(page)
  const route = PAGE_ROUTES[nextPage]
  if (nextPage !== 'graph' || !address) {
    return route
  }

  const params = new URLSearchParams({ address })
  return `${route}?${params.toString()}`
}
