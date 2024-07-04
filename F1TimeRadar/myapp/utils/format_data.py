from datetime import datetime, timedelta
from myapp.utils.dataScheduler import scheduler
import base64, zlib, json, datetime

class Data:
  def __init__(self, time, type, data_live):
    self._time = time
    self._type = type
    self._data = data_live

def format_time(time):
  utc_dt = str(time).replace("Z","")
  if '.' in utc_dt:
      if len(utc_dt.split(".")[1])>6:
          time = datetime.strptime(utc_dt[:-1], "%Y-%m-%dT%H:%M:%S.%f")
      else:
          time = datetime.strptime(utc_dt, "%Y-%m-%dT%H:%M:%S.%f")
  else:
      time = datetime.strptime(utc_dt, "%Y-%m-%dT%H:%M:%S")
  return time

def full_data_update(msg):
   pass

# CarData.z
def carData(msg):
  decoded_bytes = base64.b64decode(msg)
  try:
     decompressed_bytes = zlib.decompress(decoded_bytes)
  except zlib.error:
     decompressed_bytes = zlib.decompress(decoded_bytes, -zlib.MAX_WBITS)
  decompressed_str = decompressed_bytes.decode('utf-8')
  car_data = json.loads(decompressed_str)
  return car_data

# Position.z
def positionData(msg):
   pass

# ExtrapolatedClock
def extrapolatedClock(msg):
   pass

# TopThree
def topThree(msg):
   pass

# TimingStats
def timingStats(msg):
   pass

# TimingAppData
def timingAppData(msg):
   pass

# WeatherData
def weatherData(msg):
   pass

# TrackStatus
def trackStatus(msg):
   pass

# DriverList
def driverList(msg):
   pass

# RaceControlMessages
def raceControlMessages(msg):
   pass

# SessionInfo
def sessionInfo(msg):
   pass

# SessionData
def sessionData(msg):
   pass
# TimingData
def timingData(msg):
   pass

def format_data(msg):
  line = eval(msg)
  if 'M' in line.keys() and line['M']:
    for i in line['M']:
        if 'A' in i.keys() and i['A']:
            type = i['A'][0]
            data = str(i['A'][1])
            time = format_time(i['A'][2])
            new_data = Data(time, type, data)
  elif 'R' in line.keys():
     full_data_update(line['R'])
