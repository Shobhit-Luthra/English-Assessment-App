import { Link } from 'react-router-dom'

export default function Forbidden() {
  return (
    <div className="max-w-md mx-auto p-6 text-center flex flex-col gap-3">
      <h1 className="text-xl font-semibold">You don&apos;t have access to this page</h1>
      <Link to="/" className="text-sm underline">Go back</Link>
    </div>
  )
}
