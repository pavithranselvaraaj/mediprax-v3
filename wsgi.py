import sys, os
project_home = '/home/erhosiptalsp/mediprax_hospital'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
os.chdir(project_home)
from run import app as application
