from flask import Flask
from pathfinder.pfsweb.config import Config
from flask_bootstrap import Bootstrap, WebCDN
import os

# Create web app
template_dir = os.path.abspath('./pfsweb/templates')
print(template_dir)
app = Flask(__name__, template_folder=template_dir)
Bootstrap(app)

app.extensions['bootstrap']['cdns']['bootstrap'] = WebCDN('//stackpath.bootstrapcdn.com/bootstrap/4.4.1/')
app.extensions['bootstrap']['cdns']['fontawesome'] = WebCDN('//stackpath.bootstrapcdn.com/font-awesome/4.4.0/')

# Configure from our configuration object
app.config.from_object(Config)

# Load routes


def main():
    """Run from the 'pfs_web' command"""
    app.run()
