import {useEffect,useState} from 'react'
import {api} from './lib/api'
import './store.css'

type Request={id:number;reference:string;requester_name:string;department:string;purpose:string;store_name:string;status:string;created_at:string;lines:{id:number;name:string;quantity:number;unit:string}[]}
type Page={data:Request[];meta:{total:number}}
const statusLabel:Record<string,string>={chair_review:'Needs confirmation',dean_review:'Sent to dean',ready:'Approved by dean',rejected:'Rejected by dean',issued:'Issued'}

export function ChairDesk(){
  const[requests,setRequests]=useState<Request[]>([]),[total,setTotal]=useState(0),[page,setPage]=useState(0)
  const[open,setOpen]=useState<number|null>(null),[notes,setNotes]=useState<Record<number,string>>({})
  const[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  async function load(){try{const result=await api<Page>(`/store/requests?skip=${page*25}&limit=25`);setRequests(result.data);setTotal(result.meta.total)}catch(value){setError(value instanceof Error?value.message:'Unable to load requests')}}
  useEffect(()=>{void load()},[page])
  async function confirm(request:Request){setBusy(true);setError('');setNotice('');try{await api(`/store/requests/${request.id}/chair`,{method:'POST',body:JSON.stringify({approve:true,notes:notes[request.id]?.trim()||null})});setNotice(`${request.reference} confirmed and sent to the dean.`);setOpen(null);await load()}catch(value){setError(value instanceof Error?value.message:'Unable to confirm request')}finally{setBusy(false)}}
  return <div className="store-page chair-desk"><div className="store-intro"><div><p className="eyebrow">CHAIR REVIEW</p><h2>Material requests</h2><p>Confirm requests addressed to you and forward them to the dean.</p></div></div>
    {error&&<p className="store-error" role="alert">{error}</p>}{notice&&<p className="store-notice" role="status">{notice}</p>}
    <div className="store-list">{requests.length===0&&<p className="store-empty">No requests are assigned to you.</p>}{requests.map(request=><article className="store-row" key={request.id}>
      <button type="button" className="store-row-head" aria-expanded={open===request.id} onClick={()=>setOpen(open===request.id?null:request.id)}><span><b>{request.reference} · {request.requester_name}</b><small>{request.department} · {request.store_name} · {new Date(request.created_at).toLocaleString()}</small></span><span className="store-status">{statusLabel[request.status]||request.status}</span><span>{open===request.id?'−':'+'}</span></button>
      {open===request.id&&<div className="store-row-body"><p>{request.purpose}</p><div className="store-materials">{request.lines.map(line=><div key={line.id}><b>{line.name}</b><span>{line.quantity} {line.unit}</span></div>)}</div>{request.status==='chair_review'&&<><label className="store-discrepancy">Note for dean (optional)<input value={notes[request.id]||''} onChange={event=>setNotes({...notes,[request.id]:event.target.value})}/></label><div className="store-actions"><button type="button" disabled={busy} onClick={()=>void confirm(request)}>Confirm &amp; send to dean</button></div></>}</div>}
    </article>)}{total>25&&<div className="store-pages"><button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</button><span>{page+1} / {Math.ceil(total/25)}</span><button disabled={(page+1)*25>=total} onClick={()=>setPage(page+1)}>Next</button></div>}</div>
  </div>
}
