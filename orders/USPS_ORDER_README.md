# USPS order
> `orders/usps_cascadia_order.py`

The United States Postal Service (USPS) ships outbound welcome kits, replenishment kits, and serial swab packs for the Cascadia study. This project contains a household in a single record with multiple participants as different events in each record. The script iteraetes through 

### Welcome Pack
The script will send welcome packs to each member of the household if the whole household is enrolled and `swab_survey` is not completed. Welcome packs consist of 5 swab kits and some swag. The quantity is measured by  pack not by each indevidual kit.

A maximum of 3 welcome packs can fit in one box so the overflow must be placed in an additional order.

### Replenishment Kits
The script will replenish all participants in a household so that they have 6 swab kits in their posession if a household member's kit inventory drops below 3.

This is calculated by counting all the assigned barcodes to each participant and subtracting all the number of DE retrun tracking numbers for their kit returns
> total assigned barcodes - DE return orders = current kit inventory

A maximum of 20 replenishment can fit in one box so the overflow must be placed in an additional order.

### Serial Swab Pack
When a participant tests postive, they are triggred to start the serial swab seriese. This involves taking multiple swabs over 2 weeks. This pack contains 7 swab kits.