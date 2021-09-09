#!/usr/bin/env python3

import json
import requests
import datetime
import os

#TODO: add S3 commands to get apple's participant IDs and Check-in Datetimes

#file path may need to be updated depending on file name
file = input("Enter file name:")
f = open(file, "r")
appleData = json.loads(f.read())
f.close()
print(appleData)

#Find all (redcap) ids without a welcome_date
#todo: include apple ids
data = {
    'token': '', # ADD API TOKEN
    'content': 'record',
    'format': 'json',
    'type': 'flat',
    'fields[0]': 'record_id',
    'fields[1]': 'current_apple_pid',
    'events':'enrollment_arm_1',
    'rawOrLabel': 'raw',
    'rawOrLabelHeaders': 'raw',
    'exportCheckboxLabel': 'false',
    'exportSurveyFields': 'false',
    'exportDataAccessGroups': 'false',
    'returnFormat': 'json',
    'filterLogic': '[welcome_date] = ""'
}
notWelcome = []
r = requests.post('https://redcap.iths.org/api/',data=data)
notWelcome = r.json()
print('REDCap records without welcome_date: ' + str(len(notWelcome))) #redcap ids without a welcome_date

#find matches of apple ids to redcap ids and the earliest date
welcome = []
for record in notWelcome:
    oldestCheckin = datetime.datetime.today()
    redcapID = -1
    for welcomeId in appleData:
        appleID = record['current_apple_pid']
        welcomeIdDateTime = datetime.datetime.strptime(welcomeId['LastCheckIn'], '%Y-%m-%d %H:%M:%S')
        if((appleID == welcomeId["ParticipantExternalID"]) & (welcomeIdDateTime <= oldestCheckin)):
            oldestCheckin = welcomeIdDateTime
            redcapID = record['record_id']
    if(int(redcapID) > 0):
        welcome.append({
            'record_id': redcapID,
            'current_apple_pid': appleID,
            'welcome_date': oldestCheckin.strftime('%Y-%m-%d %H:%M:%S')})
print('REDCap records without a welcome_date that have their apple ids in the file from Apple and LastCheckIn <= today: ' + str(welcome)) #list of redcap_id and welcome_date

#format for REDCap import (needs to have redcap_event_name for longitudinal projects)
toImport = []
for value in welcome:
    toImport.append({
        'record_id': value['record_id'],
        'redcap_event_name': 'enrollment_arm_1',
        'welcome_date': value['welcome_date']})
print("Formatted REDCap records to import: " + str(toImport)) #formatted list of data containing redcap id and welcome_date for each "new" PT

#push toImport to REDCap
data = {
    'token': '', # ADD API TOKEN
    'content': 'record',
    'format': 'json',
    'type': 'flat',
    'overwriteBehavior': 'normal',
    'forceAutoNumber': 'false',
    'returnContent': 'ids',
    'returnFormat': 'json',
    'data': json.dumps(toImport)
}
r = requests.post('https://redcap.iths.org/api/',data=data)
print('IDs Added:' + str(r.json())) #list of ids updated
os.system("pause")
