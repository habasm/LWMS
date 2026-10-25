from datetime import date, datetime, time
from enum import Enum
from sqlalchemy import Boolean, Column, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, Numeric, String, Table, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core.database import Base

class Status(str, Enum): pending='pending'; approved='approved'; assigned='assigned'; in_progress='in_progress'; completed='completed'; rejected='rejected'
class EquipmentStatus(str, Enum): available='available'; in_use='in_use'; under_maintenance='under_maintenance'; out_of_service='out_of_service'
class ProjectStatus(str, Enum): planned='planned'; active='active'; completed='completed'; cancelled='cancelled'
user_roles = Table('user_roles', Base.metadata, Column('user_id', ForeignKey('users.id'), primary_key=True), Column('role_id', ForeignKey('roles.id'), primary_key=True))
project_members = Table('project_members', Base.metadata, Column('project_id', ForeignKey('projects.id'), primary_key=True), Column('user_id', ForeignKey('users.id'), primary_key=True))
class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
class Role(Base, Timestamped):
    __tablename__='roles'; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(80),unique=True); permissions: Mapped[str]=mapped_column(Text,default='[]'); users: Mapped[list['User']]=relationship(secondary=user_roles,back_populates='roles')
class User(Base, Timestamped):
    __tablename__='users'; id: Mapped[int]=mapped_column(primary_key=True); email: Mapped[str]=mapped_column(String(255),unique=True,index=True); full_name: Mapped[str]=mapped_column(String(150)); password_hash: Mapped[str]; must_change_password: Mapped[bool]=mapped_column(Boolean,default=True); is_active: Mapped[bool]=mapped_column(Boolean,default=True); assigned_facility_id: Mapped[int|None]=mapped_column(ForeignKey('facilities.id')); assigned_facility_ids: Mapped[list]=mapped_column(JSON,default=list); pending_facility_ids: Mapped[list]=mapped_column(JSON,default=list); roles: Mapped[list[Role]]=relationship(secondary=user_roles,back_populates='users')
class Facility(Base, Timestamped):
    __tablename__='facilities'; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(150),unique=True); kind: Mapped[str]=mapped_column(String(20)); capacity: Mapped[int]=mapped_column(Integer); location: Mapped[str]=mapped_column(String(150)); description: Mapped[str|None]=mapped_column(Text); manager_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); equipment: Mapped[list['Equipment']]=relationship(back_populates='facility')
class Equipment(Base, Timestamped):
    __tablename__='equipment'; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(150)); asset_number: Mapped[str]=mapped_column(String(80),unique=True,index=True); category: Mapped[str]=mapped_column(String(80)); purchase_date: Mapped[date|None]=mapped_column(Date); status: Mapped[EquipmentStatus]=mapped_column(SAEnum(EquipmentStatus),default=EquipmentStatus.available); facility_id: Mapped[int]=mapped_column(ForeignKey('facilities.id')); facility: Mapped[Facility]=relationship(back_populates='equipment')
class FacilityResource(Base, Timestamped):
    __tablename__='facility_resources'; id: Mapped[int]=mapped_column(primary_key=True); facility_id: Mapped[int]=mapped_column(ForeignKey('facilities.id'),index=True); name: Mapped[str]=mapped_column(String(150)); category: Mapped[str]=mapped_column(String(80)); quantity: Mapped[int]=mapped_column(Integer,default=1); properties: Mapped[dict]=mapped_column(JSON,default=dict); accepted: Mapped[bool]=mapped_column(Boolean,default=False); archived: Mapped[bool]=mapped_column(Boolean,default=False); review_status: Mapped[str]=mapped_column(String(20),default='pending',index=True); review_notes: Mapped[str|None]=mapped_column(Text); revision: Mapped[int]=mapped_column(Integer,default=1); submitted_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); last_accepted_snapshot: Mapped[dict|None]=mapped_column(JSON); checked_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); checked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); assets: Mapped[list['ResourceAsset']]=relationship(back_populates='resource',cascade='all, delete-orphan')
