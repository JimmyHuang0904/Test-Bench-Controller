from flask import Blueprint, render_template, flash, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from testbench.models import db
from testbench.models.reservations import Reservation

from testbench.extensions import cache
from testbench.forms import UfarmNewForm, TestBenchEditForm

import testbench.tasks.testbench as tb_tasks
import testbench.tasks.reservation as reserve_tasks

from datetime import datetime
import boto3
import json
from multiprocessing.pool import ThreadPool

testbench = Blueprint('testbench', __name__)

def on_raw_message(body):
    print(body)

@testbench.route("/testbench.json")
@testbench.route("/testbench")
@login_required
def testbeds():
    testbeds = tb_tasks.list_testbeds()
    if request.path.endswith('.json'):
        return jsonify(testbeds)
    else:
        return render_template('testbench/testbeds.html', testbeds=testbeds)

@testbench.route("/testbench/reservation")
@login_required
def list_reservations():
    active_reservations = []
    other_reservations = []
    all_reservations = []

    print(Reservation.query.all())
    for reservation in Reservation.query.all():
        reservation_info = json.loads(reservation.reservation_info)

        # Display active reservations first before all others
        if reservation_info.get("state") == "READY":
            active_reservations.append(reservation.reservation_info)
        else:
            other_reservations.append(reservation.reservation_info)

    all_reservations = active_reservations + other_reservations

    return render_template('testbench/reservation.html', reservations=all_reservations)

@testbench.route("/testbench/reservation/new", methods=('GET', 'POST'))
@login_required
def testbed_reserve_request():
    if request.method == 'POST':
        uuid = str(reserve_tasks.generate_uuid())
        print("uuid is %s" % uuid)

        pool = ThreadPool(processes=1)
        async_result = pool.apply_async(reserve_tasks.create_reservation, (uuid, request.json, current_user.username))

        return json.dumps({'uuid': uuid})
    else:
        # Here should print all the reservations
        print(request.method)

    return render_template('testbench/reservation.html')

@testbench.route("/testbench/reservation/<uuid>", methods=('GET', 'DELETE'))
@login_required
def reserve_info_by_uuid(uuid):
    # If uuid does not exist in database, return error on webpage
    reservation = Reservation.query.filter_by(uuid=uuid).first_or_404()

    if request.method == 'DELETE':
        result = reserve_tasks.delete_reservation(reservation)
        if result is False:
            return "Failed to delete UUID"

        # Load new reservation_info after delete_reservation
        reservation_info = json.loads(reservation.reservation_info)

        return jsonify(reservation_info)

    if reserve_tasks.is_reservation_error(reservation):
        error = reservation.reservation_info
    else:
        reservation_info = json.loads(reservation.reservation_info)

        # Update reservation_info['info'] from get_testbed if there are new values
        if 'info' in reservation_info and reservation_info['state'] != "DELETED":
            if cmp(reservation_info['info'], tb_tasks.get_testbed(reservation_info['testbed'])) != 0:
                reservation_info['info']=tb_tasks.get_testbed(reservation_info['testbed'])
                reserve_tasks.update_reservation_db(uuid=uuid, reservation_info=json.dumps(reservation_info))

        return jsonify(reservation_info)

    return error
    # return render_template('testbench/reservation.html')

@testbench.route("/testbench/testbed/<testbed_id>.json")
@testbench.route("/testbench/testbed/<testbed_id>")
@login_required
def testbed_view(testbed_id):
    testbed = tb_tasks.get_testbed(testbed_id)
    if request.path.endswith('.json'):
        return jsonify(testbed)
    else:
        return render_template('testbench/testbed.html', testbed_id=testbed_id, testbed=testbed)

@testbench.route("/testbench/<testbed_id>/edit", methods=('GET', 'POST'))
@login_required
def testbed_edit(testbed_id):
    testbed = tb_tasks.get_testbed(testbed_id)

    data = {}

    from wtforms import StringField
    for prop in testbed['properties']:
        setattr(TestBenchEditForm, prop, StringField(default=testbed['properties'][prop]))
        data[prop] = testbed['properties'][prop]

    form = TestBenchEditForm()

    if request.method == 'POST' and form.validate_on_submit():
        for field in form:
            if field.type == 'StringField' and data[field.name] != field.data:
                tb_tasks.set_testbed_info(testbed_id, 'properties', field.name, field.data)
        return redirect(url_for('testbench.testbed_view', testbed_id=testbed_id))

    return render_template('testbench/testbed_edit.html', testbed_id=testbed_id, testbed=testbed, form=form)

@testbench.route("/testbench/testbed/<testbed_id>/launch")
@login_required
def testbed_launch(testbed_id):
    uuid = str(reserve_tasks.generate_uuid())
    print("uuid is %s" % uuid)

    request = {"filters":{"testbed_id":testbed_id}, "description": "Launched from browser UI"}

    # If launched from UI, we want to wait for testbed to launch before redirection
    reserve_tasks.create_reservation(uuid, request, current_user.username)

    return redirect(url_for('testbench.testbed_view', testbed_id=testbed_id))

@testbench.route("/testbench/testbed/<testbed_id>/destroy")
@login_required
def testbed_destroy(testbed_id):
    testbed = tb_tasks.get_testbed(testbed_id)

    uuid = testbed.get('instance', {}).get('uuid')

    reservation = Reservation.query.filter_by(uuid=uuid).first()
    if reservation == None:
        print("is UUID successfully written in instances or the database?")

        # Try to search for a reservation with testbed_id that is in a READY state and overide the state in the DB
        for reservation in Reservation.query.all():
            reservation_info = json.loads(reservation.reservation_info)
            if reservation_info.get("testbed") == testbed_id and reservation_info.get("state") == "READY":
                reservation_info['end_date'] = str(datetime.now())
                reservation_info["state"] = "DELETED"
                reserve_tasks.update_reservation_db(uuid=reservation.uuid, reservation_info=json.dumps(reservation_info))

        # Manually destroy the testbed_id anyways
        tb_tasks.destroy(testbed_id)
    else:
        result = reserve_tasks.delete_reservation(reservation)
        if result is False:
            return "Failed to destroy testbed"

    return redirect(url_for('testbench.testbed_view', testbed_id=testbed_id))

