from datetime import date, datetime, time, timezone
from typing import Any, Type
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .core.security import create_token, hash_password, verify_password
from .dependencies import current_user, require_roles
from .core.database import get_db
from .models import Announcement, AuditLog, Equipment, EquipmentUsageRequest, Facility, FacilityResource, MaintenanceHistory, MaintenanceRequest, Project, Request, ResourceAsset, ResourceHistory, Role, Schedule, Status, User
from .schemas import AnnouncementIn, EquipmentIn, EquipmentUsageCreate, EquipmentUsageDecision, FacilityIn, FacilityResourceIn, FacilityResourceUpdate, Login, MaintenanceActionIn, MaintenanceAssignmentIn, MaintenanceIn, MaintenanceResolutionIn, MaintenanceVerificationIn, MaintenanceWorkflowCreate, PasswordChange, ProjectDecisionIn, ProjectRequestIn, ProjectUpdate, RequestIn, ResourceActionIn, ResourceReviewIn, ScheduleCreate, ScheduleUpdate, StatusUpdate, Token, UserCreate, UserOut, UserUpdate

api=APIRouter(prefix='/api/v1')
COORDINATOR_ROLES={'coordinator','super_admin'}
DEAN_ROLES={'dean'}
MANAGEMENT_ROLES=COORDINATOR_ROLES|DEAN_ROLES
OPERATIONAL_USER_ROLES={'lab_admin','maintainer'}
def has_any(user:User,names:set[str]): return bool({role.name for role in user.roles}.intersection(names))
def role_names(user:User): return {role.name for role in user.roles}
def audit(db:Session,actor:User|None,action:str,entity:str,entity_id:int|None=None):
    db.add(AuditLog(actor_id=actor.id if actor else None,action=action,entity=entity,entity_id=entity_id))
def added_by_name(db:Session,entity:str,entity_id:int):
    event=db.scalar(select(AuditLog).where(AuditLog.entity==entity,AuditLog.entity_id==entity_id,AuditLog.action=='created').order_by(AuditLog.created_at,AuditLog.id).limit(1))
    actor=db.get(User,event.actor_id) if event and event.actor_id else None
    return actor.full_name if actor else 'System'
def ensure_user_role_scope(actor:User,target_roles:set[str],target:User|None=None):
    if has_any(actor,DEAN_ROLES):
        if target_roles!={'coordinator'}: raise HTTPException(403,'Dean can only manage coordinator accounts')
    elif has_any(actor,COORDINATOR_ROLES):
        if not target_roles or not target_roles.issubset(OPERATIONAL_USER_ROLES): raise HTTPException(403,'Coordinator can only manage facility assistants and maintainers')
        if target and not role_names(target).issubset(OPERATIONAL_USER_ROLES): raise HTTPException(403,'This protected account cannot be changed from the coordinator workspace')
admin=Depends(require_roles('coordinator','super_admin','laboratory_manager','workshop_manager','lab_admin'))
def page(db:Session, model:Type[Any], skip:int, limit:int, search:str|None=None):
    q=select(model)
    if search and hasattr(model,'name'): q=q.where(model.name.ilike(f'%{search}%'))
    total=len(db.scalars(q).all()); rows=db.scalars(q.offset(skip).limit(limit)).all()
    return {'data':rows,'meta':{'total':total,'skip':skip,'limit':limit}}
def require_new_assistant_handover(db:Session,facility_id:int,actor:User,assistant:User):
    for resource in db.scalars(select(FacilityResource).where(FacilityResource.facility_id==facility_id,FacilityResource.archived.is_(False))).all():
        before=resource_snapshot(resource);resource.revision=(resource.revision or 1)+1;resource.review_status='pending';resource.review_notes=None;resource.accepted=False;resource.submitted_by_id=actor.id;resource.checked_by_id=None;resource.checked_at=None
        record_resource_history(db,resource,actor,'assigned_to_new_assistant',f'Handover assigned to {assistant.full_name}; acceptance is required after first password change',before,before)
@api.post('/auth/login',response_model=Token)
def login(payload:Login,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==payload.email))
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,'Incorrect email or password')
    if not user.is_active: raise HTTPException(401,'Your account is disabled. Please contact the system administrator.')
    return Token(access_token=create_token(str(user.id),[r.name for r in user.roles]),must_change_password=user.must_change_password)
@api.get('/auth/me')
def me(user:User=Depends(current_user),db:Session=Depends(get_db)):
    facility=db.get(Facility,user.assigned_facility_id) if user.assigned_facility_id else None
    return {'id':user.id,'email':user.email,'full_name':user.full_name,'is_active':user.is_active,'must_change_password':user.must_change_password,'assigned_facility_id':user.assigned_facility_id,'assigned_facility':{'id':facility.id,'name':facility.name,'kind':facility.kind,'location':facility.location,'capacity':facility.capacity} if facility else None,'role_names':[role.name for role in user.roles]}