class ResourceAsset(Base, Timestamped):
    """A traceable physical unit belonging to a grouped facility resource."""
    __tablename__='resource_assets'; id: Mapped[int]=mapped_column(primary_key=True); resource_id: Mapped[int]=mapped_column(ForeignKey('facility_resources.id'),index=True); identifier: Mapped[str]=mapped_column(String(120),unique=True,index=True); status: Mapped[str]=mapped_column(String(30),default='available'); notes: Mapped[str|None]=mapped_column(Text); resource: Mapped[FacilityResource]=relationship(back_populates='assets')
class ResourceHistory(Base):
    """Immutable handover and revision history for a facility resource."""
    __tablename__='resource_history'; id: Mapped[int]=mapped_column(primary_key=True); resource_id: Mapped[int]=mapped_column(ForeignKey('facility_resources.id'),index=True); facility_id: Mapped[int]=mapped_column(ForeignKey('facilities.id'),index=True); actor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); action: Mapped[str]=mapped_column(String(50)); revision: Mapped[int]=mapped_column(Integer); notes: Mapped[str|None]=mapped_column(Text); before_snapshot: Mapped[dict|None]=mapped_column(JSON); after_snapshot: Mapped[dict|None]=mapped_column(JSON); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class EquipmentUsageRequest(Base, Timestamped):
    __tablename__='equipment_usage_requests'; id: Mapped[int]=mapped_column(primary_key=True); resource_id: Mapped[int]=mapped_column(ForeignKey('facility_resources.id'),index=True); facility_id: Mapped[int]=mapped_column(ForeignKey('facilities.id'),index=True); requester_id: Mapped[int]=mapped_column(ForeignKey('users.id')); quantity: Mapped[int]=mapped_column(Integer); usage_type: Mapped[str]=mapped_column(String(20),default='consumed'); purpose: Mapped[str]=mapped_column(Text); asset_ids: Mapped[list]=mapped_column(JSON,default=list); asset_identifiers: Mapped[list]=mapped_column(JSON,default=list); status: Mapped[Status]=mapped_column(SAEnum(Status),default=Status.pending); approver_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); decision_notes: Mapped[str|None]=mapped_column(Text); decided_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class MaintenanceRequest(Base, Timestamped):
    __tablename__='maintenance_requests'; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(180)); details: Mapped[str|None]=mapped_column(Text); priority: Mapped[str]=mapped_column(String(20),default='medium'); kind: Mapped[str]=mapped_column(String(20),default='internal'); status: Mapped[Status]=mapped_column(SAEnum(Status),default=Status.pending); cost: Mapped[float|None]=mapped_column(Numeric(12,2)); equipment_id: Mapped[int|None]=mapped_column(ForeignKey('equipment.id')); resource_id: Mapped[int|None]=mapped_column(ForeignKey('facility_resources.id')); asset_id: Mapped[int|None]=mapped_column(ForeignKey('resource_assets.id'),index=True); facility_id: Mapped[int|None]=mapped_column(ForeignKey('facilities.id')); requester_id: Mapped[int]=mapped_column(ForeignKey('users.id')); technician_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); completion_notes: Mapped[str|None]=mapped_column(Text); resolution: Mapped[str|None]=mapped_column(String(30)); assistant_verification: Mapped[str|None]=mapped_column(String(30)); verification_notes: Mapped[str|None]=mapped_column(Text); verified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); parent_request_id: Mapped[int|None]=mapped_column(ForeignKey('maintenance_requests.id'))
