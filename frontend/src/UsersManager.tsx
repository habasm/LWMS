import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './lib/api'
import type { Page } from './lib/api'
import './facility-actions.css'
import './facility-manager.css'

type Role={id:number;name:string}
type Facility={id:number;name:string;kind:string;manager_id:number|null}
type Activity={id:number;action:string;actor_name:string;created_at:string}
type User={id:number;full_name:string;email:string;is_active:boolean;must_change_password:boolean;assigned_facility_id:number|null;assigned_facility_ids?:number[];assigned_facilities?:Facility[];pending_facility_ids?:number[];pending_facilities?:Facility[];outgoing_pending_facilities?:Facility[];role_names:string[];added_by_name:string;activity?:Activity[]}

const PAGE_SIZE=10
const roleLabels:Record<string,string>={lab_admin:'facility assistant',maintainer:'maintainer',coordinator:'coordinator'}
const roleLabel=(name:string)=>roleLabels[name]??name.replaceAll('_',' ')
const actionLabel=(value:string)=>value.split(':')[0].replaceAll('_',' ')

export function UsersManager(){
  const[users,setUsers]=useState<User[]>([])
  const[assistantOptions,setAssistantOptions]=useState<User[]>([])
  const[roles,setRoles]=useState<Role[]>([])
  const[facilities,setFacilities]=useState<Facility[]>([])
  const[editing,setEditing]=useState<User|null>(null)
  const[disabling,setDisabling]=useState<User|null>(null)
  const[transfering,setTransfering]=useState<User|null>(null)
  const[role,setRole]=useState('')
  const[facilityIds,setFacilityIds]=useState<number[]>([])
  const[transferFacilityId,setTransferFacilityId]=useState('')
  const[transferTargetId,setTransferTargetId]=useState('')
  const[notice,setNotice]=useState('')
  const[search,setSearch]=useState('')
  const[status,setStatus]=useState<'active'|'disabled'|'all'>('active')
  const[page,setPage]=useState(1)
  const[total,setTotal]=useState(0)

  const load=async(nextPage=page,nextSearch=search,nextStatus=status)=>{
    const params=new URLSearchParams({limit:String(PAGE_SIZE),skip:String((nextPage-1)*PAGE_SIZE),active:nextStatus})
    if(nextSearch.trim())params.set('search',nextSearch.trim())
    const [result,roleRows,facilityRows,assistantRows]=await Promise.all([
      api<Page<User>>(`/users?${params.toString()}`),
      api<Role[]>('/roles'),
      api<Page<Facility>>('/facilities?limit=100'),
      api<Page<User>>('/users?limit=100&active=active'),
    ])
    setUsers(result.data);setTotal(result.meta.total);setRoles(roleRows);setFacilities(facilityRows.data);setAssistantOptions(assistantRows.data.filter(user=>user.role_names.includes('lab_admin')))
  }
  useEffect(()=>{void load(page,search,status)},[page,status])
  useEffect(()=>{const id=setTimeout(()=>{setPage(1);void load(1,search,status)},250);return()=>clearTimeout(id)},[search])

  function beginEdit(user:User){setEditing(user);setRole(user.role_names[0]??'');setFacilityIds(user.assigned_facility_ids?.length?user.assigned_facility_ids:(user.assigned_facility_id?[user.assigned_facility_id]:[]))}
  function cancelEdit(){setEditing(null);setRole('');setFacilityIds([])}
  function toggleFacility(id:number,checked:boolean){setFacilityIds(current=>checked?[...new Set([...current,id])]:current.filter(value=>value!==id))}
  const needsFacility=role==='lab_admin'
  const pages=Math.max(1,Math.ceil(total/PAGE_SIZE))
  const protectedAssistant=(user:User)=>user.is_active&&user.role_names.includes('lab_admin')&&((user.assigned_facility_ids?.length??0)>0||!!user.assigned_facility_id)

  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    const form=event.currentTarget,data=new FormData(form)
    const payload={full_name:data.get('full_name'),email:data.get('email'),role_names:[role],assigned_facility_ids:needsFacility?facilityIds:[],is_active:data.get('is_active')==='on'}
    try{
      await api(editing?`/users/${editing.id}`:'/users',{method:editing?'PATCH':'POST',body:JSON.stringify(payload)})
      const first=String(payload.full_name).trim().split(/\s+/)[0].toLowerCase()
      cancelEdit();form.reset();await load()
      setNotice(editing?'User updated successfully.':`User created. Temporary password: ${first}password`)
    }catch(error){setNotice(error instanceof Error?error.message:'Unable to save user')}
  }

  async function transferFacilities(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    if(!transfering)return
    try{
      await api(`/users/${Number(transferTargetId)}/transfer-facilities`,{method:'POST',body:JSON.stringify({assigned_facility_ids:[Number(transferFacilityId)]})})
      setTransfering(null);setTransferFacilityId('');setTransferTargetId('');await load()
      setNotice('Facility ownership request sent. The previous owner record stays in history.')
    }catch(error){setNotice(error instanceof Error?error.message:'Unable to request transfer')}
  }

  async function disableUser(){if(!disabling)return;try{await api(`/users/${disabling.id}`,{method:'DELETE'});setDisabling(null);await load();setNotice('User disabled. They cannot sign in until reactivated.')}catch(error){setDisabling(null);setNotice(error instanceof Error?error.message:'Unable to disable user')}}
  async function cancelTransfer(facilityId:number){try{await api(`/users/transfer-facilities/${facilityId}/cancel`,{method:'POST'});await load();setNotice('Pending transfer cancelled. Current facility owner remains unchanged.')}catch(error){setNotice(error instanceof Error?error.message:'Unable to cancel transfer')}}
  async function reactivate(user:User){try{await api(`/users/${user.id}`,{method:'PATCH',body:JSON.stringify({is_active:true})});await load();setNotice('User reactivated.')}catch(error){setNotice(error instanceof Error?error.message:'Unable to reactivate user')}}

  return <div className="admin-module">
    <div className="module-heading"><p className="eyebrow">ACCESS CONTROL / USERS</p><h2>People & roles</h2><p>Create accounts, assign assistants to facilities, and transfer facility ownership by assistant acceptance.</p></div>
    <div className="module-grid">
      <section className="panel form-panel">
        <h3>{editing?'Edit user':'Add a user'}</h3>
        {editing&&protectedAssistant(editing)?<div className="locked-user-edit"><b>{editing.full_name}</b><p>This active assistant already owns accepted facility resources. Use disable/reactivate or transfer facility ownership instead of editing profile details.</p><button type="button" className="secondary" onClick={cancelEdit}>Close</button></div>:<form key={editing?.id??'new'} onSubmit={save}>
          <label>Full name<input name="full_name" defaultValue={editing?.full_name} required/></label>
          <label>Email address<input name="email" type="email" defaultValue={editing?.email} required/></label>
          <label>Role<select value={role} onChange={e=>{setRole(e.target.value);setFacilityIds([])}} required><option value="">Choose role</option>{roles.map(r=><option key={r.id} value={r.name}>{roleLabel(r.name)}</option>)}</select></label>
          {needsFacility&&<fieldset className="facility-checkboxes"><legend>Assigned facilities</legend><p>An assistant can work in more than one laboratory or workshop.</p>{facilities.map(f=><label key={f.id}><input type="checkbox" checked={facilityIds.includes(f.id)} onChange={e=>toggleFacility(f.id,e.target.checked)}/><span>{f.name}</span><em>{f.kind}</em></label>)}</fieldset>}
          <label className="check-label"><input name="is_active" type="checkbox" defaultChecked={editing?.is_active??true}/> Active account</label>
          <div className="form-actions"><button className="primary" disabled={needsFacility&&facilityIds.length===0}>{editing?'Update user':'Create user'}</button>{editing&&<button type="button" className="secondary" onClick={cancelEdit}>Cancel</button>}</div>
        </form>}
        {notice&&<div className="form-message">{notice}<button type="button" onClick={()=>setNotice('')}>x</button></div>}
      </section>
      <section className="panel list-panel">
        <div className="panel-title"><div><h3>Workspace users</h3><p>{total} matching records</p></div></div>
        <div className="facility-tools"><input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search user name or email..."/><select value={status} onChange={event=>{setStatus(event.target.value as 'active'|'disabled'|'all');setPage(1)}}><option value="active">Active users</option><option value="disabled">Disabled users</option><option value="all">All users</option></select></div>
        {users.length===0?<p className="empty-state">No users match this view.</p>:users.map(user=><details className={'table-row user-row '+(!user.is_active?'disabled-row':'')} key={user.id}>
          <summary><div><b>{user.full_name}</b><small>{user.email} · {user.role_names.map(roleLabel).join(', ')||'No role'} · Added by {user.added_by_name}</small><small>{user.is_active?'Active':'Disabled'}</small></div><span className="resource-actions">{!protectedAssistant(user)&&<button type="button" onClick={event=>{event.preventDefault();beginEdit(user)}}>Edit</button>}{user.role_names.includes('lab_admin')&&user.assigned_facilities?.length&&(user.outgoing_pending_facilities?.length??0)===0?<button type="button" onClick={event=>{event.preventDefault();setTransfering(user);setTransferFacilityId(user.assigned_facilities?.[0]?.id?String(user.assigned_facilities[0].id):'');setTransferTargetId('')}}>Transfer</button>:null}{user.outgoing_pending_facilities?.map(facility=><button key={facility.id} type="button" onClick={event=>{event.preventDefault();void cancelTransfer(facility.id)}}>Cancel transfer</button>)}{user.is_active?<button type="button" className="danger" onClick={event=>{event.preventDefault();setDisabling(user)}}>Disable</button>:<button type="button" onClick={event=>{event.preventDefault();void reactivate(user)}}>Reactivate</button>}</span></summary>
          <div className="user-row-details"><p><b>Working facilities</b>{user.assigned_facilities?.length?user.assigned_facilities.map(f=><span key={f.id}>{f.name}</span>):<em>None</em>}</p><p><b>Pending transfer in</b>{user.pending_facilities?.length?user.pending_facilities.map(f=><span key={f.id}>{f.name}</span>):<em>None</em>}</p><p><b>Pending transfer out</b>{user.outgoing_pending_facilities?.length?user.outgoing_pending_facilities.map(f=><span key={f.id}>{f.name}</span>):<em>None</em>}</p><div className="user-history"><b>Recent account activity</b>{user.activity?.length?user.activity.map(event=><small key={event.id}>{actionLabel(event.action)} by {event.actor_name} · {new Date(event.created_at).toLocaleString()}</small>):<small>No activity recorded yet.</small>}</div></div>
        </details>)}
        <div className="pagination"><span>Page {page} of {pages}</span><div><button type="button" disabled={page===1} onClick={()=>setPage(value=>value-1)}>Previous</button><button type="button" disabled={page===pages} onClick={()=>setPage(value=>value+1)}>Next</button></div></div>
      </section>
    </div>
    {transfering&&<div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal transfer-modal"><p className="eyebrow">TRANSFER FACILITY OWNER</p><h2>Transfer from {transfering.full_name}</h2><p className="confirm-copy">This requests another assistant to become the owner of the selected facility. Equipment review happens after ownership is accepted.</p><form onSubmit={transferFacilities}>
      <label>Facility to transfer<select value={transferFacilityId} onChange={event=>setTransferFacilityId(event.target.value)} required>{transfering.assigned_facilities?.map(f=><option key={f.id} value={f.id}>{f.name} · {f.kind}</option>)}</select></label>
      <label>New assistant owner<select value={transferTargetId} onChange={event=>setTransferTargetId(event.target.value)} required><option value="">Choose assistant</option>{assistantOptions.filter(user=>user.id!==transfering.id).map(user=><option key={user.id} value={user.id}>{user.full_name}</option>)}</select></label>
      <div className="modal-actions"><button type="button" className="secondary" onClick={()=>{setTransfering(null);setTransferFacilityId('');setTransferTargetId('')}}>Cancel</button><button type="submit" className="primary" disabled={!transferFacilityId||!transferTargetId}>Request transfer</button></div>
    </form></div></div>}
    {disabling&&<div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal"><p className="eyebrow">DISABLE USER</p><h2>Disable {disabling.full_name}?</h2><p className="confirm-copy">Their record stays in the system, but they will not be able to sign in until reactivated.</p><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setDisabling(null)}>Keep active</button><button type="button" className="primary danger" onClick={disableUser}>Disable user</button></div></div></div>}
  </div>
}
