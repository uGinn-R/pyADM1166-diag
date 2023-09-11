from machine import Pin, I2C
import utime as time

DEVICE_ADDRESS = 52
# RoundRobin Registers:
RRSEL1 = 128 # 0x80
RRSEL2 = 129 # 0x81
RRCTRL = 130 # 0x82
# ADC Registers:
ADC = {"VH": 0xA8, "VX1": 0xAA, "VX2": 0xAC, "VX3": 0xAE, "VX4": 0xB0,
    "VX5": 0xB2,"PWR_GD-1V8": 0xB6, "VP1":0xA0, "VP2":0xA2, "VP3":0xA4}
# Fault status registers (fault = 1):
FSTAT1 = 0xE0 # [bit:channel] 7:VX3 6:VX2 5:VX1 4:VH 3:VP4 2"VP3 1:VP2 0:VP1
FSTAT2 = 0xE1 # [bit:channel] 1:VX5 0:VX4
FAULT_REGISTERS = {"OVSTAT1": 0xE2, "OVSTAT2": 0xE3, "UVSTAT1": 0xE4, "UVSTAT2": 0xE5}
OVSTAT1 = 0xE2 # OverVoltage Register, bit order same as for FSTAT1
OVSTAT2 = 0xE3 # OverVoltage Register, bit order same as for FSTAT2
UVSTAT1 = 0xE4 # UnderVoltage Register, bit order same as for FSTAT1 and OVSTAT1
UVSTAT2 = 0xE5 # UnderVoltage Register, bit order same as for FSTAT2 and OVSTAT2
# Fault registers dictionaries [bit:name]:
FR1DICT = {7: "MGTAVCC / 1V0_AVCC", 6: "1V0 (U4 ADP5135)", 5: "0V95 (U18 ADP2386A)", 4: "VIN / 5V0", 
           3: "VCCO_33_34 / 1V8", 2: "VCCO_13 / VADJ", 1: "VCCO_12 / VADJ", 0: "1V8 (U4 ADP5135)"}
FR2DICT = {0: "MGTAVTT / 1V2_AVTT", 1: "1.35V (U4 ADP5135)"}

# ADC Constants:
ADCref = 2.048 # adc reference voltage
ADCrange = 4095 # adc range for 12 bit
MidRangeAtten = 4.3636 # VP2, VP3, VH Attenuation
VP1Atten = 2.1818 # VP1 Attenuation

i2c = I2C(scl=Pin(14), sda=Pin(12), freq=100000) # i2c init

# waiting for slave i2c deivce
while not DEVICE_ADDRESS in i2c.scan():
     print("waiting for device...")

print("Device detected!")
time.sleep(0.5) # waiting to filter spikes at power on (false overvoltage triggering)

fault = False # init global fault

def PerformAdcReading(register):
    i2c.writeto_mem(DEVICE_ADDRESS, RRSEL1, b'\x00') # select all channels for RRSEL1
    i2c.writeto_mem(DEVICE_ADDRESS, RRSEL2, b'\x00') # select all channels for RRSEL2
    i2c.writeto_mem(DEVICE_ADDRESS, RRCTRL, b'\x06') # set Enable and Average bits to 1
    i2c.writeto_mem(DEVICE_ADDRESS, RRCTRL, b'\x0E') # set Enable, Average and STOPWRITE bits to 1 
    result = i2c.readfrom_mem(DEVICE_ADDRESS, register, 2)
    i2c.writeto_mem(DEVICE_ADDRESS, RRCTRL, b'\x06') # set Enable and Average bits to 1
    return int.from_bytes(result, "big")

def to_mV(result, attenuation = 1.0):
    return round(((result / ADCrange) * ADCref * attenuation) / 16, 3) # 16x avrg and round to 3 decimal places

def ReadFaultStatus(register_key):
        global fault
        StatusByte = i2c.readfrom_mem(DEVICE_ADDRESS, FAULT_REGISTERS[register_key], 1)
        bitsArray = "{:08b}".format(int(StatusByte.hex(), 16))
        bitsArray = ''.join(reversed(bitsArray)) # reversing string to fit correct bits order
        for bit in range(len(bitsArray)):
            if bitsArray[bit] == "1":
                if register_key.endswith('1'):
                    print("Fault detected in ",FR1DICT[bit])
                else:
                     print("Fault detected in ",FR2DICT[bit])
                print(register_key, hex(int.from_bytes(StatusByte, "big")), bitsArray)
                fault = True
                break
            break

def PrintAdcReadings():
        for key in ADC:
            result = PerformAdcReading(ADC[key])
            if key in {"VH", "VP2", "VP3"}:
                print(key, to_mV(result, MidRangeAtten))
            elif key == "VP1":
                print(key, to_mV(result, VP1Atten))
            else:
                print(key, to_mV(result))

t = time.ticks_ms() # init timer

while fault is False:
    for key in FAULT_REGISTERS:
        ReadFaultStatus(key)
    if time.ticks_diff(time.ticks_ms(), t) >= 1000: # read ADC values each 1 second and reset timer
        t = time.ticks_ms()
        PrintAdcReadings()