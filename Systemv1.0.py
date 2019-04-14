from apscheduler.schedulers.background import BackgroundScheduler
from Adafruit_IO import Client, Feed, Data, RequestError
from email.message import EmailMessage
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import RPi.GPIO as GPIO
import board
import os
import busio
import time
import datetime
import signal
import sys
import random

# Change to 60 if you need minutes. Display shows it.
multiplier = 1

# Change time messages are displayed for. (Seconds)
readTime = 2
#----------------------------------------------
ADAFRUIT_IO_KEY = '1e93eaf324474204a089b238aa4a8956'
ADAFRUIT_IO_USERNAME = 'torrjose'
try:
    aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    print("CLOUD CONNECT!")
    
except:
    print("FAILED TO CONNECT TO CLOUD!")

val1 = 0
val2 = 0

# How often(seconds) to send data to cloud. Must be > 11
cloudInterval = 15
#---------------------------------------------
pumpOn = False
pumpInt = False

pumpOnTime = 5
delay = 10
usrPH = 10
usrEC = 10
#----------------------------------------------
lcd_columns = 16
lcd_rows = 2

i2c = busio.I2C(board.SCL, board.SDA)
lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)

lcd.backlight = False

lcd.clear()

msg1 = "        "
msg2 = "        "
msg3 = "        "
msg4 = "        "

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

def cloudSend():
    # Flow 1 and 2
    # Add global for sensor
    global number
    global number2
    global pumpOn

    val1 = random.randint(1,256)
    val2 = random.randint(1,256)

    print('Data being sent to cloud')
 # Uncomment for network testing.
 #   print(str(datetime.datetime.now()))
 #   print(str(number) + "\n" + str(number2) + "\n" + str(pumpOn) + "\n" + str(val1) + "\n" + str(val2) + "\n")

    if pumpOn:
        pumpStat = 200
    else:
        pumpStat = 0

    # Change val1/val2 to sensor global
    aio.send('block-validation.temp', number)
    aio.send('block-validation.feed-two', number2)
    aio.send('block-validation.feed-three', pumpStat)
    aio.send('block-validation.feed-four', val1)
    aio.send('block-validation.feed-five', val2)

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
    variableNums = [10, 10, 10, 10]

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

    lcd.message = "Pump On Time: " + str(pumpOnTime) + "\n" + "Cycle Delauyy: " + str(delay)
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

GPIO.setup(channel, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(flow2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

GPIO.setup(mainpump, GPIO.OUT)
GPIO.setup(auxpump1, GPIO.OUT)
GPIO.setup(solnd1, GPIO.OUT)
GPIO.setup(solnd2, GPIO.OUT)

GPIO.add_event_detect(channel, GPIO.RISING, callback=flow1)
GPIO.add_event_detect(flow2, GPIO.FALLING, callback=flowm2)

#-----------------------------------------------------------



#-----------------------------------------------------------

scheduler = BackgroundScheduler()
scheduler.start()

pump_job = scheduler.add_job(runMainPump, 'interval', seconds = delay * multiplier, id = 'mPump')
cloud_job = scheduler.add_job(cloudSend, 'interval', seconds = cloudInterval)

signal.signal(signal.SIGINT, signal_handler)

GPIO.output(auxpump1, GPIO.LOW)

print('Running')

msg3 = "Timing: "
msgNew = ""

buttonNum = 1

while True:
    msgOut =  (msg1 + msg2 + "\n" + msg3 + msg4)

    print(str(delay) + " " + str(pumpOnTime) + " " + str(usrEC) + " " + str(usrPH))

    if msgOut != msgNew:
        lcd.message = msgOut

    if(pumpOn):
#        print("Pump is on!")

        msg1 = "Pump on!"
    else:
        msg1 = "Pump off"

        if number2 < 0.8 * number:
#            print("Solenoid 2 on, Draining!")
            GPIO.output(solnd2, GPIO.HIGH)
        
    msg3 = "Timing: "
    msg4 = ""
    msg4 = str(pumpOnTime)

    msgNew = msgOut
    
 #   print("!")




