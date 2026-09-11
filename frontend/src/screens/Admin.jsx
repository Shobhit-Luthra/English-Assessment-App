import { useCallback, useEffect, useState } from 'react'
import {
  adminCreateRole, adminCreateUser, adminDeleteRole, adminListPermissions,
  adminListRoles, adminListUsers, adminPatchRole, adminPatchUser,
  adminDismissPasswordResetRequest, adminListPasswordResetRequests,
} from '../api'
import { Link } from 'react-router-dom'

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-gray-500">{label}</span>
      {children}
    </label>
  )
}

const inputCls = 'border rounded px-2 py-1 text-sm'

export default function Admin() {
  const [tab, setTab] = useState('users')
  return (
    <div className="max-w-5xl mx-auto p-6 flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Admin</h1>
      <div className="flex gap-2 border-b">
        {(['users', 'roles', 'password requests']).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm border-b-2 capitalize ${tab === t ? 'border-blue-700 text-blue-800' : 'border-transparent text-gray-500'}`}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === 'users' && <UsersTab />}
      {tab === 'roles' && <RolesTab />}
      {tab === 'password requests' && <PasswordRequestsTab />}
      <Link to="/recruiter-preview" className="self-start rounded-lg border border-blue-700 px-3 py-2 text-sm font-medium text-blue-800 hover:bg-blue-50">Preview recruiter workspace</Link>
    </div>
  )
}

function UsersTab() {
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [message, setMessage] = useState(null)
  const [form, setForm] = useState({ email: '', password: '', display_name: '', role_id: '' })

  const load = useCallback(async () => {
    const [us, rs] = await Promise.all([adminListUsers(), adminListRoles()])
    setUsers(us)
    setRoles(rs)
  }, [])

  useEffect(() => { load() }, [load])

  const createUser = async () => {
    setMessage(null)
    try {
      await adminCreateUser({ ...form, role_id: Number(form.role_id) })
      setForm({ email: '', password: '', display_name: '', role_id: '' })
      setMessage('User created.')
      await load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  const patch = async (id, payload, ok) => {
    setMessage(null)
    try {
      await adminPatchUser(id, payload)
      setMessage(ok)
      await load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {message && <p className="text-sm text-gray-700">{message}</p>}

      <div className="border p-4 flex flex-wrap items-end gap-3">
        <Field label="Name">
          <input className={inputCls} value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        </Field>
        <Field label="Email">
          <input className={inputCls} value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password">
          <input className={inputCls} type="password" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <Field label="Role">
          <select className={inputCls} value={form.role_id}
            onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
            <option value="">Select</option>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </Field>
        <button type="button" onClick={createUser}
          disabled={!form.display_name || !form.email || !form.password || !form.role_id}
          className="px-3 py-1 rounded bg-blue-800 text-white text-sm disabled:opacity-40">
          Add user
        </button>
      </div>

      <div className="divide-y border">
        {users.map((u) => (
          <div key={u.id} className="p-3 flex flex-wrap items-center justify-between gap-2 text-sm">
            <div>
              <span className="font-medium">{u.display_name}</span>
              <span className="ml-2 text-gray-500">{u.email}</span>
              <span className="ml-2 text-gray-500">{u.role.name}</span>
              <span className={`ml-2 px-2 py-0.5 rounded text-xs ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                {u.is_active ? 'active' : 'disabled'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <select
                className={inputCls}
                value={u.role.id}
                onChange={(e) => patch(u.id, { role_id: Number(e.target.value) }, 'Role updated.')}
              >
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
              <button type="button"
                onClick={() => patch(u.id, { is_active: !u.is_active }, u.is_active ? 'Account disabled.' : 'Account enabled.')}
                className="px-2 py-1 rounded border border-gray-400 text-gray-600">
                {u.is_active ? 'Disable' : 'Enable'}
              </button>
              <button type="button"
                onClick={() => {
                  const pw = window.prompt('New password (min 10 chars) for ' + u.email)
                  if (pw && pw.length >= 10) patch(u.id, { password: pw }, 'Password reset.')
                }}
                className="px-2 py-1 rounded border border-gray-400 text-gray-600">
                Reset password
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RolesTab() {
  const [roles, setRoles] = useState([])
  const [permissions, setPermissions] = useState([])
  const [draft, setDraft] = useState({})
  const [newName, setNewName] = useState('')
  const [message, setMessage] = useState(null)

  const load = useCallback(async () => {
    const [rs, ps] = await Promise.all([adminListRoles(), adminListPermissions()])
    setRoles(rs)
    setPermissions(ps)
    setDraft(Object.fromEntries(rs.map((r) => [r.id, new Set(r.permission_keys)])))
  }, [])

  useEffect(() => { load() }, [load])

  const saveRole = async (role) => {
    setMessage(null)
    try {
      await adminPatchRole(role.id, { permission_keys: [...draft[role.id]] })
      setMessage(`Saved permissions for ${role.name}.`)
      await load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  const createRole = async () => {
    setMessage(null)
    try {
      await adminCreateRole({ name: newName })
      setNewName('')
      setMessage('Role created.')
      await load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  const removeRole = async (role) => {
    setMessage(null)
    try {
      await adminDeleteRole(role.id)
      setMessage(`Deleted ${role.name}.`)
      await load()
    } catch (e) {
      setMessage(e.message)
    }
  }

  const toggle = (roleId, key) => {
    setDraft((d) => {
      const next = new Set(d[roleId])
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return { ...d, [roleId]: next }
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {message && <p className="text-sm text-gray-700">{message}</p>}

      <div className="flex items-center gap-2">
        <input className={inputCls} placeholder="New role name"
          value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button type="button" onClick={createRole} disabled={!newName.trim()}
          className="px-3 py-1 rounded bg-blue-800 text-white text-sm disabled:opacity-40">
          Create role
        </button>
      </div>

      <div className="divide-y border">
        {roles.map((role) => (
          <div key={role.id} className="p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {role.name}
                {role.is_system && <span className="ml-2 text-xs text-gray-400">system</span>}
              </span>
              <div className="flex gap-2">
                <button type="button" onClick={() => saveRole(role)}
                  className="px-3 py-1 rounded border border-blue-700 text-blue-800 text-sm">
                  Save
                </button>
                {!role.is_system && (
                  <button type="button" onClick={() => removeRole(role)}
                    className="px-3 py-1 rounded border border-red-600 text-red-700 text-sm">
                    Delete
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {permissions.map((p) => (
                <label key={p.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={draft[role.id]?.has(p.key) ?? false}
                    onChange={() => toggle(role.id, p.key)} />
                  <span className="text-gray-700">{p.key}</span>
                  <span className="text-gray-400 text-xs truncate">{p.description}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PasswordRequestsTab() {
  const [requests, setRequests] = useState([])
  const [message, setMessage] = useState(null)
  const load = useCallback(async () => { try { setRequests(await adminListPasswordResetRequests()) } catch (e) { setMessage(e.message) } }, [])
  useEffect(() => { load() }, [load])
  const dismiss = async (id) => { try { await adminDismissPasswordResetRequest(id); setMessage('Request dismissed.'); await load() } catch (e) { setMessage(e.message) } }
  return <div className="flex flex-col gap-4">
    <p className="text-sm text-gray-600">Reset a matching account’s password from the Users tab; doing so completes its pending request and revokes existing sessions.</p>
    {message && <p role="status" className="text-sm text-gray-700">{message}</p>}
    {!requests.length ? <p className="text-sm text-gray-500">No active password requests.</p> : <div className="divide-y border">{requests.map((request) => <div key={request.id} className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm"><div><p className="font-medium">{request.email}</p><p className="text-gray-500">{request.user ? `${request.user.display_name} · ${request.user.role.name}` : 'No matching account'} · requested {new Date(request.created_at).toLocaleDateString()} · expires {new Date(request.expires_at).toLocaleDateString()}</p></div><button type="button" onClick={() => dismiss(request.id)} className="rounded border border-gray-400 px-2 py-1 text-gray-700 hover:bg-gray-50">Dismiss</button></div>)}</div>}
  </div>
}