@api.post('/auth/change-password',status_code=204)
def change_password(payload:PasswordChange,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not verify_password(payload.current_password,user.password_hash): raise HTTPException(400,'Current password is incorrect')
    user.password_hash=hash_password(payload.new_password);user.must_change_password=False;db.commit()
@api.get('/roles')
def roles(db:Session=Depends(get_db),user:User=Depends(require_roles('dean','coordinator','super_admin'))):
    if has_any(user,DEAN_ROLES): return db.scalars(select(Role).where(Role.name=='coordinator')).all()
    return db.scalars(select(Role).where(Role.name.in_(OPERATIONAL_USER_ROLES)).order_by(Role.name)).all()
@api.get('/users')
def users(skip:int=0,limit:int=Query(25,le=100),search:str|None=None,active:str='active',db:Session=Depends(get_db),user:User=Depends(require_roles('dean','coordinator','super_admin'))):
    all_users=db.scalars(select(User).order_by(User.full_name)).all()
    if has_any(user,DEAN_ROLES): all_users=[u for u in all_users if any(role.name=='coordinator' for role in u.roles)]
    elif has_any(user,COORDINATOR_ROLES): all_users=[u for u in all_users if role_names(u).issubset(OPERATIONAL_USER_ROLES)]
    if active=='active': all_users=[u for u in all_users if u.is_active]
    elif active=='disabled': all_users=[u for u in all_users if not u.is_active]
    query=(search or '').strip().lower()
    if query: all_users=[u for u in all_users if query in u.full_name.lower() or query in u.email.lower()]
    rows=all_users[skip:skip+limit]
    return {'data':[{'id':u.id,'email':u.email,'full_name':u.full_name,'is_active':u.is_active,'must_change_password':u.must_change_password,'assigned_facility_id':u.assigned_facility_id,'role_names':[r.name for r in u.roles],'added_by_name':added_by_name(db,'user',u.id)} for u in rows],'meta':{'total':len(all_users),'skip':skip,'limit':limit}}
@api.post('/users',response_model=UserOut,status_code=201)
def create_user(payload:UserCreate,db:Session=Depends(get_db),actor:User=Depends(require_roles('dean','coordinator','super_admin'))):
    ensure_user_role_scope(actor,set(payload.role_names))
    if db.scalar(select(User).where(User.email==payload.email)): raise HTTPException(409,'Email is already registered')
    roles=db.scalars(select(Role).where(Role.name.in_(payload.role_names))).all()
    if len(roles)!=len(set(payload.role_names)): raise HTTPException(422,'One or more roles are invalid')
    # Administrators may set a temporary password, otherwise use first-name + password.
    # Every provisioned account must update this initial credential on first login.
    if payload.assigned_facility_id:
        facility=db.get(Facility,payload.assigned_facility_id)
        if not facility: raise HTTPException(422,'Selected facility does not exist')
        if 'lab_admin' not in payload.role_names: raise HTTPException(422,'A facility can only be assigned to a facility assistant')
    default_password=f"{payload.full_name.strip().split()[0].lower()}password"
    user=User(email=payload.email,full_name=payload.full_name,password_hash=hash_password(payload.password or default_password),must_change_password=True,roles=roles); db.add(user);db.flush()
    if payload.assigned_facility_id:
        assigned=db.get(Facility,payload.assigned_facility_id)
        user.assigned_facility_id=assigned.id
        require_new_assistant_handover(db,assigned.id,actor,user)
    audit(db,actor,'created','user',user.id)
    db.commit();db.refresh(user);return user
@api.patch('/users/{user_id}',response_model=UserOut)
def update_user(user_id:int,payload:UserUpdate,db:Session=Depends(get_db),actor:User=Depends(require_roles('dean','coordinator','super_admin'))):
    user=db.get(User,user_id)
    if not user: raise HTTPException(404,'User not found')
    if has_any(actor,DEAN_ROLES):
        current=role_names(user);requested=set(payload.role_names) if payload.role_names is not None else current
        if current!={'coordinator'} or requested!={'coordinator'}: raise HTTPException(403,'Dean can only update coordinator accounts')
    previous_facility_id=user.assigned_facility_id
    data=payload.model_dump(exclude_unset=True)
    requested_role_names=data.pop('role_names',None)
    if requested_role_names is not None:
        ensure_user_role_scope(actor,set(requested_role_names),user)
        roles=db.scalars(select(Role).where(Role.name.in_(requested_role_names))).all()
        if len(roles)!=len(set(requested_role_names)): raise HTTPException(422,'One or more roles are invalid')
        user.roles=roles
    else: ensure_user_role_scope(actor,role_names(user),user)
    selected_facility_id=data.get('assigned_facility_id',user.assigned_facility_id)
    selected_role_names=requested_role_names if requested_role_names is not None else [role.name for role in user.roles]
    if selected_facility_id:
        facility=db.get(Facility,selected_facility_id)
        if not facility: raise HTTPException(422,'Selected facility does not exist')
        if 'lab_admin' not in selected_role_names: raise HTTPException(422,'A facility can only be assigned to a facility assistant')
    for managed in db.scalars(select(Facility).where(Facility.manager_id==user.id)).all(): managed.manager_id=None
    for key,value in data.items(): setattr(user,key,value)
    if selected_facility_id and selected_facility_id!=previous_facility_id: require_new_assistant_handover(db,selected_facility_id,actor,user)
    audit(db,actor,'updated','user',user.id)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Email is already registered')
    db.refresh(user);return user
@api.delete('/users/{user_id}',status_code=204)
def delete_user(user_id:int,db:Session=Depends(get_db),actor:User=Depends(require_roles('dean','coordinator','super_admin'))):
    if actor.id==user_id: raise HTTPException(400,'You cannot disable your own account')
    user=db.get(User,user_id)
    if not user: raise HTTPException(404,'User not found')
    if has_any(actor,DEAN_ROLES) and {role.name for role in user.roles}!={'coordinator'}: raise HTTPException(403,'Dean can only disable coordinator accounts')
    if has_any(actor,COORDINATOR_ROLES) and not role_names(user).issubset(OPERATIONAL_USER_ROLES): raise HTTPException(403,'This protected account cannot be disabled from the coordinator workspace')
    user.is_active=False
    audit(db,actor,'disabled','user',user.id);db.commit()
def crud(path:str,model:Type[Any],schema:Type[Any]):
    router=APIRouter(prefix=path,tags=[path.strip('/')])
    @router.get('')
    def list_items(skip:int=0,limit:int=Query(25,le=100),search:str|None=None,db:Session=Depends(get_db),_:User=Depends(current_user)):
        result=page(db,model,skip,limit,search)
        if model is Facility:
            result['data']=[{'id':item.id,'name':item.name,'kind':item.kind,'location':item.location,'capacity':item.capacity,'manager_id':item.manager_id,'created_at':item.created_at,'added_by_name':added_by_name(db,model.__tablename__,item.id)} for item in result['data']]
        return result
    @router.post('',status_code=201)
    def create_item(payload:schema,db:Session=Depends(get_db),user:User=admin):
        data=payload.model_dump();
        if model is Project: data['members']=[db.get(User,i) for i in data.pop('member_ids') if db.get(User,i)]
        if model is MaintenanceRequest: data['requester_id']=user.id
        if model is Request: data['requester_id']=user.id
        obj=model(**data);db.add(obj)
        db.flush();audit(db,user,'created',model.__tablename__,obj.id)
        try: db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'A record with this unique value already exists')
        db.refresh(obj);return obj
    @router.get('/{item_id}')
    def get_item(item_id:int,db:Session=Depends(get_db),_:User=Depends(current_user)):
        obj=db.get(model,item_id)
        if not obj: raise HTTPException(404,'Record not found')
        return obj
    @router.patch('/{item_id}')
    def update_item(item_id:int,payload:schema,db:Session=Depends(get_db),user:User=admin):
        obj=db.get(model,item_id)
        if not obj: raise HTTPException(404,'Record not found')
        data=payload.model_dump(exclude_unset=True)
        if model is Project and 'member_ids' in data: obj.members=[db.get(User,i) for i in data.pop('member_ids') if db.get(User,i)]
        for k,v in data.items(): setattr(obj,k,v)
        audit(db,user,'updated',model.__tablename__,obj.id)
        try: db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'A record with this unique value already exists')
        db.refresh(obj);return obj
    @router.delete('/{item_id}',status_code=204)
    def delete_item(item_id:int,db:Session=Depends(get_db),user:User=admin):
        obj=db.get(model,item_id)
        if not obj: raise HTTPException(404,'Record not found')
        audit(db,user,'deleted',model.__tablename__,obj.id);db.delete(obj);db.commit()
    return router
