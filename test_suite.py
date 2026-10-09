import sys
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import User, Category, ServiceRequest, StatusEnum, PriorityEnum, RoleEnum
from app.schemas import ServiceRequestCreate, ServiceRequestAssign, ServiceRequestStatusUpdate
from app import crud
from fastapi import HTTPException

def run_tests():
    db = SessionLocal()
    print("==================================================")
    print("   RUNNING HACKATHON AUTOMATED TEST SUITE        ")
    print("==================================================")

    passed = 0
    failed = 0

    def assert_test(name, condition):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            failed += 1

    try:
        # TEST 1: Positive - Create Ticket & Auto SLA Calculation
        req_in = ServiceRequestCreate(
            requester_id=1,
            subject="VPN connection failing from home",
            description="Unable to connect to company gateway through Cisco AnyConnect.",
            category_id=3, # Network
            priority=PriorityEnum.CRITICAL
        )
        ticket = crud.create_service_request(db, req_in)
        assert_test("Ticket Created with status 'New'", ticket.status == StatusEnum.NEW)
        assert_test("Critical SLA computed to 4 Hours", ticket.sla_due_at is not None and (ticket.sla_due_at - ticket.created_at).total_seconds() == 14400)
        assert_test("SLA status flagged as 'Within SLA'", ticket.sla_status == "Within SLA")

        # TEST 2: Positive - Valid IT Agent Assignment
        assign_in = ServiceRequestAssign(assignee_id=3, actor_id=5) # Charlie (IT_Agent)
        assigned_ticket = crud.assign_request(db, ticket.id, assign_in)
        assert_test("Ticket Assigned to IT Agent", assigned_ticket.assignee_id == 3)
        assert_test("Status auto-moves from New -> Assigned", assigned_ticket.status == StatusEnum.ASSIGNED)

        # TEST 3: Negative - Invalid Assignment to non-IT user
        try:
            crud.assign_request(db, ticket.id, ServiceRequestAssign(assignee_id=2, actor_id=5)) # Bob is Requester
            assert_test("Block assignment to non-IT user", False)
        except HTTPException as e:
            assert_test("Block assignment to non-IT user (HTTP 400)", e.status_code == 400)

        # TEST 4: Negative - Invalid Status Transition (Cannot jump Assigned -> Closed directly)
        try:
            crud.update_status(db, ticket.id, ServiceRequestStatusUpdate(new_status=StatusEnum.CLOSED, actor_id=3))
            assert_test("Block direct jump to Closed", False)
        except HTTPException as e:
            assert_test("Block direct jump to Closed without processing (HTTP 400)", e.status_code == 400)

        # TEST 5: Negative - Resolve without resolution details
        crud.update_status(db, ticket.id, ServiceRequestStatusUpdate(new_status=StatusEnum.IN_PROGRESS, actor_id=3))
        try:
            crud.update_status(db, ticket.id, ServiceRequestStatusUpdate(new_status=StatusEnum.RESOLVED, actor_id=3, resolution_details=""))
            assert_test("Block Resolve without details", False)
        except HTTPException as e:
            assert_test("Block Resolve without resolution details (HTTP 400)", e.status_code == 400)

        # TEST 6: Positive - Proper Resolution & Closure
        resolved_ticket = crud.update_status(db, ticket.id, ServiceRequestStatusUpdate(
            new_status=StatusEnum.RESOLVED,
            actor_id=3,
            resolution_details="Reset user VPN profile and certificates on firewall."
        ))
        assert_test("Ticket marked Resolved with details", resolved_ticket.status == StatusEnum.RESOLVED and resolved_ticket.resolved_at is not None)

        closed_ticket = crud.update_status(db, ticket.id, ServiceRequestStatusUpdate(new_status=StatusEnum.CLOSED, actor_id=5))
        assert_test("Ticket marked Closed", closed_ticket.status == StatusEnum.CLOSED and closed_ticket.closed_at is not None)

        # TEST 7: Negative - Modify a Closed Ticket
        try:
            crud.assign_request(db, ticket.id, ServiceRequestAssign(assignee_id=4, actor_id=5))
            assert_test("Block modifying a closed ticket", False)
        except HTTPException as e:
            assert_test("Block modifying a closed ticket (HTTP 400)", e.status_code == 400)

        # TEST 8: Positive - Audit History Trail
        history = crud.get_history(db, ticket.id)
        assert_test("Audit history recorded every action (>= 4 records)", len(history) >= 4)

    finally:
        db.close()

    print("==================================================")
    print(f"TESTS COMPLETED: {passed} Passed, {failed} Failed")
    print("==================================================")

if __name__ == "__main__":
    run_tests()