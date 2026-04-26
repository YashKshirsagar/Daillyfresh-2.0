# AWS Free Deployment Plan for Daillyfresh

## Short Answer

If you want the most professional setup on AWS, the right answer is **not** a fully free AWS stack.

For this Django app, the best **free or near-free AWS approach** is:

- **1 EC2 Linux instance** for the Django app + PostgreSQL
- **Nginx** as reverse proxy
- **Gunicorn** for Django
- **Cloudinary** for media uploads
- **WhiteNoise** for static files
- **Route 53 or external DNS** for the domain
- **Let's Encrypt** for SSL

This is the cleanest option if you must stay on AWS and avoid monthly charges for separate managed services.

## Important Reality Check

AWS Free Tier in 2026 is mostly based on **credits and time-limited plans**, not a permanently free production platform.

- **EC2** can fit a very small deployment, but free usage depends on your account/free-plan status.
- **RDS** is not a good long-term "free" production answer for client delivery.
- **S3** is not permanently free either; it uses credits or paid usage.

So if you need **professional and free**, the realistic AWS answer is:

- keep the stack **simple**
- run **app + database on one EC2 box**
- keep **Cloudinary** for media

## Recommended Architecture for This Repo

This repository is already close to server deployment:

- production settings use `DATABASE_URL`
- Gunicorn is already in `requirements.txt`
- WhiteNoise is already configured for static files
- Cloudinary is already configured for media storage

Recommended target architecture:

```text
Internet
  |
  v
Domain + SSL
  |
  v
Nginx on EC2
  |
  v
Gunicorn -> Django (config.settings.production)
  |
  v
PostgreSQL on same EC2 instance

Media uploads -> Cloudinary
Static files -> WhiteNoise
```

## Why This Is Better Than Recreating Railway/Render on AWS

Your current pattern is split across multiple hosted services. On AWS, doing the same in a free way is usually worse because:

- managed database is not truly free long-term
- managed app hosting is not truly free long-term
- multiple services increase handoff complexity for the client

For a small Django ecommerce-style app, one EC2 instance is more practical for delivery.

## Settings Note for This Project

This project previously assumed a managed PostgreSQL service that requires SSL.

For EC2-hosted PostgreSQL on the same machine, set:

```env
DB_SSL_REQUIRE=false
```

The production settings now support this.

## Required Environment Variables

Set these in `/etc/daillyfresh/daillyfresh.env` or a systemd EnvironmentFile:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,ec2-public-ip-or-dns
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

DATABASE_URL=postgresql://dailyfresh_user:strongpassword@127.0.0.1:5432/dailyfresh
DB_SSL_REQUIRE=false

CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=...

RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...

SHIPROCKET_ENABLED=true
SHIPROCKET_EMAIL=...
SHIPROCKET_PASSWORD=...
SHIPROCKET_WEBHOOK_TOKEN=...
```

## EC2 Deployment Steps

Example target:

- Ubuntu 24.04 LTS
- small free-tier-eligible EC2 instance if available on your account
- one EBS volume

### 1. Create the server

- Launch Ubuntu EC2
- Attach a security group allowing `22`, `80`, and `443`
- Attach an Elastic IP only if you accept AWS public IPv4 charges; otherwise use the instance public DNS and update DNS carefully
- Point your domain to the instance

### 2. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib nginx certbot python3-certbot-nginx
```

### 3. Create PostgreSQL database

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

### 4. Deploy the code

```bash
sudo mkdir -p /srv/daillyfresh
sudo chown $USER:$USER /srv/daillyfresh
git clone <your-repo-url> /srv/daillyfresh
cd /srv/daillyfresh

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Create env file

```bash
sudo mkdir -p /etc/daillyfresh
sudo nano /etc/daillyfresh/daillyfresh.env
```

Paste the environment variables from the earlier section.

### 6. Run migrations and static collection

```bash
source /srv/daillyfresh/.venv/bin/activate
cd /srv/daillyfresh
export $(grep -v '^#' /etc/daillyfresh/daillyfresh.env | xargs)
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser
```

### 7. Create systemd service for Gunicorn

Create `/etc/systemd/system/daillyfresh.service`:

```ini
[Unit]
Description=Daillyfresh Django application
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/daillyfresh
EnvironmentFile=/etc/daillyfresh/daillyfresh.env
ExecStart=/srv/daillyfresh/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo chown -R www-data:www-data /srv/daillyfresh
sudo systemctl daemon-reload
sudo systemctl enable daillyfresh
sudo systemctl start daillyfresh
sudo systemctl status daillyfresh
```

### 8. Configure Nginx

Create `/etc/nginx/sites-available/daillyfresh`:

```nginx
server {
    server_name yourdomain.com www.yourdomain.com;

    location /static/ {
        alias /srv/daillyfresh/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/daillyfresh /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 9. Enable SSL

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Recommended Client Handoff Standard

If you are delivering this to a client, give them these items:

- AWS account ownership in the client's account, not yours
- EC2 instance login method documented
- domain/DNS ownership documented
- `/etc/daillyfresh/daillyfresh.env` variable list documented
- database backup command documented
- restore procedure documented
- admin URL and superuser handoff documented

## Backup Plan

Because this free architecture uses one VM, backups matter.

Minimum standard:

- nightly PostgreSQL dump with cron
- keep dumps in a protected location
- optionally copy dumps off-server

Example:

```bash
pg_dump -U dailyfresh_user -h 127.0.0.1 dailyfresh > /var/backups/daillyfresh/dailyfresh-$(date +%F).sql
```

## What I Would Recommend to a Client

### If the requirement is strictly free

Use:

- EC2 single instance
- local PostgreSQL
- Nginx + Gunicorn
- Cloudinary retained

This is the best balance of AWS branding, simplicity, and low cost.

### If the requirement is professional and durable

Use paid AWS services:

- EC2 or ECS for app
- RDS PostgreSQL for database
- S3 or CloudFront for assets if desired
- Route 53 for DNS
- CloudWatch for logs/alerts

That is the real long-term professional setup.

## Recommendation for This Project

For **this exact repo**, I recommend:

1. Keep **Cloudinary** for media.
2. Deploy Django to **one EC2 instance**.
3. Run **PostgreSQL on the same EC2 instance**.
4. Use **Nginx + Gunicorn + systemd**.
5. Set `DB_SSL_REQUIRE=false`.
6. Put the domain and AWS account in the client's ownership from day one.

If later the client starts getting traffic or needs reliability, migrate the database from local PostgreSQL to **RDS PostgreSQL** without changing the app code structure.