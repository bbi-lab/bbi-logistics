#!/usr/bin/env python3

import re
from os import path, environ, listdir
from pathlib import Path
from datetime import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from smtplib import SMTP
import envdir

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(path.join(base_dir, '.env/email'))


def send_email():
    msg = MIMEMultipart()
    subject_date = datetime.now().strftime('%m/%d')
    msg['To'] = environ.get("DE_RECEIVERS")
    msg['From'] = environ.get("DE_SENDER")
    msg['Cc'] = environ.get("DE_CC")
    msg['Date'] = formatdate(localtime=True)
    filename = most_recent_order_today()
    if filename:
        with open(filename, "rb") as file:
            part = MIMEApplication(file.read(), Name=Path(filename).name)
            part[
                'Content-Disposition'] = f'attachment; filename="{Path(filename).name}"'
            msg.attach(part)

        msg['Subject'] = f'{subject_date} Successfully Generated Delivery Express Order File'
        msg.attach(
            MIMEText(
                f'''Hello BBI Logistics,<br><br>The Delivery Express Order file for
                {subject_date} was successfully generated and is attached to this email.<br><br>
                Best,<br>
                Cooper Marshall<br><br>
                <span style='font-style: italic;'>This email was sent automatically.</span>''',
                'html'))
    else:
        msg['Subject'] = f'{subject_date} Failed to Generate Delivery Express Order File'
        msg.attach(
            MIMEText(
                f'''Hello BBI Logistics,<br><br>The Delivery Express Order file
                for {subject_date} failed to generate. Please generate the file
                by running "python3 orders/delivery_express_order.py"
                from inside the "logistics" folder.<br><br>
                Best,<br>
                Cooper
                Marshall<br><br>
                <span style='font-style: italic;'>This email was sent automatically.</span>''',
                'html'))
    with SMTP(host='smtp.office365.com', port=587) as smtp:
        print(smtp.noop())
        smtp.starttls()
        smtp.login(environ.get("DE_SENDER"),
                   environ.get("DE_OUTLOOK_PASSWORD"))
        smtp.send_message(msg)


def most_recent_order_today():
    data_dir = path.join(base_dir, 'data')
    files = [
        f for f in listdir(path.join(data_dir))
        if path.isfile(path.join(data_dir, f))
        and re.match(r'DeliveryExpressOrder\d{4}_\d{2}_\d{2}_\d{2}_\d{2}.csv',
                     path.basename(f)) and datetime.
        strptime(path.basename(f), 'DeliveryExpressOrder%Y_%m_%d_%H_%M.csv'
                 ).date() == datetime.today().date()
    ]

    files.sort(key=lambda x: datetime.strptime(
        x, 'DeliveryExpressOrder%Y_%m_%d_%H_%M.csv'),
               reverse=True)

    return path.join(data_dir, files[0]) if files else None


if __name__ == "__main__":
    send_email()
