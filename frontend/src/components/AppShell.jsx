import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

function SidebarIcon({ d }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 shrink-0">
      <path d={d} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const CANDIDATE_ICON = 'M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z'
const ANALYTICS_ICON = 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z'
const ADMIN_ICON = 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z'
const RESULTS_ICON = 'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15a2.25 2.25 0 0 1 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z'

export default function AppShell({ children }) {
  const { user, has, signOut } = useAuth()
  const name = user?.profile?.full_name || user?.display_name
  const workspace = has('candidates.view')

  const sidebarLinks = []
  if (has('candidates.view')) sidebarLinks.push({ to: '/dashboard', label: 'Candidates', icon: CANDIDATE_ICON })
  if (has('analytics.view')) sidebarLinks.push({ to: '/analytics', label: 'Analytics', icon: ANALYTICS_ICON })
  if (has('roles.manage')) sidebarLinks.push({ to: '/admin', label: 'Admin', icon: ADMIN_ICON })

  const topLinks = []
  if (has('test.take')) topLinks.push({ to: '/results', label: 'My results', icon: RESULTS_ICON })

  if (workspace) {
    return (
      <div className="h-screen overflow-hidden bg-gray-50 flex">
        <aside className="w-60 shrink-0 bg-white border-r border-gray-200 flex flex-col h-full">
          <div className="px-5 h-14 flex items-center border-b border-gray-200 shrink-0">
            <Link to="/" className="font-semibold text-gray-900 text-sm">
              English Assessment
            </Link>
          </div>
          <nav className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
            {sidebarLinks.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    isActive
                      ? 'bg-blue-50 text-blue-800 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <SidebarIcon d={icon} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="shrink-0 px-3 pb-4 flex flex-col gap-2 border-t border-gray-200 pt-4">
            <Link
              to="/results"
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-50 transition"
            >
              <SidebarIcon d={RESULTS_ICON} />
              My results
            </Link>
            <div className="px-3 py-2">
              <p className="text-sm font-medium leading-tight truncate">{name}</p>
              <p className="text-xs text-gray-400 capitalize leading-tight">{user?.role?.name}</p>
            </div>
            <button
              type="button"
              onClick={signOut}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-red-700 hover:bg-red-50 transition"
            >
              Sign out
            </button>
          </div>
        </aside>
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          <main className="flex-1">{children}</main>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 h-14 flex flex-wrap items-center gap-x-6 gap-y-2">
          <Link to="/" className="font-semibold text-gray-900">
            English Assessment
          </Link>
          <nav className="flex items-center gap-1">
            {topLinks.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm ${
                    isActive
                      ? 'bg-blue-50 text-blue-800 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {name && (
              <div className="hidden sm:block text-right">
                <p className="text-sm font-medium leading-tight">{name}</p>
                <p className="text-xs text-gray-400 capitalize leading-tight">{user?.role?.name}</p>
              </div>
            )}
            <button
              type="button"
              onClick={signOut}
              className="px-3 py-1.5 rounded-md text-sm border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-5 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-400">
          <span className="font-medium text-gray-500">English Assessment</span>
          <span>Interview-grade English proficiency scoring</span>
        </div>
      </footer>
    </div>
  )
}