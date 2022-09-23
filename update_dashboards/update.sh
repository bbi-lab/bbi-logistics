#! /bin/bash
pipenv run python3 /home/ec2-user/logistics/update_dashboards/courier.py
echo "Courier Data Extract Successful"
pipenv run python3 /home/ec2-user/logistics/update_dashboards/kits_shipped.py
echo "Kits Shipped Data Extract Successful"
pipenv run python3 /home/ec2-user/logistics/update_dashboards/pc.py
echo "Participant-Comm Data Extract Sucessful"
pipenv run python3 /home/ec2-user/logistics/update_dashboards/tpchd.py
echo "TPCHD Data Extract Successful"