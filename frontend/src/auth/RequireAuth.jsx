import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import AppShell from '../components/AppShell'
import Forbidden from './Forbidden'

export default function RequireAuth({ permission, children }) {
  const { user, loading, has } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (permission && !has(permission)) return <AppShell><Forbidden /></AppShell>
  return children
}