class MaintenanceHistory(Base):
    __tablename__='maintenance_history'; id: Mapped[int]=mapped_column(primary_key=True); request_id: Mapped[int]=mapped_column(ForeignKey('maintenance_requests.id'),index=True); actor_id: Mapped[int]=mapped_column(ForeignKey('users.id')); action: Mapped[str]=mapped_column(String(50)); from_status: Mapped[str|None]=mapped_column(String(30)); to_status: Mapped[str|None]=mapped_column(String(30)); notes: Mapped[str|None]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Project(Base, Timestamped):
    __tablename__='projects'; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(180)); description: Mapped[str|None]=mapped_column(Text); kind: Mapped[str]=mapped_column(String(20)); stakeholder_name: Mapped[str|None]=mapped_column(String(160)); organization: Mapped[str|None]=mapped_column(String(180)); contact_email: Mapped[str|None]=mapped_column(String(255)); requested_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); approval_status: Mapped[str]=mapped_column(String(20),default='pending'); approval_notes: Mapped[str|None]=mapped_column(Text); approved_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); approved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); status: Mapped[ProjectStatus]=mapped_column(SAEnum(ProjectStatus),default=ProjectStatus.planned); start_date: Mapped[date|None]=mapped_column(Date); end_date: Mapped[date|None]=mapped_column(Date); facility_id: Mapped[int|None]=mapped_column(ForeignKey('facilities.id')); members: Mapped[list[User]]=relationship(secondary=project_members)
class Schedule(Base, Timestamped):
    __tablename__='schedules'; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(180)); schedule_type: Mapped[str]=mapped_column(String(20),default='class'); facility_id: Mapped[int]=mapped_column(ForeignKey('facilities.id')); instructor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); instructor_name: Mapped[str|None]=mapped_column(String(160)); student_group: Mapped[str|None]=mapped_column(String(100)); project_id: Mapped[int|None]=mapped_column(ForeignKey('projects.id')); notes: Mapped[str|None]=mapped_column(Text); schedule_days: Mapped[list]=mapped_column(JSON,default=list); period_start: Mapped[date|None]=mapped_column(Date); period_end: Mapped[date|None]=mapped_column(Date); time_from: Mapped[time|None]=mapped_column(Time); time_to: Mapped[time|None]=mapped_column(Time); start_at: Mapped[datetime]=mapped_column(DateTime); end_at: Mapped[datetime]=mapped_column(DateTime)
class Request(Base, Timestamped):
    __tablename__='requests'; id: Mapped[int]=mapped_column(primary_key=True); kind: Mapped[str]=mapped_column(String(30)); title: Mapped[str]=mapped_column(String(180)); details: Mapped[str|None]=mapped_column(Text); status: Mapped[Status]=mapped_column(SAEnum(Status),default=Status.pending); requester_id: Mapped[int]=mapped_column(ForeignKey('users.id')); approver_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
class Announcement(Base, Timestamped):
    __tablename__='announcements'; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(180)); body: Mapped[str]=mapped_column(Text); audience: Mapped[str]=mapped_column(String(30),default='all'); expires_at: Mapped[datetime|None]=mapped_column(DateTime); published: Mapped[bool]=mapped_column(Boolean,default=False); author_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
class Notification(Base, Timestamped):
    __tablename__='notifications'; id: Mapped[int]=mapped_column(primary_key=True); user_id: Mapped[int]=mapped_column(ForeignKey('users.id')); message: Mapped[str]=mapped_column(String(255)); read: Mapped[bool]=mapped_column(Boolean,default=False)
class AuditLog(Base):
    __tablename__='audit_logs'; id: Mapped[int]=mapped_column(primary_key=True); actor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id')); action: Mapped[str]=mapped_column(String(80)); entity: Mapped[str]=mapped_column(String(80)); entity_id: Mapped[int|None]; created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class StoreItem(Base, Timestamped):
    __tablename__='store_items'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(150),index=True)
    category: Mapped[str]=mapped_column(String(80))
    kind: Mapped[str]=mapped_column(String(20))  # consumable or durable
    unit: Mapped[str]=mapped_column(String(40),default='each')
    description: Mapped[str|None]=mapped_column(Text)

