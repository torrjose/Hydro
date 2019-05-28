#!/usr/bin/python


import RPi.GPIO as GPIO                    #Import GPIO library
import time                                #Import time library
GPIO.setmode(GPIO.BCM)                     #Set GPIO pin numbering 

TRIG = 4                                  #Associate pin 15 to TRIG
ECHO = 5                                  #Associate pin 14 to Echo


GPIO.setup(TRIG,GPIO.OUT)                  #Set pin as GPIO out
GPIO.setup(ECHO,GPIO.IN)                   #Set pin as GPIO in

GPIO.output(TRIG, GPIO.HIGH)
GPIO.output(TRIG, GPIO.LOW)

def DistanceMeasure():
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
    else:
      print ("Out Of Range")                      #display out of range

try:
  while True:
    DistanceMeasure()
    time.sleep(2)

except KeyboardInterrupt:
    print(" Quit")
    GPIO.cleanup()
