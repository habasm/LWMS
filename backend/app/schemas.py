from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from .models import EquipmentStatus, ProjectStatus, Status
class ORM(BaseModel): model_config=ConfigDict(from_attributes=True)
class Login(BaseModel): email: str = Field(min_length=3, max_length=255); password: str
class Token(BaseModel): access_token: str; token_type: str='bearer'; must_change_password: bool=False
class UserCreate(BaseModel): email: EmailStr; full_name: str=Field(min_length=2); role_names: list[str]=Field(min_length=1); password: str|None=Field(default=None,min_length=8); assigned_facility_id:int|None=None
class UserUpdate(BaseModel): email:EmailStr|None=None; full_name:str|None=Field(default=None,min_length=2); role_names:list[str]|None=None; assigned_facility_id:int|None=None; is_active:bool|None=None
class UserOut(ORM): id:int; email:str; full_name:str; must_change_password:bool; is_active:bool; assigned_facility_id:int|None=None
class PasswordChange(BaseModel): current_password:str; new_password:str=Field(min_length=8)
class FacilityIn(BaseModel): name:str; kind:str=Field(pattern='^(laboratory|workshop)$'); capacity:int=Field(gt=0); location:str; description:str|None=None; manager_id:int|None=None
class FacilityResourceIn(BaseModel):
    facility_id:int; name:str=Field(min_length=2); category:str; quantity:int=Field(gt=0); asset_identifiers:list[str]=Field(min_length=1); properties:dict[str,str]=Field(default_factory=dict)
    @model_validator(mode='after')
    def identifiers_match_quantity(self):
        cleaned=[value.strip() for value in self.asset_identifiers if value.strip()]
        if len(cleaned)!=self.quantity: raise ValueError('Provide one unique serial or asset number for every quantity')
        if len(set(value.casefold() for value in cleaned))!=len(cleaned): raise ValueError('Serial or asset numbers must be unique')
        self.asset_identifiers=cleaned;return self
class FacilityResourceUpdate(BaseModel):
    name:str|None=None; category:str|None=None; quantity:int|None=Field(default=None,gt=0); asset_identifiers:list[str]|None=None; properties:dict[str,str]|None=None
    @model_validator(mode='after')
    def validate_identifiers(self):
        if self.asset_identifiers is not None:
            cleaned=[value.strip() for value in self.asset_identifiers if value.strip()]
            if self.quantity is not None and len(cleaned)!=self.quantity: raise ValueError('Provide one unique serial or asset number for every quantity')
            if len(set(value.casefold() for value in cleaned))!=len(cleaned): raise ValueError('Serial or asset numbers must be unique')
            self.asset_identifiers=cleaned
        return self
class ResourceReviewIn(BaseModel): decision:str=Field(pattern='^(accepted|rejected)$'); notes:str=Field(min_length=3,max_length=1000)
class ResourceActionIn(BaseModel): notes:str=Field(min_length=3,max_length=1000)
class EquipmentUsageCreate(BaseModel): resource_id:int; quantity:int=Field(gt=0); usage_type:str=Field(default='consumed',pattern='^(consumed|discarded)$'); purpose:str=Field(min_length=3)
class EquipmentUsageDecision(BaseModel): decision:str=Field(pattern='^(approved|rejected)$'); notes:str|None=None
class EquipmentIn(BaseModel): name:str; asset_number:str; category:str; purchase_date:date|None=None; status:EquipmentStatus=EquipmentStatus.available; facility_id:int
class MaintenanceIn(BaseModel): title:str; details:str|None=None; priority:str='medium'; kind:str='internal'; equipment_id:int|None=None; technician_id:int|None=None; cost:float|None=None
class MaintenanceWorkflowCreate(BaseModel):
    resource_id:int; asset_id:int|None=None; asset_ids:list[int]=Field(default_factory=list); title:str=Field(min_length=3); details:str=Field(min_length=3); priority:str=Field(pattern='^(low|medium|high|critical)$'); kind:str=Field(default='internal',pattern='^(internal|external)$')
    @model_validator(mode='after')
    def has_assets(self):
        ids=[self.asset_id] if self.asset_id else []
        ids.extend(self.asset_ids)
        cleaned=[]
        for value in ids:
            if value and value not in cleaned: cleaned.append(value)
        if not cleaned: raise ValueError('Select at least one serial or asset number')
        self.asset_ids=cleaned;self.asset_id=cleaned[0];return self
