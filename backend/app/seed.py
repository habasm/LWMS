from datetime import datetime, time, timedelta

from .core.database import SessionLocal
from .core.security import hash_password
from .models import (
    AuditLog,
    EquipmentUsageRequest,
    Facility,
    FacilityResource,
    MaintenanceHistory,
    MaintenanceRequest,
    Project,
    ProjectStatus,
    ResourceAsset,
    ResourceHistory,
    Role,
    Schedule,
    Status,
    User,
)

ROLES = ['dean', 'coordinator', 'super_admin', 'lab_admin', 'maintainer']
DEMO_PASSWORD = 'Demo123!'

USERS = [
    ('dean@bdu.edu.et', 'Dr. Tadesse Alemu', 'dean'),
    ('coordinator@bdu.edu.et', 'Eng. Selamawit Tesfaye', 'coordinator'),
    ('control.lab@bdu.edu.et', 'Abebe Mekonnen', 'lab_admin'),
    ('power.lab@bdu.edu.et', 'Mekdes Getachew', 'lab_admin'),
    ('machines.lab@bdu.edu.et', 'Yonas Desta', 'lab_admin'),
    ('thermal.lab@bdu.edu.et', 'Hana Bekele', 'lab_admin'),
    ('manufacturing.workshop@bdu.edu.et', 'Bereket Assefa', 'lab_admin'),
    ('automotive.workshop@bdu.edu.et', 'Rahel Girma', 'lab_admin'),
    ('maintainer.electrical@bdu.edu.et', 'Kebede Wolde', 'maintainer'),
    ('maintainer.mechanical@bdu.edu.et', 'Almaz Hailu', 'maintainer'),
    ('external.maintainer@bdu.edu.et', 'Dawit Worku', 'maintainer'),
]

FACILITIES = [
    ('Electrical Machines Laboratory', 'laboratory', 35, 'BIT Engineering Block E-201', 'Motors, alternators, transformers, and drive experiments'),
    ('Power Systems Laboratory', 'laboratory', 32, 'BIT Engineering Block E-205', 'Protection relays, transmission models, and power quality analysis'),
    ('Control and Instrumentation Laboratory', 'laboratory', 30, 'BIT Engineering Block E-214', 'PLC, sensors, feedback control, and measurement systems'),
    ('Thermal and Fluid Laboratory', 'laboratory', 28, 'Mechanical Block M-104', 'Heat transfer, pumps, turbines, and fluid mechanics benches'),
    ('Manufacturing Workshop', 'workshop', 42, 'Mechanical Workshop Hall W-01', 'Machining, welding, fitting, and fabrication practice'),
    ('Automotive Workshop', 'workshop', 36, 'Mechanical Workshop Hall W-03', 'Engines, transmission systems, chassis, and vehicle diagnostics'),
]

ASSIGNMENTS = {
    'machines.lab@bdu.edu.et': 'Electrical Machines Laboratory',
    'power.lab@bdu.edu.et': 'Power Systems Laboratory',
    'control.lab@bdu.edu.et': 'Control and Instrumentation Laboratory',
    'thermal.lab@bdu.edu.et': 'Thermal and Fluid Laboratory',
    'manufacturing.workshop@bdu.edu.et': 'Manufacturing Workshop',
    'automotive.workshop@bdu.edu.et': 'Automotive Workshop',
}

