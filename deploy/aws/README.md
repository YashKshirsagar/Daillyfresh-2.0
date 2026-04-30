# AWS EC2 Deployment Steps

Use this folder when deploying Daillyfresh to a single Ubuntu EC2 instance.

## Step 1: Launch the EC2 server

- Create an Ubuntu 24.04 LTS EC2 instance.
- Allow inbound ports `22`, `80`, and `443` in the security group.
- Point your domain DNS to the server public IP or public DNS.

## Step 2: Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib nginx certbot python3-certbot-nginx
```

## Step 3: Create the database

```bash
sudo -u postgres psql
CREATE DATABASE dailyfresh;
CREATE USER dailyfresh_user WITH PASSWORD 'strongpassword';
ALTER ROLE dailyfresh_user SET client_encoding TO 'utf8';
ALTER ROLE dailyfresh_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE dailyfresh_user SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE dailyfresh TO dailyfresh_user;
\q
```

## Step 4: Clone the project and create a venv

```bash
sudo mkdir -p /srv/daillyfresh
sudo chown $USER:$USER /srv/daillyfresh
git clone <your-repository-url> /srv/daillyfresh
cd /srv/daillyfresh

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 5: Create the environment file

```bash
sudo mkdir -p /etc/daillyfresh
sudo cp deploy/aws/daillyfresh.env.example /etc/daillyfresh/daillyfresh.env
sudo nano /etc/daillyfresh/daillyfresh.env
```

Fill all real values before starting the service.

Important for single-server PostgreSQL:

```env
DB_SSL_REQUIRE=false
```

## Step 6: Run Django setup

```bash
source /srv/daillyfresh/.venv/bin/activate
cd /srv/daillyfresh
set -a
source /etc/daillyfresh/daillyfresh.env
set +a

python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser
```

## Step 7: Install the systemd service

```bash
sudo cp deploy/aws/daillyfresh.service /etc/systemd/system/daillyfresh.service
sudo chown -R www-data:www-data /srv/daillyfresh
sudo systemctl daemon-reload
sudo systemctl enable daillyfresh
sudo systemctl start daillyfresh
sudo systemctl status daillyfresh
```

If the service fails, check logs:

```bash
sudo journalctl -u daillyfresh -n 100 --no-pager
```

## Step 8: Install the Nginx site

```bash
sudo cp deploy/aws/nginx-daillyfresh.conf /etc/nginx/sites-available/daillyfresh
sudo nano /etc/nginx/sites-available/daillyfresh
sudo ln -s /etc/nginx/sites-available/daillyfresh /etc/nginx/sites-enabled/daillyfresh
sudo nginx -t
sudo systemctl reload nginx
```

Before saving, replace `yourdomain.com` with the real domain.

## Step 9: Enable HTTPS

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Step 10: Validate the deployment

Run these checks:

```bash
curl -I http://127.0.0.1:8000
curl -I https://yourdomain.com
sudo systemctl status daillyfresh
sudo systemctl status nginx
```

## Step 11: Client handoff

Give the client:

- AWS account ownership
- domain and DNS ownership
- `/etc/daillyfresh/daillyfresh.env` values list
- Django admin credentials
- backup and restore instructions

## Backup command

```bash
mkdir -p /var/backups/daillyfresh
PGPASSWORD='strongpassword' pg_dump -U dailyfresh_user -h 127.0.0.1 dailyfresh > /var/backups/daillyfresh/dailyfresh-$(date +%F).sql
```