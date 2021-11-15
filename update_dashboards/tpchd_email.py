import os
import envdir
from pathlib import Path
from datetime import datetime, timedelta

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from smtplib import SMTP

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(base_dir / f'.env/email')

def send_email():
	sender = os.environ.get("OUTLOOK_USERNAME")
	receivers = os.environ.get("TPCHD_RECEIVERS")
	cc = os.environ.get("BBI_CC")
	password = os.environ.get("OUTLOOK_PASSWORD")

	msg = MIMEMultipart()
	subject_date = datetime.now().strftime('%m/%d')
	msg['Subject'] = f'SCAN | TPCHD {subject_date}'
	msg['To'] = receivers
	msg['From'] = sender
	msg['Cc'] = cc
	msg['Date'] = formatdate(localtime=True)
	msg.attach(MIMEText('''Hello TPCHD,<br><br>The 
		<a href="https://public.tableau.com/app/profile/cooper.marshall/viz/SCANTPCHDMetricsDashbaord/TPCHDSCANMetricsDashboard">
			Dashbaord
		</a>
		 has been updated and the raw data is attached to this email.<br><br>
		Best,<br>
		Cooper Marshall<br><br>
		<span style='font-style: italic;'>This email was sent automatically.</span>''','html'))
	today = datetime.now().strftime('%Y_%m_%d')
	filename = base_dir / f'data/SCAN_TPCHD_{today}.xlsx'
	with open(filename, "rb") as file:
		part = MIMEApplication(
			file.read(),
			Name=Path(filename).name
		)
		part['Content-Disposition'] = f'attachment; filename="{Path(filename).name}"'
		msg.attach(part)

	with SMTP(host='smtp.office365.com', port=587) as smtp:
		print(smtp.noop())
		smtp.starttls()
		smtp.login(sender, password)
		smtp.send_message(msg)

if __name__ == "__main__":
    send_email()