for path,model,schema in [('/facilities',Facility,FacilityIn),('/equipment',Equipment,EquipmentIn),('/maintenance',MaintenanceRequest,MaintenanceIn),('/requests',Request,RequestIn),('/announcements',Announcement,AnnouncementIn)]: api.include_router(crud(path,model,schema))

def project_payload(project:Project,db:Session):
    facility=db.get(Facility,project.facility_id) if project.facility_id else None
    requester=db.get(User,project.requested_by_id) if project.requested_by_id else None
    return {'id':project.id,'title':project.title,'description':project.description,'kind':project.kind,'stakeholder_name':project.stakeholder_name,'organization':project.organization,'contact_email':project.contact_email,'requested_by_id':project.requested_by_id,'requester_name':requester.full_name if requester else None,'approval_status':project.approval_status,'approval_notes':project.approval_notes,'approved_by_id':project.approved_by_id,'approved_at':project.approved_at,'status':project.status,'start_date':project.start_date,'end_date':project.end_date,'facility_id':project.facility_id,'facility_name':facility.name if facility else None,'created_at':project.created_at}
@api.get('/projects')
def list_projects(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(Project).order_by(Project.created_at.desc())).all();roles={role.name for role in user.roles}
    if not roles.intersection(MANAGEMENT_ROLES): rows=[row for row in rows if row.requested_by_id==user.id or row.approval_status=='approved']
    return {'data':[project_payload(row,db) for row in rows]}
@api.post('/projects',status_code=201)
def request_project(payload:ProjectRequestIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin','lab_admin'))):
    if payload.facility_id and not db.get(Facility,payload.facility_id): raise HTTPException(422,'Preferred facility does not exist')
    project=Project(**payload.model_dump(),requested_by_id=user.id,approval_status='pending',status='planned');db.add(project);db.flush();audit(db,user,'created','projects',project.id);db.commit();db.refresh(project);return project_payload(project,db)
@api.patch('/projects/{project_id}/decision')
def decide_project(project_id:int,payload:ProjectDecisionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('dean'))):
    project=db.get(Project,project_id)
    if not project: raise HTTPException(404,'Project request not found')
    if project.approval_status!='pending': raise HTTPException(409,'This project request has already been decided')
    project.approval_status=payload.decision;project.approval_notes=payload.notes;project.approved_by_id=user.id;project.approved_at=datetime.now(timezone.utc);audit(db,user,payload.decision,'projects',project.id);db.commit();db.refresh(project);return project_payload(project,db)
