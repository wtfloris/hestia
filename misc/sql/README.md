# SQL Secrets With `sops` (Rocky Linux)

This directory supports two file types:

- `*.sql.enc` (preferred): encrypted with `sops`
- `*.sql` (plaintext, transition only)

`build.sh` behavior:

- Applies all files in `misc/sql` in sorted order
- If both `foo.sql` and `foo.sql.enc` exist, it applies only `foo.sql.enc`
- Decrypts `*.sql.enc` with `sops` before running `psql`

## 1. Install tools on prod (Rocky Linux)

```bash
sudo dnf install -y age
SOPS_VERSION="3.9.4"
curl -fsSL -o /tmp/sops.rpm "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-${SOPS_VERSION}-1.x86_64.rpm"
sudo dnf install -y /tmp/sops.rpm
sops --version
age --version
```

## 2. Create an AGE key on prod

```bash
sudo mkdir -p /root/.config/sops/age
sudo age-keygen -o /root/.config/sops/age/keys.txt
sudo chmod 600 /root/.config/sops/age/keys.txt
sudo grep '^# public key:' /root/.config/sops/age/keys.txt
```

Copy the printed public key (`age1...`) for encryption.

## 3. Encrypt SQL files

From a machine with the repo checked out and `sops` installed:

```bash
export SOPS_AGE_RECIPIENTS='age1REPLACE_WITH_PROD_PUBLIC_KEY'
sops --encrypt --age "$SOPS_AGE_RECIPIENTS" misc/sql/20260214_add_hoekstra_target.sql > misc/sql/20260214_add_hoekstra_target.sql.enc
```

Then remove plaintext from git:

```bash
git rm misc/sql/20260214_add_hoekstra_target.sql
git add misc/sql/20260214_add_hoekstra_target.sql.enc
```

## 3a. Enable automatic protection in git hooks

```bash
bash scripts/setup-git-hooks.sh
```

Hook behavior:

- `pre-commit`: auto-encrypts staged `misc/sql/*.sql` into `*.sql.enc` when `SOPS_AGE_RECIPIENTS` is set
- `pre-push`: blocks pushing if any plaintext `misc/sql/*.sql` is tracked
- CI also fails if plaintext `misc/sql/*.sql` is tracked

## 4. Ensure decryption works on prod

On prod, before running `build.sh`, ensure:

```bash
export SOPS_AGE_KEY_FILE=/root/.config/sops/age/keys.txt
sops --decrypt misc/sql/20260214_add_hoekstra_target.sql.enc >/dev/null
```

## 5. Run build

```bash
export SOPS_AGE_KEY_FILE=/root/.config/sops/age/keys.txt
bash build.sh -y
```

or for dev:

```bash
export SOPS_AGE_KEY_FILE=/root/.config/sops/age/keys.txt
bash build.sh dev -y
```
