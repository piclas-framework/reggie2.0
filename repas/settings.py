# settings.py
import os

def init():
    global absolute_reggie_path
    absolute_reggie_path='/home/stephen/Flexi/reggie/'
    if not os.path.exists(absolute_reggie_path) :
        print "Reggie repository not found under: '%s'" % absolute_reggie_path
        exit(1)

