"""Standalone materials store workflow, separate from equipment handover."""
import base64
import binascii
import secrets
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from .core.database import get_db
from .dependencies import current_user, require_roles
from .models import AuditLog, Store, StoreAllocation, StoreEvent, StoreItem, StoreLot, StoreMovement, StoreRequest, StoreRequestLine, User

store = APIRouter(prefix='/api/v1/store', tags=['workshop store'])
STORE_ROLES = {'dean', 'coordinator', 'super_admin'}
REQUEST_ROLES = STORE_ROLES | {'store_manager', 'chair'}
UPLOADS = Path(__file__).resolve().parents[1] / 'uploads' / 'store'

def roles(user: User) -> set[str]:
    return {role.name for role in user.roles}

def managed_stores(db: Session, user: User) -> set[int]:
    if 'store_manager' not in roles(user):
        return set()
    return set(db.scalars(select(Store.id).where(Store.manager_id==user.id)).all())

def require_store(db: Session, store_id: int) -> Store:
    row = db.get(Store, store_id)
    if not row:
        raise HTTPException(422, 'Choose a store')
    return row

def event(db: Session, action: str, actor: User | None = None, request: StoreRequest | None = None, lot: StoreLot | None = None, store_row: Store | None = None, notes: str | None = None):
    db.add(StoreEvent(action=action, actor_id=actor.id if actor else None, request_id=request.id if request else None, lot_id=lot.id if lot else None, store_id=store_row.id if store_row else (lot.store_id if lot else request.store_id if request else None), notes=notes))

def store_data(db: Session, row: Store):
    manager=db.get(User,row.manager_id) if row.manager_id else None
    return {'id':row.id,'name':row.name,'location':row.location,'description':row.description,'manager_id':row.manager_id,
            'manager_name':manager.full_name if manager else None,'review_status':row.review_status,'revision':row.revision,
            'accepted_at':row.accepted_at,'created_at':row.created_at}

def item_data(item: StoreItem):
    return {'id': item.id, 'name': item.name, 'category': item.category, 'kind': item.kind, 'unit': item.unit, 'description': item.description}

def lot_data(db: Session, lot: StoreLot):
    item = db.get(StoreItem, lot.item_id)
    store_row = db.get(Store, lot.store_id)
    return {'id': lot.id, 'item': item_data(item), 'store_id': lot.store_id, 'store_name': store_row.name,
            'quantity': lot.quantity, 'available': lot.available, 'status': lot.status, 'purchase_reference': lot.purchase_reference,
            'supplier': lot.supplier, 'received_by': db.get(User, lot.received_by_id).full_name,
            'accepted_by': db.get(User, lot.accepted_by_id).full_name if lot.accepted_by_id else None,
            'created_at': lot.created_at, 'accepted_at': lot.accepted_at}

def request_data(db: Session, request: StoreRequest, public: bool = False):
    store_row = db.get(Store, request.store_id)
    lines = db.scalars(select(StoreRequestLine).where(StoreRequestLine.request_id == request.id)).all()
    data = {'reference': request.reference, 'requester_name': request.requester_name, 'department': request.department,
            'purpose': request.purpose, 'kind': request.kind, 'requester_position':request.requester_position,'status': request.status,
            'store_id': request.store_id, 'store_name': store_row.name if store_row else None,
            'chair_name': request.chair_name, 'created_at': request.created_at, 'issued_at': request.issued_at,
            'chair_id': request.chair_id,
            'assigned_manager_id': request.assigned_manager_id,
            'assigned_manager_name': db.get(User,request.assigned_manager_id).full_name if request.assigned_manager_id else None,
            'due_at': request.due_at, 'notes': request.notes,
            'authorized_by': db.get(User,request.dean_id).full_name if request.dean_id else db.get(User,request.assigned_by_id).full_name if request.assigned_by_id else None,
            'lines': [{**item_data(db.get(StoreItem, line.item_id)), 'quantity': line.quantity, 'returned': line.returned} for line in lines]}
    if not public:
        data.update({'id': request.id, 'requester_contact': request.requester_contact,
                     'has_signed_document': bool(request.signed_document),
                     'events': [{'action': row.action, 'actor': db.get(User, row.actor_id).full_name if row.actor_id else 'Requester',
                                 'notes': row.notes, 'created_at': row.created_at} for row in db.scalars(
                                     select(StoreEvent).where(StoreEvent.request_id == request.id).order_by(StoreEvent.id)).all()]})
    return data

class ItemIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=80)
    kind: Literal['consumable', 'durable']
    unit: str = Field(default='each', min_length=1, max_length=40)
    description: str | None = None

class StoreIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=150)
    description: str | None = None

class AssignIn(BaseModel):
    manager_id: int

