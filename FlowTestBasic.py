from apscheduler.schedulers.background import BackgroundScheduler
from Adafruit_IO import Client, Feed, Data, RequestError
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import RPi.GPIO as GPIO
import board
import busio
import time
import datetime
import signal
import sys
import random

# Change to 60 if you need minutes. Display shows it.
multiplier = 1

val1 = 0
val2 = 0

# How often(seconds) to send data to cloud. Must be > 11
cloudInterval = 15
#---------------------------------------------
pumpOn = False
pumpInt = False

pumpOnTime = 5
#----------------------------------------------
slp = 0.25
#--------------------------------------------
GPIO.setmode(GPIO.BCM)

# Pins for Flow meters(1&2), main pump, etc.
channel = 6
flow2 = 5
mainpump = 17
auxpump1 = 25
solnd1 = 27
solnd2 = 22

curTime = 2
prevTime = 1
curTime2 = 2
prevTime2 = 1

deltaT = 1
olddetlaT = 1
deltaT2 = 1
olddeltaT2 = 1

number = 0
oldnumber = 0
number2 = 0
oldnumber2 = 0

REFRESH_INTERVAL = pumpOnTime + 30 #seconds
#------------------------------------------

def runMainPump():
    print('Running Main Pump!')

    global number
    global number2
    global pumpOn
    global pumpInt


    print('Number 1: {}'.format(number))
    print('Number 2: {}'.format(number2*(4/3)))

    number = 0
    number2 = 0

    # Run pump for time, open solnd, close upon end.
    # Else, if int, dont run.
    if(not pumpInt):
        GPIO.output(mainpump, GPIO.LOW)
        GPIO.output(solnd1, GPIO.LOW)
        pumpOn = True
    
        time.sleep(pumpOnTime * multiplier)

        GPIO.output(mainpump, GPIO.HIGH)
        GPIO.output(solnd1, GPIO.HIGH)
        pumpOn = False
    else:
        print("Pump should be on")

def flow1(channel):
   # print('Rising Edge Detected!')

    global number
    global curTime, prevTime
    global deltaT

    curTime = time.time()
    number = number + 1

    deltaT = curTime-prevTime

    prevTime = curTime

def flowm2(channel):
    global number2
    global curTime2, prevTime2
    global deltaT2

    curTime2 = time.time()
    number2 = number2 + 1

    deltaT2 = curTime2-prevTime2

    prevTime2 = curTime2

def signal_handler(sig, fram):
    print('Exiting!')

    global pump_job

    pump_job.remove()
    GPIO.cleanup()
    lcd
    sys.exit(0)

GPIO.setup(channel, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(flow2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

GPIO.setup(mainpump, GPIO.OUT)
GPIO.setup(auxpump1, GPIO.OUT)
GPIO.setup(solnd1, GPIO.OUT)
GPIO.setup(solnd2, GPIO.OUT)

GPIO.add_event_detect(channel, GPIO.RISING, callback=flow1)
GPIO.add_event_detect(flow2, GPIO.FALLING, callback=flowm2)

scheduler = BackgroundScheduler()
scheduler.start()

pump_job = scheduler.add_job(runMainPump, 'interval', seconds = REFRESH_INTERVAL * multiplier, id = 'mPump')

signal.signal(signal.SIGINT, signal_handler)

GPIO.output(auxpump1, GPIO.LOW)

print('Running')

msg3 = "Timing: "
msgNew = ""

buttonNum = 1

while True:
        
    msg3 = "Timing: "
    msg4 = ""
    msg4 = str(pumpOnTime)

    buttonNum += 1

    if buttonNum == 6:
        buttonNum = 1
    if pumpOnTime < 1:
        pumpOnTime = 1

    
 #   print("!")




