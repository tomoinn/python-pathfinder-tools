from pathfinder.pfsweb import app
from flask import render_template
from pathfinder.pfsweb.forms import LoginForm


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home', user='Foo')


@app.route('/login')
def login():
    form = LoginForm()
    return render_template('login.html', title='Sign In', form=form)
