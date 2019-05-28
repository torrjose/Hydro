# -*- coding: utf-8 -*-
from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
from datetime import datetime, timezone
from tzlocal import get_localzone
from numpy import median
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
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
import math

# Change to 60 if you need minutes. Display shows it.
multiplier = 1

# Change time messages are displayed for. (Seconds)
readTime = 2
#----------------------------------------------
DEVICE_TOKEN = '48RPJxBwbPUSxANfiNC7MMmtn'

val1 = 0
val2 = 0

# How often(seconds) to send data to cloud. Must be > 11
cloudInterval = 30
# How often(seconds) to read data from the sensors.
senseInterval = 15
PHInterval = senseInterval/5 if senseInterval / 5 > 10 else 10
#---------------------------------------------
pumpOn = False
pumpInt = False

sysError = False
sysErrorMsg = 'ERROR'

pumpOnTime = 30
delay = 120
usrPH = 6.5
usrEC = 1.25
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

slp = 2
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
PHSamples = [0.0, 0.0, 0.0, 0.0, 0.0]
PHTested = [False, False, False, False, False]
phMedian = 0.0

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


    print('Flow 1: {}'.format(flowPing1))
    print('Flow 2: {}'.format(flowPing2*(4/3)))

    flow2 = flowPing2*(8/3)

    if flowPing1*0.8 <= flow2 <= flowPing1*1.05:
        enterError("Flow Rates didn't Match!")
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
                if i == 2 or i == 3:
                    variableNums[i] -= 0.1
                else:
                    variableNums[i] -= 1
                lcd.clear()
                print("Left, Dec by 1")
        elif lcd.up_button:
                if i == 2 or i == 3:
                    variableNums[i] += 1
                else:
                    variableNums[i] += 5
                lcd.clear()
                print("Up, Increment by 5")
        elif lcd.down_button:
                if i == 2 or i == 3:
                    variableNums[i] -= 1
                else:
                    variableNums[i] -= 5
                lcd.clear() 
                print("Down, Decrement by 5")
        elif lcd.right_button:
                if i == 2 or i == 3:
                    variableNums[i] += 0.1
                else:
                    variableNums[i] += 1
                lcd.clear()
                print("Right, Increment by 1") 
        elif lcd.select_button:
                if variableNums[i] < 0:
                    lcd.message = "Invalid Number \n Try again"
                    time.sleep(slp)
                    lcd.clear()
                    continue
                if i == 1:
                    if variableNums[0] < 2*variableNums[1]:
                        lcd.message = "Delay must be bigger than \n 2x pump time"
                        time.sleep(slp)
                        lcd.clear()
                        continue
                if i == 2:
                    if variableNums[2] > 10:
                        lcd.message = "PH must be below 10"
                        time.sleep(slp)
                        lcd.clear()
                        continue
                if i == 3:
                    if variableNums[3] > 5:
                        lcd.message = "EC must be below 5"
                        time.sleep(slp)
                        lcd.clear()
                        continue
                if i == 4:
                    if variableNums[4] < 3:
                        lcd.message = "Cloud interval must \n be more than 30s"
                        time.sleep(slp)
                        lcd.clear()
                        continue
                i += 1
                lcd.clear()
                print("Select")

        if i == 5:
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
    
    print("Attempting PH READ")
    if pumpOn is True:
        print("Pump ON")
        return
    #power PH circuit, poll sensor, turn off PH circuit
    global PHBits
    global PHVolts
    sampleMax = 0
    sampleMin = 0
    sample = 0
    
    GPIO.output(ch1, GPIO.LOW)
    time.sleep(5)

    for i in range(100):
        sample = analogInput(1)
        if i==0:
            sampleMin = sample
            sampleMax = sample
        if i>0:
            if sample < sampleMin:
                sampleMin = sample
            if sample > sampleMax:
                sampleMax = sample
        time.sleep(0.01)
        
    PHBits = (sampleMax + sampleMin)/2
    PHVolts = Volts(PHBits)
    PHVolts = round(PHVolts, 3)
    time.sleep(1)
    GPIO.output(ch1, GPIO.HIGH)
    time.sleep(5)
    print("pH circuit voltage: ", PHVolts)
    
#reads EC sensor
def ECData():
    print ("Attempting EC Read")
    global ECBits
    global ECVolts
    sampleMax = 0
    sampleMin = 0
    sample = 0
    
	#power EC circuit
    GPIO.output(ch2, GPIO.LOW)
    time.sleep(5)

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
    time.sleep(5)

