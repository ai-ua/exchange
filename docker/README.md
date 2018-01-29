## Development Environment Setup

**Requirements:**
- Docker Compose 1.12.0+ (`docker-compose version`)
- Docker API 1.25+ (`docker version`)
- Git

**Note:** You will also need to append nginx to your 127.0.0.1 entry in `/etc/hosts`.

```bash
##
# Host Database
#
# localhost is used to configure the loopback interface
# when the system is booting.  Do not change this entry.
##
127.0.0.1       localhost nginx
255.255.255.255 broadcasthost
::1             localhost
```

The reason for this is due to osgeo_importer. It uses gsconfig which parses `workspace_style_url` from geoserver rest 
xml atom:link, which uses the entry from global.xml. Since each application is in separate containers, localhost will 
not work as that value. To bypass this the nginx service alias `nginx` is used. If added to your `/etc/hosts` it will 
resolve as localhost.


**Note:** You will have to set `vm.max_map_count` on your host for the elasticsearch container to not 
fail  ([elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html#docker-cli-run-prod-mode)).  
On MacOS you will need to ensure that the docker process is running and then do the following:

```bash
screen ~/Library/Containers/com.docker.docker/Data/com.docker.driver.amd64-linux/tty
# press any key to show prompt in tty session
sysctl -w vm.max_map_count=262144
# in the terminal press Ctrl-a + k <-- this will kill the window
# select y to the prompt "Really kill this window [y/n]"
```

for Linux do the following:

```bash
sudo sysctl -w vm.max_map_count=262144
```
 
#### Clone Repo
There are three submodules in the vendor directory
- geonode
- maploom
- sphinx-theme (used for documentation)

Run the following command to clone all repositories

```bash
git clone --recursive -j8 git://github.com/boundlessgeo/exchange.git
cd exchange
```

#### Update submodules
To ensure the latest version/commits are being used in all the submodules, run: 

```bash
cd exchange
git submodule update --init --remote --recursive
```

when working off a different branch on one of the submodule, you may have to specify the specific branch to follow.  
This can be done by specifying the branch name using the ```branch``` variable in ```.gitmodules```.  
The branch the goenode submodule follows changes over time, but is currently set to ```exchange/1.4.x```. 

#### Initial Docker Setup
This will run all the docker containers and display log output in the terminal

```bash
docker-compose up
```

Note: To run in detached mode append a `-d` to the above. This will not display the log output in the terminal.
If you want access to the logs for a specific container then you will need to run the following command:
```bash
docker-compose logs -f exchange
```

**IMPORTANT:** If you you run the following:
```bash
docker-compose down
docker-compose restart
```
All data will persist due to the named volumes. If you are wanting to start from a clean slate. You will need 
to do the following:
```bash
docker-compose down
docker volume prune # add `-f` to bypass the prompt
docker-compose up
```
To display the volumes run the following:
```bash
docker volume ls
```
Example output:
```bash
DRIVER              VOLUME NAME
local               0ce98919212c546e67e4c48e09bb595612143a5a8d386c55f17ed0287e8c2e0c # random volume created for nginx
local               exchange_db_data
local               exchange_django_media
local               exchange_geoserver_data
local               exchange_queue_data
local               exchange_search_data
```

Additional Online References:
- [docker-compose up](https://docs.docker.com/compose/reference/up/)
- [docker-compose build](https://docs.docker.com/compose/reference/build/)
- [docker-compose down](https://docs.docker.com/compose/reference/down/)
- [docker-compose ps](https://docs.docker.com/compose/reference/ps/)
- [docker-compose exec](https://docs.docker.com/compose/reference/exec/)
- [docker volume](https://docs.docker.com/engine/reference/commandline/volume/)

#### Development Attached Volume
There are two volumes used in the development setup

1. $PWD:/code:ro

The first one mounts the exchange directory including submodules in the `/code` directory for the `exchange`
container. `:rw` is required in order to run tests and coverage.

#### Settings
Docker reads from two areas for settings in this environment.

1. .env
2. docker-compose:environment:

The first one id where you may need to make adjustments. The second should not require any changes. The only
containers that utilize the `.env` file are exchange and registry.

**Note:** In the `.env` file you will see a `DEV=True` entry. Placing a `DEV=False` will run django using 
waitress and setting `DEBUG = False`.

#### Running Tests and Coverage
```bash
docker-compose exec exchange /bin/bash -c /code/docker/exchange/run_tests.sh
```
Output will be in 2 files:

1. `docker/data/pytest-results.xml` - pytest results
2. `docker/data/coverage.xml` - coverage results

To run pycodestyle and yamllint run the following command:

```bash
docker run -v $PWD:/code \
           -w /code quay.io/boundlessgeo/sonar-maven-py3-alpine bash \
           -e -c '. docker/devops/helper.sh && lint'
```

**Note:** `$PWD` is `exchange` root directory

#### Questions
If you have any questions feel free to reach out in the following `Boundless` slack channels:

- `#exchange-dev` Exchange Development Team
- `#qa-deployment` Exhange QA/Deployment (CI)

#### Makefile
Easy commands to get started

```bash
Boundless:exchange bex$ make
  make lint     - run to lint (style check) repo
  make html     - build sphinx documentation
  make start    - start containers
  make stop     - stop containers
  make purge    - stop containers and prune volumes
  make recreate - stop containers, prune volumes and recreate/build containers
  make test     - run unit tests
```