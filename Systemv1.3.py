# -*- coding: utf-8 -*-
from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
from datetime import datetime, timezone
from tzlocal import get_localzone
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import wiringpi
import smtplib
import RPi.GPIO as GPIO
import cloud4rpi
import sys
import board
import os
import pytz
import busio
import time
import signal
import random
import rpi
import spidev

# Change to 60 if you need minutes. Display shows it.
multiplier = 1

# Change time messages are displayed for. (Seconds)
readTime = .25
#----------------------------------------------
DEVICE_TOKEN = '48RPJxBwbPUSxANfiNC7MMmtn'

val1 = 0
val2 = 0

# How often(seconds) to send data to cloud. Must be > 11
cloudInterval = 15
# How often(seconds) to read data from the sensors.
senseInterval = 15
#---------------------------------------------
pumpOn = False
pumpInt = False

sysError = False
sysErrorMsg = 'ERROR'

pumpOnTime = 30
delay = 60
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
flow1 = 12
flow2 = 6
mainpump = 13
auxpump1 = 22
solnd1 = 16
solnd2 = 17
doser1 = 19
doser2 = 20
doser3 = 21
doser4 = 23
doser5 = 24

#EC/PH Switch
ch1 = 26
ch2 = 25

#ADC
adcClk = 11
adcDout = 9
adcDin = 10
adccs = 8

#Level Sensors
TRIG = 4
ECHO = 5

#SPI
spi = spidev.SpiDev()
spi.open(0,0)

#EC and PH variables
PHVolts = 0.0
ECVolts = 0.0
PHBits = 0
ECBits = 0

flowPing1 = 0
flowPing2 = 0
#------------------------------------------
senUltra = 0
senPH = 0
senEC = 0
#-------------------------------------------
autodoserLevels = [0.,0.,0.,0.,0.]
autodoserLevelErrors = [False,False,False,False,False]
#-------------------------------------------

def runMainPump():
    print('Running Main Pump!')

    global flowPing1
    global flowPing2
    global pumpOn
    global pumpInt


    print('Number 1: {}'.format(flowPing1))
    #print('Number 2: {}'.format(flowPing2*(4/3)))

    flow2 = flowPing2*(4/3)

    if flowPing1*0.8 <= flow2 <= flowPing1*1.05:
        #enterError("Flow Rates didn't Match!")
        print("error")

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

def flow1Int(ch1):
    global flowPing1

    flowPing1 = flowPing1 + 1

def flow2Int(ch1):
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
    global cloudInterval
    
    i = 0

    lcd.message = "Change values \n Up or Down"
    time.sleep(readTime)
    lcd.clear()
    lcd.message = "Press Select \n When Done"
    time.sleep(readTime)
    lcd.clear()

    variables = ["Delay   ", "PumpTime", "PH Set ", "EC Set", "Cloud Interval"]
    variableNums = [30, 10, 10, 10, 10]

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
        
    delay, pumpOnTime, usrPH, usrEC, cloudInterval = variableNums
    
#reads raw ADC data
def analogInput(channel):
    spi.max_speed_hz = 1350000
    adc = spi.xfer2([1, (8+channel)<<4,0])
    data = ((adc[1]&3) << 8) + adc[2]
    return data

#converts raw adc value to volts
def Volts(data):
  #data * Vref / (2^10 - 1)
  volts = (data * 2.5) / float(1023)
  volts = round(volts, 2) # Round off to 2 decimal places
  return volts

#reads PH sensor
def PHData():
    #power PH circuit, poll sensor, turn off PH circuit
    GPIO.output(ch1, GPIO.LOW)
    time.sleep(10)
    PHBits = analogInput(1)
    PHVolts = Volts(PHBits)
    time.sleep(1)
    GPIO.output(ch1, GPIO.HIGH)
    
#reads EC sensor
def ECData():
    global ECBits
    global ECVolts
    sampleMax = 0
    sampleMin = 0
    sample = 0
    
	#power EC circuit
    GPIO.output(ch2, GPIO.LOW)
    time.sleep(10)

	#sample i times, find max and min value
	#this is to find the average value in the output voltage waveform
    for i in range(100):
        sample = analogInput(0)
        if i==0:
            sampleMin = sample
            sampleMax = sample
        if i>0:
            if sample < sampleMin:
                sampleMin = sample
            if sample > sampleMax:
                sampleMax = sample
        
    ECBits = (sampleMax + sampleMin)/2
    ECVolts = Volts(ECBits)
    time.sleep(1)
    GPIO.output(ch2, GPIO.HIGH)

#mapping waveform to convert volts to electrical conductivity     
def ECValue(Volts):
    EC = 0.00
    EC = (0.673*Volts*Volts)+(0.724*Volts)+0.05
    return EC
    
