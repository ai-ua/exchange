#!/bin/bash

set -e

find /code -type f -name '*pyc' -exec rm {} +
manage='python /code/manage.py'
setup='python /code/setup.py'
maploom_static='/code/exchange/maploom/static/maploom'
maploom_templates='/code/exchange/maploom/templates'
# let the db intialize
if [[ $MAPLOOM_DEV == True ]]; then
  rm -r $maploom_static
  ln -s /code/vendor/maploom/build $maploom_static
  if [[ -f $maploom_templates/maps/maploom.html ]]; then
    rm $maploom_templates/maps/maploom.html
  fi
  ln -s /code/vendor/maploom/build/maploom.html $maploom_templates/maps/maploom.html
fi
sleep 15
$setup build_sphinx
# app integration
plugins=()
# anywhere integration
if [[ -f /code/vendor/exchange-mobile-extension/setup.py ]]; then
   pip install /code/vendor/exchange-mobile-extension
   plugins=("${plugins[@]}" "geonode_anywhere")
fi
# worm integration
if [[ -f /code/vendor/services/setup.py ]]; then
  pip install /code/vendor/services
  plugins=("${plugins[@]}" "worm")
fi
if [ "$plugins" ]; then
  ADDITIONAL_APPS=$(IFS=,; echo "${plugins[*]}")
fi
until $manage migrate account --noinput; do
  >&2 echo "db is unavailable - sleeping"
  sleep 5
done
$manage migrate --noinput
$manage collectstatic --noinput
$manage loaddata default_users
$manage loaddata base_resources
# anywhere fixture
$manage loaddata /code/docker/exchange/docker_oauth_apps.json
if [[ -f /code/vendor/exchange-mobile-extension/setup.py ]]; then
  $manage loaddata /code/docker/exchange/anywhere.json
fi
$manage rebuild_index
if [[ $DEV == True ]]; then
  $manage importservice http://data-test.boundlessgeo.io/geoserver/wms bcs-hosted-data WMS I
fi
$manage makemigrations --dry-run --verbosity 3
pip freeze
echo "Dev is set to $DEV"
supervisord -c /code/docker/exchange/supervisor.conf