RESOURCES = [
    ('Three Phase Induction Motor Trainer', 'Electrical machines', 6, 'Electrical Machines Laboratory', 'EML-IMT', {'rating': '3 kW', 'condition': 'Good'}),
    ('Synchronous Generator Training Set', 'Electrical machines', 4, 'Electrical Machines Laboratory', 'EML-SGT', {'rating': '5 kVA', 'condition': 'Good'}),
    ('Transformer Test Bench', 'Power equipment', 5, 'Power Systems Laboratory', 'PSL-TTB', {'rating': '2 kVA', 'condition': 'Good'}),
    ('Digital Protection Relay Kit', 'Power protection', 7, 'Power Systems Laboratory', 'PSL-DPR', {'model': 'Overcurrent and earth fault relay kit', 'condition': 'Good'}),
    ('PLC Training Rack', 'Automation', 8, 'Control and Instrumentation Laboratory', 'CIL-PLC', {'controller': 'Siemens S7 class', 'condition': 'Good'}),
    ('Digital Oscilloscope', 'Measurement', 10, 'Control and Instrumentation Laboratory', 'CIL-OSC', {'bandwidth': '100 MHz', 'condition': 'Good'}),
    ('Heat Exchanger Bench', 'Thermal equipment', 3, 'Thermal and Fluid Laboratory', 'TFL-HEB', {'type': 'Shell and tube', 'condition': 'Good'}),
    ('Centrifugal Pump Test Rig', 'Fluid equipment', 4, 'Thermal and Fluid Laboratory', 'TFL-PMP', {'range': '0-60 L/min', 'condition': 'Service due'}),
    ('CNC Lathe', 'Machinery', 3, 'Manufacturing Workshop', 'MFW-CNC', {'model': 'Training CNC lathe', 'condition': 'Good'}),
    ('MIG Welding Machine', 'Welding', 6, 'Manufacturing Workshop', 'MFW-MIG', {'rating': '250 A', 'condition': 'Good'}),
    ('Engine Diagnostic Scanner', 'Automotive diagnostics', 5, 'Automotive Workshop', 'ATW-EDS', {'protocol': 'OBD-II', 'condition': 'Good'}),
    ('Diesel Engine Test Stand', 'Automotive systems', 2, 'Automotive Workshop', 'ATW-DES', {'engine': '4-cylinder diesel trainer', 'condition': 'Good'}),
]


def audit(db, actor: User | None, action: str, entity: str, entity_id: int | None) -> None:
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, entity=entity, entity_id=entity_id))


def snapshot(resource: FacilityResource) -> dict:
    return {
        'name': resource.name,
        'category': resource.category,
        'quantity': resource.quantity,
        'properties': resource.properties or {},
        'asset_identifiers': [asset.identifier for asset in resource.assets if asset.status != 'retired'],
    }


def maintenance_event(db, item: MaintenanceRequest, actor: User, action: str, old: str | None, new: str | None, notes: str) -> None:
    db.add(MaintenanceHistory(request_id=item.id, actor_id=actor.id, action=action, from_status=old, to_status=new, notes=notes))


