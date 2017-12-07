from testbench.extensions import celery
from celery.utils.log import get_task_logger

from testbench.models import db
from testbench.models.reservations import Reservation

import testbench.tasks.testbench as tb_tasks
import json
import time
from datetime import datetime, timedelta

logger = get_task_logger(__name__)

@celery.task()
def generate_uuid():
    import uuid
    return uuid.uuid4()

@celery.task()
def write_to_reservation_db(uuid, reservation_info):
    result = False
    try:
        reservation = Reservation(reservation_info=reservation_info, uuid=str(uuid))
        db.session.add(reservation)
        db.session.commit()
        result = True
    except:
        logger.info("DB may be locked due to external operations. Reservation discarded")

    return result

@celery.task()
def update_reservation_db(uuid, reservation_info):
    result = False
    try:
        reservation = Reservation.query.filter_by(uuid=uuid).update(dict(reservation_info=reservation_info))
        db.session.commit()
        result = True
    except:
        print("Error - Updating UUID: %s has failed" % uuid)

    return result

@celery.task()
def description_from_request(request):
    description = request.get("description", "No description was provided")

    return {"description": description}

@celery.task()
def date_now(date_key):
    return {date_key: str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}

@celery.task()
def state_json(state):
    return {"state": state}

@celery.task()
def create_reservation(uuid, request, user):
    reservation_info = {}
    try:
        # Write state to be IN PROGRESS
        state = state_json("IN PROGRESS")
        reservation_info.update(state)

        # Write description from request
        description = description_from_request(request)
        reservation_info.update(description)

        # Write creation_date
        creation_date = date_now("creation_date")
        reservation_info.update(creation_date)

        # Write user - path to user name
        user_info = {'info' : {'user': {'name':user}}}
        reservation_info.update(user_info)

        # First write to the reservation_db (an initial state)
        result = write_to_reservation_db(uuid=uuid, reservation_info=json.dumps(reservation_info))
        if result == False:
            print("Failed to initialize reservation with description and/or date")

        # Update reservation with testbed info if any
        reservation_info_update = reserve_testbed_by_request(request, user)
        reservation_info.update(reservation_info_update)

        # Write uuid into etcd under instance before getting info on testbed
        if reservation_info.get("error") == None:
            state = state_json("READY")

            tb_tasks.set_testbed_info(reservation_info["testbed"], 'instance', 'uuid', uuid)
            reservation_info["info"] = tb_tasks.get_testbed(reservation_info.get("testbed"))
        else:
            state = state_json("ERROR")

            # Declare end_date of the reservation
            end_date = date_now("end_date")
            reservation_info.update(end_date)

        reservation_info.update(state)

        # Second write to the reservation_db (an update state)
        result = update_reservation_db(uuid=uuid, reservation_info=json.dumps(reservation_info))
        if result == False:
            print("Failed to update reservation into the database")

    except:
        error ={'error': "Unexpected error in reserve_task.create_reservation"}
        reservation_info.update(error)
        logger.info(error.get('error'))

        state = state_json("ERROR")
        reservation_info.update(state)
        try:
            # Try to display error into the reservation
            update_reservation_db(uuid=uuid, reservation_info=json.dumps(reservation_info))
        except:
            logger.info("Failed to update reservation")

@celery.task()
def reserve_testbed_by_request(request, user):
    error = None
    testbeds = tb_tasks.list_testbeds()

    if 'filters' not in request:
        error = {'error': "There is no 'filters' tag in the request"}
        return error

    # Initialize boolean array for all testbed to be true
    boolArray = {}
    for testbed in testbeds:
        boolArray[testbed] = True

    for filter in request["filters"]:
        for testbed in testbeds:
            if "testbed_id" in filter and request["filters"]["testbed_id"] == testbed:
                continue
            elif filter not in testbeds[testbed]['properties']:
                boolArray[testbed] = False
                continue
            elif request["filters"][filter] != testbeds[testbed]['properties'][filter]:
                boolArray[testbed] = False
                continue

    if not any(boolArray.values()):
        error = {'error': "No Matching filters"}
        return error

    matching_testbeds = set()
    for testbed in boolArray:
        if boolArray[testbed] == True:
            if is_launched_by_user(testbed, user):
                return {'testbed': testbed}
            else:
                matching_testbeds.add(testbed)

    # Retry for 10 seconds
    wait_until = datetime.now() + timedelta(seconds=10)
    while True:
        for testbed in matching_testbeds:
            time.sleep(0.5)
            if is_launched_by_user(testbed, user):
                return {'testbed': testbed}
        if wait_until < datetime.now():
            break

    print(user)
    error = {'error': "No testbed with the requirements are available at the moment",
             'state': "EXPIRED" }
    return error

class ReservationAlreadyDeleted(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

@celery.task()
def delete_reservation(reservation):
    deleted = False
    try:
        if is_reservation_error(reservation):
            raise Exception

        reservation_info = json.loads(reservation.reservation_info)
        testbed_id = reservation_info.get("testbed")

        tb_tasks.destroy(testbed_id)

        # Append the end_date and overwrite the reservation_info in the database
        if reservation_info.get("end_date") != None:
            raise ReservationAlreadyDeleted(reservation_info)
        else:
            end_date = date_now("end_date")
            reservation_info.update(end_date)

            reservation_info['state'] = "DELETED"
            result = update_reservation_db(uuid=reservation.uuid, reservation_info=json.dumps(reservation_info))
            if result == False:
                raise Exception("DB may be locked due to external operations. Updating UUID: %s has failed" % reservation.uuid)

            deleted = True
    except ReservationAlreadyDeleted:
        print("Reservation already deleted")
    except:
        print("Unexpected error occured when deleting reservation UUID: %s" % reservation.uuid)

    return deleted

@celery.task()
def is_launched_by_user(testbed_id, user):
    result = tb_tasks.launch(testbed_id, { 'name': user })
    if result.get("launched") == None:
        raise Exception("tb_tasks.launch returns result that is neither True or False")
    if result.get("launched") == True:
        return True
    return False

@celery.task()
def is_reservation_error(reservation):
    data = json.loads(reservation.reservation_info)

    if data.get("error") == None:
        return False
    return True

