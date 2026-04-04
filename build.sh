set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/.devenv" ]] && [[ "${1:-}" != "dev" ]]; then
        echo "Error: .devenv detected; you must run this script with the 'dev' arg (e.g. 'bash build.sh dev -y')." >&2
        exit 1
fi
if [[ ! -f "${SCRIPT_DIR}/.devenv" ]] && [[ "${1:-}" == "dev" ]]; then
        echo "Error: no .devenv found; cannot run with 'dev' arg on a non-dev environment." >&2
        exit 1
fi

TAG=latest
APP_VERSION=$(git rev-parse --short HEAD)
DOCKER_COMPOSE_ARGS='-f docker/docker-compose.yml'
DB_CONTAINER='hestia-database'

if [[ $1 == dev ]]; then
        TAG=dev
        DOCKER_COMPOSE_ARGS='-f docker/docker-compose-dev.yml'
        APP_VERSION="$APP_VERSION-dev"
        DB_CONTAINER='hestia-database-dev'
fi

docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-bot:$TAG -f docker/Dockerfile.bot .
docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-scraper:$TAG -f docker/Dockerfile.scraper .
docker build --tag wtfloris/hestia-web:$TAG -f web/Dockerfile web/

if [[ $1 == -y ]] || [[ $2 == -y ]]; then
        docker compose $DOCKER_COMPOSE_ARGS up -d
        exit
fi

read -p "Run the containers? [y/N]" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
        docker compose $DOCKER_COMPOSE_ARGS up -d
fi