class ReviewIn(BaseModel):
    accepted: bool
    checked_lot_ids: list[int] = Field(default_factory=list)
    notes: str | None = None

class MaterialIn(ItemIn):
    quantity: int = Field(gt=0)
    purchase_reference: str = Field(min_length=2, max_length=120)
    supplier: str | None = None

class LotIn(BaseModel):
    item_id: int
    store_id: int
    quantity: int = Field(gt=0)
    purchase_reference: str = Field(min_length=2, max_length=120)
    supplier: str | None = None

class LineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)

class RequestIn(BaseModel):
    requester_name: str = Field(min_length=2, max_length=150)
    requester_contact: str = Field(min_length=3, max_length=160)
    department: str = Field(min_length=2, max_length=150)
    purpose: str = Field(min_length=3)
    kind: Literal['consumable', 'durable']
    requester_position: Literal['staff', 'chair', 'dean'] = 'staff'
    chair_id: int | None = None
    store_id: int
    lines: list[LineIn] = Field(min_length=1)

class DecisionIn(BaseModel):
    approve: bool
    notes: str | None = None

class IssueIn(BaseModel):
    paper_verified: bool
    borrower_verified: bool = False
    due_at: datetime | None = None
    notes: str | None = None

class ReturnIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)
    notes: str | None = None

class DocumentIn(BaseModel):
    filename: str
    content_base64: str

@store.get('/stores')
def list_stores(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}): raise HTTPException(403,'Store access required')
    query=select(Store).order_by(Store.name)
    if 'store_manager' in roles(user) and not roles(user).intersection(STORE_ROLES):
        query=query.where(Store.manager_id==user.id)
    return [store_data(db,row) for row in db.scalars(query)]

