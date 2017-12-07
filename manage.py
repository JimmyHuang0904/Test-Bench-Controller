#!/usr/bin/env python3

import os

from flask_script import Manager, Server
from flask_script.commands import ShowUrls, Clean
from testbench import create_app
from testbench.models import db
from testbench.models.user import User
from testbench.models.aws import AwsInstanceInfo

from testbench.extensions import celery

# default to dev config because no one should use this in
# production anyway
env = os.environ.get('TESTBENCH_ENV', 'dev')
app = create_app('testbench.settings.%sConfig' % env.capitalize())

manager = Manager(app)
manager.add_command("server", Server(host='0.0.0.0'))
manager.add_command("show-urls", ShowUrls())
manager.add_command("clean", Clean())

@manager.shell
def make_shell_context():
    """ Creates a python REPL with several default imports
        in the context of the app
    """

    return dict(app=app, db=db, User=User)

@manager.command
def createdb():
    """ Creates a database with all of the tables defined in
        your SQLAlchemy models
    """

    db.create_all()
    AwsInstanceInfo.reload()

@manager.command
def worker():
    with app.app_context():
        celery.start()

if __name__ == "__main__":
    manager.run()

