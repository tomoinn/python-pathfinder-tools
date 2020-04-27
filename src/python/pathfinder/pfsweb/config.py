import os


class Config(object):
    """
    Flask web app configuration
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
