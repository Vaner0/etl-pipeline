select observation_date, total_precipitation
from {{ ref('int_weather_cotonou_daily') }}
where total_precipitation < 0