def PHValue(Volts):
    PH = 0.00
    PH = -20(Volts)+32
    return PH

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
# sys primer water funcs already inverted.
def sysPrimer():
    # Turn pump on, wait for flow at flow meter 1.
    global mainpump
    global solnd1
    global solnd2
    global flowPing1
    global flowPing2
    global pumpOnTime
    global firstFlowRate
    
    flowPing1 = 0
    flowPing2 = 0
    
    GPIO.output(mainpump, GPIO.HIGH)
    GPIO.output(solnd1, GPIO.HIGH)
    GPIO.output(solnd2, GPIO.HIGH)
    
    temp = 0
    lcd.clear()
    lcd.message = "Priming System"
    lcd.clear()
    lcd.message = "Running Flow1"
    GPIO.output(mainpump, GPIO.LOW)
    GPIO.output(solnd1, GPIO.LOW)
    print("Priming System")
    print("Running pump")

    time.sleep(pumpOnTime)
    
    print(str(flowPing1))
    
    firstFlowRate = flowPing1

    if flowPing1 == 0:
        enterError("No Reading at flow sensor 1. Possible bad pump or clog.")

    print("Sol1 off")
    lcd.clear()
    lcd.message = "Testing Sol1"
    temp = flowPing1
    GPIO.output(solnd1, GPIO.HIGH)
    
    time.sleep(10)
    print(str(flowPing1))

    if 2*temp < flowPing1:
        enterError("Continued Flow after Solenoid closing. Possible Clog.")

    print("Waiting for flow2")
    lcd.clear()
    lcd.message = "Testing Flow2"
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.HIGH)

    time.sleep(15)
    
    GPIO.output(solnd2, GPIO.LOW)
    time.sleep(5)
    
    if flowPing2 == 0:
        #enterError("No Reading at flow sensor 2. Possible clog in system.")
        print("error")

    print("Pump off")
    lcd.clear()
    lcd.message = "Testing Sol2"
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.HIGH)
    GPIO.output(mainpump, GPIO.LOW)

    temp = flowPing2

    time.sleep(10)

    print("Sold2 Closing.")    
    if 2*temp < flowPing2:
        #enterError("Continued Flow after Solenoid 2 closing. Possible Clog.")
        print("error")
        
    lcd.clear()
    lcd.message = "System Passed!"
    time.sleep(slp)


def enterError(msg):
    global mainpump
    global solnd1
    global solnd2
    global lcd

    # Make sure everything is off
    GPIO.output(mainpump, GPIO.LOW)
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.HIGH)

    print(msg)
    lcd.message = msg
    time.sleep(slp)
    
    sendEmail(msg)

    sysError = True
    lcd.clear()
    lcd.message = 'After Fixing\nPress Select'
    while sysError:
        if lcd.select_button:
            sysError = False
            break

def sendEmail(msg):
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
            
def readSenUltra():
    GPIO.output(TRIG, GPIO.LOW)                 #Set TRIG as LOW
    print ("Waiting For Sensor To Settle")

    GPIO.output(TRIG, GPIO.HIGH)                  #Set TRIG as HIGH
    time.sleep(0.000001)                          #Delay of 0.00001 seconds
    GPIO.output(TRIG, GPIO.LOW)                   #Set TRIG as LOW

    while GPIO.input(ECHO)==0:               	  #Check if Echo is LOW
      pulseStart = time.time()                   #Time of the last  LOW pulse

    while GPIO.input(ECHO)==1:                    #Check whether Echo is HIGH
      pulseEnd = time.time()                     #Time of the last HIGH pulse 

    pulseDuration = pulseEnd - pulseStart      #pulse duration to a variable

    distance = pulseDuration * 17150             #Calculate distance
    distance = round(distance, 2)                 #Round to two decimal points

    if distance > 20 and distance < 400:          #Is distance within range
      print ("Distance:",distance - 0.5,"cm")     #Distance with calibration
      return distance - 0.5
    else:
      print ("Out Of Range")                      #display out of range    
      return 0
    
def readSenEC():
    ECData()
    return ECValue(ECVolts)

#gets called 5 times/sense interval
def phJob():
    PHData()
    arrj[] PHValue(PHVolts)

#gets called once every sense interval
def readSenPH():
    #make phMedian global
    global: phMedian
    return phMedian
    
#reads autodoser level sensors
def AutoLevelData():
    for i in range(len(autodoserLevels)):
        rawIn = analogInput(i+2)
        autodoserLevels[i] = Volts(rawIn) 
        
#checks autodoser level sensors for low levels
def AutoLevelTest():
    for i in range(len(autodoserLevels)):
        #print("chan ", i, ": ", autodoserLevels[i], '\n')
        if autodoserLevels[i] < 1.0:
            autodoserLevelErrors[i] = True
        else:
            autodoserLevelErrors[i] = False