#mapping waveform to convert volts to electrical conductivity     
def ECValue(Volts):
    EC = 0.00
    EC = (0.673*Volts*Volts)+(0.724*Volts)+0.05
    round(EC, 2)
    return EC
    
def PHValue(Volts):
    global senPH
    PH = 0.00
    PH = -20*Volts + 32
    #print("Raw value: " + str(PH))
    #return PH
    #if push comes to shove, uncomment statement line above and comment out all lines below.
    for i in range(5):
        if PHTested[i] == False:
            PHSamples[i] = PH
            PHTested[i] = True
            #if i == 0 && senPH  == 0.0:
            #    senPH = PH
            break

    if PHTested[4] == True:
        PHSamples.sort()
<<<<<<< HEAD:oldSystemv1.3.py
        senPH = median(PHSamples)
        
=======
        phMedian = median(PHSamples)
>>>>>>> 3ee1090c8e4f3beab78e2d3064357a68e777d5dc:Systemv1.3.py
        for i in range(5):
            PHTested[i] = False
		
    return


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
    return usrEC

def userPHSet(value):
    global usrPH

    if value != None:
        usrPH = value
        
    return usrPH

def sysErrorSet(value):
    global sysError

    if value != None:
        sysError = value
    return sysError
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
    
    print("\n\n\n\n")
    
    flowPing1 = 0
    flowPing2 = 0
    
    GPIO.output(mainpump, GPIO.HIGH)
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2, GPIO.HIGH)        
    
    time.sleep(5)
    
    temp = 0
    lcd.clear()
    lcd.message = "Priming System"
    lcd.clear()
    lcd.message = "Running Flow1"
    print("Turning on pump, and sol1")
    print("Pump time: " + str(pumpOnTime))
    GPIO.output(mainpump, GPIO.LOW)
    GPIO.output(solnd1, GPIO.HIGH)
    GPIO.output(solnd2, GPIO.HIGH)
    print("Priming System")
    print("Running pump")

    time.sleep(pumpOnTime)
    
    print("Flow1: " + str(flowPing1))
    print("Flow2: " + str(flowPing2))    
    
    firstFlowRate = flowPing1

    if flowPing1 == 0:
        enterError("No Reading at flow sensor 1. Possible bad pump or clog.")

    print("Sol1 off")
    lcd.clear()
    #lcd.message = "Testing Sol1"
    temp = flowPing1
    GPIO.output(solnd1, GPIO.LOW)

    print("Flow1: " + str(flowPing1))
    print("Flow2: " + str(flowPing2))  

#    if 2*temp < flowPing1:
#        enterError("Continued Flow after Solenoid closing. Possible Clog.")

    print("Waiting for flow2")
    lcd.clear()
    lcd.message = "Testing Flow2"
    print("Pump on, sol1 on, sol2 off")
    GPIO.output(solnd1, GPIO.HIGH)
    GPIO.output(solnd2, GPIO.LOW)

    time.sleep(15)
    
    
    GPIO.output(solnd2, GPIO.HIGH)
    time.sleep(5)
   
    print("Flow1: " + str(flowPing1))
    print("Flow2: " + str(flowPing2))      
    
    if flowPing2 == 0:
        enterError("No Reading at flow sensor 2. Possible clog in system.")
        print("error")

    print("Pump off")
    lcd.clear()
    lcd.message = "Testing Sol2"
    print("pump on, sol1 on, sol2 off")
    GPIO.output(solnd1, GPIO.HIGH)
    GPIO.output(solnd2, GPIO.HIGH)
    GPIO.output(mainpump, GPIO.LOW)

    temp = flowPing2

    time.sleep(10)

    print("Flow1: " + str(flowPing1))
    print("Flow2: " + str(flowPing2))  

    print("Sold2 Closing.")    
    if 2*temp < flowPing2:
        enterError("Continued Flow after Solenoid 2 closing. Possible Clog.")
        print("error")
        
    lcd.clear()
    lcd.message = "System Passed!"
    time.sleep(slp)
    
    print("\n\n\n\n")



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
    to = ['torrjose@oregonstate.edu']
    subject = 'AUTOMATED GREENHOUSE IMPORTANT MESSAGE'

    email = EmailMessage()
    email['Subject'] = subject
    email['From'] = sent_from
    email['To'] = to
    email.set_content(msg)
    
    print("\nError message: \n" + msg + "\n")

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
    time.sleep(0.00001)                          #Delay of 0.00001 seconds
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
      return 100 - 100*(distance - 0.5)/56
    else:
      print ("Out Of Range")                      #display out of range    
      return 0
    
def readSenEC():
    global ECRead
    
    ECRead = True
    ECData()
    ECRead = False
    return ECValue(ECVolts)

