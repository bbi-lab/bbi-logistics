import json
import requests
import pandas
from datetime import date
import datetime



exportFields = [
    'Record Id',
    'Today Tomorrow',
    'Order Date',
    'Project Name',
    'First Name',
    'Last Name',
    'Street Address',
    'Apt Number',
    'City',
    'State',
    'Zipcode',
    'Delivery Instructions',
    'Email',
    'Phone',
    'Notification Pref',
    'Pickup Location'
]

def getSSRequests(project, report):
    data = {
        'token': projectDict[project]['Token'],
        'content': 'report',
        'report_id': projectDict[project][report],
        'format': 'json',
        'type': 'flat',
        'rawOrLabel': 'labeled',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'returnFormat': 'json'
    }
    r = requests.post('https://redcap.iths.org/api/',data=data)
    results = r.json()

    print(results)

    # recordID = -1
    # mostRecentOrderDate = datetime.datetime.strptime('01-01-2010', '%d-%m-%Y')
    # order = {}
    # orders = []

    # for record in results:
    #     if recordID == record['record_id']:
    #         orderDate = record[projectDict[project]['Order Date']]
    #         if orderDate == '':
    #             continue
    #         orderDate = datetime.datetime.strptime(orderDate,projectDict[project]['Order Date Format'])
    #         if orderDate < mostRecentOrderDate:
    #             continue
    #         if project == "Childcare":
    #             if record['s_s_request'] != 1:
    #                 continue
    #         mostRecentOrderDate = orderDate
    #     else:
    #         orders.append({})
    #         orderNum = len(orders)-1
    #         recordID = record['record_id']
    #     for column in exportFields:
    #         if(column == 'Project Name'):
    #             orders[orderNum][column] = project
    #             continue
    #         redcapField = record[projectDict[project][column]]
    #         if redcapField != '':
    #             orders[orderNum][column] = redcapField

    # print(str(project)+' s&s orders: '+str(len(orders)))
    # return orders
    #resultsP = pandas.DataFrame(results)



# input = ''
# while input != 'm' and input != 'a':
#     input = input('Morning or Afternoon fulfilment (m/a)?')
# if input == 'm':
#     report = 'Morning'
# elif input == 'a':
#     report = 'Afternoon'

report = 'Morning'
orders = []
for project in projectDict:
    print('Searching '+str(project)+'...')
    orders.extend(getSSRequests(project, report))
df = pandas.DataFrame(data=orders,columns=exportFields)
df.info()
df.to_csv('DEImport.csv')


# input = input('Morning or Afternoon fulfilment (m/a)?')
# if input == 'm':
#     for project in projectDict:
#         getSSRequests(project, 'Morning')
# elif input == 'a':
#     for project in projectDict:
#         getSSRequests(project, 'Afternoon')
# else:
#     print('Not a valid input. Report generation failed.')


# test = [1,2,3,4]
# df = pandas.DataFrame(data=test)
# df.to_csv('DispatchScienceImport.csv')




# filter = '([event-name][illness_questionnaire_complete] = 2 OR [group_enroll_arm_4][return_pickup_complete]= 2) AND [event-name][back_end_mail_scans_complete] = 0 AND [event-name][opt_out_complete] = 0 AND [event-name][yakima] <> 1 AND ([event-name][today_accept_ce] = 1 OR [event-name][pierce_accept] = 1)'
# #filter = '[event-name][enro][event-name][test_order_survey_complete]=2 AND [event-name][test_fulfillment_form_complete]=0 AND [event-name][tomorrow_accept_ce]=0'
#
# data = {
#     'token': token,
#     'content': 'record',
#     'format': 'json',
#     'type': 'flat',
#     'fields': ",".join(map(str, projectDict[project].values())),
#     'events':",".join(map(str, projectDict[project]['Events'])),
#     'rawOrLabel': 'raw',
#     'rawOrLabelHeaders': 'raw',
#     'exportCheckboxLabel': 'false',
#     'returnFormat': 'json',
#     'filterLogic': filter
# }
