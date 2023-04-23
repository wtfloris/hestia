set -e

VERSION=1.0.0
docker build --tag wtfloris/hestia:latest .
docker tag wtfloris/hestia:latest wtfloris/hestia:$VERSION
docker push wtfloris/hestia:latest
docker push wtfloris/hestia:$VERSION
