from flask import Blueprint, render_template, flash, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from farm.models import db
from farm.models.reservations import Reservation

from farm.extensions import cache
from farm.forms import UfarmNewForm, TestBenchEditForm

import farm.tasks.testbench as tb_tasks
import farm.tasks.reservation as reserve_tasks

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

@testbench.route("/testbench/testbed/<testbed_id>.json")
@testbench.route("/testbench/testbed/<testbed_id>")
@login_required
def testbed_view(testbed_id):
    testbed = tb_tasks.get_testbed(testbed_id)
    if request.path.endswith('.json'):
        return jsonify(testbed)
    else:
        return render_template('testbench/testbed.html', testbed_id=testbed_id, testbed=testbed)

@testbench.route("/testbench/testbed/<testbed_id>/edit", methods=('GET', 'POST'))
@login_required
def testbed_edit(testbed_id):
    testbed = tb_tasks.get_testbed(testbed_id)

    data = {}

    from wtforms import StringField
    for prop in testbed.get('properties'):
        setattr(TestBenchEditForm, prop, StringField(default=testbed['properties'][prop]))
        data[prop] = testbed['properties'][prop]

    form = TestBenchEditForm()

    # Clean attribute to prevent cached form
    for prop in testbed.get('properties'):
        delattr(TestBenchEditForm, prop)

    if request.method == 'POST' and form.validate_on_submit():
        for field in form:
            if field.type == 'StringField' and data[field.name] != field.data:
                tb_tasks.set_testbed_info(testbed_id, 'properties', field.name, field.data)
        return redirect(url_for('testbench.testbed_view', testbed_id=testbed_id))

    return render_template('testbench/testbed_edit.html', testbed_id=testbed_id, testbed=testbed, form=form)

@testbench.route("/testbench/testbed/<testbed_id>/launch")
@login_required
def testbed_launch(testbed_id):
    request = {"filters":{"testbed_id":testbed_id}, "description": "Launched from browser UI"}

    # If launched from UI, we want to wait for testbed to launch before redirection
    reserve_tasks.create_reservation(request=request, user=current_user.username)

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
                end_date = reserve_tasks.date_now("end_date")
                reservation_info.update(end_date)

                reservation_info["state"] = "DELETED"
                reserve_tasks.update_reservation_db(uuid=reservation.uuid, reservation_info=json.dumps(reservation_info))

        # Manually destroy the testbed_id anyways
        tb_tasks.destroy(testbed_id)
    else:
        result = reserve_tasks.delete_reservation(reservation)
        if result is False:
            return "Failed to destroy testbed"

    return redirect(url_for('testbench.testbed_view', testbed_id=testbed_id))

