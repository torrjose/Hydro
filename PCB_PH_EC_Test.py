import RPi.GPIO as GPIO
import time                                #Import time library
import spidev

GPIO.setmode(GPIO.BCM)

#pins for all system peripherals

#Water Control
mainpump = 13
solnd1 = 16
solnd2 = 17

#Nutrient Autodoser
doser1 = 19
doser2 = 20
doser3 = 21
doser4 = 22
doser5 = 23
airpump = 24

#EC/PH switch
ch1 = 25
ch2 = 26

#ADC
adcCLK = 11
adcDout = 9
adcDin = 10
adcCS = 8

#Flow Sensors
flow1 = 12
flow2 = 6

#Level Sensor
TRIG = 4
ECHO = 5

#LCD i2c pins
sda1 = 2
scl1 = 3


#SPI setup
spi = spidev.SpiDev()
spi.open(0,0)

#GPIO pin setup
GPIO.setup(ch1, GPIO.OUT)
GPIO.setup(ch2, GPIO.OUT)
GPIO.output(ch1, GPIO.HIGH)
GPIO.output(ch2, GPIO.HIGH)

#Global PH and EC variables
PHVolts = 0.0
ECVolts = 0.0
PHBits = 0
ECBits = 0



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

try:
    while True:
        #PHData()
        #time.sleep(2)
        ECData()
        print("EC Bits ", ECBits)
        print("EC Volts ", ECVolts)
        EC = ECValue(ECVolts)
        print("Calculated EC Value: ", EC)
        time.sleep(2)
        
except KeyboardInterrupt:
    print("quit")
    GPIO.output(ch1, GPIO.HIGH)
    GPIO.output(ch2, GPIO.HIGH)
    GPIO.cleanup
