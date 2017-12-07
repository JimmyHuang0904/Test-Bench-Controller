import os
import tempfile
db_file = tempfile.NamedTemporaryFile()

class Config(object):
    SECRET_KEY = 'REPLACE ME'

    LDAP_BASE_DN = 'OU=SWI,DC=sierrawireless,DC=local'
    LDAP_HOST = os.environ.get('LDAP_HOST', '10.1.10.1')
    #LDAP_PORT = 636
    LDAP_USE_SSL = True
    LDAP_OPENLDAP = True
    LDAP_USER_OBJECT_FILTER = '(&(objectclass=person)(sAMAccountName=%s))'
    LDAP_GROUP_OBJECT_FILTER = '(&(objectclass=group)(sAMAccountName=%s))'

class ProdConfig(Config):
    ENV = 'prod'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///../database.db'

    CACHE_TYPE = 'simple'

    LDAP_LOGIN = True
    LDAP_USERNAME = os.environ.get('LDAP_USERNAME')
    LDAP_PASSWORD = os.environ.get('LDAP_PASSWORD')

class DevConfig(Config):
    ENV = 'dev'
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    SQLALCHEMY_DATABASE_URI = 'sqlite:///../database.db'

    CACHE_TYPE = 'null'
    ASSETS_DEBUG = True

    LDAP_LOGIN = False
    if 'LDAP_USERNAME' in os.environ:
        LDAP_LOGIN = True
        LDAP_USERNAME = os.environ.get('LDAP_USERNAME')
        LDAP_PASSWORD = os.environ.get('LDAP_PASSWORD')

class TestConfig(Config):
    ENV = 'test'
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + db_file.name
    SQLALCHEMY_ECHO = True

    CACHE_TYPE = 'null'
    WTF_CSRF_ENABLED = False
    LDAP_LOGIN = False

