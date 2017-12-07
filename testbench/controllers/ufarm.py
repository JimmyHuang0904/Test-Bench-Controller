from flask import Blueprint, render_template, flash, request, redirect, url_for
from flask_login import login_user, logout_user, login_required

from testbench.extensions import cache
from testbench.forms import UfarmNewForm
from testbench.models.aws import AwsInstanceInfo

from testbench.tasks.aws import add_together

import boto3

ufarm = Blueprint('ufarm', __name__)

@ufarm.route('/ufarm/new')
@login_required
@cache.cached(timeout=1000)
def new():
    form = UfarmNewForm()

    instance_types = []
    for info in AwsInstanceInfo.query.all():
        desc = "%s [ %s ECU | %s vCPU | %sGB RAM | %.2fUSD/h ]" % (info.size, info.ECU, info.vCPU, info.memory, info.price)
        instance_types.append( (info.size, desc) )

    available_ids = []
    for id in range(3,254):
        available_ids.append( ("10.101.%d.0" % id, id) )

    form.subnet.choices = available_ids

    form.master_instance_type.data = "t2.medium"
    form.master_instance_type.choices = instance_types

    form.nodes_instance_type.data = 'm4.xlarge'
    form.nodes_instance_type.choices = instance_types

    return render_template('ufarm/new.html', form=form)

@ufarm.route('/ufarm')
@login_required
@cache.cached(timeout=1000)
def list():
    return render_template('ufarm/list.html')

