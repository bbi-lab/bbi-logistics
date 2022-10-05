# USPS Ordering Script

The United States Postal Service (USPS) ships outbound welcome kits, replenishment kits, and serial swab packs for the Cascadia study. This script queries two Cascadia REDCap reports (one for welcome and replenishment kits, the other for serial packs) and constructs an order form in CSV format that can be provided to USPS and used for delivery of kits.

### Kit Descriptions
##### Welcome Pack

The script will send welcome packs to each member of the household once the whole household is enrolled and consented to the study. Welcome packs consist of 5 swab kits and some swag. The quantity is measured by  pack not by each individual kit.

A maximum of 3 welcome packs can fit in one box so the overflow must be placed in an additional order.

##### Replenishment Kits
The script will replenish all participants in a household so that they have 6 swab kits in their posession if a household member's kit inventory drops below 3.

This is calculated by counting all the assigned barcodes to each participant and subtracting all the number of DE retrun tracking numbers for their kit returns
> total assigned barcodes - DE return orders = current kit inventory

A maximum of 20 replenishment kits can fit in one box so the overflow must be placed in an additional order.

##### Serial Swab Pack
When a participant tests postive, they are triggred to start the serial swab series. This involves taking multiple swabs over 2 weeks. This pack contains 7 swab kits.

### Environment Setup

This script depends on [Pycap](https://github.com/redcap-tools/PyCap/releases/tag/1.1.3) (v1.1.3) for a wrapper to the REDCap API. You'll also need a local installation of [Pipenv](https://pipenv.pypa.io/en/latest/) and Python3 installed.

You'll also need an API key for the Cascadia study. This can be requested through the REDCap web application once you have access to the projects. If you are uploading data to S3, you will also need credentials from an account with access to the BBI logistics S3 bucket. The REDCap credentials are expected to be in a folder `.env/redcap` at the top level of this directory.

### Running the Script

Create a virtual environment within the top level bbi-logistics directory with the command `pipenv install`. You can then run the command `envdir <path to aws credentials> pipenv run python3 orders/usps_cascadia_order.py` to run the script.

You can pass the flag `--save` to the script to save the order form CSV to the `data/` directory at this repositories top level. Alternatively or in addition, you can pass the `--s3-upload` flag to upload the order form to the appropriate location within the logistics S3 bucket. By default, all order forms will be saved in the format `USPSOrder_YYYY_MM_DD_HH_mm.csv`.

Logging is set to log INFO level log events by default. Set the environment variable `LOG_LEVEL` to one of `DEBUG, WARNING, ERROR` to change this behavior.

### Deploying

To deploy a new version of this script, ssh onto the AWS EC2 instance used to host the BBI Tableau Server. Navigate to the logistics directory and run `git pull` followed by `pipenv sync` to ensure all dependencies are up to date.

This script runs automatically through cron and is set to run at 6:41AM daily. Use `crontab -e` to edit the crontab controlling this behavior.

### Script Specific Notes
- Where possible, the head of household's address is used for kit orders
- If a participant is under study pause, they won't have kits sent to them
- Resupplies are by household so as not to schedule too many excess deliveries
