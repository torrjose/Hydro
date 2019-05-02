# -*- coding: utf-8 -*-
from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import smtplib
import RPi.GPIO as GPIO
import cloud4rpi
import sys
import board
import os
import busio
import time
import datetime
import signal
import random
import rpi

# Change to 60 if you need minutes. Display shows it.
multiplier = 1

# Change time messages are displayed for. (Seconds)
readTime = 2
#----------------------------------------------
DEVICE_TOKEN = '48RPJxBwbPUSxANfiNC7MMmtn'

val1 = 0
val2 = 0

# How often(seconds) to send data to cloud. Must be > 11
cloudInterval = 15
# How often(seconds) to read data from the sensors.
senseInterval = 5
#---------------------------------------------
pumpOn = False
pumpInt = False

sysError = False
sysErrorMsg = 'ERROR'

pumpOnTime = 5
delay = 10
usrPH = 10
usrEC = 10
#----------------------------------------------
lcd_columns = 16
lcd_rows = 2
#----------------------------------------------
gmail_user = 'osuteam40@gmail.com'
gmail_password = 'Greenhouse40!'

msg1 = "        "
msg2 = "        "
msg3 = "        "
msg4 = "        "

slp = 0.25
#--------------------------------------------
GPIO.setmode(GPIO.BCM)

# Pins for Flow meters(1&2), main pump, etc.
flow1 = 6
flow2 = 5
mainpump = 17
auxpump1 = 25
solnd1 = 27
solnd2 = 22

flowPing1 = 0
flowPing2 = 0
#------------------------------------------

def runMainPump():
    print('Running Main Pump!')

    global flowPing1
    global flowPing2
    global pumpOn
    global pumpInt


    print('Number 1: {}'.format(flowPing1))
    print('Number 2: {}'.format(flowPing2*(4/3)))

    flow2 = flowPing2*(4/3)

    if flowPing1*0.8 <= flow2 <= flowPing1*1.05:
        enterError("Flow Rates didn't Match!")

    flowPing1 = 0
    flowPing2 = 0

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

def flow1Int(flow1):
    global flowPing1

    flowPing1 = flowPing1 + 1

def flow2Int(flow1):
    global flowPing2

    flowPing2 = flowPing2 + 1

def signal_handler(sig, fram):
    print('Exiting!')

    global scheduler

    GPIO.cleanup()
    scheduler.remove_all_jobs()
    lcd
    sys.exit(0)

# Function that allows the user to change the variables
# within the system. 
def valSet():
    global pumpOnTime
    global delay
    global usrPH
    global usrEC
    
    i = 0

    lcd.message = "Change values \n Up or Down"
    time.sleep(readTime)
    lcd.clear()
    lcd.message = "Press Select \n When Done"
    time.sleep(readTime)
    lcd.clear()

    variables = ["Delay   ", "PumpTime", "PH Set ", "EC Set"]
    variableNums = [30, 10, 10, 10]

    oldmsgOut = " "

    # Loop through all 4 variables, allowing the user to change. 
    while True:
        if lcd.left_button:
                variableNums[i] -= 1
                lcd.clear()
                print("Left, Dec by 1")
        elif lcd.up_button:
                variableNums[i] += 5
                lcd.clear()
                print("Up, Increment by 5")
        elif lcd.down_button:
                variableNums[i] -= 5
                lcd.clear()
                print("Down, Decrement by 5")
        elif lcd.right_button:
                variableNums[i] += 1
                lcd.clear()
                print("Right, Increment by 1") 
        elif lcd.select_button:
                i += 1
                lcd.clear()
                print("Select")

        if i == 4:
            i = 0
            break

        msgOut = (variables[i] + "\n" + str(variableNums[i]))

        if msgOut != oldmsgOut:
            lcd.message = msgOut
        else:
            oldmsgOut = msgOut
        
    delay = variableNums[0]
    pumpOnTime = variableNums[1]
    usrPH = variableNums[2]
    usrEC = variableNums[3]

#----------------------------------------------------
#Set functions, which grab values from the cloud
# and set them locally. 

def pumpDelaySet(value):
    global delay

    if value != None:
        delay = value

def pumpOnTimeSet(value):
    global pumpOnTime

    if value != None:
        pumpOnTime = value

def userECSet(value):
    global usrEC

    if value != None:
        usrEC = value

def userPHSet(value):
    global usrPH

    if value != None:
        usrPH = value/2

def sysErrorSet(value):
    global sysError

    if value != None:
        sysError = value
#------------------------------------------------------
def publishData():
    device.publish_data()
def publishDiag():
    device.publish_diag()
