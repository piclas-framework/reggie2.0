# settings.py
import os
import sys

def init():
    global absolute_reggie_path
    absolute_reggie_path=os.path.abspath(os.path.join(__file__ ,"../.."))
    if not os.path.exists(absolute_reggie_path) :
        print "Reggie repository not found under: '%s'" % absolute_reggie_path
        exit(1)

