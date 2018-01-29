#!/bin/bash

# Code style checks
function lint {
    echo "-------> exchange pycodestyle"
    pycodestyle exchange --ignore=E722,E731
    echo "-------> exchange flake8"
    flake8 --ignore=F405,E722,E731 exchange
    echo "-------> exchange yamllint"
    yamllint -d "{extends: relaxed, rules: {line-length: {max: 120}}}" $(find . -name "*.yml" -not -path "./vendor/*")
}

# Jenkins specific function for builds on master branch, requires sonar auth token
function sonar-scan {
    exchange_ver=`grep "__version__ =" exchange/__init__.py | sed "s/__version__ = '\(.*\)'/\1/"`
    echo $exchange_ver
    sonar-scanner -Dsonar.host.url=$SONAR_HOST_URL \
              -Dsonar.login=$SONAR_TOKEN \
              -Dsonar.projectKey=com.boundlessgeo.exchange \
              -Dsonar.sources=exchange \
              -Dsonar.projectVersion=$exchange_ver \
              -Dsonar.projectName=exchange \
              -Dsonar.language=py \
              -Dsonar.python.pylint=/usr/bin/pylint
    sonar-scanner -Dsonar.host.url=$SONAR_HOST_URL \
              -Dsonar.login=$SONAR_TOKEN \
              -Dsonar.projectKey=com.boundlessgeo.geonode \
              -Dsonar.sources=vendor/geonode/geonode \
              -Dsonar.projectVersion=2.6.1 \
              -Dsonar.projectName=geonode \
              -Dsonar.language=py \
              -Dsonar.python.pylint=/usr/bin/pylint
}

# Jenkins function for exchange healthcheck
function exchange-healthcheck {
    for i in $(seq 1 20);
        do echo $(docker inspect --format '{{ .State.Health.Status }}' exchange) | grep -w healthy && s=0 && break || \
           s=$? && echo "exchange is not ready, trying again in 30 seconds" && sleep 30;
    done; docker-compose logs && (exit $s)
}

# function to build maploom from src
function build-maploom {
    pushd vendor/maploom
    npm install
    bower install --allow-root
    grunt
    PACKAGE_VERSION=$(cat package.json \
    | grep version \
    | head -1 \
    | awk -F: '{ print $2 }' \
    | sed 's/[",]//g')
    VERSION=${PACKAGE_VERSION// /}
    echo "{% load i18n static %}
    <link rel=\"stylesheet\" type=\"text/css\" href=\"{% static 'maploom/assets/MapLoom-$VERSION.css' %}\"/>
    <script type=\"text/javascript\" src=\"{% static 'maploom/assets/MapLoom-$VERSION.js' %}\"/>" > bin/_maploom_js.html
    sed -n '/body class="maploom-body">/,/body>/p' bin/index.html > bin/index_body.html
    sed '/body>/d' bin/index_body.html > bin/index_body_no_tag.html
    echo '{% load staticfiles i18n %}{% verbatim %}' > bin/_maploom_map.html
    cat bin/index_body_no_tag.html >> bin/_maploom_map.html
    echo '{% endverbatim %}' >> bin/_maploom_map.html
    if [[ -f /code/exchange/maploom/templates/maploom/_maploom_js.html ]]; then
      rm /code/exchange/maploom/templates/maploom/_maploom_js.html
    fi
    cp bin/_maploom_js.html /code/exchange/maploom/templates/maploom/_maploom_js.html
    if [[ -f /code/exchange/maploom/templates/maploom/_maploom_map.html ]]; then
      rm /code/exchange/maploom/templates/maploom/_maploom_map.html
    fi
    cp bin/_maploom_map.html /code/exchange/maploom/templates/maploom/_maploom_map.html
    if [[ -f /code/exchange/maploom/templates/maps/maploom.html ]]; then
      rm /code/exchange/maploom/templates/maps/maploom.html
    fi
    cp bin/maploom.html /code/exchange/maploom/templates/maps/maploom.html
    if [[ -d /code/exchange/maploom/static/maploom ]]; then
      rm -r /code/exchange/maploom/static/maploom
    fi
    mkdir /code/exchange/maploom/static/maploom
    cp -r bin/assets /code/exchange/maploom/static/maploom/assets
    cp -r bin/fonts /code/exchange/maploom/static/maploom/fonts
    rm -f package-lock.json
    popd
}
