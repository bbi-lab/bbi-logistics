# Dashboard README
This readme describes the environment, data storage, and access for the BBI Tableau Dashboards.

## Tableau Server
All except the Vaccine Effectiveness dashboard are hosted on BBI's Tableau Server Instance. The server can be accessed at https://tableau.brotmanbaty.org/. The server is running on a private AWS EC2 instance with a Bastion Host for ssh access. This architecture was used to maintain HIPAA compliance.

A list of users and their groups can be found [here](https://uwnetid.sharepoint.com/:x:/r/sites/seattle_flu_study/analytics/_layouts/15/Doc.aspx?sourcedoc=%7B33f7869a-8a7f-45db-bda3-d8d2c644f34f%7D&action=editnew&cid=ba57fee9-e6c8-41e1-95e0-8ad93e3e9f8e). You can also login to the tableau server admin account to see the Users and Groups. Groups are used to partition which accounts have viewing rights to certain dashboards.



#### Tableau External Dashboard Failure to Auto-Update Troubleshooting Checklist:
1. **On Tableau online in a project folder:**
    * look to refresh a dashboard data extract source in a drop down menu.
2. **Check either Notifications icon or Jobs icon to see if refresh was successful:**
    * Check relevant googlesheet if recent changes are updating (new dates added, etc.).
    * If failure to update arises, Jobs page will provide more detailed error message to why a job failed. 
3. **Explore the Data for points of error, places to look/questions to ask**
   * Try manually publishing the new data extract from tableau desktop.
   * Are there any map/shape files used in the dashboard that need to be published on Tableau seperately?
   * What does the schedule look like for past updates on this dashboard in the Jobs tab?
   * Are you using a version of Tableau Desktop that is different to the one used on the server?
   * Are there many entires/tables that a dashboard is dependent on? (Limitation of Google   sheets only allows for 200,000 update operations a second)
   * Look at project related python script in ['update_dashboards/'](https://github.com/cooperqmarshall/bbi-logistics/tree/master/update_dashboards). 
4. All else fails reach out to dev team for 2nd opinion. 





## Google Sheets

The external dashboards use Google Sheets for their data source. These sheets are owned by the `kittrack.bbi` google account. This was done because the external dashboards were previously hosted on Tableau Public to provide viewing rights to anyone with the link to the dashboard. Tableau Public would only allow automatic refreshings for the dashboards with Google Sheets as their data source.

The external dashboards have since been migrated to BBI's Tableau Server for security. Although using google sheets as the data source is not necessary now, this artifact remains.
 > TODO: Transfer data source from google sheets to Postgres database connection for all dashboards possible.

Using google sheets in this manner required a set of ETL python scripts to be developed to keep the sheets updated. These scripts are in [`update_dashboards/`](update_dashboards/).

#### Relevant libraries/technologies used (documentation links attached): 
* [Google Service Accounts](https://cloud.google.com/iam/docs/understanding-service-accounts#:~:text=A%20service%20account%20is%20a,on%20virtual%20machines%20(VMs).) (GSA) - google cloud accounts with user permissions that interact/update google sheets.  
* Python [gspread](https://docs.gspread.org/en/latest/user-guide.html) library - to interact with google sheets via GSA accounts (append rows, delete tables, etc).
* Linux [cronjobs/crontabs](https://www.ibm.com/docs/en/aix/7.2?topic=c-crontab-command) - a linux library that allows shell commands to be run at regular intervals such as updating a google sheet.   

*Future Dev Note:* The infrastructure set up to interact google sheets may be useful in setting up future dashboard/order-report projects that involve interacting with external delivery data from Delivery Express or USPS vendors (TBD).

## BBI Analytics Website
> depts.washington.edu/kittrack

When the tableau.brotmanbaty.org site was used as the main point of interaction, there was often confusion in locating the dashboards because the URLs would change when updating the name of the workbook or dashboard tabs. Because of this, a simple static website was developed that embedded the dashboards in their own web pages. This allowed the dashboards to be updated and the URLs to remain the same. The dashboards still require a login to access.

This version control for this website is hosted at github.com/cooperqmarshall/kittrack. The website itself is associated with the kittrack@uw.edu account as part of the ovid server cluster. You can read more about it [here](https://itconnect.uw.edu/connect/web-publishing/shared-hosting/web-development-environments/ovid-u-washington-edu/).
> to connect use `ssh kittrack@ovid.u.washington.edu`

dashboard|permissions|data source|query|host|update method|schedule|notes
-|-|-|-|-|-|-|-
Internal SCAN Stakeholder Dashboard|BBI|ID3C|[681](https://backoffice.seattleflu.org/metabase/question/681-scan-internal-dashboard-query)|Tableau Server|Data Extract|Daily|The first dashboard built!
External SCAN Stakeholder Dashboard|BBI, GV|Google sheets|[753](https://backoffice.seattleflu.org/metabase/question/753-scan-stakeholder-query)|Tableau Server|[`update_dashboards/stakeholder.py`](stakeholder.py)|Daily|
Internal Residuals Dashbaord|BBI|ID3C|[880](https://backoffice.seattleflu.org/metabase/question/880-new-retrospective-samples-query)|Tableau Server|Data Extract|
External Residuals Dashboard|BBI, GV|Google Sheets|[904](https://backoffice.seattleflu.org/metabase/question/904-external-residuals-query)|Tableau Server|[`update_dashboards/residual.py`](residual.py)|Daily|
Logistics Dashboard|BBI|Google Sheets, REDCap, Delivery Express||Tableau Server|[`update_dashboards/courier.py`](courier.py) [`update_dashboards/kits_shipped.py`](kits_shipped.py) [`update_dashboards/pc.py`](pc.py)|Daily|Most data sources!
Vaccine Effectiveness Dashboard|BBI, Public|Google Sheets|[869](https://backoffice.seattleflu.org/metabase/question/869-ve-dashboard-query)|Tableau Public|[`update_dashboards/ve.R`](ve.R)|On demand|Most complex data processing!
TPCHD SCAN Dashboard|BBI TPCHD|Google Sheets||Tableau Server|[`update_dashboards/tpchd.py`](tpchd.py)|Weekly|
Open Array Dashboard|BBI|ID3C|[898](https://backoffice.seattleflu.org/metabase/question/898-oa-dashboard-query-collected-accessioned)|Tableau Server|Data Extract|Daily|

### Notes:
- ID3C (Infectious Disease Data Distribution Center) is the database used by BBI to store data gathered from various COVID-19 research studies.
- The Google Sheet data sources get their data from ID3C, but the dashboards connect directly to google sheets and not ID3C.
- Data Extract refers to: If the dashboard uses a direct connection to ID3C, tableau can manage the updates on its own.



