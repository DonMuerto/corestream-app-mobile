import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * A 401 from /auth/login means wrong credentials, not an expired session.
 * Before the fix, the response interceptor tried /auth/refresh for ANY 401
 * (including login's), and since there's no session cookie yet, that refresh
 * call failed with "No se proporcionó refresh_token" — replacing the real
 * "Email o contraseña incorrectos" error from the login response.
 */

let responseRejectedHandler: ((error: any) => any) | undefined

vi.mock('axios', () => {
  const post = vi.fn()
  // Axios instances are callable (used for the retried request), so the mock
  // must be a function, not a plain object.
  const instance: any = vi.fn().mockResolvedValue({ data: {} })
  instance.interceptors = {
    request: { use: vi.fn() },
    response: {
      use: vi.fn((_fulfilled: any, rejected: any) => {
        responseRejectedHandler = rejected
      }),
    },
  }
  instance.post = post
  return {
    default: {
      create: vi.fn(() => instance),
      post,
    },
  }
})

describe('api response interceptor', () => {
  beforeEach(async () => {
    vi.resetModules()
    responseRejectedHandler = undefined
    // Re-import so createApiClient() runs again and registers the interceptor
    // against the freshly mocked axios instance.
    await import('@/services/api')
  })

  it('does not retry /auth/refresh when the 401 comes from /auth/login', async () => {
    const axios = (await import('axios')).default as any
    const loginError = {
      config: { url: '/auth/login', headers: {} },
      response: { status: 401, data: { detail: 'Email o contraseña incorrectos' } },
    }

    await expect(responseRejectedHandler!(loginError)).rejects.toBe(loginError)
    expect(axios.post).not.toHaveBeenCalled()
  })

  it('does retry via /auth/refresh for a 401 on any other endpoint', async () => {
    const axios = (await import('axios')).default as any
    axios.post.mockResolvedValue({ data: { access_token: 'new-token' } })

    const otherError = {
      config: { url: '/tickets/', headers: {} },
      response: { status: 401, data: {} },
    }

    await responseRejectedHandler!(otherError)
    expect(axios.post).toHaveBeenCalledWith('/api/auth/refresh', {}, expect.any(Object))
  })
})