@store.get('/managers')
def store_managers(db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    return [{'id':row.id,'full_name':row.full_name,'email':row.email} for row in db.scalars(select(User).where(User.is_active==True).order_by(User.full_name)).all() if 'store_manager' in roles(row)]

@store.post('/stores', status_code=201)
def create_store(payload: StoreIn, db: Session = Depends(get_db), user: User = Depends(require_roles('coordinator','super_admin'))):
    name=payload.name.strip()
    if db.scalar(select(Store).where(func.lower(Store.name)==name.lower())): raise HTTPException(409,'Store name already exists')
    row=Store(name=name,location=payload.location.strip(),description=payload.description,created_by_id=user.id,review_status='unassigned',revision=1)
    db.add(row);db.flush();event(db,'store_created',user,store_row=row)
    db.add(AuditLog(actor_id=user.id,action='created',entity='store',entity_id=row.id))
    db.commit();db.refresh(row);return store_data(db,row)

@store.post('/stores/{store_id}/assign')
def assign_store(store_id:int,payload:AssignIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    row=require_store(db,store_id)
    if not db.scalar(select(StoreLot.id).where(StoreLot.store_id==store_id,StoreLot.status!='rejected').limit(1)):
        raise HTTPException(409,'Record the store materials before assigning a store man')
    manager=db.get(User,payload.manager_id)
    if not manager or not manager.is_active or 'store_manager' not in roles(manager): raise HTTPException(422,'Choose an active store man')
    if row.manager_id==manager.id and row.review_status=='pending': raise HTTPException(409,'Store assignment is already awaiting acceptance')
    if row.manager_id: row.revision+=1
    row.manager_id=manager.id;row.review_status='pending';row.accepted_by_id=None;row.accepted_at=None
    event(db,'store_assigned',user,store_row=row,notes=f'Assigned to {manager.full_name}; revision {row.revision}')
    for request in db.scalars(select(StoreRequest).where(StoreRequest.store_id==row.id,StoreRequest.kind=='consumable',StoreRequest.status=='ready')).all():
        request.assigned_manager_id=manager.id
        event(db,'request_reassigned_to_store_man',user,request=request,notes=f'{row.name} · {manager.full_name}')
    db.commit();return store_data(db,row)

@store.post('/stores/{store_id}/review')
def review_store(store_id:int,payload:ReviewIn,db:Session=Depends(get_db),user:User=Depends(require_roles('store_manager'))):
    row=require_store(db,store_id)
    if row.manager_id!=user.id: raise HTTPException(403,'This store is not assigned to you')
    if row.review_status != 'pending': raise HTTPException(409,'No store handover is pending')
    lots=db.scalars(select(StoreLot).where(StoreLot.store_id==row.id,StoreLot.status.in_(['pending','accepted'])).order_by(StoreLot.id)).all()
    if not lots: raise HTTPException(409,'No materials are recorded for this store')
    if payload.accepted and (len(payload.checked_lot_ids)!=len(lots) or set(payload.checked_lot_ids)!={lot.id for lot in lots}):
        raise HTTPException(422,'Check every recorded material before accepting the store')
    if not payload.accepted and not (payload.notes or '').strip(): raise HTTPException(422,'Describe the inventory discrepancy')
    row.review_status='accepted' if payload.accepted else 'rejected'
    if payload.accepted:
        row.accepted_by_id=user.id;row.accepted_at=datetime.now(timezone.utc)
        for lot in lots:
            if lot.status!='pending': continue
            lot.status='accepted';lot.available=lot.quantity;lot.accepted_by_id=user.id;lot.accepted_at=row.accepted_at
            db.add(StoreMovement(store_id=row.id,item_id=lot.item_id,lot_id=lot.id,actor_id=user.id,action='receipt',quantity=lot.quantity))
            event(db,'accepted_delivery',user,lot=lot)
    event(db,'store_accepted' if payload.accepted else 'store_rejected',user,store_row=row,
          notes=payload.notes or f'Checked {len(lots)} material delivery records')
    db.commit();return store_data(db,row)

@store.get('/public/catalog')
def catalog(db: Session = Depends(get_db)):
    stores = db.scalars(select(Store).where(Store.review_status=='accepted').order_by(Store.name)).all()
    items=[]
    for row in stores:
        for lot in db.scalars(select(StoreLot).where(StoreLot.store_id==row.id,StoreLot.status=='accepted',StoreLot.available>0)).all():
            existing=next((item for item in items if item['store_id']==row.id and item['id']==lot.item_id),None)
            if existing: existing['available']+=lot.available
            else: items.append({**item_data(db.get(StoreItem,lot.item_id)),'store_id':row.id,'available':lot.available})
    chairs=[{'id':row.id,'name':row.full_name} for row in db.scalars(select(User).where(User.is_active==True).order_by(User.full_name)).all() if 'chair' in roles(row)]
    return {'stores':[{'id':row.id,'name':row.name,'location':row.location} for row in stores], 'items':items, 'chairs':chairs}

@store.post('/public/requests', status_code=201)
def create_request(payload: RequestIn, db: Session = Depends(get_db)):
    row=require_store(db,payload.store_id)
    if row.review_status!='accepted' or not row.manager_id: raise HTTPException(409,'Store is not yet open for requests')
    if payload.kind=='consumable' and payload.requester_position=='staff':
        chair=db.get(User,payload.chair_id) if payload.chair_id else None
        if not chair or not chair.is_active or 'chair' not in roles(chair): raise HTTPException(422,'Choose the responsible chair')
    if len({line.item_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(422, 'List each material once')
    for line in payload.lines:
        item = db.get(StoreItem, line.item_id)
        if not item or item.kind != payload.kind:
            raise HTTPException(422, 'Choose materials of the selected type')
        available=db.scalar(select(func.coalesce(func.sum(StoreLot.available),0)).where(StoreLot.store_id==row.id,StoreLot.item_id==line.item_id,StoreLot.status=='accepted')) or 0
        if line.quantity>available: raise HTTPException(409,f'Only {available} {item.unit} of {item.name} available')
    stage='ready' if payload.kind=='durable' else {'staff':'chair_review','chair':'dean_review','dean':'coordinator_review'}[payload.requester_position]
    request = StoreRequest(reference='WS-' + secrets.token_hex(6).upper(), requester_name=payload.requester_name.strip(),
        requester_contact=payload.requester_contact.strip(), department=payload.department.strip(), purpose=payload.purpose.strip(),
        kind=payload.kind,requester_position=payload.requester_position,chair_id=payload.chair_id if stage=='chair_review' else None,
        status=stage,store_id=row.id,facility_id=None)
    db.add(request); db.flush()
    for line in payload.lines:
        db.add(StoreRequestLine(request_id=request.id, item_id=line.item_id, quantity=line.quantity, returned=0))
    event(db, 'submitted', request=request)
    db.commit(); db.refresh(request)
    return request_data(db, request, public=True)

@store.get('/public/requests/{reference}')
def track_request(reference: str, db: Session = Depends(get_db)):
    request = db.scalar(select(StoreRequest).where(StoreRequest.reference == reference.strip().upper()))
    if not request:
        raise HTTPException(404, 'Request number not found')
    return request_data(db, request, public=True)

@store.get('/items')
def items(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}): raise HTTPException(403,'Store access required')
    return [item_data(i) for i in db.scalars(select(StoreItem).order_by(StoreItem.name))]

@store.post('/items', status_code=201)
def add_item(payload: ItemIn, db: Session = Depends(get_db), user: User = Depends(require_roles('coordinator','super_admin'))):
    item = StoreItem(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return item_data(item)

@store.post('/stores/{store_id}/materials', status_code=201)
def record_material(store_id:int,payload:MaterialIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    row=require_store(db,store_id)
    name=payload.name.strip()
    existing=db.scalars(select(StoreLot).join(StoreItem,StoreLot.item_id==StoreItem.id).where(
        StoreLot.store_id==store_id,func.lower(StoreItem.name)==name.lower(),StoreLot.status!='rejected')).first()
    if existing: raise HTTPException(409,'This material is already recorded in the store; add a delivery to increase its quantity')
    item=StoreItem(name=name,category=payload.category.strip(),kind=payload.kind,unit=payload.unit.strip(),description=payload.description)
    db.add(item);db.flush()
    lot=StoreLot(item_id=item.id,store_id=store_id,facility_id=None,quantity=payload.quantity,available=0,
                 status='pending',purchase_reference=payload.purchase_reference.strip(),supplier=payload.supplier,received_by_id=user.id)
    db.add(lot);db.flush()
    event(db,'material_recorded',user,lot=lot,notes=f'{payload.quantity} {item.unit} · {payload.purchase_reference}')
    db.add(AuditLog(actor_id=user.id,action='created',entity='store_material',entity_id=lot.id))
    db.commit();return lot_data(db,lot)

@store.get('/lots')
def lots(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        raise HTTPException(403, 'Store access required')
    allowed = managed_stores(db, user)
    query = select(StoreLot).order_by(StoreLot.id.desc())
    if not roles(user).intersection(STORE_ROLES):
        query = query.where(StoreLot.store_id.in_(allowed))
    return [lot_data(db, lot) for lot in db.scalars(query)]

@store.post('/lots', status_code=201)
def add_lot(payload: LotIn, db: Session = Depends(get_db), user: User = Depends(require_roles('coordinator','super_admin'))):
    row=require_store(db,payload.store_id)
    if not db.get(StoreItem, payload.item_id):
        raise HTTPException(422, 'Unknown material')
    if not db.scalar(select(StoreLot.id).where(StoreLot.store_id==row.id,StoreLot.item_id==payload.item_id).limit(1)):
        raise HTTPException(422,'Record this material in the selected store first')
    lot = StoreLot(**payload.model_dump(), facility_id=None,available=0, status='pending', received_by_id=user.id)
    db.add(lot); db.flush(); event(db, 'received_from_purchase', user, lot=lot, notes=payload.purchase_reference)
    db.commit(); db.refresh(lot)
    return lot_data(db, lot)

@store.post('/lots/{lot_id}/accept')
def accept_lot(lot_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    lot = db.get(StoreLot, lot_id)
    if not lot or lot.store_id not in managed_stores(db, user):
        raise HTTPException(404, 'Delivery not found in your stores')
    if require_store(db,lot.store_id).review_status!='accepted': raise HTTPException(409,'Accept the store handover first')
    if lot.status != 'pending':
        raise HTTPException(409, 'Delivery already reviewed')
    lot.status='accepted'; lot.available=lot.quantity; lot.accepted_by_id=user.id; lot.accepted_at=datetime.now(timezone.utc)
    db.add(StoreMovement(store_id=lot.store_id,item_id=lot.item_id,lot_id=lot.id,actor_id=user.id,action='receipt',quantity=lot.quantity))
    event(db, 'accepted_delivery', user, lot=lot); db.commit(); db.refresh(lot)
    return lot_data(db, lot)

@store.post('/lots/{lot_id}/reject')
def reject_lot(lot_id: int, decision: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    lot = db.get(StoreLot, lot_id)
    if not lot or lot.store_id not in managed_stores(db, user):
        raise HTTPException(404, 'Delivery not found in your stores')
    if lot.status != 'pending':
        raise HTTPException(409, 'Delivery already reviewed')
    lot.status='rejected'; event(db, 'rejected_delivery', user, lot=lot, notes=decision.notes)
    db.commit(); return lot_data(db, lot)

@store.get('/requests')
def requests(skip: int = 0, limit: int = Query(25, ge=1, le=100), store_id:int|None=None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(REQUEST_ROLES):
        raise HTTPException(403, 'Store access required')
    query = select(StoreRequest)
    if store_id: query=query.where(StoreRequest.store_id==store_id)
    if 'chair' in roles(user) and not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        query=query.where(StoreRequest.chair_id==user.id)
    elif not roles(user).intersection(STORE_ROLES):
        managed=StoreRequest.store_id.in_(managed_stores(db,user))
        manager_queue=and_(managed,or_(StoreRequest.kind=='durable',StoreRequest.status=='issued',
            and_(StoreRequest.status=='ready',or_(StoreRequest.assigned_manager_id==user.id,StoreRequest.assigned_manager_id.is_(None)))))
        chair_queue=and_(StoreRequest.chair_id==user.id,StoreRequest.status=='chair_review') if 'chair' in roles(user) else None
        query=query.where(or_(manager_queue,chair_queue) if chair_queue is not None else manager_queue)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if 'chair' in roles(user) and not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        query=query.order_by(case((StoreRequest.status=='chair_review',0),else_=1),StoreRequest.id.desc())
    else: query=query.order_by(StoreRequest.id.desc())
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    return {'data': [request_data(db, row) for row in rows], 'meta': {'total': total, 'skip': skip, 'limit': limit}}

@store.get('/loans/overdue')
def overdue_loans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        raise HTTPException(403, 'Store access required')
    query = select(StoreRequest).where(StoreRequest.status == 'borrowed', StoreRequest.due_at < datetime.now(timezone.utc))
    if not roles(user).intersection(STORE_ROLES):
        query = query.where(StoreRequest.store_id.in_(managed_stores(db, user)))
    return [{'reference': row.reference, 'requester_name': row.requester_name,
             'requester_contact': row.requester_contact, 'due_at': row.due_at,
             'store_name': db.get(Store, row.store_id).name} for row in db.scalars(query.order_by(StoreRequest.due_at)).all()]

@store.get('/loans')
def loans(status: Literal['active', 'overdue', 'returned', 'all'] = 'active', skip: int = 0,
          limit: int = 25, store_id: int | None = None,
          db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        raise HTTPException(403, 'Store access required')
    if skip < 0 or limit < 1 or limit > 100: raise HTTPException(422, 'Invalid loan page')
    allowed = managed_stores(db, user)
    if store_id:
        require_store(db, store_id)
        if not roles(user).intersection(STORE_ROLES) and store_id not in allowed:
            raise HTTPException(403, 'Not your store')
    query = select(StoreRequest).where(StoreRequest.kind == 'durable', StoreRequest.status.in_(['borrowed', 'returned']))
    if store_id: query = query.where(StoreRequest.store_id == store_id)
    elif not roles(user).intersection(STORE_ROLES): query = query.where(StoreRequest.store_id.in_(allowed))
    now = datetime.now(timezone.utc)
    if status == 'active': query = query.where(StoreRequest.status == 'borrowed')
    elif status == 'overdue': query = query.where(StoreRequest.status == 'borrowed', StoreRequest.due_at < now)
    elif status == 'returned': query = query.where(StoreRequest.status == 'returned')
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(StoreRequest.id.desc()).offset(skip).limit(limit)).all()
    return {'data': [request_data(db, row) for row in rows], 'meta': {'total': total, 'skip': skip, 'limit': limit}}

@store.get('/stores/{store_id}/history')
def store_history(store_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require_store(db,store_id)
    if not roles(user).intersection(STORE_ROLES) and store_id not in managed_stores(db,user): raise HTTPException(403,'Not your store')
    rows=db.scalars(select(StoreEvent).where(StoreEvent.store_id==store_id).order_by(StoreEvent.id.desc()).limit(100)).all()
    return [{'action':row.action,'notes':row.notes,'actor':db.get(User,row.actor_id).full_name if row.actor_id else 'Requester','created_at':row.created_at} for row in rows]

@store.get('/report')
def report(store_id:int|None=None,start:date|None=None,end:date|None=None,movement_skip:int=0,movement_limit:int=25,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES|{'store_manager'}): raise HTTPException(403,'Store access required')
    if start and end and start>end: raise HTTPException(422,'Start date must precede end date')
    if movement_skip<0 or movement_limit<1 or movement_limit>100: raise HTTPException(422,'Invalid movement page')
    allowed=managed_stores(db,user)
    if store_id:
        require_store(db,store_id)
        if not roles(user).intersection(STORE_ROLES) and store_id not in allowed: raise HTTPException(403,'Not your store')
        store_ids={store_id}
    elif roles(user).intersection(STORE_ROLES):
        store_ids=set(db.scalars(select(Store.id)).all())
    else: store_ids=allowed
    lots=db.scalars(select(StoreLot).where(StoreLot.store_id.in_(store_ids))).all()
    requests=db.scalars(select(StoreRequest).where(StoreRequest.store_id.in_(store_ids))).all()
    moves=db.scalars(select(StoreMovement).where(StoreMovement.store_id.in_(store_ids)).order_by(StoreMovement.id.desc())).all()
    if start: moves=[m for m in moves if m.created_at.date()>=start]
    if end: moves=[m for m in moves if m.created_at.date()<=end]
    period_requests=[r for r in requests if (not start or r.created_at.date()>=start) and (not end or r.created_at.date()<=end)]
    active_lots=[lot for lot in lots if lot.status=='accepted']
    by_item={}
    for lot in active_lots:
        item=db.get(StoreItem,lot.item_id)
        key=(lot.store_id,item.id)
        row=by_item.setdefault(key,{'store_id':lot.store_id,'store_name':db.get(Store,lot.store_id).name,'item_id':item.id,'name':item.name,'kind':item.kind,'unit':item.unit,'available':0,'received':0,'issued':0,'returned':0})
        row['available']+=lot.available
    for movement in moves:
        item=db.get(StoreItem,movement.item_id)
        key=(movement.store_id,item.id)
        row=by_item.setdefault(key,{'store_id':movement.store_id,'store_name':db.get(Store,movement.store_id).name,'item_id':item.id,'name':item.name,'kind':item.kind,'unit':item.unit,'available':0,'received':0,'issued':0,'returned':0})
        row[{'receipt':'received','issue':'issued','return':'returned'}[movement.action]]+=movement.quantity
    now=datetime.now(timezone.utc)
    overdue=[r for r in requests if r.status=='borrowed' and r.due_at and r.due_at.replace(tzinfo=timezone.utc) < now]
    stages={}
    for row in period_requests: stages[row.status]=stages.get(row.status,0)+1
    return {'summary':{'stores':len(store_ids),'on_hand':sum(lot.available for lot in active_lots),
        'received':sum(m.quantity for m in moves if m.action=='receipt'),
        'consumed':sum(m.quantity for m in moves if m.action=='issue' and db.get(StoreItem,m.item_id).kind=='consumable'),
        'lent':sum(m.quantity for m in moves if m.action=='issue' and db.get(StoreItem,m.item_id).kind=='durable'),
        'returned':sum(m.quantity for m in moves if m.action=='return'),
        'outstanding_loans':sum(line.quantity-line.returned for row in requests if row.status=='borrowed' for line in db.scalars(select(StoreRequestLine).where(StoreRequestLine.request_id==row.id))),
        'overdue':len(overdue),'requests':len(period_requests)},
        'stages':stages,'items':sorted(by_item.values(),key=lambda row:(row['store_name'],row['name'])),
        'movements_meta':{'total':len(moves),'skip':movement_skip,'limit':movement_limit},
        'movements':[{'id':m.id,'store_name':db.get(Store,m.store_id).name,'item_name':db.get(StoreItem,m.item_id).name,'action':m.action,'quantity':m.quantity,
                      'actor':db.get(User,m.actor_id).full_name,'reference':db.get(StoreRequest,m.request_id).reference if m.request_id else db.get(StoreLot,m.lot_id).purchase_reference,
                      'borrower':db.get(StoreRequest,m.request_id).requester_name if m.request_id and db.get(StoreRequest,m.request_id).kind=='durable' else None,
                      'created_at':m.created_at} for m in moves[movement_skip:movement_skip+movement_limit]]}

def transition(db: Session, request_id: int, expected: str, user: User) -> StoreRequest:
    request = db.get(StoreRequest, request_id)
    if not request:
        raise HTTPException(404, 'Request not found')
    if request.status != expected:
        raise HTTPException(409, f'Request is {request.status}; refresh the list')
    return request

@store.post('/requests/{request_id}/chair')
def chair_review(request_id: int, decision: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles('chair'))):
    request = transition(db, request_id, 'chair_review', user)
    if request.kind != 'consumable': raise HTTPException(409, 'Chair review applies to consumables')
    if request.chair_id != user.id: raise HTTPException(403,'This request belongs to another chair')
    if not decision.approve: raise HTTPException(422,'Chair can only confirm and send a request to the dean')
    request.status = 'dean_review'
    request.chair_name = user.full_name; request.notes = decision.notes
    event(db, 'chair_confirmed', user, request, notes=decision.notes)
    db.commit(); return request_data(db, request)

def assign_approved_request(db:Session,request:StoreRequest,actor:User):
    store_row=require_store(db,request.store_id)
    manager=db.get(User,store_row.manager_id) if store_row.manager_id else None
    if store_row.review_status!='accepted' or not manager or not manager.is_active or 'store_manager' not in roles(manager):
        raise HTTPException(409,'The requested store needs an active, accepted store man before confirmation')
    for line in db.scalars(select(StoreRequestLine).where(StoreRequestLine.request_id==request.id)).all():
        available=db.scalar(select(func.coalesce(func.sum(StoreLot.available),0)).where(
            StoreLot.store_id==store_row.id,StoreLot.item_id==line.item_id,StoreLot.status=='accepted')) or 0
        if available<line.quantity: raise HTTPException(409,f'Insufficient accepted stock for {db.get(StoreItem,line.item_id).name}')
    request.assigned_manager_id=manager.id
    request.assigned_by_id=actor.id
    return store_row,manager

@store.post('/requests/{request_id}/dean')
def dean_review(request_id: int, decision: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles('dean'))):
    request = transition(db, request_id, 'dean_review', user)
    if request.chair_id==user.id: raise HTTPException(403,'The chair who confirmed this request cannot approve it as dean')
    if not decision.approve and not (decision.notes or '').strip(): raise HTTPException(422,'Give a rejection reason')
    assignment=assign_approved_request(db,request,user) if decision.approve else None
    request.status = 'ready' if decision.approve else 'rejected'
    request.dean_id = user.id; request.notes = decision.notes
    if assignment:
        store_row,manager=assignment
        event(db,'dean_confirmed_and_sent_to_store_man',user,request,
              notes=f'{store_row.name} · {manager.full_name}' + (f' · {decision.notes}' if decision.notes else ''))
    else: event(db,'dean_rejected',user,request,notes=decision.notes)
    db.commit(); return request_data(db, request)

@store.post('/requests/{request_id}/coordinator')
def coordinator_review(request_id:int,decision:DecisionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    request=transition(db,request_id,'coordinator_review',user)
    if not decision.approve and not (decision.notes or '').strip(): raise HTTPException(422,'Give a rejection reason')
    assignment=assign_approved_request(db,request,user) if decision.approve else None
    request.status='ready' if decision.approve else 'rejected'
    request.notes=decision.notes
    if assignment:
        store_row,manager=assignment
        event(db,'coordinator_confirmed_and_sent_to_store_man',user,request,
              notes=f'{store_row.name} · {manager.full_name}' + (f' · {decision.notes}' if decision.notes else ''))
    else: event(db,'coordinator_rejected',user,request,notes=decision.notes)
    db.commit();return request_data(db,request)

@store.post('/requests/{request_id}/workshop')
def workshop_review(request_id: int, decision: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    request = transition(db, request_id, 'workshop_review', user)
    if request.store_id not in managed_stores(db, user): raise HTTPException(403, 'Not your store')
    request.status = 'ready' if decision.approve else 'rejected'; request.notes = decision.notes
    event(db, 'workshop_approved' if decision.approve else 'workshop_rejected', user, request, notes=decision.notes)
    db.commit(); return request_data(db, request)

@store.post('/requests/{request_id}/issue')
def issue(request_id: int, payload: IssueIn, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    request = transition(db, request_id, 'ready', user)
    if request.store_id not in managed_stores(db, user): raise HTTPException(403, 'Not your store')
    if request.kind=='consumable' and request.assigned_manager_id and request.assigned_manager_id!=user.id:
        raise HTTPException(403,'This request was sent to another store man')
    if require_store(db,request.store_id).review_status!='accepted': raise HTTPException(409,'Accept the store handover first')
    if request.kind == 'consumable' and not payload.paper_verified:
        raise HTTPException(422, 'Verify the signed paper before issuing consumables')
    if request.kind == 'durable' and (not payload.due_at or payload.due_at <= datetime.now(timezone.utc)):
        raise HTTPException(422, 'Enter a future return date')
    if request.kind == 'durable' and not payload.borrower_verified:
        raise HTTPException(422, 'Confirm the borrower name and contact at handover')
    lines = db.scalars(select(StoreRequestLine).where(StoreRequestLine.request_id == request.id)).all()
    allocations = []
    for line in lines:
        remaining = line.quantity
        lots = db.scalars(select(StoreLot).where(StoreLot.store_id == request.store_id,
            StoreLot.item_id == line.item_id, StoreLot.status == 'accepted', StoreLot.available > 0).order_by(StoreLot.id)).all()
        if sum(lot.available for lot in lots) < remaining:
            raise HTTPException(409, f'Insufficient accepted stock for {db.get(StoreItem, line.item_id).name}')
        for lot in lots:
            used = min(remaining, lot.available)
            if used: allocations.append((line.id, lot.id, used)); remaining -= used
            if not remaining: break
    for line_id, lot_id, quantity in allocations:
        updated = db.execute(update(StoreLot).where(StoreLot.id == lot_id, StoreLot.available >= quantity)
            .values(available=StoreLot.available - quantity))
        if updated.rowcount != 1:
            db.rollback(); raise HTTPException(409, 'Stock changed; refresh and try again')
        db.add(StoreAllocation(line_id=line_id, lot_id=lot_id, quantity=quantity, returned=0))
        lot=db.get(StoreLot,lot_id)
        db.add(StoreMovement(store_id=request.store_id,item_id=lot.item_id,lot_id=lot_id,request_id=request.id,actor_id=user.id,action='issue',quantity=quantity))
        event(db, 'issued_stock', user, request, lot, notes=f'{quantity} units')
    request.status = 'issued' if request.kind == 'consumable' else 'borrowed'
    request.issued_by_id = user.id; request.issued_at = datetime.now(timezone.utc); request.due_at = payload.due_at
    event(db, 'issued' if request.kind == 'consumable' else 'borrowed', user, request,
          notes=payload.notes if request.kind == 'consumable' else
          f'Borrower {request.requester_name} ({request.requester_contact}); due {payload.due_at.isoformat()}' +
          (f'; {payload.notes}' if payload.notes else ''))
    db.commit(); return request_data(db, request)

@store.post('/requests/{request_id}/return')
def return_item(request_id: int, payload: ReturnIn, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    request = transition(db, request_id, 'borrowed', user)
    if request.store_id not in managed_stores(db, user): raise HTTPException(403, 'Not your store')
    line = db.scalar(select(StoreRequestLine).where(StoreRequestLine.request_id == request.id, StoreRequestLine.item_id == payload.item_id))
    if not line or payload.quantity > line.quantity - line.returned:
        raise HTTPException(422, 'Return quantity exceeds outstanding quantity')
    remaining = payload.quantity
    allocations = db.scalars(select(StoreAllocation).where(StoreAllocation.line_id == line.id).order_by(StoreAllocation.id)).all()
    for allocation in allocations:
        quantity = min(remaining, allocation.quantity - allocation.returned)
        if not quantity: continue
        lot = db.get(StoreLot, allocation.lot_id)
        if not lot: raise HTTPException(409, 'Original delivery lot missing')
        allocation.returned += quantity; lot.available += quantity; remaining -= quantity
        db.add(StoreMovement(store_id=request.store_id,item_id=lot.item_id,lot_id=lot.id,request_id=request.id,actor_id=user.id,action='return',quantity=quantity))
        event(db, 'returned_stock', user, request, lot, notes=f'{quantity} units. {payload.notes or ""}')
        if not remaining: break
    if remaining: raise HTTPException(409, 'Issue allocation is incomplete')
    line.returned += payload.quantity
    lines = db.scalars(select(StoreRequestLine).where(StoreRequestLine.request_id == request.id)).all()
    if all(row.returned == row.quantity for row in lines):
        request.status = 'returned'; event(db, 'return_complete', user, request)
    db.commit(); return request_data(db, request)

@store.post('/requests/{request_id}/signed-document')
def signed_document(request_id: int, payload: DocumentIn, db: Session = Depends(get_db), user: User = Depends(require_roles('store_manager'))):
    request = db.get(StoreRequest, request_id)
    if not request or request.store_id not in managed_stores(db, user): raise HTTPException(404, 'Request not found')
    if request.kind != 'consumable' or request.status not in {'ready', 'issued'}:
        raise HTTPException(409, 'Signed form upload is for confirmed consumable requests')
    suffix = Path(payload.filename).suffix.lower()
    if suffix not in {'.jpg', '.jpeg', '.png', '.pdf'}: raise HTTPException(422, 'Upload a JPG, PNG, or PDF')
    try: content = base64.b64decode(payload.content_base64, validate=True)
    except (ValueError, binascii.Error): raise HTTPException(422, 'Invalid file')
    if len(content) > 5_000_000 or not content: raise HTTPException(422, 'File must be under 5 MB')
    valid = (suffix == '.pdf' and content.startswith(b'%PDF-')) or (suffix == '.png' and content.startswith(b'\x89PNG')) or (suffix in {'.jpg','.jpeg'} and content.startswith(b'\xff\xd8'))
    if not valid: raise HTTPException(422, 'File content does not match its type')
    UPLOADS.mkdir(parents=True, exist_ok=True)
    path = UPLOADS / f'{request.reference}-{secrets.token_hex(4)}{suffix}'
    path.write_bytes(content); request.signed_document = path.name
    event(db, 'signed_paper_uploaded', user, request); db.commit()
    return {'uploaded': True}

@store.get('/requests/{request_id}/signed-document')
def get_signed_document(request_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not roles(user).intersection(STORE_ROLES | {'store_manager'}):
        raise HTTPException(403, 'Store access required')
    request = db.get(StoreRequest, request_id)
    if not request or not request.signed_document: raise HTTPException(404, 'Document not found')
    if not roles(user).intersection(STORE_ROLES) and request.store_id not in managed_stores(db, user):
        raise HTTPException(403, 'Not your store')
    path = UPLOADS / Path(request.signed_document).name
    if not path.is_file(): raise HTTPException(404, 'Document not found')
    return FileResponse(path)
