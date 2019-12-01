from flask import Blueprint, render_template, flash, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from farm.models import db
from farm.models.reservations import Reservation

from farm.extensions import cache
from farm.forms import RequestForm

import farm.tasks.testbench as tb_tasks
import farm.tasks.reservation as reserve_tasks

import boto3
import json
from multiprocessing.pool import ThreadPool

tb_reservation = Blueprint('tb_reservation', __name__)

def on_raw_message(body):
    print(body)

@tb_reservation.route("/testbench/reservation/list.json")
@tb_reservation.route("/testbench/reservation/list")
@tb_reservation.route("/testbench/reservation", methods=('GET', 'POST'))
@login_required
def reservations():
    form = RequestForm()
    error = None

    try:
        if form.validate_on_submit():
            json_data = json.loads(form.request.data)
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(reserve_tasks.create_reservation, (json_data, current_user.username))

            return redirect(url_for('tb_reservation.reservations'))
    except ValueError as e:
        print(e)
        error = e.message
        print(error)

    reservations = reserve_tasks.list_reservations()
    if request.path.endswith('.json'):
        return jsonify(reservations)
    else:
        return render_template('testbench/reservation.html', reservations=reservations, form=form, error=error)

@tb_reservation.route("/testbench/reservation/new", methods=('GET', 'POST'))
@login_required
def testbed_reserve_request():
    if request.method == 'POST':
        uuid = str(reserve_tasks.generate_uuid())
 
        pool = ThreadPool()
        async_result = pool.apply_async(reserve_tasks.create_reservation, (request.json, current_user.username, uuid))

        return json.dumps({'uuid': uuid})

    return redirect(url_for('tb_reservation.reservations'))

@tb_reservation.route("/testbench/reservation/<uuid>", methods=('GET', 'DELETE'))
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

    reservation_info = json.loads(reservation.reservation_info)
    if reserve_tasks.is_reservation_error(reservation):
        print(reservation_info.get("error", "Error finding information on uuid %s" % uuid))
        pass
    else:
        reservation_info = json.loads(reservation.reservation_info)

        # Update reservation_info['info'] from get_testbed if there are new values
        if reservation_info.get("testbed") != None and reservation_info['state'] != "DELETED":
            if cmp(reservation_info.get("info"), tb_tasks.get_testbed(reservation_info.get("testbed"))) != 0:
                reservation_info['info']=tb_tasks.get_testbed(reservation_info['testbed'])
                reserve_tasks.update_reservation_db(uuid=uuid, reservation_info=json.dumps(reservation_info))

    return jsonify(reservation_info)

