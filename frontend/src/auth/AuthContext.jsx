import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, setToken, setOnUnauthorized } from '../api.js'

const TOKEN_KEY = 'antigen_token'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sessionExpired, setSessionExpired] = useState(false)

  const clearAuth = useCallback(() => {
    setUser(null)
    setToken(null)
    localStorage.removeItem(TOKEN_KEY)
  }, [])

  // Any request coming back 401 (expired/invalid token) lands here — distinct
  // from a manual logout() so Login can explain why you're back here instead
  // of silently dropping you at a blank login screen.
  const handleUnauthorized = useCallback(() => {
    setSessionExpired(true)
    clearAuth()
  }, [clearAuth])

  useEffect(() => {
    setOnUnauthorized(handleUnauthorized)
  }, [handleUnauthorized])

  // On first load, try to restore a session from a saved token.
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (!stored) {
      setIsLoading(false)
      return
    }
    setToken(stored)
    api
      .getMe()
      .then((me) => setUser(me))
      .catch(() => clearAuth())
      .finally(() => setIsLoading(false))
  }, [clearAuth])

  async function login(username, password) {
    setError(null)
    setSessionExpired(false)
    let data
    try {
      data = await api.login(username, password)
    } catch (err) {
      setError(err.message || 'Login failed')
      throw err
    }

    // Backend may return the JWT as `access_token` (standard OAuth2-style) or
    // `token` — support either so this doesn't silently break either way.
    const token = data.access_token || data.token
    if (!token) {
      const err = new Error('Login response did not include an access token')
      setError(err.message)
      throw err
    }

    localStorage.setItem(TOKEN_KEY, token)
    setToken(token)

    // Some login endpoints return the user object inline; if not, fetch it.
    const me = data.user || (await api.getMe())
    setUser(me)
    return me
  }

  function logout() {
    clearAuth()
  }

  const value = {
    user,
    isLoading,
    error,
    sessionExpired,
    login,
    logout,
    isAuthenticated: !!user,
    isOwner: user?.role === 'OWNER',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}