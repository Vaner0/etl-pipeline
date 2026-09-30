select
    date_trunc('month', observation_date)::date as month,
    sum(avg_temperature_2m * temperature_observation_count)
        / nullif(sum(temperature_observation_count), 0) as avg_temperature_2m,
    min(min_temperature_2m) as min_temperature_2m,
    max(max_temperature_2m) as max_temperature_2m,
    sum(avg_relative_humidity_2m * humidity_observation_count)
        / nullif(sum(humidity_observation_count), 0) as avg_relative_humidity_2m,
    sum(total_precipitation) as total_precipitation,
    sum(case when total_precipitation > 0 then 1 else 0 end) as rainy_days,
    sum(rainy_hours) as rainy_hours,
    sum(observation_count) as observation_count
from {{ ref('int_weather_cotonou_daily') }}
group by date_trunc('month', observation_date)::date
