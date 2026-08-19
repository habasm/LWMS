import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import './facility-actions.css'
import './facility-manager.css'

type Facility = { id: number; name: string; kind: string; location: string; capacity: number }
const PAGE_SIZE = 10

export function FacilitiesManager() {
  const [list, setList] = useState<Facility[]>([])
  const [editing, setEditing] = useState<Facility | null>(null)
  const [deleting, setDeleting] = useState<Facility | null>(null)
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('all')
  const [page, setPage] = useState(1)

  const load = async () => setList((await api<Page<Facility>>('/facilities?limit=100')).data)
  useEffect(() => { void load() }, [])
  useEffect(() => { setPage(1) }, [search, kind])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return list.filter(item => (kind === 'all' || item.kind === kind) && (!query || `${item.name} ${item.location}`.toLowerCase().includes(query)))
  }, [list, search, kind])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const values = { name: data.get('name'), kind: data.get('kind'), location: data.get('location'), capacity: Number(data.get('capacity')) }
    try {
      await api(editing ? `/facilities/${editing.id}` : '/facilities', { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(values) })
      setEditing(null)
      await load()
      setNotice('Facility saved successfully.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Unable to save facility') }
  }

  async function destroy() {
    if (!deleting) return
    try {
      await api(`/facilities/${deleting.id}`, { method: 'DELETE' })
      setDeleting(null)
      await load()
      setPage(current => Math.min(current, Math.max(1, Math.ceil((filtered.length - 1) / PAGE_SIZE))))
      setNotice('Facility deleted.')
    } catch (error) { setDeleting(null); setNotice(error instanceof Error ? error.message : 'Unable to delete facility') }
  }

  return <div className="admin-module">
    <div className="module-heading"><p className="eyebrow">SUPER ADMIN / FACILITIES</p><h2>Laboratories & workshops</h2><p>Search, filter, and manage recorded facilities.</p></div>
    <div className="module-grid">
      <section className="panel form-panel"><h3>{editing ? 'Edit facility' : 'Add a facility'}</h3><form onSubmit={save} key={editing?.id ?? 'new'}><label>Name<input name="name" defaultValue={editing?.name} required /></label><label>Type<select name="kind" defaultValue={editing?.kind ?? 'laboratory'}><option value="laboratory">Laboratory</option><option value="workshop">Workshop</option></select></label><label>Location<input name="location" defaultValue={editing?.location} required /></label><label>Capacity<input name="capacity" type="number" min="1" defaultValue={editing?.capacity} required /></label><div className="form-actions"><button className="primary">{editing ? 'Update facility' : 'Create facility'}</button>{editing && <button type="button" className="secondary" onClick={() => setEditing(null)}>Cancel</button>}</div></form>{notice && <div className="form-message">{notice}<button type="button" onClick={() => setNotice('')}>×</button></div>}</section>
      <section className="panel list-panel"><div className="panel-title"><div><h3>Recorded facilities</h3><p>{filtered.length} matching records</p></div></div><div className="facility-tools"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name or location…" /><select value={kind} onChange={event => setKind(event.target.value)}><option value="all">All types</option><option value="laboratory">Laboratories</option><option value="workshop">Workshops</option></select></div>{visible.length === 0 ? <p className="empty-state">No facilities match these filters.</p> : visible.map(item => <div className="table-row" key={item.id}><div><b>{item.name}</b><small>{item.kind} · {item.location} · {item.capacity} people</small></div><span className="resource-actions"><button type="button" onClick={() => setEditing(item)}>Edit</button><button type="button" onClick={() => setDeleting(item)}>Delete</button></span></div>)}<div className="pagination"><span>Page {page} of {pages}</span><div><button type="button" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><button type="button" disabled={page === pages} onClick={() => setPage(value => value + 1)}>Next</button></div></div></section>
    </div>
    {deleting && <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal"><p className="eyebrow">DELETE FACILITY</p><h2>Delete {deleting.name}?</h2><p className="confirm-copy">This permanently removes the facility record.</p><div className="modal-actions"><button type="button" className="secondary" onClick={() => setDeleting(null)}>Cancel</button><button type="button" className="primary danger" onClick={destroy}>Delete facility</button></div></div></div>}
  </div>
}