def seed() -> None:
    db = SessionLocal()
    try:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        role_map: dict[str, Role] = {}
        for name in ROLES:
            role = Role(name=name, permissions='["*"]')
            db.add(role)
            role_map[name] = role
        db.flush()

        user_map: dict[str, User] = {}
        for email, full_name, role_name in USERS:
            user = User(email=email, full_name=full_name, password_hash=hash_password(DEMO_PASSWORD), must_change_password=False, is_active=True, roles=[role_map[role_name]])
            db.add(user)
            user_map[email] = user
        db.flush()
        dean = user_map['dean@bdu.edu.et']
        coordinator = user_map['coordinator@bdu.edu.et']
        for user in user_map.values():
            audit(db, dean if user is coordinator else coordinator, 'created', 'user', user.id)

        facility_map: dict[str, Facility] = {}
        for name, kind, capacity, location, description in FACILITIES:
            facility = Facility(name=name, kind=kind, capacity=capacity, location=location, description=description, manager_id=coordinator.id)
            db.add(facility)
            facility_map[name] = facility
        db.flush()
        for facility in facility_map.values():
            audit(db, coordinator, 'created', 'facilities', facility.id)

        for email, facility_name in ASSIGNMENTS.items():
            user_map[email].assigned_facility_id = facility_map[facility_name].id
            audit(db, coordinator, 'updated', 'user', user_map[email].id)

        resource_map: dict[str, FacilityResource] = {}
        asset_map: dict[str, list[ResourceAsset]] = {}
        for name, category, quantity, facility_name, prefix, properties in RESOURCES:
            facility = facility_map[facility_name]
            assistant_email = next(email for email, assigned in ASSIGNMENTS.items() if assigned == facility_name)
            assistant = user_map[assistant_email]
            accepted = name not in {'Centrifugal Pump Test Rig', 'Digital Protection Relay Kit'}
            resource = FacilityResource(name=name, category=category, quantity=quantity, facility_id=facility.id, properties=properties, accepted=accepted, archived=False, review_status='accepted' if accepted else 'pending', review_notes='Accepted by assigned assistant after physical check.' if accepted else 'Awaiting assistant acceptance after new delivery.', revision=1, submitted_by_id=coordinator.id, checked_by_id=assistant.id if accepted else None, checked_at=now - timedelta(days=6) if accepted else None)
            db.add(resource)
            resource_map[name] = resource
        db.flush()

        for name, category, quantity, facility_name, prefix, properties in RESOURCES:
            resource = resource_map[name]
            assets = []
            for number in range(1, quantity + 1):
                asset = ResourceAsset(resource_id=resource.id, identifier=f'{prefix}-{number:03d}', status='available')
                db.add(asset)
                assets.append(asset)
            asset_map[name] = assets
        db.flush()

        for name, resource in resource_map.items():
            facility_name = next(item[3] for item in RESOURCES if item[0] == name)
            assistant_email = next(email for email, assigned in ASSIGNMENTS.items() if assigned == facility_name)
            assistant = user_map[assistant_email]
            current = snapshot(resource)
            resource.last_accepted_snapshot = current if resource.accepted else None
            db.add(ResourceHistory(resource_id=resource.id, facility_id=resource.facility_id, actor_id=coordinator.id, action='created_and_submitted', revision=1, notes='Coordinator recorded initial BDU-BIT equipment handover.', before_snapshot=None, after_snapshot=current))
            if resource.accepted:
                db.add(ResourceHistory(resource_id=resource.id, facility_id=resource.facility_id, actor_id=assistant.id, action='accepted', revision=1, notes='Assistant verified quantity, identifiers, and condition.', before_snapshot=current, after_snapshot=current))
            audit(db, coordinator, 'created', 'facility_resources', resource.id)

        cnc = resource_map['CNC Lathe']
        before = snapshot(cnc)
        new_asset = ResourceAsset(resource_id=cnc.id, identifier='MFW-CNC-004', status='available')
        db.add(new_asset)
        db.flush()
        cnc.quantity = 4
        cnc.revision = 2
        after = snapshot(cnc)
        cnc.last_accepted_snapshot = after
        db.add(ResourceHistory(resource_id=cnc.id, facility_id=cnc.facility_id, actor_id=coordinator.id, action='updated_quantity', revision=2, notes='One additional CNC training lathe added after procurement.', before_snapshot=before, after_snapshot=after))
        audit(db, coordinator, 'updated', 'facility_resources', cnc.id)

        project_specs = [
            ('Smart three-phase motor protection panel', 'internal', 'Dr. Fitsum Gebre', 'Electrical and Computer Engineering', 'fitsum.gebre@bdu.edu.et', 'approved', 'Build and test a relay-based motor protection panel for senior electrical engineering projects.', 'Electrical Machines Laboratory', user_map['machines.lab@bdu.edu.et'], now.date() + timedelta(days=5), now.date() + timedelta(days=30)),
            ('Micro-hydro turbine runner performance test', 'internal', 'Dr. Hirut Teshome', 'Mechanical Engineering', 'hirut.teshome@bdu.edu.et', 'approved', 'Use the thermal and fluid laboratory to compare runner blade angles under controlled flow.', 'Thermal and Fluid Laboratory', user_map['thermal.lab@bdu.edu.et'], now.date() + timedelta(days=9), now.date() + timedelta(days=28)),
            ('Automated injera mitad temperature controller', 'external', 'Aster Kebede', 'Blue Nile Small Industries PLC', 'aster.kebede@bdu.edu.et', 'pending', 'Prototype a controller and enclosure for regulated electric mitad surface temperature.', 'Control and Instrumentation Laboratory', user_map['control.lab@bdu.edu.et'], now.date() + timedelta(days=12), now.date() + timedelta(days=35)),
            ('Solar grain dryer frame fabrication', 'external', 'Mulugeta Abebe', 'Amhara Agro-Tech Cooperative', 'mulugeta.abebe@bdu.edu.et', 'pending', 'Fabricate and test a collapsible mechanical frame for a solar grain dryer.', 'Manufacturing Workshop', user_map['manufacturing.workshop@bdu.edu.et'], now.date() + timedelta(days=15), now.date() + timedelta(days=40)),
            ('Imported vehicle ECU training module', 'external', 'Tesfaye Nigussie', 'Bahir Dar Garage Association', 'tesfaye.nigussie@bdu.edu.et', 'rejected', 'Request for long-term occupation of automotive workshop diagnostic tools.', 'Automotive Workshop', user_map['automotive.workshop@bdu.edu.et'], now.date() + timedelta(days=4), now.date() + timedelta(days=75)),
        ]
        project_map: dict[str, Project] = {}
        for title, kind, stakeholder, organization, contact, approval, description, facility_name, requester, start_date, end_date in project_specs:
            project = Project(title=title, description=description, kind=kind, stakeholder_name=stakeholder, organization=organization, contact_email=contact, requested_by_id=requester.id, approval_status=approval, approval_notes='Approved by Dean for coordinator scheduling.' if approval == 'approved' else 'Awaiting Dean review.' if approval == 'pending' else 'Rejected because requested duration conflicts with teaching schedule.', approved_by_id=dean.id if approval != 'pending' else None, approved_at=now - timedelta(days=2) if approval != 'pending' else None, status=ProjectStatus.active if approval == 'approved' else ProjectStatus.planned, start_date=start_date, end_date=end_date, facility_id=facility_map[facility_name].id)
            db.add(project)
            project_map[title] = project
        db.flush()
        for project in project_map.values():
            audit(db, db.get(User, project.requested_by_id) if project.requested_by_id else None, 'created', 'projects', project.id)
            if project.approval_status != 'pending':
                audit(db, dean, project.approval_status, 'projects', project.id)

        schedules = [
            ('Electrical Machines II Practical', 'class', 'Electrical Machines Laboratory', None, 'Dr. Getnet Molla', 'Electrical Year 3 - Section A', [0, 2], now.date() - timedelta(days=7), now.date() + timedelta(days=50), time(8, 0), time(10, 30), 'Motor loading and transformer efficiency practical.'),
            ('Power System Protection Lab', 'class', 'Power Systems Laboratory', None, 'Dr. Wubet Tarekegn', 'Electrical Year 4', [1], now.date() + timedelta(days=1), now.date() + timedelta(days=45), time(9, 0), time(12, 0), 'Relay coordination and fault simulation sessions.'),
            ('Manufacturing Processes Practice', 'class', 'Manufacturing Workshop', None, 'Eng. Meseret Yilma', 'Mechanical Year 2 - Group B', [3], now.date() - timedelta(days=1), now.date() + timedelta(days=42), time(13, 30), time(16, 30), 'Lathe, welding, and fitting practice.'),
            ('Motor protection panel build', 'project', 'Electrical Machines Laboratory', project_map['Smart three-phase motor protection panel'], None, None, [], now.date() + timedelta(days=5), now.date() + timedelta(days=8), time.min, time.max, 'Dean-approved electrical capstone project.'),
            ('Micro-hydro runner test booking', 'project', 'Thermal and Fluid Laboratory', project_map['Micro-hydro turbine runner performance test'], None, None, [], now.date() + timedelta(days=9), now.date() + timedelta(days=12), time.min, time.max, 'Fluid test bench reserved for approved project.'),
            ('Obsolete machining safety induction', 'class', 'Manufacturing Workshop', None, 'Eng. Meseret Yilma', 'Mechanical Year 1', [4], now.date() - timedelta(days=28), now.date() - timedelta(days=20), time(10, 0), time(12, 0), 'Archived class session for schedule archive testing.'),
        ]
        for title, schedule_type, facility_name, project, instructor_name, student_group, days, period_start, period_end, time_from, time_to, notes in schedules:
            schedule = Schedule(title=title, schedule_type=schedule_type, facility_id=facility_map[facility_name].id, project_id=project.id if project else None, instructor_name=instructor_name, student_group=student_group, schedule_days=days, period_start=period_start, period_end=period_end, time_from=time_from, time_to=time_to, start_at=datetime.combine(period_start, time_from), end_at=datetime.combine(period_start, time_to), notes=notes)
            db.add(schedule)
            db.flush()
            audit(db, coordinator, 'created', 'schedules', schedule.id)

        usage_specs = [
            ('Digital Oscilloscope', 'control.lab@bdu.edu.et', 2, 'Control systems laboratory needs oscilloscopes for sensor signal practice.', 'consumed', Status.pending, None),
            ('MIG Welding Machine', 'manufacturing.workshop@bdu.edu.et', 1, 'One welding torch liner damaged during supervised practice.', 'discarded', Status.approved, 'Approved after workshop assistant attached damage report.'),
            ('Engine Diagnostic Scanner', 'automotive.workshop@bdu.edu.et', 1, 'Requested scanner temporary transfer to an off-campus garage training.', 'consumed', Status.rejected, 'Rejected; diagnostic scanners must remain inside BDU workshop.'),
            ('Transformer Test Bench', 'power.lab@bdu.edu.et', 1, 'One terminal block consumed during replacement after short circuit practice.', 'discarded', Status.approved, 'Approved; replacement terminal consumed and inventory reduced.'),
        ]
        for resource_name, requester_email, quantity, purpose, usage_type, status, notes in usage_specs:
            requester = user_map[requester_email]
            resource = resource_map[resource_name]
            request = EquipmentUsageRequest(resource_id=resource.id, facility_id=resource.facility_id, requester_id=requester.id, quantity=quantity, usage_type=usage_type, purpose=purpose, status=status)
            if status != Status.pending:
                request.approver_id = coordinator.id
                request.decision_notes = notes
                request.decided_at = now - timedelta(days=1)
                if status == Status.approved:
                    resource.quantity = max(0, resource.quantity - quantity)
            db.add(request)
            db.flush()
            audit(db, requester, 'created', 'equipment_usage_requests', request.id)
            if status != Status.pending:
                audit(db, coordinator, status.value, 'equipment_usage_requests', request.id)

        maintenance_specs = [
            ('Relay kit display not powering', 'Digital Protection Relay Kit', [0], 'power.lab@bdu.edu.et', None, Status.pending, None, 'high', 'internal', None, 'Display remains blank after power input check.'),
            ('Oscilloscope channel two noise', 'Digital Oscilloscope', [1], 'control.lab@bdu.edu.et', 'maintainer.electrical@bdu.edu.et', Status.assigned, None, 'medium', 'internal', None, 'Channel two has unstable baseline during measurements.'),
            ('Centrifugal pump seal leakage', 'Centrifugal Pump Test Rig', [0], 'thermal.lab@bdu.edu.et', 'maintainer.mechanical@bdu.edu.et', Status.in_progress, None, 'critical', 'internal', None, 'Pump seal leaks after ten minutes of operation.'),
            ('CNC lathe chuck vibration', 'CNC Lathe', [0], 'manufacturing.workshop@bdu.edu.et', 'maintainer.mechanical@bdu.edu.et', Status.completed, 'fixed', 'high', 'internal', 'Chuck jaws realigned and vibration reduced to acceptable level.', 'Chuck vibrates at medium spindle speed.'),
            ('Diesel test stand fuel pressure drop', 'Diesel Engine Test Stand', [0], 'automotive.workshop@bdu.edu.et', None, Status.completed, 'not_fixed', 'critical', 'external', 'Outsourced maintainer inspected fuel pump; replacement part is required.', 'Fuel pressure drops under load test.'),
            ('Induction motor bearing overheating', 'Three Phase Induction Motor Trainer', [2], 'machines.lab@bdu.edu.et', 'maintainer.electrical@bdu.edu.et', Status.rejected, None, 'low', 'internal', None, 'Assistant reported smell, but inspection found normal operating temperature.'),
        ]
        created_maintenance: dict[str, MaintenanceRequest] = {}
        for title, resource_name, indexes, requester_email, maintainer_email, status, resolution, priority, kind, completion, details in maintenance_specs:
            requester = user_map[requester_email]
            maintainer = user_map[maintainer_email] if maintainer_email else None
            resource = resource_map[resource_name]
            for index in indexes:
                asset = asset_map[resource_name][index]
                if status in (Status.pending, Status.assigned, Status.in_progress) or resolution == 'not_fixed':
                    asset.status = 'maintenance'
                elif resolution == 'fixed':
                    asset.status = 'available'
                item = MaintenanceRequest(title=title, details=details, priority=priority, kind=kind, status=status, resource_id=resource.id, asset_id=asset.id, facility_id=resource.facility_id, requester_id=requester.id, technician_id=maintainer.id if maintainer else None, resolution=resolution, completion_notes=completion, cost=6200 if kind == 'external' else 0 if status == Status.completed else None)
                db.add(item)
                db.flush()
                audit(db, requester, 'created', 'maintenance_requests', item.id)
                maintenance_event(db, item, requester, 'submitted', None, 'pending', f'{asset.identifier}: {details}')
                if status == Status.rejected:
                    maintenance_event(db, item, coordinator, 'rejected', 'pending', 'rejected', 'Inspection showed no repair was required.')
                    audit(db, coordinator, 'rejected', 'maintenance_requests', item.id)
                elif status != Status.pending:
                    maintenance_event(db, item, coordinator, 'approved', 'pending', 'approved', 'Coordinator approved the maintenance request.')
                    audit(db, coordinator, 'approved', 'maintenance_requests', item.id)
                if maintainer and status not in (Status.pending, Status.rejected):
                    maintenance_event(db, item, coordinator, 'assigned', 'approved', 'assigned', f'Assigned to {maintainer.full_name}.')
                    audit(db, coordinator, 'assigned', 'maintenance_requests', item.id)
                if status == Status.in_progress and maintainer:
                    maintenance_event(db, item, maintainer, 'started', 'assigned', 'in_progress', 'Maintainer started diagnosis and locked out the equipment.')
                    audit(db, maintainer, 'started', 'maintenance_requests', item.id)
                if status == Status.completed:
                    actor = maintainer or coordinator
                    maintenance_event(db, item, actor, 'fixed' if resolution == 'fixed' else 'outsourced_not_fixed', 'assigned' if maintainer else 'approved', 'completed', completion or 'Maintenance completed.')
                    audit(db, actor, 'completed', 'maintenance_requests', item.id)
                    if resolution == 'fixed':
                        item.assistant_verification = 'accepted'
                        item.verification_notes = 'Assistant verified the exact unit after repair.'
                        item.verified_at = now - timedelta(hours=4)
                        maintenance_event(db, item, requester, 'fix_verified', 'completed', 'completed', item.verification_notes)
                    else:
                        item.assistant_verification = 'follow_up_requested'
                        item.verification_notes = 'Assistant confirmed the equipment is still not fixed.'
                        item.verified_at = now - timedelta(hours=3)
                created_maintenance[title] = item

        parent = created_maintenance['Diesel test stand fuel pressure drop']
        follow_up = MaintenanceRequest(title='Follow-up: diesel test stand fuel pressure drop', details='Vendor part is required; previous outsourced repair did not fix the pressure drop.', priority='critical', kind='external', status=Status.pending, resource_id=parent.resource_id, asset_id=parent.asset_id, facility_id=parent.facility_id, requester_id=user_map['automotive.workshop@bdu.edu.et'].id, parent_request_id=parent.id)
        db.add(follow_up)
        db.flush()
        audit(db, user_map['automotive.workshop@bdu.edu.et'], 'created', 'maintenance_requests', follow_up.id)
        maintenance_event(db, parent, user_map['automotive.workshop@bdu.edu.et'], 'follow_up_requested', 'completed', 'completed', parent.verification_notes or 'Follow-up requested.')
        maintenance_event(db, follow_up, user_map['automotive.workshop@bdu.edu.et'], 'follow_up_submitted', None, 'pending', 'Follow-up request opened after not-fixed result.')

        db.commit()
    finally:
        db.close()


if __name__ == '__main__':
    seed()
