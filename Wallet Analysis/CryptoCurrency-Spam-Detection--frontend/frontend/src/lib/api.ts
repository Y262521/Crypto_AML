import axios from 'axios'

const baseURL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.VITE_API_URL ??
  'http://localhost:3000'

export const api = axios.create({
  baseURL,
  timeout: 30_000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    return Promise.reject(err)
  },
)

