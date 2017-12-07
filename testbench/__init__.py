#!/usr/bin/env python

from flask import Flask, render_template
from webassets.loaders import PythonLoader as PythonAssetsLoader

from testbench import assets
from testbench.models import db

from testbench.controllers.main import main
from testbench.controllers.testbench import testbench
from testbench.controllers.ufarm import ufarm

from testbench.extensions import (
    cache,
    assets_env,
    debug_toolbar,
    login_manager,
    ldap,
    celery
)

def create_app(object_name):
    """
    An flask application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/

    Arguments:
        object_name: the python path of the config object,
                     e.g. testbench.settings.ProdConfig
    """

    app = Flask(__name__)

    app.config.from_object(object_name)

    # task manager
    celery.init_app(app)

    # initialize the cache
    cache.init_app(app)

    # initialize the debug tool bar
    debug_toolbar.init_app(app)

    # initialize SQLAlchemy
    db.init_app(app)

    login_manager.init_app(app)

    # Import and register the different asset bundles
    assets_env.init_app(app)
    assets_loader = PythonAssetsLoader(assets)
    for name, bundle in assets_loader.load_bundles().items():
        assets_env.register(name, bundle)

    # register our blueprints
    app.register_blueprint(main)
    app.register_blueprint(testbench)
    app.register_blueprint(ufarm)

    # LDAP
    if app.config['LDAP_LOGIN']:
        ldap.app = app
        ldap.init_app(app)

    return app