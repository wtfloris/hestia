set -e

TAG=latest
APP_VERSION=$(git rev-parse --short HEAD)
DOCKER_COMPOSE_ARGS='-f docker/docker-compose.yml'

if [[ $1 == dev ]]; then
        TAG=dev
        DOCKER_COMPOSE_ARGS='-f docker/docker-compose-dev.yml'
        APP_VERSION="$APP_VERSION-dev"
fi

docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-bot:$TAG -f docker/Dockerfile.bot .
docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-scraper:$TAG -f docker/Dockerfile.scraper .

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
