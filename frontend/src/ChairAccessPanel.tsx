import {useEffect,useState} from 'react'
import {api} from './lib/api'
import './chair-access.css'

type Account={id:number;full_name:string;email:string;is_active:boolean;has_chair_access:boolean}

export function ChairAccessPanel({onChanged}:{onChanged:()=>void}){
  const[accounts,setAccounts]=useState<Account[]>([]),[search,setSearch]=useState(''),[selectedId,setSelectedId]=useState('')
  const[busy,setBusy]=useState(false),[message,setMessage]=useState('')
  async function load(){try{setAccounts(await api<Account[]>('/users/chair-access'))}catch(value){setMessage(value instanceof Error?value.message:'Unable to load accounts')}}
  useEffect(()=>{void load()},[])
  const filtered=accounts.filter(account=>`${account.full_name} ${account.email}`.toLowerCase().includes(search.trim().toLowerCase()))
  const selected=accounts.find(account=>String(account.id)===selectedId)
  async function change(){if(!selected)return;setBusy(true);setMessage('');try{await api(`/users/${selected.id}/chair-access`,{method:'PUT',body:JSON.stringify({enabled:!selected.has_chair_access})});setMessage(selected.has_chair_access?'Chair access removed.':'Chair access granted.');await load();onChanged()}catch(value){setMessage(value instanceof Error?value.message:'Unable to change access')}finally{setBusy(false)}}
  return <section className="chair-access-bar"><div><h3>Chair request access</h3><p>Grant request confirmation to any existing user. Their other responsibilities stay unchanged.</p></div><div className="chair-access-controls"><input aria-label="Find account for chair access" value={search} onChange={event=>{setSearch(event.target.value);setSelectedId('')}} placeholder="Find user by name or email"/><select aria-label="User for chair access" value={selectedId} onChange={event=>setSelectedId(event.target.value)}><option value="">Choose user</option>{filtered.map(account=><option key={account.id} value={account.id}>{account.full_name} · {account.email}{account.is_active?'':' (disabled)'}</option>)}</select><button type="button" disabled={!selected||busy} onClick={()=>void change()}>{selected?.has_chair_access?'Remove chair access':'Grant chair access'}</button></div>{selected&&<small>{selected.has_chair_access?'Chair access enabled':'No chair access'}{selected.is_active?'':' · Account disabled'}</small>}{message&&<p role="status" className="chair-access-message">{message}</p>}</section>
}
