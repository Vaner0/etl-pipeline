select
    observed_at_local::date as observation_date,
    avg(temperature_2m) as avg_temperature_2m,
    min(temperature_2m) as min_temperature_2m,
    max(temperature_2m) as max_temperature_2m,
    count(temperature_2m) as temperature_observation_count,
    avg(relative_humidity_2m) as avg_relative_humidity_2m,
    count(relative_humidity_2m) as humidity_observation_count,
    sum(precipitation) as total_precipitation,
    count(*) filter (where precipitation > 0) as rainy_hours,
    max(wind_speed_10m) as max_wind_speed_10m,
    count(*) as observation_count
from {{ ref('stg_weather_cotonou') }}
group by observed_at_local::date
