import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.core.database import Base
from app.models import Role, Store, StoreLot, StoreRequest, User
from app.router import ChairAccessIn, set_chair_access, validate_user_facilities
from app.store import (AssignIn, DecisionIn, DocumentIn, IssueIn, LineIn, MaterialIn, RequestIn,
                       ReturnIn, ReviewIn, StoreIn, accept_lot,
                       assign_store, catalog, chair_review, coordinator_review, create_request,
                       create_store, dean_review, issue, items, list_stores, loans, record_material, report, requests, return_item, review_store, signed_document)


class StoreFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.users = {}
        for name in ('coordinator', 'chair', 'dean', 'lab_admin', 'store_manager'):
            role = Role(name=name, permissions='[]')
            user = User(email=f'{name}@bdu.edu.et', full_name=name, password_hash='test', roles=[role],
                        must_change_password=False, is_active=True, assigned_facility_ids=[], pending_facility_ids=[])
            self.db.add(user); self.users[name] = user
        self.db.flush()
        self.store = create_store(StoreIn(name='Engineering Materials', location='Block A'), self.db, self.users['coordinator'])

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def material(self, kind):
        lot = record_material(self.store['id'], MaterialIn(name=f'{kind} test', category='test', kind=kind,
            unit='each', quantity=8, purchase_reference='PUR-001'), self.db, self.users['coordinator'])
        item = lot['item']
        assign_store(self.store['id'], AssignIn(manager_id=self.users['store_manager'].id), self.db, self.users['coordinator'])
        with self.assertRaises(HTTPException):
            accept_lot(lot['id'], self.db, self.users['store_manager'])
        with self.assertRaises(HTTPException):
            review_store(self.store['id'], ReviewIn(accepted=True), self.db, self.users['store_manager'])
        review_store(self.store['id'], ReviewIn(accepted=True, checked_lot_ids=[lot['id']]), self.db, self.users['store_manager'])
        return item, lot['id']

    def request(self, item, kind, position='staff'):
        return create_request(RequestIn(requester_name='Test Student', requester_contact='student@bdu.edu.et',
            department='Engineering', purpose='Class demonstration', kind=kind,
            requester_position=position, chair_id=self.users['chair'].id if position=='staff' else None,
            store_id=self.store['id'],
            lines=[LineIn(item_id=item['id'], quantity=3)]), self.db)

    def test_consumable_requires_chair_dean_and_paper(self):
        item, lot_id = self.material('consumable')
        request = self.request(item, 'consumable')
        row = self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        self.assertEqual(requests(skip=0,limit=25,db=self.db,user=self.users['store_manager'])['meta']['total'],0)
        chair_review(row.id, DecisionIn(approve=True), self.db, self.users['chair'])
        dean_review(row.id, DecisionIn(approve=True), self.db, self.users['dean'])
        self.assertEqual(row.assigned_manager_id,self.users['store_manager'].id)
        self.assertEqual(requests(skip=0,limit=25,db=self.db,user=self.users['store_manager'])['meta']['total'],1)
        with self.assertRaises(Exception):
            issue(row.id, IssueIn(paper_verified=False), self.db, self.users['store_manager'])
        with self.assertRaises(Exception):
            issue(row.id, IssueIn(paper_verified=True), self.db, self.users['lab_admin'])
        issue(row.id, IssueIn(paper_verified=True), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, lot_id).available, 5)
        self.assertEqual(row.status, 'issued')
        summary = report(store_id=self.store['id'], db=self.db, user=self.users['coordinator'])['summary']
        self.assertEqual((summary['received'], summary['consumed'], summary['on_hand']), (8, 3, 5))
        manager_report=report(db=self.db,user=self.users['store_manager'])
        self.assertEqual(manager_report['summary']['consumed'],3)
        self.assertEqual(manager_report['movements'][0]['reference'],row.reference)
        self.assertEqual(manager_report['movements'][0]['actor'],self.users['store_manager'].full_name)

    def test_durable_partial_return_restores_source_lot(self):
        item, lot_id = self.material('durable')
        request = self.request(item, 'durable')
        row = self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        with self.assertRaises(HTTPException):
            issue(row.id, IssueIn(paper_verified=False, due_at=datetime.now(timezone.utc)+timedelta(minutes=30)), self.db, self.users['store_manager'])
        issue(row.id, IssueIn(paper_verified=False, borrower_verified=True, due_at=datetime.now(timezone.utc)+timedelta(minutes=30)), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, lot_id).available, 5)
        active=loans(db=self.db,user=self.users['store_manager'])
        self.assertEqual(active['meta']['total'],1)
        self.assertEqual(active['data'][0]['requester_contact'],'student@bdu.edu.et')
        self.assertEqual(active['data'][0]['lines'][0]['quantity'],3)
        self.assertEqual(report(db=self.db,user=self.users['dean'])['movements'][0]['borrower'],'Test Student')
        return_item(row.id, ReturnIn(item_id=item['id'], quantity=2), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, lot_id).available, 7)
        self.assertEqual(row.status, 'borrowed')
        self.assertEqual(loans(db=self.db,user=self.users['store_manager'])['data'][0]['lines'][0]['returned'],2)
        return_item(row.id, ReturnIn(item_id=item['id'], quantity=1), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, lot_id).available, 8)
        self.assertEqual(row.status, 'returned')
        self.assertEqual(loans(db=self.db,user=self.users['store_manager'])['meta']['total'],0)
        self.assertEqual(loans(status='returned',db=self.db,user=self.users['store_manager'])['meta']['total'],1)

    def test_signed_form_only_for_confirmed_consumables_and_assigned_store_man(self):
        item,_=self.material('consumable')
        request=self.request(item,'consumable')
        row=self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        document=DocumentIn(filename='signed.jpg',content_base64='invalid')
        with self.assertRaises(HTTPException) as error:
            signed_document(row.id,document,self.db,self.users['store_manager'])
        self.assertEqual(error.exception.status_code,409)
        chair_review(row.id,DecisionIn(approve=True),self.db,self.users['chair'])
        dean_review(row.id,DecisionIn(approve=True),self.db,self.users['dean'])
        with self.assertRaises(HTTPException) as error:
            signed_document(row.id,document,self.db,self.users['lab_admin'])
        self.assertEqual(error.exception.status_code,404)
        with self.assertRaises(HTTPException) as error:
            signed_document(row.id,document,self.db,self.users['store_manager'])
        self.assertEqual(error.exception.status_code,422)

    def test_overdue_loan_only_visible_to_own_store_manager_and_dean(self):
        item,_=self.material('durable')
        request=self.request(item,'durable')
        row=self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        issue(row.id,IssueIn(paper_verified=False,borrower_verified=True,
            due_at=datetime.now(timezone.utc)+timedelta(minutes=1)),self.db,self.users['store_manager'])
        row.due_at=datetime.now(timezone.utc)-timedelta(minutes=1)
        self.db.commit()
        self.assertEqual(loans(status='overdue',db=self.db,user=self.users['store_manager'])['meta']['total'],1)
        self.assertEqual(loans(status='overdue',db=self.db,user=self.users['dean'])['meta']['total'],1)
        with self.assertRaises(HTTPException) as error:
            loans(status='overdue',db=self.db,user=self.users['chair'])
        self.assertEqual(error.exception.status_code,403)
        return_item(row.id,ReturnIn(item_id=item['id'],quantity=3),self.db,self.users['store_manager'])
        self.assertEqual(loans(status='overdue',db=self.db,user=self.users['store_manager'])['meta']['total'],0)

    def test_chair_and_dean_request_routes(self):
        item, _ = self.material('consumable')
        chair_request = self.request(item, 'consumable', 'chair')
        chair_row = self.db.query(StoreRequest).filter_by(reference=chair_request['reference']).one()
        self.assertEqual(chair_row.status, 'dean_review')
        dean_review(chair_row.id, DecisionIn(approve=True), self.db, self.users['dean'])
        self.assertEqual(chair_row.status, 'ready')
        dean_request = self.request(item, 'consumable', 'dean')
        dean_row = self.db.query(StoreRequest).filter_by(reference=dean_request['reference']).one()
        self.assertEqual(dean_row.status, 'coordinator_review')
        coordinator_review(dean_row.id, DecisionIn(approve=True), self.db, self.users['coordinator'])
        self.assertEqual(dean_row.status, 'ready')

    def test_only_selected_chair_can_review_staff_request(self):
        item, _ = self.material('consumable')
        request = self.request(item, 'consumable')
        row = self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        other = User(email='other.chair@bdu.edu.et', full_name='Other Chair', password_hash='test',
                     roles=[self.users['chair'].roles[0]], must_change_password=False,
                     is_active=True, assigned_facility_ids=[], pending_facility_ids=[])
        self.db.add(other)
        self.db.commit()
        self.assertEqual(requests(skip=0, limit=25, db=self.db, user=other)['meta']['total'], 0)
        with self.assertRaises(HTTPException) as error:
            chair_review(row.id, DecisionIn(approve=True), self.db, other)
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(row.status, 'chair_review')

    def test_coordinator_can_grant_chair_to_existing_user_without_changing_primary_role(self):
        assistant=self.users['lab_admin']
        result=set_chair_access(assistant.id,ChairAccessIn(enabled=True),self.db,self.users['coordinator'])
        self.assertTrue(result['has_chair_access'])
        self.assertEqual({role.name for role in assistant.roles},{'lab_admin','chair'})
        result=set_chair_access(assistant.id,ChairAccessIn(enabled=False),self.db,self.users['coordinator'])
        self.assertFalse(result['has_chair_access'])
        self.assertEqual({role.name for role in assistant.roles},{'lab_admin'})
        dean=self.users['dean']
        set_chair_access(dean.id,ChairAccessIn(enabled=True),self.db,self.users['coordinator'])
        self.assertEqual({role.name for role in dean.roles},{'dean','chair'})

    def test_chair_role_only_confirms_assigned_requests(self):
        item,_=self.material('consumable')
        request=self.request(item,'consumable')
        row=self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        chair=self.users['chair']
        for operation in (lambda:list_stores(self.db,chair),lambda:items(self.db,chair),
                          lambda:report(db=self.db,user=chair)):
            with self.assertRaises(HTTPException) as error: operation()
            self.assertEqual(error.exception.status_code,403)
        with self.assertRaises(HTTPException) as error:
            chair_review(row.id,DecisionIn(approve=False,notes='No'),self.db,chair)
        self.assertEqual(error.exception.status_code,422)
        self.assertEqual(row.status,'chair_review')
        chair_review(row.id,DecisionIn(approve=True),self.db,chair)
        self.assertEqual(row.status,'dean_review')

    def test_same_person_cannot_confirm_as_chair_and_approve_as_dean(self):
        item,_=self.material('consumable')
        dean=self.users['dean']
        set_chair_access(dean.id,ChairAccessIn(enabled=True),self.db,self.users['coordinator'])
        request=create_request(RequestIn(requester_name='Staff Member',requester_contact='staff@bdu.edu.et',
            department='Engineering',purpose='Workshop practice',kind='consumable',chair_id=dean.id,
            store_id=self.store['id'],lines=[LineIn(item_id=item['id'],quantity=1)]),self.db)
        row=self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        chair_review(row.id,DecisionIn(approve=True),self.db,dean)
        with self.assertRaises(HTTPException) as error:
            dean_review(row.id,DecisionIn(approve=True),self.db,dean)
        self.assertEqual(error.exception.status_code,403)

    def test_dean_report_covers_all_stores_but_store_man_only_theirs(self):
        self.material('consumable')
        other=create_store(StoreIn(name='Second Materials Store',location='Block B'),self.db,self.users['coordinator'])
        lot=record_material(other['id'],MaterialIn(name='Copper wire',category='Electrical',kind='consumable',
            unit='roll',quantity=5,purchase_reference='PO-25'),self.db,self.users['coordinator'])
        manager=User(email='second.store@bdu.edu.et',full_name='Second Store Man',password_hash='test',
            roles=[self.users['store_manager'].roles[0]],must_change_password=False,is_active=True,
            assigned_facility_ids=[],pending_facility_ids=[])
        self.db.add(manager);self.db.flush()
        assign_store(other['id'],AssignIn(manager_id=manager.id),self.db,self.users['coordinator'])
        review_store(other['id'],ReviewIn(accepted=True,checked_lot_ids=[lot['id']]),self.db,manager)
        dean_report=report(db=self.db,user=self.users['dean'])
        first_report=report(db=self.db,user=self.users['store_manager'])
        self.assertEqual(dean_report['summary']['stores'],2)
        self.assertEqual(dean_report['summary']['on_hand'],13)
        self.assertEqual(report(db=self.db,user=self.users['dean'],movement_limit=1)['movements_meta']['total'],2)
        self.assertEqual(len(report(db=self.db,user=self.users['dean'],movement_skip=1,movement_limit=1)['movements']),1)
        self.assertEqual(first_report['summary']['stores'],1)
        self.assertEqual(first_report['summary']['on_hand'],8)
        with self.assertRaises(HTTPException) as error:
            report(store_id=other['id'],db=self.db,user=self.users['store_manager'])
        self.assertEqual(error.exception.status_code,403)

    def test_pending_approved_request_follows_store_man_reassignment(self):
        item,lot_id=self.material('consumable')
        request=self.request(item,'consumable')
        row=self.db.query(StoreRequest).filter_by(reference=request['reference']).one()
        chair_review(row.id,DecisionIn(approve=True),self.db,self.users['chair'])
        dean_review(row.id,DecisionIn(approve=True),self.db,self.users['dean'])
        replacement=User(email='replacement.store@bdu.edu.et',full_name='Replacement Store Man',password_hash='test',
            roles=[self.users['store_manager'].roles[0]],must_change_password=False,is_active=True,
            assigned_facility_ids=[],pending_facility_ids=[])
        self.db.add(replacement);self.db.flush()
        assign_store(self.store['id'],AssignIn(manager_id=replacement.id),self.db,self.users['coordinator'])
        self.assertEqual(row.assigned_manager_id,replacement.id)
        with self.assertRaises(HTTPException):
            issue(row.id,IssueIn(paper_verified=True),self.db,self.users['store_manager'])
        review_store(self.store['id'],ReviewIn(accepted=True,checked_lot_ids=[lot_id]),self.db,replacement)
        issue(row.id,IssueIn(paper_verified=True),self.db,replacement)
        self.assertEqual(self.db.get(StoreLot,lot_id).available,5)

    def test_store_manager_is_not_facility_assistant(self):
        with self.assertRaises(HTTPException):
            validate_user_facilities(self.db, {'store_manager'}, {1})

    def test_coordinator_records_material_before_handover(self):
        with self.assertRaises(HTTPException) as error:
            assign_store(self.store['id'], AssignIn(manager_id=self.users['store_manager'].id), self.db, self.users['coordinator'])
        self.assertEqual(error.exception.status_code, 409)
        lot = record_material(self.store['id'], MaterialIn(name='Welding rods', category='Welding',
            kind='consumable', unit='box', quantity=12, purchase_reference='PO-22'),
            self.db, self.users['coordinator'])
        self.assertEqual(lot['status'], 'pending')
        self.assertEqual(catalog(self.db)['stores'], [])
        with self.assertRaises(HTTPException):
            create_request(RequestIn(requester_name='Staff Member', requester_contact='staff@bdu.edu.et',
                department='Engineering', purpose='Class practice', kind='consumable',
                chair_id=self.users['chair'].id, store_id=self.store['id'],
                lines=[LineIn(item_id=lot['item']['id'], quantity=2)]), self.db)
        assign_store(self.store['id'], AssignIn(manager_id=self.users['store_manager'].id), self.db, self.users['coordinator'])
        with self.assertRaises(HTTPException):
            review_store(self.store['id'], ReviewIn(accepted=True, checked_lot_ids=[]), self.db, self.users['store_manager'])
        review_store(self.store['id'], ReviewIn(accepted=True, checked_lot_ids=[lot['id']]), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, lot['id']).available, 12)
        self.assertEqual(catalog(self.db)['stores'][0]['id'], self.store['id'])

    def test_handover_requires_every_recorded_material(self):
        first = record_material(self.store['id'], MaterialIn(name='Steel bar', category='Metal',
            kind='consumable', unit='piece', quantity=10, purchase_reference='PO-23'),
            self.db, self.users['coordinator'])
        assign_store(self.store['id'], AssignIn(manager_id=self.users['store_manager'].id), self.db, self.users['coordinator'])
        second = record_material(self.store['id'], MaterialIn(name='Drill press', category='Tools',
            kind='durable', unit='piece', quantity=2, purchase_reference='PO-24'),
            self.db, self.users['coordinator'])
        with self.assertRaises(HTTPException):
            review_store(self.store['id'], ReviewIn(accepted=True, checked_lot_ids=[first['id']]),
                         self.db, self.users['store_manager'])
        review_store(self.store['id'], ReviewIn(accepted=True,
            checked_lot_ids=[first['id'], second['id']]), self.db, self.users['store_manager'])
        self.assertEqual(self.db.get(StoreLot, first['id']).available, 10)
        self.assertEqual(self.db.get(StoreLot, second['id']).available, 2)


if __name__ == '__main__':
    unittest.main()
