select
    observed_at,
    observed_at at time zone 'Africa/Porto-Novo' as observed_at_local,
    temperature_2m,
    relative_humidity_2m,
    precipitation,
    rain,
    weather_code,
    wind_speed_10m,
    loaded_at
from {{ source('weather', 'staging_weather_cotonou') }}
