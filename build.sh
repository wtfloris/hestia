set -e

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

run_sql_files() {
        if ! find misc/sql -maxdepth 1 -type f \( -name '*.sql' -o -name '*.sql.enc' \) | grep -q .; then
                echo "No SQL files found in misc/sql (expected .sql or .sql.enc)"
                return
        fi

        echo "Waiting for database container (${DB_CONTAINER})..."
        for _ in $(seq 1 30); do
                if docker exec "$DB_CONTAINER" pg_isready -q -d hestia -U claude; then
                        break
                fi
                sleep 1
        done
        docker exec "$DB_CONTAINER" pg_isready -q -d hestia -U claude

        echo "Applying SQL files from misc/sql"
        for sql_file in $(find misc/sql -maxdepth 1 -type f \( -name '*.sql' -o -name '*.sql.enc' \) | sort); do
                # If both exist, prefer encrypted file and skip plaintext twin.
                if [[ "$sql_file" == *.sql ]] && [[ -f "${sql_file}.enc" ]]; then
                        continue
                fi

                sql_name=$(basename "$sql_file")
                tmp_path="/tmp/${sql_name}"
                echo "  -> ${sql_name}"
                if [[ "$sql_file" == *.enc ]]; then
                        if ! command -v sops >/dev/null 2>&1; then
                                echo "sops is required to decrypt ${sql_name} but is not installed."
                                exit 1
                        fi
                        decrypted_file=$(mktemp)
                        sops --decrypt "$sql_file" > "$decrypted_file"
                        docker cp "$decrypted_file" "${DB_CONTAINER}:${tmp_path}.sql"
                        docker exec "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 hestia claude -f "${tmp_path}.sql"
                        rm -f "$decrypted_file"
                else
                        echo "     (warning) applying plaintext SQL; prefer .sql.enc for secrets"
                        docker cp "$sql_file" "${DB_CONTAINER}:${tmp_path}"
                        docker exec "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 hestia claude -f "$tmp_path"
                fi
        done
}

docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-bot:$TAG -f docker/Dockerfile.bot .
docker build --build-arg=APP_VERSION="$APP_VERSION" --tag wtfloris/hestia-scraper:$TAG -f docker/Dockerfile.scraper .

if [[ $1 == -y ]] || [[ $2 == -y ]]; then
        docker compose $DOCKER_COMPOSE_ARGS up -d
        run_sql_files
        exit
fi

read -p "Run the containers? [y/N]" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
        docker compose $DOCKER_COMPOSE_ARGS up -d
        run_sql_files
fi
