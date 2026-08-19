// The production Vite build is mounted by FastAPI. A relative URL keeps the
// browser on the exact same host (localhost or 127.0.0.1) and avoids CORS.
const API_URL = import.meta.env.VITE_API_URL ?? '/api/v1'
export type Page<T> = { data:T[]; meta:{total:number;skip:number;limit:number} }
export type Dashboard = { equipment:number; open_maintenance:number; active_projects:number; upcoming_sessions:number }
export async function api<T>(path:string, options:RequestInit={}) : Promise<T> {
  const token=localStorage.getItem('lwms_token')
  const response=await fetch(`${API_URL}${path}`,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{}) ,...options.headers}})
  if(!response.ok) {
    const body=await response.json().catch(()=>null)
    const detail=Array.isArray(body?.detail) ? body.detail.map((item:{msg?:string})=>item.msg).join(', ') : body?.detail
    throw new Error(detail ?? `Request failed (${response.status})`)
  }
  return response.status===204 ? undefined as T : response.json()
}
