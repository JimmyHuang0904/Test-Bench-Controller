from flask import current_app
from flask_wtf import FlaskForm
from flask_sqlalchemy import SQLAlchemy
from wtforms import TextField, PasswordField, SelectField
from wtforms import validators

from .models.user import User
from .extensions import ldap

db = SQLAlchemy()

class LoginForm(FlaskForm):
    username = TextField(u'Username', validators=[validators.required()])
    password = PasswordField(u'Password', validators=[validators.optional()])

    def validate(self):
        check_validate = super(LoginForm, self).validate()

        # if our validator do not pass
        if not check_validate:
            return False

        if current_app.config['LDAP_LOGIN']:
            # Check credentials against LDAP server
            if not ldap.bind_user(self.username.data, self.password.data):
                self.username.errors.append('Invalid username or password')
                return False
            else:
                current_app.logger.debug("Login OK for %s" % self.username.data)

        # Does our user exists
        user = User.query.filter_by(username=self.username.data).first()
        if not user:
            user = User(username=self.username.data)
            db.session.add(user)
            db.session.commit()

        return True

class TestBenchEditForm(FlaskForm):
    pass

class UfarmNewForm(FlaskForm):
    subnet = SelectField(u'Subnet', validators=[validators.required()])

    # master
    master_instance_type = SelectField(u'Instance Type', validators=[validators.required()])

    # nodes
    nodes_count = TextField(u'Count', validators=[validators.required()], default=1)
    nodes_instance_type = SelectField(u'Instance Type', validators=[validators.required()])