PHRead = False

#gets called 5 times/sense interval
def phJob():

    PHData()
    PHValue(PHVolts)

    
#reads autodoser level sensors
def AutoLevelData():
    for i in range(len(autodoserLevels)):
        rawIn = analogInput(i+2)
        autodoserLevels[i] = Volts(rawIn) 
        
#checks autodoser level sensors for low levels
def AutoLevelTest():
    for i in range(len(autodoserLevels)):
        #print("chan ", i, ": ", autodoserLevels[i], '\n')
        if autodoserLevels[i] < 0.8:
            autodoserLevelErrors[i] = True
        else:
            autodoserLevelErrors[i] = False
        print("bottle Channel ", i, ": ", autodoserLevelErrors[i])

msg3 = "Timing: "
msgNew = ""
firstFlowRate = 0

def flowPing1Get():
    global flowPing1
    return flowPing1
    
def flowPing2Get():
    global flowPing2
    return (flowPing2)
    
def pumpOnGet():
    global pumpOn
    return pumpOn
    
def senPHGet():
    global senPH
    return senPH
    
def senECGet():
    global senEC
    return senEC
    
def senUltraGet():
    global senUltra
    return senUltra

ECRead = False

if __name__ == "__main__":
    # Set up the i2c port, and initialize the display
    i2c = busio.I2C(board.SCL, board.SDA)
    lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)

    lcd.backlight = False

    lcd.clear()

    #------------------------------------------------
    # Check config file, check if the user wants new values,
    # save new ones if needed, close file.
    #if True:
    #    lcd.clear()
    
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
    
    GPIO.add_event_detect(flow1, GPIO.FALLING, callback=flow1Int)
    GPIO.add_event_detect(flow2, GPIO.FALLING, callback=flow2Int)  
    #-----------------------------------------------------------
    #-----------------------------------------------------------
    # Start up thread service. Load up pumps, and cloud interface
    # to start up every x seconds.
    scheduler = BackgroundScheduler()
    scheduler.start()
    signal.signal(signal.SIGINT, signal_handler)
    
    GPIO.output(mainpump, GPIO.HIGH)
    GPIO.output(solnd1, GPIO.LOW)
    GPIO.output(solnd2,GPIO.LOW)
 
    GPIO.output(auxpump1, GPIO.HIGH)
    print("air pump on")
    GPIO.output(ch1, GPIO.HIGH)
    GPIO.output(ch2, GPIO.HIGH)
    
    GPIO.output(TRIG, GPIO.HIGH)
    GPIO.output(TRIG, GPIO.LOW)
    
    
    GPIO.output(doser1, GPIO.HIGH)
    GPIO.output(doser2, GPIO.HIGH)
    GPIO.output(doser3, GPIO.HIGH)
    GPIO.output(doser4, GPIO.HIGH)
    GPIO.output(doser5, GPIO.HIGH)
    
    if os.path.isfile('./config.txt'):
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
        print('usrPH: %d, Cycle Delay: %d, Pump on time: %d, usrEC: %d' %(usrPH, delay, pumpOn, usrEC))

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

    # Setup cloud vairables, and diagnostic variables. Start up cloud interface.
    variables = {
        'flowPing1': {
            'type': 'numeric',
            'bind': flowPing1Get
        },
        'flowPing2': {
            'type': 'string',
            'bind': flowPing2Get
        },
        'pumpOn': {
            'type': 'bool',
            'bind': pumpOnGet
        },
        'PH Sensor': {
            'type': 'numeric',
            'bind': senPHGet
        },
        'EC Sensor': {
            'type': 'numeric',
            'bind': senECGet
        },
        'Ultrasonic Sensor': {
            'type': 'numeric',
            'bind': senUltraGet
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
    date = datetime.today()
    
    logName = './log-' + date.strftime('%m-%d-%Y-%H-%M')
    
    log = open(logName, 'a+')
    
    log.write('\t\tSenPH\tSenEC\t\n')
    
    log.close()
    
    lcd.clear()
    
    print("going")
    #GPIO.output(solnd2, GPIO.LOW)
    #GPIO.output(mainpump, GPIO.LOW)
    #GPIO.output(solnd1, GPIO.HIGH)
    
    i = 0
    #while True:
       # print(str(flowPing1))
     #   print(str(flowPing2))
      #  time.sleep(1)
    
    #i = 1
    #while True:
        #print("Running pump: " + str(i))
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

    print('Running') 
    
    flowPing1 = 0
    flowPing2 = 0
    
    senseIter = 0
    
    iter = 1
    #-----------------------------------------------------------
    # Test system, throw errors otherwise.
    sysPrimer()
    #-----------------------------------------------------------

    pump_job = scheduler.add_job(runMainPump, 'interval', seconds = delay , id = 'mPump')
    cloudData_job = scheduler.add_job(publishData, 'interval', seconds = cloudInterval)
    cloudDiag_job = scheduler.add_job(publishDiag, 'interval', seconds = cloudInterval)
    #phSense_jon = scheduler.add_job(phJob, 'interval', seconds =PHInterval)
    
    GPIO.output(auxpump1, GPIO.LOW)
    
    while True:
        nextTime = pump_job.next_run_time
        local = get_localzone()
        
        #print(nextTime)
        #print(datetime.now(timezone.utc))

        currTime = datetime.now(timezone.utc)
        currTimez = currTime.astimezone(local)
        deltaTime = nextTime-currTimez
        temp = 0.00
        mess = ""
        
        if iter % 2 == 0:
            lcd.clear()
            lcd.message = "Next pump in:\n" + str(deltaTime)
        else:
            lcd.clear()
            mess = "PH: " + str(senPH) + "\n" + "EC: " + str(senEC)
            if temp != senPH:
                lcd.message = "*" + mess
            else:
                lcd.message = mess
            temp = senPH
            time.sleep(slp)
            lcd.clear()
            lcd.message = "User PH: " + str((usrPH)) + "\n" + "User EC: " + str((usrEC))
        
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
            
        print("PH Interval: " + str(senseInterval))
            
        if senseIter % PHInterval == 0:
            phJob()
        
        if senseIter % senseInterval == 0:
            #-------------------------------------------
            # Read Ultrasonic
            senUltra = readSenUltra()

            senEC = readSenEC()

            AutoLevelData()
            AutoLevelTest()
            
            #sysError = True

            # Error Checking, pause apscheduler before enterError.

            scheduler.pause()
            if senUltra < 15:
                sendEmail("Water is Low, Fill Up Soon!")        
                
            elif senUltra < 18:
                #enterError("Water Level Critical. Fill Up Now.")
                print("error")
                
            if senPH > usrPH * 1.05 and senPH != 0.0:
                print("Pumping in on Doser4! PH UP")
                GPIO.output(doser4, GPIO.LOW)
                time.sleep(2)
                GPIO.output(doser4, GPIO.HIGH)
                
            if senEC > usrEC * 1.05:
                sendEmail("Water is too concentrated, please add more water!")
                
            if senPH < usrPH * 0.95 and senPH != 0.0:
                print("Pumping in on Doser 5, PH Down!")
                GPIO.output(doser5, GPIO.LOW)
                time.sleep(2)
                GPIO.output(doser5, GPIO.HIGH)
                
            if senEC < usrEC * 0.95:
                print("Pumping in on Doser 1, Fertilizer 1!")
                GPIO.output(doser1, GPIO.LOW)
                time.sleep(10)
                GPIO.output(doser1, GPIO.HIGH)
                
            if autodoserLevelErrors[0]:
                print(autodoserLevels[0])
                sendEmail("Fertilizer 1 Level Low, Fill Up Soon!")
            elif autodoserLevelErrors[1]:
                sendEmail("Fertilizer 2 Level Low, Fill Up Soon!")
            elif autodoserLevelErrors[2]:
                sendEmail("Fertilizer 3 Level Low, Fill Up Soon!")
            #elif autodoserLevelErrors[3]:
             #   sendEmail("PH Down is Low, Fill Up Soon!")
            elif autodoserLevelErrors[4]:
                sendEmail("PH Up is Low, Fill Up Soon!")
                
            scheduler.resume()

            #-------------------------------------------
            # Call user if water levels are low
            #-------------------------------------------

            if not pumpOn:
                print("Solenoid 2 on, Draining!")
                GPIO.output(solnd2, GPIO.LOW)
                print("error")
                
            print("\n\n\n\n")
            print("--------------------Running main loop---------------------")
            print("EC: " + str(senEC) + "\tPH: " + str(senPH) + "\t US: " + str(senUltra))
            print("Flow1: " + str(flowPing1) + "\t Flow2: " + str(flowPing2))
            print("Level Sensor: " + str(autodoserLevelErrors))
            print("---------------------------------------------------------")
            print("\n\n\n\n")
            
            log = open(logName, 'a+')
            log.write(date.strftime('%m-%d %H:%M') + '\t' + str(senPH) + '\t' + str(senEC) + '\n')
            log.close()
            device.publish_data()
        
        time.sleep(1)    
        iter += 1
        senseIter += 1
