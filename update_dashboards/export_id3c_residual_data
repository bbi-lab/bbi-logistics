#!/usr/bin/env bash

cd "$(dirname "$0")/.."

PGSERVICE=seattleflu-production psql -c "\copy (
with query as (select distinct on (sample.sample_id)
    sample.sample_id,
    case
        when sample.collected is null then (sample.created at time zone 'PDT')
        else sample.collected::date
    end as date_received,
    sample.details ->> 'sample_origin' as origin,
    PA.device,
    PA.present
from warehouse.sample
    left join (
        select pa.sample_id, pa.target_id,
            pa.details ->> 'device' as device,
            case
                when present then 'positive'
                when not present then 'negative'
                when present is null then 'inconclusive'
            end as present
        from warehouse.presence_absence pa
        where target_id in (select T.target_id
                from warehouse.target T
                left join warehouse.organism O using (organism_id)
                where O.lineage = 'Human_coronavirus.2019') 
        and pa.details ->> 'device' = 'OpenArray') PA using (sample_id)
where sample.details ->> 'sample_origin' in ('phskc_retro', 'sch_retro', 'hmc_retro', 'nwh_retro', 'uwmc_retro')
order by sample_id desc)

select * from query where
date_received between '2018-01-01 00:00:00'::timestamp and CURRENT_DATE
)
to ./data/id3c_scan_residual_data.csv csv header;"
