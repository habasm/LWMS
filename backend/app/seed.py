from datetime import datetime, timedelta, time
from sqlalchemy import select
from .core.database import SessionLocal
from .core.security import hash_password
from .models import EquipmentUsageRequest, Facility, FacilityResource, MaintenanceHistory, MaintenanceRequest, Project, ProjectStatus, ResourceAsset, ResourceHistory, Role, Schedule, Status, User

ROLES=['super_admin','laboratory_manager','workshop_manager','lab_admin','maintainer','technician','instructor']
DEMO_PASSWORD='Demo123!'
USERS=[
    ('admin@lwms.local','LWMS Administrator','super_admin'),
    ('lab.admin@lwms.test','Amina Hassan','lab_admin'),
    ('workshop.admin@lwms.test','Peter Mwangi','lab_admin'),
    ('maintainer@lwms.test','David Kimani','maintainer'),
    ('technician@lwms.test','Sarah Njeri','technician'),
    ('instructor@lwms.test','Dr Catherine Kamau','instructor'),
]

def seed() -> None:
    db=SessionLocal()
    try:
        role_map={}
        for name in ROLES:
            role=db.scalar(select(Role).where(Role.name==name)) or Role(name=name,permissions='["*"]')
            db.add(role);role_map[name]=role
        db.flush()
        user_map={}
        for email,full_name,role_name in USERS:
            user=db.scalar(select(User).where(User.email==email))
            if not user:
                password='ChangeMe123!' if role_name=='super_admin' else DEMO_PASSWORD
                user=User(email=email,full_name=full_name,password_hash=hash_password(password),must_change_password=False,is_active=True,roles=[role_map[role_name]])
                db.add(user)
            user_map[email]=user
        db.flush()
        facility_specs=[
            ('Engineering Laboratory','laboratory',40,'Block A, Level 2','Electronics and instrumentation laboratory'),
            ('Biomedical Laboratory','laboratory',28,'Science Block, Level 1','Biomedical testing and microscopy'),
            ('Mechanical Workshop','workshop',32,'Technology Block, Ground Floor','Machining, fabrication and welding'),
            ('Digital Fabrication Workshop','workshop',24,'Innovation Hub','3D printing and rapid prototyping'),
        ]
        facility_map={}
        for name,kind,capacity,location,description in facility_specs:
            facility=db.scalar(select(Facility).where(Facility.name==name)) or Facility(name=name,kind=kind,capacity=capacity,location=location,description=description)
            db.add(facility);facility_map[name]=facility
        db.flush()
        for facility in facility_map.values(): facility.manager_id=user_map['admin@lwms.local'].id
        user_map['lab.admin@lwms.test'].assigned_facility_id=facility_map['Engineering Laboratory'].id
        user_map['workshop.admin@lwms.test'].assigned_facility_id=facility_map['Mechanical Workshop'].id
        for legacy_email in ('lab.manager@lwms.test','workshop.manager@lwms.test','student@lwms.test'):
            legacy=db.scalar(select(User).where(User.email==legacy_email))
            if legacy: db.delete(legacy)
        resources=[
            ('Digital Oscilloscope','Test equipment',12,'Engineering Laboratory',{'model':'Rigol DS1054Z','condition':'Good'}),
            ('Soldering Station','Tools',20,'Engineering Laboratory',{'power':'60W','condition':'Good'}),
            ('Centrifuge','Biomedical equipment',4,'Biomedical Laboratory',{'max_rpm':'15000','condition':'Good'}),
            ('Compound Microscope','Optics',16,'Biomedical Laboratory',{'magnification':'1000x','condition':'Good'}),
            ('CNC Milling Machine','Machinery',2,'Mechanical Workshop',{'model':'VM-3','condition':'Service due'}),
            ('Arc Welder','Fabrication',8,'Mechanical Workshop',{'rating':'250A','condition':'Good'}),
            ('3D Printer','Rapid prototyping',6,'Digital Fabrication Workshop',{'material':'PLA/ABS','condition':'Good'}),
        ]
        resource_map={}
        for name,category,quantity,facility_name,properties in resources:
            resource=db.scalar(select(FacilityResource).where(FacilityResource.name==name,FacilityResource.facility_id==facility_map[facility_name].id))
            if not resource:
                resource=FacilityResource(name=name,category=category,quantity=quantity,facility_id=facility_map[facility_name].id,properties=properties,accepted=True,review_status='accepted',review_notes='Seed inventory verified',revision=1,submitted_by_id=user_map['admin@lwms.local'].id,checked_by_id=user_map['admin@lwms.local'].id,checked_at=datetime.now())
                db.add(resource)
            resource_map[name]=resource
        db.flush()
        asset_prefixes={'Digital Oscilloscope':'ENG-OSC','Soldering Station':'ENG-SLD','Centrifuge':'BIO-CEN','Compound Microscope':'BIO-MIC','CNC Milling Machine':'MEC-CNC','Arc Welder':'MEC-WLD','3D Printer':'FAB-3DP'}
        asset_map={}
        for name,resource in resource_map.items():
            existing=list(db.scalars(select(ResourceAsset).where(ResourceAsset.resource_id==resource.id,ResourceAsset.status!='retired')).all())
            prefix=asset_prefixes.get(name,f'LWMS-{resource.id}')
            for number in range(len(existing)+1,resource.quantity+1):
                asset=ResourceAsset(resource_id=resource.id,identifier=f'{prefix}-{number:03d}',status='available');db.add(asset);existing.append(asset)
            asset_map[name]=existing
        db.flush()
        # Backfill user-created legacy resource groups that predate serialized assets.
        for resource in db.scalars(select(FacilityResource).where(FacilityResource.archived.is_(False))).all():
            existing=list(db.scalars(select(ResourceAsset).where(ResourceAsset.resource_id==resource.id,ResourceAsset.status!='retired')).all())
            for number in range(len(existing)+1,resource.quantity+1):
                db.add(ResourceAsset(resource_id=resource.id,identifier=f'LWMS-{resource.id}-{number:03d}',status='available'))
        db.flush()
        for resource in resource_map.values():
            snapshot={'name':resource.name,'category':resource.category,'quantity':resource.quantity,'properties':resource.properties or {},'asset_identifiers':[asset.identifier for asset in resource.assets if asset.status!='retired']}
            if not db.scalar(select(ResourceHistory).where(ResourceHistory.resource_id==resource.id).limit(1)):
                resource.review_status='accepted';resource.accepted=True;resource.revision=resource.revision or 1;resource.submitted_by_id=resource.submitted_by_id or user_map['admin@lwms.local'].id;resource.last_accepted_snapshot=snapshot
                db.add(ResourceHistory(resource_id=resource.id,facility_id=resource.facility_id,actor_id=user_map['admin@lwms.local'].id,action='accepted_seed_inventory',revision=resource.revision,notes='Initial verified inventory imported by seed data',before_snapshot=snapshot,after_snapshot=snapshot))
        for resource in db.scalars(select(FacilityResource)).all():
            if not db.scalar(select(ResourceHistory).where(ResourceHistory.resource_id==resource.id).limit(1)):
                snapshot={'name':resource.name,'category':resource.category,'quantity':resource.quantity,'properties':resource.properties or {},'asset_identifiers':[asset.identifier for asset in resource.assets if asset.status!='retired']}
                resource.revision=resource.revision or 1;resource.submitted_by_id=resource.submitted_by_id or user_map['admin@lwms.local'].id
                if resource.accepted and not resource.last_accepted_snapshot: resource.last_accepted_snapshot=snapshot
                db.add(ResourceHistory(resource_id=resource.id,facility_id=resource.facility_id,actor_id=user_map['admin@lwms.local'].id,action='imported_existing_record',revision=resource.revision,notes='Existing resource brought under versioned handover control',before_snapshot=None,after_snapshot=snapshot))
        now=datetime.now().replace(minute=0,second=0,microsecond=0)
        project_specs=[
            ('Solar-powered irrigation controller','internal','Dr Miriam Otieno','School of Engineering','miriam.otieno@acacia.edu','approved','Prototype control board and enclosure fabrication',facility_map['Engineering Laboratory'],user_map['instructor@lwms.test']),
            ('Community water-quality sensor','external','Joseph Muli','Green Rivers Foundation','joseph.muli@greenrivers.example','pending','Build and calibrate portable sensor housings',facility_map['Digital Fabrication Workshop'],user_map['lab.admin@lwms.test']),
            ('Aluminium mobility frame prototype','external','Grace Wanjiku','Access Mobility Ltd','grace@accessmobility.example','rejected','Machine an early mobility-frame prototype',facility_map['Mechanical Workshop'],user_map['workshop.admin@lwms.test']),
        ]
        project_map={}
        for title,kind,stakeholder,organization,contact,approval,description,facility,requester in project_specs:
            project=db.scalar(select(Project).where(Project.title==title))
            if not project:
                project=Project(title=title,kind=kind,stakeholder_name=stakeholder,organization=organization,contact_email=contact,approval_status=approval,approval_notes='Approved for scheduled facility access' if approval=='approved' else 'Awaiting management review' if approval=='pending' else 'Requested period conflicts with core teaching activity',approved_by_id=user_map['admin@lwms.local'].id if approval!='pending' else None,approved_at=datetime.now() if approval!='pending' else None,description=description,facility_id=facility.id,requested_by_id=requester.id,status=ProjectStatus.active if approval=='approved' else ProjectStatus.planned,start_date=(now+timedelta(days=4)).date(),end_date=(now+timedelta(days=30)).date())
                db.add(project)
            project_map[title]=project
        db.flush()
        if not db.scalar(select(Schedule).where(Schedule.title=='Electronics Practical Session')):
            db.add_all([
                Schedule(title='Electronics Practical Session',facility_id=facility_map['Engineering Laboratory'].id,instructor_id=user_map['instructor@lwms.test'].id,student_group='ENGR Year 2',start_at=now+timedelta(days=1,hours=1),end_at=now+timedelta(days=1,hours=3)),
                Schedule(title='CNC Manufacturing Workshop',facility_id=facility_map['Mechanical Workshop'].id,instructor_id=user_map['instructor@lwms.test'].id,student_group='MECH Year 3',start_at=now+timedelta(days=2,hours=2),end_at=now+timedelta(days=2,hours=5)),
                Schedule(title='Microscopy Laboratory',facility_id=facility_map['Biomedical Laboratory'].id,instructor_id=user_map['instructor@lwms.test'].id,student_group='BIO Year 1',start_at=now+timedelta(days=3),end_at=now+timedelta(days=3,hours=2)),
            ])
        if not db.scalar(select(Schedule).where(Schedule.title=='Solar controller prototype session')):
            db.add(Schedule(title='Solar controller prototype session',schedule_type='project',facility_id=facility_map['Engineering Laboratory'].id,project_id=project_map['Solar-powered irrigation controller'].id,notes='Prototype assembly and bench testing',start_at=now+timedelta(days=4,hours=2),end_at=now+timedelta(days=4,hours=6)))
        db.flush()
        recurring_samples={
            'Electronics Practical Session':([0,1,4],(now+timedelta(days=1)).date(),(now+timedelta(days=60)).date(),time(8,0),time(10,30)),
            'CNC Manufacturing Workshop':([1,3],(now+timedelta(days=2)).date(),(now+timedelta(days=45)).date(),time(9,0),time(12,0)),
            'Microscopy Laboratory':([2],(now+timedelta(days=3)).date(),(now+timedelta(days=35)).date(),time(8,30),time(10,30)),
        }
        for title,(days,period_start,period_end,time_from,time_to) in recurring_samples.items():
            sample=db.scalar(select(Schedule).where(Schedule.title==title))
            if sample: sample.schedule_type='class';sample.instructor_name='Dr Catherine Kamau';sample.schedule_days=days;sample.period_start=period_start;sample.period_end=period_end;sample.time_from=time_from;sample.time_to=time_to
        project_sample=db.scalar(select(Schedule).where(Schedule.title=='Solar controller prototype session'))
        if project_sample: project_sample.schedule_days=[project_sample.start_at.weekday()];project_sample.period_start=project_sample.start_at.date();project_sample.period_end=project_sample.start_at.date();project_sample.time_from=project_sample.start_at.time();project_sample.time_to=project_sample.end_at.time()
        if not db.scalar(select(EquipmentUsageRequest).where(EquipmentUsageRequest.purpose=='Student electronics practical')):
            db.add(EquipmentUsageRequest(resource_id=resource_map['Digital Oscilloscope'].id,facility_id=facility_map['Engineering Laboratory'].id,requester_id=user_map['lab.admin@lwms.test'].id,quantity=2,purpose='Student electronics practical',status=Status.pending))
        if not db.scalar(select(MaintenanceRequest).where(MaintenanceRequest.title=='CNC spindle vibration')):
            maintenance=MaintenanceRequest(title='CNC spindle vibration',details='Unusual vibration above 4000 RPM',priority='high',kind='internal',status=Status.assigned,resource_id=resource_map['CNC Milling Machine'].id,asset_id=asset_map['CNC Milling Machine'][0].id,facility_id=facility_map['Mechanical Workshop'].id,requester_id=user_map['workshop.admin@lwms.test'].id,technician_id=user_map['maintainer@lwms.test'].id)
            asset_map['CNC Milling Machine'][0].status='maintenance'
            db.add(maintenance);db.flush()
            db.add_all([
                MaintenanceHistory(request_id=maintenance.id,actor_id=user_map['workshop.admin@lwms.test'].id,action='submitted',from_status=None,to_status='pending',notes='Machine stopped pending inspection'),
                MaintenanceHistory(request_id=maintenance.id,actor_id=user_map['admin@lwms.local'].id,action='approved',from_status='pending',to_status='approved',notes='Approved as high priority'),
                MaintenanceHistory(request_id=maintenance.id,actor_id=user_map['admin@lwms.local'].id,action='assigned',from_status='approved',to_status='assigned',notes='Assigned to David Kimani'),
            ])
        else:
            legacy_maintenance=db.scalar(select(MaintenanceRequest).where(MaintenanceRequest.title=='CNC spindle vibration'))
            if legacy_maintenance and not legacy_maintenance.asset_id:
                legacy_maintenance.asset_id=asset_map['CNC Milling Machine'][0].id;asset_map['CNC Milling Machine'][0].status='maintenance'
        db.commit()
    finally: db.close()

if __name__=='__main__': seed()