@api.patch('/projects/{project_id}')
def update_project(project_id:int,payload:ProjectUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    project=db.get(Project,project_id)
    if not project: raise HTTPException(404,'Project not found')
    for key,value in payload.model_dump(exclude_unset=True).items(): setattr(project,key,value)
    if project.start_date and project.end_date and project.end_date<project.start_date: raise HTTPException(422,'Project end date must be on or after its start date')
    audit(db,user,'updated','projects',project.id);db.commit();db.refresh(project);return project_payload(project,db)
@api.delete('/projects/{project_id}',status_code=204)
def delete_project(project_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    project=db.get(Project,project_id)
    if not project: raise HTTPException(404,'Project not found')
    if db.scalar(select(Schedule).where(Schedule.project_id==project.id).limit(1)): raise HTTPException(409,'Delete project schedules before deleting this project')
    audit(db,user,'deleted','projects',project.id);db.delete(project);db.commit()

def schedule_payload(item:Schedule,db:Session):
    facility=db.get(Facility,item.facility_id);project=db.get(Project,item.project_id) if item.project_id else None;instructor=db.get(User,item.instructor_id) if item.instructor_id else None
    days=item.schedule_days or [item.start_at.weekday()]
    period_start=item.period_start or item.start_at.date();period_end=item.period_end or item.end_at.date();time_from=item.time_from or item.start_at.time();time_to=item.time_to or item.end_at.time();display_start=datetime.combine(period_start,time_from);display_end=datetime.combine(period_start,time_to)
    state=schedule_state(item)
    return {'id':item.id,'title':item.title,'schedule_type':item.schedule_type,'facility_id':item.facility_id,'facility_name':facility.name if facility else None,'instructor_id':item.instructor_id,'instructor_name':item.instructor_name or (instructor.full_name if instructor else None),'student_group':item.student_group,'project_id':item.project_id,'project_title':project.title if project else None,'notes':item.notes,'schedule_days':days,'period_start':period_start,'period_end':period_end,'time_from':time_from,'time_to':time_to,'start_at':display_start,'end_at':display_end,'schedule_state':state,'is_archived':state=='archived','created_at':item.created_at}
def schedule_state(item:Schedule,now:datetime|None=None):
    now=now or datetime.now()
    today=now.date();current_time=now.time();days=set(item.schedule_days or [item.start_at.weekday()])
    period_start=item.period_start or item.start_at.date();period_end=item.period_end or item.end_at.date();time_from=item.time_from or item.start_at.time();time_to=item.time_to or item.end_at.time()
    if datetime.combine(period_end,time_to)<now: return 'archived'
    if item.schedule_type=='project':
        return 'active' if period_start<=today<=period_end else 'upcoming'
    if period_start<=today<=period_end and today.weekday() in days and time_from<=current_time<=time_to: return 'active'
    return 'upcoming'
def anchor_schedule(data:dict):
    days=data.get('schedule_days') or [data['period_start'].weekday()];first=data['period_start']
    for offset in range(7):
        candidate=first.fromordinal(first.toordinal()+offset)
        if candidate.weekday() in days: first=candidate;break
    data['schedule_days']=sorted(set(days));data['time_from']=data.get('time_from') or time.min;data['time_to']=data.get('time_to') or time.max;data['start_at']=datetime.combine(first,data['time_from']);data['end_at']=datetime.combine(first,data['time_to'])
def validate_schedule(db:Session,data:dict,exclude_id:int|None=None):
    if not db.get(Facility,data['facility_id']): raise HTTPException(422,'Selected facility does not exist')
    if data.get('schedule_type')=='project':
        project=db.get(Project,data.get('project_id'))
        if not project or project.approval_status!='approved': raise HTTPException(422,'Only an approved project can be scheduled')
        duplicate=select(Schedule).where(Schedule.project_id==project.id)
        if exclude_id: duplicate=duplicate.where(Schedule.id!=exclude_id)
        if db.scalar(duplicate.limit(1)): raise HTTPException(409,'This approved project is already allocated in the schedule archive or active calendar')
    conflict_query=select(Schedule).where(Schedule.facility_id==data['facility_id'],Schedule.schedule_type==data['schedule_type'])
    if exclude_id: conflict_query=conflict_query.where(Schedule.id!=exclude_id)
    candidate_days=set(data['schedule_days'] or [data['period_start'].weekday()])
    for conflict in db.scalars(conflict_query).all():
        if schedule_state(conflict)=='archived': continue
        conflict_start=conflict.period_start or conflict.start_at.date();conflict_end=conflict.period_end or conflict.end_at.date();conflict_days=set(conflict.schedule_days or [conflict.start_at.weekday()]);conflict_from=conflict.time_from or conflict.start_at.time();conflict_to=conflict.time_to or conflict.end_at.time()
        dates_overlap=data['period_start']<=conflict_end and data['period_end']>=conflict_start
        if data['schedule_type']=='project' and dates_overlap: raise HTTPException(409,f'Project date conflict with "{conflict.title}" in this facility')
        if data['schedule_type']=='class' and dates_overlap and candidate_days.intersection(conflict_days) and data['time_from']<conflict_to and data['time_to']>conflict_from: raise HTTPException(409,f'Time conflict with "{conflict.title}" on a shared weekday in this facility')
@api.get('/schedules')
def list_schedules(db:Session=Depends(get_db),user:User=Depends(current_user)):
    query=select(Schedule).order_by(Schedule.start_at);roles={role.name for role in user.roles}
    if 'lab_admin' in roles:
        if not user.assigned_facility_id: return {'data':[]}
        query=query.where(Schedule.facility_id==user.assigned_facility_id)
    return {'data':[schedule_payload(row,db) for row in db.scalars(query).all()]}
@api.post('/schedules',status_code=201)
def create_schedule(payload:ScheduleCreate,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    data=payload.model_dump();anchor_schedule(data);validate_schedule(db,data);item=Schedule(**data);db.add(item);db.flush();audit(db,user,'created','schedules',item.id);db.commit();db.refresh(item);return schedule_payload(item,db)
@api.patch('/schedules/{schedule_id}')
def update_schedule(schedule_id:int,payload:ScheduleUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(Schedule,schedule_id)
    if not item: raise HTTPException(404,'Schedule not found')
    data={'title':item.title,'schedule_type':item.schedule_type,'facility_id':item.facility_id,'instructor_name':item.instructor_name,'student_group':item.student_group,'project_id':item.project_id,'notes':item.notes,'schedule_days':item.schedule_days or [item.start_at.weekday()],'period_start':item.period_start or item.start_at.date(),'period_end':item.period_end or item.end_at.date(),'time_from':item.time_from or item.start_at.time(),'time_to':item.time_to or item.end_at.time()};data.update(payload.model_dump(exclude_unset=True))
    if data['period_end']<data['period_start']: raise HTTPException(422,'Schedule period end must be on or after start date')
    if data['schedule_type']=='class' and (not data.get('time_from') or not data.get('time_to')): raise HTTPException(422,'Class start and end times are required')
    if data['schedule_type']=='class' and data['time_to']<=data['time_from']: raise HTTPException(422,'Schedule end time must be after start time')
    if data['schedule_type']=='class' and not data.get('student_group'): raise HTTPException(422,'Class name or group is required')
    if data['schedule_type']=='class' and not data.get('schedule_days'): raise HTTPException(422,'Select at least one class day')
    if data['schedule_type']=='project' and not data.get('project_id'): raise HTTPException(422,'Approved project is required')
    anchor_schedule(data)
    validate_schedule(db,data,item.id)
    for key,value in data.items(): setattr(item,key,value)
    audit(db,user,'updated','schedules',item.id);db.commit();db.refresh(item);return schedule_payload(item,db)
@api.delete('/schedules/{schedule_id}',status_code=204)
def delete_schedule(schedule_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(Schedule,schedule_id)
    if not item: raise HTTPException(404,'Schedule not found')
    audit(db,user,'deleted','schedules',item.id);db.delete(item);db.commit()

# Public signage and project-intake endpoints intentionally require no JWT.
@api.get('/public/schedules')
def public_schedules(db:Session=Depends(get_db)):
    rows=db.scalars(select(Schedule).order_by(Schedule.period_start,Schedule.start_at)).all()
    rows=[row for row in rows if schedule_state(row)=='active']
    data=[]
    for row in rows:
        payload=schedule_payload(row,db);facility=db.get(Facility,row.facility_id)
        payload.update({'facility_kind':facility.kind if facility else None,'facility_location':facility.location if facility else None})
        data.append(payload)
    return {'data':data}
@api.get('/public/facilities')
def public_facilities(db:Session=Depends(get_db)):
    return {'data':[{'id':row.id,'name':row.name,'kind':row.kind,'location':row.location} for row in db.scalars(select(Facility).order_by(Facility.name)).all()]}
@api.post('/public/project-requests',status_code=201)
def public_project_request(payload:ProjectRequestIn,db:Session=Depends(get_db)):
    if payload.facility_id and not db.get(Facility,payload.facility_id): raise HTTPException(422,'Preferred facility does not exist')
    project=Project(**payload.model_dump(),requested_by_id=None,approval_status='pending',status='planned');db.add(project);db.flush();audit(db,None,'created','projects',project.id);db.commit();db.refresh(project)
    return {'id':project.id,'title':project.title,'approval_status':project.approval_status,'message':'Project request submitted for Dean review'}
@api.get('/facility-resources')
def list_resources(facility_id:int|None=None,include_archived:bool=False,db:Session=Depends(get_db),user:User=Depends(current_user)):
    q=select(FacilityResource)
    if not include_archived: q=q.where(FacilityResource.archived.is_(False))
    if facility_id: q=q.where(FacilityResource.facility_id==facility_id)
    roles={role.name for role in user.roles}
    if not roles.intersection(MANAGEMENT_ROLES) and roles.intersection({'lab_admin','laboratory_manager','workshop_manager'}):
        if not user.assigned_facility_id: return {'data':[]}
        q=q.where(FacilityResource.facility_id==user.assigned_facility_id)
    rows=db.scalars(q.order_by(FacilityResource.updated_at.desc())).all()
    return {'data':[resource_payload(row,db) for row in rows]}
def resource_snapshot(resource:FacilityResource):
    return {'name':resource.name,'category':resource.category,'quantity':resource.quantity,'properties':resource.properties or {},'asset_identifiers':[asset.identifier for asset in resource.assets if asset.status!='retired']}
def resource_payload(resource:FacilityResource,db:Session):
    submitter=db.get(User,resource.submitted_by_id) if resource.submitted_by_id else None;reviewer=db.get(User,resource.checked_by_id) if resource.checked_by_id else None
    return {'id':resource.id,'facility_id':resource.facility_id,'name':resource.name,'category':resource.category,'quantity':resource.quantity,'properties':resource.properties or {},'accepted':resource.accepted,'archived':resource.archived,'review_status':resource.review_status or ('accepted' if resource.accepted else 'pending'),'review_notes':resource.review_notes,'revision':resource.revision or 1,'submitted_by_id':resource.submitted_by_id,'submitted_by_name':submitter.full_name if submitter else 'System','added_by_name':added_by_name(db,'facility_resources',resource.id),'reviewed_by_name':reviewer.full_name if reviewer else None,'reviewed_at':resource.checked_at,'has_accepted_version':bool(resource.last_accepted_snapshot),'updated_at':resource.updated_at,'assets':[{'id':asset.id,'identifier':asset.identifier,'status':asset.status,'notes':asset.notes} for asset in resource.assets if asset.status!='retired']}
def record_resource_history(db:Session,resource:FacilityResource,actor:User,action:str,notes:str|None,before:dict|None,after:dict|None):
    db.add(ResourceHistory(resource_id=resource.id,facility_id=resource.facility_id,actor_id=actor.id,action=action,revision=resource.revision or 1,notes=notes,before_snapshot=before,after_snapshot=after))
def reconcile_resource_assets(db:Session,resource:FacilityResource,identifiers:list[str]):
    all_assets={asset.identifier:asset for asset in resource.assets}
    for asset in resource.assets:
        if asset.status!='retired' and asset.identifier not in identifiers: asset.status='retired'
    for identifier in identifiers:
        if identifier in all_assets: all_assets[identifier].status='available'
        else: db.add(ResourceAsset(resource_id=resource.id,identifier=identifier,status='available'))
    resource.quantity=len(identifiers)
def ensure_assistant_ready(db:Session,user:User):
    if user.must_change_password: raise HTTPException(403,'Change your initial password before using the workspace')
    if not user.assigned_facility_id: raise HTTPException(403,'No laboratory or workshop is assigned to your account')
    unreviewed=db.scalar(select(FacilityResource.id).where(FacilityResource.facility_id==user.assigned_facility_id,FacilityResource.archived.is_(False),FacilityResource.review_status!='accepted').limit(1))
    if unreviewed: raise HTTPException(403,'Review every pending or rejected resource handover before starting operational work')
@api.post('/facility-resources',status_code=201)
def create_resource(payload:FacilityResourceIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    if not db.get(Facility,payload.facility_id): raise HTTPException(422,'Selected facility does not exist')
    values=payload.model_dump(exclude={'asset_identifiers'});resource=FacilityResource(**values,review_status='pending',accepted=False,revision=1,submitted_by_id=user.id);db.add(resource);db.flush()
    db.add_all([ResourceAsset(resource_id=resource.id,identifier=value,status='available') for value in payload.asset_identifiers])
    db.flush();record_resource_history(db,resource,user,'created_and_submitted','Initial resource handover submitted for assistant review',None,resource_snapshot(resource));audit(db,user,'created','facility_resources',resource.id)
    try: db.commit()
    except IntegrityError: db.rollback();raise HTTPException(409,'A serial or asset number is already registered')
    db.refresh(resource);return resource_payload(resource,db)
@api.patch('/facility-resources/{resource_id}')
def update_resource(resource_id:int,payload:FacilityResourceUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    resource=db.get(FacilityResource,resource_id)
    if not resource: raise HTTPException(404,'Resource not found')
    before=resource_snapshot(resource)
    values=payload.model_dump(exclude_unset=True,exclude={'asset_identifiers'})
    identifiers=payload.asset_identifiers
    if identifiers is not None:
        expected=payload.quantity if payload.quantity is not None else len(identifiers)
        if len(identifiers)!=expected: raise HTTPException(422,'Quantity must equal the number of serial or asset identifiers')
        reconcile_resource_assets(db,resource,identifiers);values['quantity']=len(identifiers)
    for key,value in values.items(): setattr(resource,key,value)
    resource.revision=(resource.revision or 1)+1;resource.submitted_by_id=user.id;resource.review_status='pending';resource.review_notes=None;resource.accepted=False;resource.checked_by_id=None;resource.checked_at=None
    db.flush();record_resource_history(db,resource,user,'edited_and_resubmitted','Resource details changed; assistant review is required again',before,resource_snapshot(resource));audit(db,user,'updated','facility_resources',resource.id)
    try: db.commit()
    except IntegrityError: db.rollback();raise HTTPException(409,'A serial or asset number is already registered')
    db.refresh(resource);return resource_payload(resource,db)
@api.delete('/facility-resources/{resource_id}',status_code=204)
def delete_resource(resource_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    resource=db.get(FacilityResource,resource_id)
    if not resource: raise HTTPException(404,'Resource not found')
    before=resource_snapshot(resource);resource.archived=True;resource.review_status='archived';resource.accepted=False
    record_resource_history(db,resource,user,'archived','Resource removed from active inventory',before,None);audit(db,user,'archived','facility_resources',resource.id)
    db.commit()
@api.post('/facility-resources/{resource_id}/accept')
def accept_resource(resource_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles('lab_admin'))):
    return review_resource(resource_id,ResourceReviewIn(decision='accepted',notes='Inventory reviewed and accepted'),db,user)
@api.post('/facility-resources/{resource_id}/review')
def review_resource(resource_id:int,payload:ResourceReviewIn,db:Session=Depends(get_db),user:User=Depends(require_roles('lab_admin','laboratory_manager','workshop_manager'))):
    if user.must_change_password: raise HTTPException(403,'Change your initial password before reviewing assigned resources')
    resource=db.get(FacilityResource,resource_id)
    if not resource: raise HTTPException(404,'Resource not found')
    if user.assigned_facility_id!=resource.facility_id:
        raise HTTPException(403,'You are not assigned to this facility')
    if resource.archived: raise HTTPException(409,'Archived resources cannot be reviewed')
    if resource.review_status=='accepted': raise HTTPException(409,'This revision has already been accepted')
    before=resource_snapshot(resource);resource.review_status=payload.decision;resource.accepted=payload.decision=='accepted';resource.review_notes=payload.notes;resource.checked_by_id=user.id;resource.checked_at=datetime.now(timezone.utc)
    if resource.accepted: resource.last_accepted_snapshot=before
    record_resource_history(db,resource,user,payload.decision,payload.notes,before,before);db.commit();db.refresh(resource);return resource_payload(resource,db)
@api.post('/facility-resources/{resource_id}/resubmit')
def resubmit_resource(resource_id:int,payload:ResourceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    resource=db.get(FacilityResource,resource_id)
    if not resource or resource.archived: raise HTTPException(404,'Active resource not found')
    if resource.review_status=='accepted': raise HTTPException(409,'Edit the accepted resource to create a new review revision')
    before=resource_snapshot(resource);resource.revision=(resource.revision or 1)+1;resource.review_status='pending';resource.review_notes=None;resource.accepted=False;resource.submitted_by_id=user.id;resource.checked_by_id=None;resource.checked_at=None
    record_resource_history(db,resource,user,'resubmitted',payload.notes,before,before);db.commit();db.refresh(resource);return resource_payload(resource,db)
@api.post('/facility-resources/{resource_id}/restore')
def restore_resource(resource_id:int,payload:ResourceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    resource=db.get(FacilityResource,resource_id)
    if not resource or resource.archived: raise HTTPException(404,'Active resource not found')
    snapshot=resource.last_accepted_snapshot
    if not snapshot: raise HTTPException(409,'This resource has no previously accepted version')
    before=resource_snapshot(resource)
    for key in ('name','category','properties'): setattr(resource,key,snapshot[key])
    reconcile_resource_assets(db,resource,snapshot['asset_identifiers']);resource.revision=(resource.revision or 1)+1;resource.review_status='pending';resource.review_notes=None;resource.accepted=False;resource.submitted_by_id=user.id;resource.checked_by_id=None;resource.checked_at=None
    db.flush();record_resource_history(db,resource,user,'restored_and_resubmitted',payload.notes,before,resource_snapshot(resource));db.commit();db.refresh(resource);return resource_payload(resource,db)
@api.get('/facility-resources/{resource_id}/history')
def resource_history(resource_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    resource=db.get(FacilityResource,resource_id)
    if not resource: raise HTTPException(404,'Resource not found')
    roles={role.name for role in user.roles}
    if not roles.intersection(MANAGEMENT_ROLES) and user.assigned_facility_id!=resource.facility_id: raise HTTPException(403,'You cannot view this resource history')
    rows=db.scalars(select(ResourceHistory).where(ResourceHistory.resource_id==resource.id).order_by(ResourceHistory.created_at.desc(),ResourceHistory.id.desc())).all()
    return {'data':[{'id':row.id,'action':row.action,'revision':row.revision,'notes':row.notes,'before_snapshot':row.before_snapshot,'after_snapshot':row.after_snapshot,'created_at':row.created_at,'actor_id':row.actor_id,'actor_name':db.get(User,row.actor_id).full_name if row.actor_id and db.get(User,row.actor_id) else 'System'} for row in rows]}
@api.get('/equipment-usage-requests')
def list_usage_requests(db:Session=Depends(get_db),user:User=Depends(current_user)):
    roles={role.name for role in user.roles}
    q=select(EquipmentUsageRequest).order_by(EquipmentUsageRequest.created_at.desc())
    if not roles.intersection(MANAGEMENT_ROLES): q=q.where(EquipmentUsageRequest.requester_id==user.id)
    rows=db.scalars(q).all()
    return {'data':[{'id':row.id,'resource_id':row.resource_id,'facility_id':row.facility_id,'requester_id':row.requester_id,'quantity':row.quantity,'usage_type':row.usage_type,'purpose':row.purpose,'status':row.status,'decision_notes':row.decision_notes,'approver_id':row.approver_id,'decided_at':row.decided_at,'created_at':row.created_at} for row in rows]}
@api.post('/equipment-usage-requests',status_code=201)
def create_usage_request(payload:EquipmentUsageCreate,db:Session=Depends(get_db),user:User=Depends(require_roles('lab_admin'))):
    ensure_assistant_ready(db,user)
    resource=db.get(FacilityResource,payload.resource_id)
    if not resource or resource.archived: raise HTTPException(404,'Active resource not found')
    if user.assigned_facility_id!=resource.facility_id: raise HTTPException(403,'You may only request resources from your assigned facility')
    if payload.quantity>resource.quantity: raise HTTPException(422,'Requested quantity exceeds available inventory')
    request=EquipmentUsageRequest(resource_id=resource.id,facility_id=resource.facility_id,requester_id=user.id,quantity=payload.quantity,usage_type=payload.usage_type,purpose=payload.purpose)
    db.add(request);db.commit();db.refresh(request);return request
@api.patch('/equipment-usage-requests/{request_id}/decision')
def decide_usage_request(request_id:int,payload:EquipmentUsageDecision,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    request=db.get(EquipmentUsageRequest,request_id)
    if not request: raise HTTPException(404,'Usage request not found')
    if request.status!=Status.pending: raise HTTPException(409,'This request has already been decided')
    resource=db.get(FacilityResource,request.resource_id)
    if payload.decision=='approved':
        if not resource or resource.quantity<request.quantity: raise HTTPException(409,'Insufficient resource quantity for approval')
        resource.quantity-=request.quantity
        if resource.quantity==0: resource.archived=True
        request.status=Status.approved
    else: request.status=Status.rejected
    request.approver_id=user.id;request.decision_notes=payload.notes;request.decided_at=datetime.now(timezone.utc);db.commit();db.refresh(request);return request
def maintenance_event(db:Session,item:MaintenanceRequest,actor:User,action:str,old:Status|str|None,new:Status|str|None,notes:str|None=None):
    db.add(MaintenanceHistory(request_id=item.id,actor_id=actor.id,action=action,from_status=old.value if isinstance(old,Status) else old,to_status=new.value if isinstance(new,Status) else new,notes=notes))
@api.get('/maintenance-workflow')
def maintenance_workflow_list(db:Session=Depends(get_db),user:User=Depends(current_user)):
    role_names={role.name for role in user.roles};q=select(MaintenanceRequest).where(MaintenanceRequest.resource_id.is_not(None)).order_by(MaintenanceRequest.created_at.desc())
    if not role_names.intersection(MANAGEMENT_ROLES):
        if 'maintainer' in role_names: q=q.where(MaintenanceRequest.technician_id==user.id)
        else: q=q.where(MaintenanceRequest.requester_id==user.id)
    rows=db.scalars(q).all()
    return {'data':[{'id':x.id,'title':x.title,'details':x.details,'priority':x.priority,'kind':x.kind,'status':x.status,'resource_id':x.resource_id,'asset_id':x.asset_id,'asset_identifier':db.get(ResourceAsset,x.asset_id).identifier if x.asset_id and db.get(ResourceAsset,x.asset_id) else None,'facility_id':x.facility_id,'requester_id':x.requester_id,'technician_id':x.technician_id,'completion_notes':x.completion_notes,'resolution':x.resolution,'assistant_verification':x.assistant_verification,'verification_notes':x.verification_notes,'verified_at':x.verified_at,'parent_request_id':x.parent_request_id,'cost':float(x.cost) if x.cost is not None else None,'created_at':x.created_at,'updated_at':x.updated_at} for x in rows]}
@api.post('/maintenance-workflow',status_code=201)
def create_maintenance_workflow(payload:MaintenanceWorkflowCreate,db:Session=Depends(get_db),user:User=Depends(require_roles('lab_admin','laboratory_manager','workshop_manager'))):
    ensure_assistant_ready(db,user)
    resource=db.get(FacilityResource,payload.resource_id)
    if not resource: raise HTTPException(404,'Resource not found')
    if user.assigned_facility_id!=resource.facility_id: raise HTTPException(403,'Resource is not in your assigned facility')
    assets=[]
    for asset_id in payload.asset_ids:
        asset=db.get(ResourceAsset,asset_id)
        if not asset or asset.resource_id!=resource.id or asset.status=='retired': raise HTTPException(422,'Select valid serial or asset numbers for this resource')
        duplicate=db.scalar(select(MaintenanceRequest).where(MaintenanceRequest.asset_id==asset.id,MaintenanceRequest.status.not_in([Status.completed,Status.rejected])).limit(1))
        if duplicate: raise HTTPException(409,f'{asset.identifier} already has an open maintenance request')
        assets.append(asset)
    data=payload.model_dump(exclude={'asset_id','asset_ids'})
    created=[]
    for asset in assets:
        item=MaintenanceRequest(**data,asset_id=asset.id,facility_id=resource.facility_id,requester_id=user.id,status=Status.pending)
        asset.status='maintenance';db.add(item);db.flush();maintenance_event(db,item,user,'submitted',None,Status.pending,f'{asset.identifier}: {payload.details}');created.append(item)
    db.commit()
    for item in created: db.refresh(item)
    return created[0] if len(created)==1 else {'data':created}
@api.get('/maintenance-workflow/{request_id}/history')
def maintenance_history(request_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(MaintenanceRequest,request_id)
    if not item: raise HTTPException(404,'Maintenance request not found')
    roles={role.name for role in user.roles}
    if not roles.intersection(MANAGEMENT_ROLES) and item.requester_id!=user.id and item.technician_id!=user.id: raise HTTPException(403,'You cannot view this history')
    rows=db.scalars(select(MaintenanceHistory).where(MaintenanceHistory.request_id==request_id).order_by(MaintenanceHistory.created_at)).all()
    return {'data':[{'id':row.id,'action':row.action,'from_status':row.from_status,'to_status':row.to_status,'notes':row.notes,'created_at':row.created_at,'actor_id':row.actor_id,'actor_name':db.get(User,row.actor_id).full_name if db.get(User,row.actor_id) else 'System'} for row in rows]}
@api.get('/resource-assets/{asset_id}/maintenance-history')
def asset_maintenance_history(asset_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    asset=db.get(ResourceAsset,asset_id)
    if not asset: raise HTTPException(404,'Asset not found')
    resource=db.get(FacilityResource,asset.resource_id);roles={role.name for role in user.roles}
    if not roles.intersection(MANAGEMENT_ROLES) and user.assigned_facility_id!=resource.facility_id and 'maintainer' not in roles: raise HTTPException(403,'You cannot view this asset history')
    requests=db.scalars(select(MaintenanceRequest).where(MaintenanceRequest.asset_id==asset.id).order_by(MaintenanceRequest.created_at.desc())).all()
    return {'asset':{'id':asset.id,'identifier':asset.identifier,'status':asset.status},'resource':{'id':resource.id,'name':resource.name},'data':[{'id':item.id,'title':item.title,'details':item.details,'priority':item.priority,'status':item.status,'resolution':item.resolution,'completion_notes':item.completion_notes,'assistant_verification':item.assistant_verification,'created_at':item.created_at,'events':[{'id':event.id,'action':event.action,'from_status':event.from_status,'to_status':event.to_status,'notes':event.notes,'created_at':event.created_at,'actor_name':db.get(User,event.actor_id).full_name if db.get(User,event.actor_id) else 'System'} for event in db.scalars(select(MaintenanceHistory).where(MaintenanceHistory.request_id==item.id).order_by(MaintenanceHistory.created_at)).all()]} for item in requests]}
@api.post('/maintenance-workflow/{request_id}/approve')
def approve_maintenance(request_id:int,payload:MaintenanceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.status!=Status.pending: raise HTTPException(409,'Only pending requests can be approved')
    old=item.status;item.status=Status.approved;maintenance_event(db,item,user,'approved',old,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/reject')
def reject_maintenance(request_id:int,payload:MaintenanceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.status not in (Status.pending,Status.approved): raise HTTPException(409,'Request cannot be rejected')
    old=item.status;item.status=Status.rejected
    if item.asset_id:
        asset=db.get(ResourceAsset,item.asset_id)
        if asset: asset.status='available'
    maintenance_event(db,item,user,'rejected',old,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/assign')
def assign_maintenance(request_id:int,payload:MaintenanceAssignmentIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(MaintenanceRequest,request_id);technician=db.get(User,payload.technician_id)
    if not item or item.status!=Status.approved: raise HTTPException(409,'Approve the request before assigning a maintainer')
    if not technician or 'maintainer' not in {r.name for r in technician.roles}: raise HTTPException(422,'Selected user is not a maintainer')
    old=item.status;item.technician_id=technician.id;item.status=Status.assigned;maintenance_event(db,item,user,'assigned',old,item.status,payload.notes or technician.full_name);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/start')
def start_maintenance(request_id:int,payload:MaintenanceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('maintainer'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.technician_id!=user.id or item.status!=Status.assigned: raise HTTPException(409,'This task cannot be started')
    old=item.status;item.status=Status.in_progress;maintenance_event(db,item,user,'started',old,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/progress')
def maintenance_progress(request_id:int,payload:MaintenanceActionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('maintainer'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.technician_id!=user.id or item.status!=Status.in_progress: raise HTTPException(409,'Task is not in progress')
    maintenance_event(db,item,user,'progress',item.status,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/resolve')
def resolve_maintenance(request_id:int,payload:MaintenanceResolutionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('maintainer'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.technician_id!=user.id or item.status!=Status.in_progress: raise HTTPException(409,'Task is not in progress')
    old=item.status;item.status=Status.completed;item.resolution=payload.resolution;item.completion_notes=payload.notes;item.cost=payload.cost
    if item.asset_id:
        asset=db.get(ResourceAsset,item.asset_id)
        if asset: asset.status='awaiting_verification' if payload.resolution=='fixed' else 'maintenance'
    maintenance_event(db,item,user,payload.resolution,old,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/outsourced-result')
def outsourced_maintenance_result(request_id:int,payload:MaintenanceResolutionIn,db:Session=Depends(get_db),user:User=Depends(require_roles('coordinator','super_admin'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.status in (Status.completed,Status.rejected): raise HTTPException(409,'Only open maintenance requests can be documented')
    old=item.status;item.status=Status.completed;item.resolution=payload.resolution;item.completion_notes=payload.notes;item.cost=payload.cost
    if item.asset_id:
        asset=db.get(ResourceAsset,item.asset_id)
        if asset: asset.status='awaiting_verification' if payload.resolution=='fixed' else 'maintenance'
    maintenance_event(db,item,user,'outsourced_fixed' if payload.resolution=='fixed' else 'outsourced_not_fixed',old,item.status,payload.notes);db.commit();return item
@api.post('/maintenance-workflow/{request_id}/verify')
def verify_maintenance(request_id:int,payload:MaintenanceVerificationIn,db:Session=Depends(get_db),user:User=Depends(require_roles('lab_admin'))):
    item=db.get(MaintenanceRequest,request_id)
    if not item or item.requester_id!=user.id or item.status!=Status.completed: raise HTTPException(409,'Only your completed request can be verified')
    if item.assistant_verification: raise HTTPException(409,'This repair has already been verified')
    item.assistant_verification='accepted' if payload.verified else 'follow_up_requested';item.verification_notes=payload.notes;item.verified_at=datetime.now(timezone.utc)
    if item.asset_id:
        asset=db.get(ResourceAsset,item.asset_id)
        if asset: asset.status='available' if payload.verified else 'maintenance'
    maintenance_event(db,item,user,'fix_verified' if payload.verified else 'follow_up_requested',item.status,item.status,payload.notes)
    follow_up=None
    if not payload.verified:
        follow_up=MaintenanceRequest(title=f'Follow-up: {item.title}',details=payload.notes,priority=item.priority,kind=item.kind,status=Status.pending,resource_id=item.resource_id,asset_id=item.asset_id,facility_id=item.facility_id,requester_id=user.id,parent_request_id=item.id)
        db.add(follow_up);db.flush();maintenance_event(db,follow_up,user,'follow_up_submitted',None,Status.pending,payload.notes)
    db.commit();return {'verified':payload.verified,'follow_up_request_id':follow_up.id if follow_up else None}
@api.patch('/maintenance/{item_id}/status')
def update_maintenance_status(item_id:int,payload:StatusUpdate,db:Session=Depends(get_db),_:User=Depends(require_roles('coordinator','super_admin','maintainer'))):
    item=db.get(MaintenanceRequest,item_id)
    if not item: raise HTTPException(404,'Record not found')
    item.status=payload.status;item.completion_notes=payload.completion_notes;db.commit();return item
@api.get('/dashboard')
def dashboard(db:Session=Depends(get_db),_:User=Depends(current_user)):
    return {'equipment':len(db.scalars(select(Equipment)).all()),'open_maintenance':len(db.scalars(select(MaintenanceRequest).where(MaintenanceRequest.status.not_in(['completed','rejected']))).all()),'active_projects':len(db.scalars(select(Project).where(Project.status=='active')).all()),'upcoming_sessions':len(db.scalars(select(Schedule)).all())}
