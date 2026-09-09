import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Forbidden from '../screens/Forbidden'

export default function RequireAuth({ permission, children }) {
  const { user, loading, has } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (permission && !has(permission)) return <Forbidden />
  return children
}