class MaintenanceAssignmentIn(BaseModel): technician_id:int; notes:str|None=None
class MaintenanceActionIn(BaseModel): notes:str=Field(min_length=2)
class MaintenanceResolutionIn(BaseModel): resolution:str=Field(pattern='^(fixed|not_fixed)$'); notes:str=Field(min_length=2); cost:float|None=Field(default=None,ge=0)
class MaintenanceVerificationIn(BaseModel): verified:bool; notes:str=Field(min_length=3)
class ProjectRequestIn(BaseModel):
    title:str=Field(min_length=3); description:str=Field(min_length=5); kind:str=Field(pattern='^(internal|external)$'); stakeholder_name:str=Field(min_length=2); organization:str|None=None; contact_email:EmailStr; facility_id:int|None=None; start_date:date|None=None; end_date:date|None=None
    @model_validator(mode='after')
    def valid_period(self):
        if self.start_date and self.end_date and self.end_date<self.start_date: raise ValueError('Project end date must be on or after its start date')
        return self
class ProjectDecisionIn(BaseModel): decision:str=Field(pattern='^(approved|rejected)$'); notes:str=Field(min_length=2)
class ProjectUpdate(BaseModel): title:str|None=Field(default=None,min_length=3); description:str|None=None; kind:str|None=Field(default=None,pattern='^(internal|external)$'); stakeholder_name:str|None=None; organization:str|None=None; contact_email:EmailStr|None=None; facility_id:int|None=None; start_date:date|None=None; end_date:date|None=None; status:ProjectStatus|None=None
class ScheduleCreate(BaseModel):
    title:str=Field(min_length=3); schedule_type:str=Field(pattern='^(class|project)$'); facility_id:int; instructor_name:str|None=Field(default=None,max_length=160); student_group:str|None=None; project_id:int|None=None; notes:str|None=None; schedule_days:list[int]=Field(default_factory=list); period_start:date; period_end:date; time_from:time|None=None; time_to:time|None=None
    @model_validator(mode='after')
    def valid_schedule(self):
        if self.period_end<self.period_start: raise ValueError('Schedule period end must be on or after its start date')
        if self.schedule_type=='class' and (not self.time_from or not self.time_to): raise ValueError('Class start and end times are required')
        if self.schedule_type=='class' and self.time_to<=self.time_from: raise ValueError('Schedule end time must be after start time')
        if self.schedule_type=='class' and not self.student_group: raise ValueError('Class name or group is required for a class schedule')
        if self.schedule_type=='class' and not self.schedule_days: raise ValueError('Select at least one class day')
        if any(day<0 or day>6 for day in self.schedule_days) or len(set(self.schedule_days))!=len(self.schedule_days): raise ValueError('Schedule days are invalid')
        if self.schedule_type=='project' and not self.project_id: raise ValueError('An approved project is required for a project schedule')
        return self
class ScheduleUpdate(BaseModel): title:str|None=None; schedule_type:str|None=Field(default=None,pattern='^(class|project)$'); facility_id:int|None=None; instructor_name:str|None=Field(default=None,max_length=160); student_group:str|None=None; project_id:int|None=None; notes:str|None=None; schedule_days:list[int]|None=None; period_start:date|None=None; period_end:date|None=None; time_from:time|None=None; time_to:time|None=None
class RequestIn(BaseModel): kind:str; title:str; details:str|None=None
class AnnouncementIn(BaseModel): title:str; body:str; audience:str='all'; expires_at:datetime|None=None; published:bool=False
class StatusUpdate(BaseModel): status:Status; completion_notes:str|None=None
