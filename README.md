# Logistics
Operational automation and dashboard updates for Brotman Baty Institute Logistics

### Ordering Script Documentation
- [Delivery Express](orders/DE_ORDER_README.md)
- [USPS](orders/USPS_ORDER_README.md)

### Dashboards Documentation
- [Dashboard Updates](update_dashboards/DASHBOARD_README.md)

## Usage
```
envdir <aws credentials path> pipenv run python3 orders/delivery_express_order.py [--save] [--s3-upload]
envdir <aws credentials path> pipenv run python3 orders/usps_cascadia_order.py [--save] [--s3-upload]
```

## Setup
Clone the logistics repo
```
cd ~/
git clone https://github.com/bbi-lab/bbi-logistics.git
cd logistics
```

Install required packages using:
```
pipenv install
```

## Configure REDCap API Token environment variables
> You need to do these steps once per REDCap project.

```
cd ~/logistics/.env/
```

You'll need to copy your REDCap API token from each project and create a new file containing only the token.
We create file names using this pattern: `REDCAP_API_TOKEN_{REDCAP API URL}_{PROJECT_ID}`.
Here's an example of creating a new environment variable for the SCAN IRB English project (project ID 22461) with the text editor `nano`:
```
nano redcap/REDCAP_API_TOKEN_redcap.iths.org_22461
```
HCT now uses the url `hct.redcap.rit.uw.edu`

Note that you are literally typing the string `REDCAP_API_TOKEN` here.
Once you're inside the file with `nano`, paste your actual token copied from REDCap.
Then, press `CTRL+X` to exit.
Remember to save your work!
(Press `Y` then hit `Enter` to confirm the original save location.)

Repeat this process for every SCAN REDCap project you need orders from.

## Configure AWS Account Credentials
```
cd ~/logistics/.env
mkdir aws
```

You'll also need your AWS access credentials for programmatic access to S3. Obtain your AWS Access Key ID and your AWS Secret Access Key. Create a file for each in the aws directory with `touch aws/AWS_ACCESS_KEY_ID` and `touch aws/AWS_SECRET_ACCESS_KEY`. Place your credentials within the respective files.

## Configure Google API Credentials
> Only needed for dashboard updates
To connect to the google sheets API, contact the admin of this repo to get the credentaials.

Create a file in the .config directory.
```
nano .config/logistics-db-1615935272839-a608db2dc31d
```
Paste the contents of what the admin sends in this file.

Then, press `CTRL+X` to exit.
Remember to save your work!
(Press `Y` then hit `Enter` to confirm the original save location.)
