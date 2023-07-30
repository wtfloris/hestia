set -e

docker build --tag wtfloris/hestia-bot:latest -f Dockerfile.bot .
docker build --tag wtfloris/hestia-scraper:latest -f Dockerfile.scraper .

ARGS=''

if [[ $1 -eq -y ]]; then
        if [[ $2 -eq dev ]]; then
                DEVARGS='-f docker-compose-dev.yml'
        fi
        docker compose $DEVARGS up -d
        exit
fi

read -p "Run the containers? [y/N]" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
        docker compose up -d
fi
