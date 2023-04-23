set -e

docker build --tag wtfloris/hestia-bot:latest -f Dockerfile.bot .
docker build --tag wtfloris/hestia-scraper:latest -f Dockerfile.scraper .

read -p "Run the containers? [y/N]" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
        docker compose up -d
fi