#------------------------------------------------------
def sysPrimer():
    # Turn pump on, wait for flow at flow meter 1.
    global mainpump
    global solnd1
    global solnd2
    global flowPing1
    global flowPing2
    
    temp = 0
    lcd.clear()
    lcd.message = "Priming System"
    GPIO.output(mainpump, GPIO.HIGH)
    GPIO.output(solnd1, GPIO.HIGH)
    print("Priming System")
    print("Running pump")

    time.sleep(5)

    if flowPing1 == 0:
        enterError("No Reading at flow sensor 1. Possible bad pump or clog.")

    print("Sol1 off")
    temp = flowPing1
    GPIO.output(solnd1, GPIO.LOW)
    time.sleep(5)

    if temp < 1.15*flowPing1:
        enterError("Continued Flow after Solenoid closing. Possible Clog.")

    print("Waiting for flow2")
    GPIO.output(solnd1, GPIO.HIGH)
    GPIO.output(solnd2, GPIO.HIGH)
    while flowPing2 == 0:
        time.sleep(1)

    time.sleep(5)

    print("Pump off")
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.LOW)
    GPIO.output(mainpump, GPIO.LOW)

    temp = flowPing2

    time.sleep(5)

    print("Sold2 Closing.")    
    if temp < 1.15*flowPing2:
        enterError("Continued Flow after Solenoid 2 closing. Possible Clog.")


def enterError(msg):
    global mainpump
    global solnd1
    global solnd2
    global lcd

    # Make sure everything is off
    GPIO.output(mainpump, GPIO.LOW)
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.HIGH)

    lcd.message = msg

    try:
        server = smtplib.SMTP('smtp.gmail.com',587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_password)

        print('Email Server Connected')
    except:
        print('Connection Error')

    sent_from = 'osuteam40@gmail.com'
    to = ['josetorres725@gmail.com']
    subject = 'AUTOMATED GREENHOUSE IMPORTANT MESSAGE'

    email = EmailMessage()
    email['Subject'] = subject
    email['From'] = sent_from
    email['To'] = to
    email.set_content(msg)

    try:
        server.send_message(email)
        server.close()
        print('Email Sent!')
    except:
        print('Email Sending Error')

    sysError = True
    lcd.clear()
    lcd.message = 'After Fixing\nPress Select'
    while sysError:
        if lcd.select_button:
            break

