from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

import sys

# Syntax sugar.
_ver = sys.version_info

#: Python 2.x?
is_py2 = (_ver[0] == 2)

#: Python 3.x?
is_py3 = (_ver[0] == 3)

if is_py3:
    import urllib.request, urllib.error, urllib.parse
elif is_py2:
    import urllib2
import csv
import re
import json

INSTANCES_ON_DEMAND_LINUX_URL =("http://a0.awsstatic.com/pricing/1/ec2/"+
"linux-od.min.js")

def load_data(url):
    """
    Method for retrieving the pricing data in a clean dictionary format.
    
    Args:
        url: The pricing source url.
        
    Returns:
        data (dict of dict: dict): Pricing data in a dictionary format
           
    """
    if is_py3:
        f = urllib.request.urlopen(url).read()
        f = re.sub("/\\*[^\x00]+\\*/", "", f.decode(), 0, re.M)
    elif is_py2:
        f = urllib2.urlopen(url).read()
        f = re.sub("/\\*[^\x00]+\\*/", "", f, 0, re.M)
    f = re.sub("([a-zA-Z0-9]+):", "\"\\1\":", f)
    f = re.sub(";", "\n", f)
    f = re.sub("callback\(", "", f)
    f = re.sub("\)$", "", f)
    data = json.loads(f)
    return data

class AwsInstanceInfo(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    region = db.Column(db.String())
    type = db.Column(db.String())
    size = db.Column(db.String())
    os = db.Column(db.String())
    price = db.Column(db.Float())
    ECU = db.Column(db.String())
    memory = db.Column(db.String())
    storage = db.Column(db.String())
    vCPU = db.Column(db.String())

    @staticmethod
    def reload():
        data = load_data(INSTANCES_ON_DEMAND_LINUX_URL)
        #print(json.dumps(data, indent=4, sort_keys=True))
        for region in data["config"]["regions"]:
            region_name = region["region"]
            if region_name != "us-west-2":
                continue

            for instanceType in region["instanceTypes"]:
                type = instanceType["type"]
                #print(type)
                #print(json.dumps(instanceType, indent=4, sort_keys=True))
                for instanceSize in instanceType["sizes"]:
                    size = instanceSize["size"]
                    info = AwsInstanceInfo.query.filter_by(size=size).first()
                    if not info:
                        info = AwsInstanceInfo()

                    info.region = region_name
                    info.type = type
                    info.size = size
                    info.os = instanceSize["valueColumns"][0]["name"]
                    info.price = float(instanceSize["valueColumns"][0]["prices"]['USD'])
                    info.ECU = instanceSize["ECU"]
                    info.memory = instanceSize["memoryGiB"]
                    info.storage = instanceSize["storageGB"]
                    info.vCPU = instanceSize["vCPU"]

                    db.session.add(info)

        db.session.commit()

