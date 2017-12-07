from testbench.extensions import celery
from celery.utils.log import get_task_logger

import etcd
import json
from os.path import basename

logger = get_task_logger(__name__)
client = None

def get_client():
    global client
    if not client:
        client = etcd.Client(host=(('10.1.11.234', 4001), ('10.1.60.1', 4001), ('10.1.60.2', 4001)),
                             allow_reconnect=True)
    return client

@celery.task()
def get_testbed(name):
    info = {
        'user': None,
        'properties': {}
    }

    try:
        for tb_info in get_client().read("/testbench/testbeds/%s" % name).children:
            key = basename(tb_info.key)
            if key == "user":
                info['user'] = json.loads(tb_info.value)
            elif key == "properties":
                for tb_prop in get_client().read(tb_info.key).children:
                    prop = basename(tb_prop.key)
                    info['properties'][prop] = tb_prop.value
            elif key == "instance":
                info['instance'] = {}
                for tb_runtime in get_client().read(tb_info.key).children:
                    prop = basename(tb_runtime.key)
                    info['instance'][prop] = tb_runtime.value
            else:
                print("'%s' not handled" % key)
    except etcd.EtcdKeyNotFound:
        logger.info("Error while getting testbed info")
    # print(info)
    return info

@celery.task()
def list_testbeds():
    testbeds = {}

    try:
        r = get_client().read('/testbench/testbeds', sorted=True)
        for tb_child in r.children:
            name = basename(tb_child.key)
            print("Testbed: %s" % name)
            testbeds[name] = get_testbed(name)
    except etcd.EtcdKeyNotFound:
        logger.info("Error while listing testbeds")

    return testbeds

@celery.task()
def does_testbed_exist(testbed_name):
    testbeds = list_testbeds()
    for testbed in testbeds:
        if testbed == testbed_name:
            return True
    return False

@celery.task()
def set_testbed_info(testbed_name, info, key, value):
    get_client().write("/testbench/testbeds/%s/%s/%s" % (testbed_name, info, key), value)

def check_key_exists(key):
    try:
        get_client().read(key)
    except etcd.EtcdKeyNotFound:
        return False

    return True

class TestBenchNotFound(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

@celery.task()
def launch(name, user, info=[]):
    launched = False
    try:
        tb_key = "/testbench/testbeds/%s" % name
        if not tb_key:
            raise TestBenchNotFound(name)

        r = get_client().write("%s/user" % tb_key, json.dumps(user), prevExist=False)
        print(r)
        launched = True
    except etcd.EtcdAlreadyExist:
        logger.info("Already launched")

    return {
        'launched': launched,
        'info': get_testbed(name)
    }

@celery.task()
def destroy(name):
    destroyed = False
    try:
        tb_key = "/testbench/testbeds/%s" % name
        if not tb_key:
            raise TestBenchNotFound(name)

        r = get_client().delete("%s/user" % tb_key, prevExist=True)
        print(r)
        destroyed = True
    except etcd.EtcdKeyNotFound:
        logger.info("Already destroyed")

    return {
        'destroyed': destroyed,
        'info': get_testbed(name)
    }