msg3 = "Timing: "
msgNew = ""
if __name__ == "__main__":

    # Set up the i2c port, and initialize the display
    i2c = busio.I2C(board.SCL, board.SDA)
    lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)

    lcd.backlight = False

    lcd.clear()
    #------------------------------------------------
    # Check config file, check if the user wants new values,
    # save new ones if needed, close file.
    if os.path.isfile('./config.txt'):
        print('Loading Config File')
        lcd.message = "Loading\nConfig File..."
        time.sleep(readTime)
        
        file = open('./config.txt', 'r+')
            
        delay = int(file.readline())
        pumpOntime = int(file.readline())
        usrPH = int(file.readline())
        usrEC = int(file.readline())

        print('Values previously saved:')
        print('usrPH: %d, Delay: %d, usrEC: %d' %(usrPH, delay, usrEC))

        lcd.message = "Values previosly\nsaved are: "
        time.sleep(readTime)
        lcd.clear()

        lcd.message = "PH Set Level: " + str(usrPH) + "\n" + "EC Set Level: " + str(usrEC)
        time.sleep(readTime)
        lcd.clear()

        lcd.message = "Pump On Time: " + str(pumpOnTime) + "\n" + "Cycle Delay: " + str(delay)
        time.sleep(readTime)
        lcd.clear()

        lcd.message = "Would you like\nto replace them?"
        time.sleep(readTime)
        lcd.clear()
        lcd.message = "Press Up for Yes\nDown for No"
        time.sleep(readTime)

        while True:
            if lcd.up_button:
                ans = "yes"
                break
            elif lcd.down_button:
                ans = "no"
                break        
        lcd.clear()
            
        if ans in ['yes', 'y']:
            file = open('./config.txt', 'w+')

            valSet()
            
            file.write('%d\n'%delay)
            file.write('%d\n'%pumpOnTime)
            file.write('%d\n' %usrPH)
            file.write('%d\n' %usrEC)  
            
            file.close()
            
            print('Saving those files../n')
            lcd.message = "Saving \nthose files..."
            time.sleep(readTime)
            lcd.clear()

    else:
        print('config file is not present')
        print('creating new config file')

        lcd.message = "Config file is\nNot present..."
        time.sleep(readTime)
        lcd.clear()
        lcd.message = "Creating new\nconfig file..."
        time.sleep(readTime)
        lcd.clear()
        
        file = open('./config.txt','w+')

        valSet()
        
        file.write('%d\n' %delay)
        file.write('%d\n' %pumpOnTime)
        file.write('%d\n' %usrPH)    
        file.write('%d\n' %usrEC)
        
        file.close()
    #----------------------------------------------------------
    # Start up pins, set interrupts for flow sensors. 
    # GPIO Setup
    GPIO.setup(flow1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(flow2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    GPIO.setup(mainpump, GPIO.OUT)
    GPIO.setup(auxpump1, GPIO.OUT)
    GPIO.setup(solnd1, GPIO.OUT)
    GPIO.setup(solnd2, GPIO.OUT)

    GPIO.add_event_detect(flow1, GPIO.RISING, callback=flow1Int)
    GPIO.add_event_detect(flow2, GPIO.FALLING, callback=flow2Int)
    #-----------------------------------------------------------
    # Setup cloud vairables, and diagnostic variables. Start up cloud interface.
    variables = {
        'Var1': {
            'type': 'numeric',
            'bind': flowPing1
        },
        'Var2': {
            'type': 'numeric',
            'bind': flowPing2
        },
        'Var3': {
            'type': 'bool',
            'bind': pumpOn
        },
        'Var4': {
            'type': 'numeric',
            'bind': val1
        },
        'Var5': {
            'type': 'numeric',
            'bind': val2
        },
        'PumpDelay': {
            'type': 'numeric',
            'bind': pumpDelaySet
        },
        'PumpOnTime': {
            'type': 'numeric',
            'bind': pumpOnTimeSet
        },
        'UserEC': {
            'type': 'numeric',
            'bind': userECSet
        },
        'UserPH': {
            'type': 'numeric',
            'bind': userPHSet
        },
        'SysError': {
            'type': 'bool',
            'bind': sysErrorSet
        }
    }

    diagnostics = {
        'CPU Temp': rpi.cpu_temp,
        'IP Address': rpi.ip_address,
        'Host': rpi.host_name,
        'Operating Sytem': rpi.os_name
        }

    device = cloud4rpi.connect(DEVICE_TOKEN)

    try:
        device.declare(variables)
        device.declare_diag(diagnostics)

        device.publish_config()

        print('Cloud Connected!')

    except Exception as e:
        error = cloud4rpi.get_error_message(e)
        cloud4rpi.log.exception("ERROR! %s %s", error, sys.exc_info()[0])
        print('Cloud Connection Error!')

    #-----------------------------------------------------------
    # Test system, throw errors otherwise.
    #sysPrimer()
    #-----------------------------------------------------------
    # Start up thread service. Load up pumps, and cloud interface
    # to start up every x seconds.
    scheduler = BackgroundScheduler()
    scheduler.start()

    pump_job = scheduler.add_job(runMainPump, 'interval', seconds = delay * multiplier, id = 'mPump')
    cloudData_job = scheduler.add_job(publishData, 'interval', seconds = cloudInterval)
    cloudDiag_job = scheduler.add_job(publishDiag, 'interval', seconds = cloudInterval)

    signal.signal(signal.SIGINT, signal_handler)

    GPIO.output(auxpump1, GPIO.LOW)

    print('Running')
    
    while True:
        if sysError:
            scheduler.pause_job(pump_job)
        else:
            scheduler.resume_job(pump_job)
        
        msgOut =  (msg1 + msg2 + "\n" + msg3 + msg4)

        #-------------------------------------------
        # Read Ultrasonic
        #-------------------------------------------

        #-------------------------------------------
        # Read PH
        #-------------------------------------------

        #-------------------------------------------
        # Read EC
        #-------------------------------------------

        #-------------------------------------------
        # Parse Data
        #-------------------------------------------

        #-------------------------------------------
        # Check if pump is running
        #-------------------------------------------

        #-------------------------------------------
        # Dose as needed
        #-------------------------------------------

        #-------------------------------------------
        # Call user if water levels are low
        #-------------------------------------------
        
        if msgOut != msgNew:
            lcd.message = msgOut

        if(pumpOn):
            print("Pump is on!")

            msg1 = "Pump on!"
        else:
            msg1 = "Pump off"

            if flowPing2 < 0.8 * flowPing1:
    #            print("Solenoid 2 on, Draining!")
                GPIO.output(solnd2, GPIO.HIGH)
            
        msg3 = "Timing: "
        msg4 = ""
        msg4 = str(pumpOnTime)

        msgNew = msgOut
        
        time.sleep(senseInterval)
