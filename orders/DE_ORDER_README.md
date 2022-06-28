# Delivery Express order README
> `orders/delivery_express_order.py`

Delivery express (DE) ships and returns swab kits for SCAN, HCT, AIRS, and other projects as part of the S&S model. We send them an order file in `.csv` format with 1 row corresponding to 1 order with the following columns:

column | definition
-|-
 Record Id | participant's redcap id
 Today Tomorrow | `0` or `1`. DE uses this coding to assign the pick up times. _ is a pick up in the evening the same day the order was shipped and _ is a pick up the next morning. 
 Order Date | When the order was placed i.e. when the corresponding redcap survey was completed
 Project Name | SCAN, HCT... Used for billing and in some cases, project specific business logic on DE's side i.e. if a line haul needs to be created
 First Name | 
 Last Name | 
 Street Address | 
 Apt Number | 
 City | 
 State | 
 Zipcode |
 Delivery Instructions | where the kit should be delivered
 Email | 
 Phone | 
 Notification Pref | what the participant prefers either `text` or `email` for delivery communication
 Pickup Location | where the kit should be picked up
 

### External APIs
The ordering script pulls data from various redcap projects. This data is compiled into a single order file and emailed to kittrack@uw.edu each morning at 6:45am. API keys are stored in `.env/redcap`. The script pulls from the following projects:

- SCAN Eng
- SCAN Span
- SCAN Viet
- SCAN Trad Chinese
- SCAN Russina
- HCT
- AIRS
- Cascadia

### Dependencies
This script depends on [Pycap](https://github.com/redcap-tools/PyCap/releases/tag/1.1.3) (v1.1.3) for a wrapper to the REDCap API.

## Methods

The DE ordering script iterates through each key (project) in `etc/redcap_variable_map.py`, exports a report from redcap containing the orders for that day, then formats the data to align with the above schema. The formatting complexity depends on the project type

### Cross-Sectional Proejcts
These projects are the simpler of the two since all the needed data is already confined to 1 row.


### Logitudinal Projects

These type of projects are more complex than cross-sectional because the nessesary data is split between two or more rows. Redcap splits this data because the surveys that collect this are part of different events; usually an enrollment and encounter event type. Below is an example of how this split would look for record_id 1:

record_id | event | name | address_1 | order_date | address_2
-|-|-|-|-|-
1 | enrollment | Joe | 1234 55th Ave NE |
1 | encounter ||| 2022-01-01 | 4321 55th Ave NE

Logitudinal projects will typically ask a participant for their address at enrollment then again when they request a swab kit to confirm. The script favors addresses provided when the participant requests a swab because this would be the most up to date. If an address is not provided during the encounter, the script will default to using the address in the enrollment event.

The `use_best_address(original_address, row, event)` function takes:
- `original_address` as a Pandas dataframe containing all the participant's addresses from the enrollment event i.e. which addresses should be used in case the encounter event does not have an address.
- `row` as a Pandas series for a single order's encounter event. The script will check if this row has address info before defaulting to the original_address.
- `event` as a string describing the redcap_event_name for the enrollment event. This is used to search the `orginal_address` dataframe for the order's address provided during enrollment. 

## Deployment
This script is deployed on the private AWS EC2 instance used for the Tableau Server. The script is set to run at 6:45am usbing crontab.

## Tests
Tests for the order script have been created and are in `tests/order_test.py`. There are 2 tests. The first one checks if the script is able to export the data from each project. This covers the connection to redcap and if the report is working. The second one mocks the data from the order report and checks if the order script creats a .csv file that is the same as the expected output .csv. The data for these mocks and expected results are in `tests/data` for each project.