class Store(Base, Timestamped):
    __tablename__='stores'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(150),unique=True)
    location: Mapped[str]=mapped_column(String(150))
    description: Mapped[str|None]=mapped_column(Text)
    manager_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    created_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    review_status: Mapped[str]=mapped_column(String(20),default='unassigned')
    revision: Mapped[int]=mapped_column(Integer,default=1)
    accepted_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class StoreLot(Base, Timestamped):
    __tablename__='store_lots'
    id: Mapped[int]=mapped_column(primary_key=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('store_items.id'),index=True)
    facility_id: Mapped[int|None]=mapped_column(ForeignKey('facilities.id'),index=True)
    store_id: Mapped[int]=mapped_column(ForeignKey('stores.id'),index=True)
    quantity: Mapped[int]=mapped_column(Integer)
    available: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(20),default='pending')
    purchase_reference: Mapped[str]=mapped_column(String(120))
    supplier: Mapped[str|None]=mapped_column(String(150))
    received_by_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    accepted_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class StoreRequest(Base, Timestamped):
    __tablename__='store_requests'
    id: Mapped[int]=mapped_column(primary_key=True)
    reference: Mapped[str]=mapped_column(String(40),unique=True,index=True)
    requester_name: Mapped[str]=mapped_column(String(150))
    requester_contact: Mapped[str]=mapped_column(String(160))
    department: Mapped[str]=mapped_column(String(150))
    purpose: Mapped[str]=mapped_column(Text)
    kind: Mapped[str]=mapped_column(String(20))
    requester_position: Mapped[str]=mapped_column(String(20),default='staff')
    chair_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    status: Mapped[str]=mapped_column(String(30),default='pending')
    facility_id: Mapped[int|None]=mapped_column(ForeignKey('facilities.id'))
    store_id: Mapped[int]=mapped_column(ForeignKey('stores.id'),index=True)
    chair_name: Mapped[str|None]=mapped_column(String(150))
    dean_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    assigned_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    assigned_manager_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    issued_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    issued_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    signed_document: Mapped[str|None]=mapped_column(String(255))
    notes: Mapped[str|None]=mapped_column(Text)

class StoreRequestLine(Base):
    __tablename__='store_request_lines'
    id: Mapped[int]=mapped_column(primary_key=True)
    request_id: Mapped[int]=mapped_column(ForeignKey('store_requests.id'),index=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('store_items.id'))
    quantity: Mapped[int]=mapped_column(Integer)
    returned: Mapped[int]=mapped_column(Integer,default=0)

class StoreAllocation(Base):
    __tablename__='store_allocations'
    id: Mapped[int]=mapped_column(primary_key=True)
    line_id: Mapped[int]=mapped_column(ForeignKey('store_request_lines.id'),index=True)
    lot_id: Mapped[int]=mapped_column(ForeignKey('store_lots.id'),index=True)
    quantity: Mapped[int]=mapped_column(Integer)
    returned: Mapped[int]=mapped_column(Integer,default=0)

class StoreMovement(Base):
    __tablename__='store_movements'
    id: Mapped[int]=mapped_column(primary_key=True)
    store_id: Mapped[int]=mapped_column(ForeignKey('stores.id'),index=True)
    item_id: Mapped[int]=mapped_column(ForeignKey('store_items.id'))
    lot_id: Mapped[int]=mapped_column(ForeignKey('store_lots.id'))
    request_id: Mapped[int|None]=mapped_column(ForeignKey('store_requests.id'))
    actor_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(20))
    quantity: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class StoreEvent(Base):
    __tablename__='store_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    request_id: Mapped[int|None]=mapped_column(ForeignKey('store_requests.id'),index=True)
    lot_id: Mapped[int|None]=mapped_column(ForeignKey('store_lots.id'),index=True)
    store_id: Mapped[int|None]=mapped_column(ForeignKey('stores.id'),index=True)
    actor_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(40))
    notes: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