msg3 = "Timing: "
msgNew = ""
firstFlowRate = 0

def changeString():
    return "vest"

if __name__ == "__main__":
    # Set up the i2c port, and initialize the display
    i2c = busio.I2C(board.SCL, board.SDA)
    lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)

    lcd.backlight = False

    lcd.clear()
    lcd.message = "!!!!!!!!!!!!!!!!!!"
    while True:
        print("s")
    #------------------------------------------------
    # Check config file, check if the user wants new values,
    # save new ones if needed, close file.
    if True:
        lcd.clear()
    elif os.path.isfile('./config.txt'):
        print('Loading Config File')
        lcd.message = "Loading\nConfig File..."
        time.sleep(readTime)
        
        file = open('./config.txt', 'r+')
            
        delay = int(file.readline())
        pumpOntime = int(file.readline())
        usrPH = int(file.readline())
        usrEC = int(file.readline())
        cloudInterval

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
            
            file.write('%d\n' %delay)
            file.write('%d\n' %pumpOnTime)
            file.write('%d\n' %usrPH)
            file.write('%d\n' %usrEC)
            file.write('%d\n' %cloudInterval)
            
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
        file.write('%d\n' %cloudInterval)
        
        file.close()
    #----------------------------------------------------------
    # Start up pins, set interrupts for flow sensors. 
    # GPIO Setup
    GPIO.setup(flow1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(flow2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(ECHO, GPIO.IN)

    GPIO.setup(mainpump, GPIO.OUT)
    GPIO.setup(auxpump1, GPIO.OUT)
    GPIO.setup(solnd1, GPIO.OUT)
    GPIO.setup(solnd2, GPIO.OUT)
    GPIO.setup(doser1, GPIO.OUT)
    GPIO.setup(doser2, GPIO.OUT)
    GPIO.setup(doser3, GPIO.OUT)
    GPIO.setup(doser4, GPIO.OUT)
    GPIO.setup(doser5, GPIO.OUT)
    
    GPIO.setup(ch1, GPIO.OUT)
    GPIO.setup(ch2, GPIO.OUT)
    
    GPIO.setup(TRIG, GPIO.OUT)
    
    GPIO.add_event_detect(flow1, GPIO.FALLING, callback=flow1Int, bouncetime=50)
    GPIO.add_event_detect(flow2, GPIO.FALLING, callback=flow2Int, bouncetime=50)
    
    #wiringpi.wiringPiSetupGpio()
    #wiringpi.pinMode(flow1, wiringpi.GPIO.INPUT)
    #wiringpi.pullUpDnControl(flow1, wiringpi.GPIO.PUD_DOWN)
    
    #wiringpi.pinMode(flow2, wiringpi.GPIO.INPUT)
    #wiringpi.pullUpDnControl(flow2, wiringpi.GPIO.PUD_DOWN)
    
    #wiringpi.wiringPiISR(flow1, wiringpi.GPIO.INT_EDGE_FALLING, flow1Int)
    #wiringpi.wiringPiISR(flow2, wiringpi.GPIO.INT_EDGE_FALLING, flow2Int)    
    #-----------------------------------------------------------
    # Setup cloud vairables, and diagnostic variables. Start up cloud interface.
    variables = {
        'flowPing1': {
            'type': 'numeric',
            'bind': flowPing1
        },
        'flowPing2': {
            'type': 'numeric',
            'bind': flowPing2
        },
        'pumpOn': {
            'type': 'bool',
            'bind': pumpOn
        },
        'PH Sensor': {
            'type': 'numeric',
            'bind': senPH if True else 0
        },
        'EC Sensor': {
            'type': 'numeric',
            'bind': senEC
        },
        'Ultrasonic Sensor': {
            'type': 'numeric',
            'bind': senUltra
        },                        
        'PumpDelay': {
            'type': 'numeric',
            'bind': pumpDelaySet
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
        },
        'String': {
            'type': 'string',
            'bind': changeString
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
    date = datetime.today()
    
    logName = './log-' + date.strftime('%m-%d-%Y-%H-%M')
    
    log = open(logName, 'a+')
    
    log.write('\t\tSenPH\tSenEC\t\n')
    
    log.close()
    
    lcd.clear()
    lcd.message = "fuck"
    
    #GPIO.output(solnd2, GPIO.HIGH)
    #GPIO.output(mainpump, GPIO.LOW)
    #GPIO.output(solnd1, GPIO.LOW)
    
    #i = 0
    #while True:
     #   i += 1
    GPIO.output(doser1, GPIO.HIGH)
    GPIO.output(doser2, GPIO.HIGH)
    GPIO.output(doser3, GPIO.HIGH)
    GPIO.output(doser4, GPIO.HIGH)
    GPIO.output(doser5, GPIO.HIGH)
    GPIO.output(auxpump1, GPIO.LOW)
    
    #i = 1
    #while True:
        #if i == 1:
            #GPIO.output(doser1, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(doser1, GPIO.HIGH)
        #elif i == 2:
            #GPIO.output(doser2, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(doser2, GPIO.HIGH)
        #elif i == 3:
            #GPIO.output(doser3, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(doser3, GPIO.HIGH)
        #elif i == 4:
            #GPIO.output(doser4, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(doser4, GPIO.HIGH)
        #elif i == 5:
            #GPIO.output(doser5, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(doser5, GPIO.HIGH)
        #elif i == 6:
            #GPIO.output(auxpump1, GPIO.LOW)
            #time.sleep(5)
            #GPIO.output(auxpump1, GPIO.HIGH)    
            #i = 0
        #i += 1
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
    phSense_jon = scheduler.add_job(phJob, 'interval', seconds = senseInterval/5)

    signal.signal(signal.SIGINT, signal_handler)
 
    GPIO.output(auxpump1, GPIO.LOW)
    GPIO.output(ch1, GPIO.HIGH)
    GPIO.output(ch2, GPIO.HIGH)
    
    GPIO.output(TRIG, GPIO.HIGH)
    GPIO.output(TRIG, GPIO.LOW)

    print('Running') 
    
    flowPing1 = 0
    flowPing2 = 0
    
    iter = 1
    
    while True:
        nextTime = pump_job.next_run_time
        local = get_localzone()
        
        print(nextTime)
        print(datetime.now(timezone.utc))

        currTime = datetime.now(timezone.utc)
        currTimez = currTime.astimezone(local)
        deltaTime = nextTime-currTimez
        
        if iter % 2 == 0:
            lcd.clear()
            lcd.message = "Next pump in:\n" + str(deltaTime)
        else:
            lcd.clear()
            lcd.message = "PH: " + str(senPH) + "\n" + "EC: " + str(senEC)
        
        if sysError:
            print("System Paused!")
            lcd.clear()
            lcd.message = "System Paused!\nPress Select to Start"
            time.sleep(slp)
            scheduler.pause()
            while sysError:
                if lcd.select_button:
                    sysError = False
        else:
            scheduler.resume()
        
        #-------------------------------------------
        # Read Ultrasonic
        senUltra = readSenUltra()
        senPH = readSenPH()
        senEC = readSenEC()

        AutoLevelData()
        AutoLevelTest()

        # Error Checking, pause apscheduler before enterError.

        scheduler.pause()
        if senUltra < 22:
            sendEmail("Water is Low, Fill Up Soon!")        
            
        elif senUltra < 26:
            #enterError("Water Level Critical. Fill Up Now.")
            print("error")
            
        if senPH > usrPH * 1.05:
            GPIO.output(doser4, GPIO.HIGH)
            time.sleep(1)
            GPIO.output(doser4, GPIO.LOW)
            
        if senEC > usrEC * 1.05:
            sendEmail("Water is too concentrated, please add more water!")
            
        if senPH < usrPH * 0.95:
            GPIO.output(doser5, GPIO.HIGH)
            time.sleep(2)
            GPIO.output(doser4, GPIO.LOW)
            
        if senEC < usrEC * 0.95:
            GPIO.output(doser1, GPIO.HIGH)
            time.sleep(1)
            GPIO.output(doser1, GPIO.LOW)
            
        if autodoserLevels[0]:
            sendEmail("Fertilizer 1 Level Low, Fill Up Soon!")
        elif autodoserLevels[1]:
            sendEmail("Fertilizer 2 Level Low, Fill Up Soon!")
        elif autodoserLevels[2]:
            sendEmail("Fertilizer 3 Level Low, Fill Up Soon!")
        elif autodoserLevels[3]:
            sendEmail("PH Down is Low, Fill Up Soon!")
        elif autodoserLevels[4]:
            sendEmail("PH Up is Low, Fill Up Soon!")
            
        scheduler.resume()

        #-------------------------------------------
        # Call user if water levels are low
        #-------------------------------------------

        if flowPing2 < 0.8 * flowPing1:
    #            print("Solenoid 2 on, Draining!")
    #        GPIO.output(solnd2, GPIO.HIGH)
            print("error")

        print("Running main loop")
        
        print("EC: " + str(senEC) + "\tPH: " + str(senPH) + "\t US: " + str(senUltra))
        print("Flow1: " + str(flowPing1) + "\t Flow2: " + str(flowPing2))
        
        log = open(logName, 'a+')
        log.write(date.strftime('%m-%d %H:%M') + '\t' + str(senPH) + '\t' + str(senEC) + '\n')
        log.close()
        time.sleep(senseInterval)
        iter += 1
        device.publish_data()
