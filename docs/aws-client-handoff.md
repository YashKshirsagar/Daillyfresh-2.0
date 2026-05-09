# AWS Client Handoff Guide for Daillyfresh

This document lists the changes to make before handing this project to the client after the AWS EC2 deployment is working.

## Goal

At handoff time, the client should own:

- the AWS account or at least the EC2 infrastructure
- the domain and DNS records
- the production secrets and third-party credentials
- the admin access and recovery path
- the backup and restore process

You should avoid keeping any production dependency tied to your own personal accounts.

## Minimum Handoff Standard

Before delivery, move these under the client's control:

- AWS EC2 instance
- domain registrar or DNS provider
- Cloudinary account
- Razorpay account
- Shiprocket account
- SMTP email account used for production mail
- Git repository access for future updates

If a service cannot be moved immediately, document it clearly and schedule a follow-up migration date.

## Service-by-Service Changes

## 1. AWS

Preferred setup:

- deploy in the client's AWS account from day one

If you deployed in your own AWS account first, before final handoff do all of this:

- create a new EC2 instance in the client's AWS account
- recreate the security group rules in the client's account
- copy the app, env file, and database backup to the client's server
- update DNS to point to the client's server
- test the site on the client's server
- terminate your own production server after cutover

Client should receive:

- AWS console access
- EC2 instance details
- key pair or approved access method
- server public IP
- security group details

## 2. Domain and DNS

The domain should be owned by the client, not by you.

### Exact change from EC2 IP testing to real client domain

During testing, you may have used the EC2 public IP in both Nginx and Django settings.

Typical temporary testing values:

```env
ALLOWED_HOSTS=12.34.56.78
CSRF_TRUSTED_ORIGINS=
```

Typical temporary Nginx value:

```nginx
server_name 12.34.56.78;
```

When the client buys the real domain, replace those with the final production values.

Example final values:

```env
ALLOWED_HOSTS=example.com,www.example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
```

Example final Nginx value:

```nginx
server_name example.com www.example.com;
```

If you want a safer transition window, keep both domain and IP briefly:

```env
ALLOWED_HOSTS=example.com,www.example.com,12.34.56.78
```

After the domain is confirmed working, remove the raw IP from `ALLOWED_HOSTS`.

Before handoff:

- point the domain `A` record to the EC2 public IP
- add `www` record if needed
- verify the domain opens the site
- issue SSL after DNS is correct

Update these values in `/etc/daillyfresh/daillyfresh.env`:

```env
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

Update Nginx:

- change `server_name` in `/etc/nginx/sites-available/daillyfresh`

Then reload services:

```bash
sudo systemctl restart daillyfresh
sudo nginx -t
sudo systemctl reload nginx
```

Recommended DNS records:

- root domain `A` record -> EC2 public IP
- `www` `CNAME` -> root domain, or another `A` record to the same IP

Validation commands after DNS update:

```bash
dig +short yourdomain.com
dig +short www.yourdomain.com
curl -I http://yourdomain.com
```

## 3. SSL Certificate

Once the real domain points to the EC2 server, issue the certificate:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

After SSL is issued:

- test `https://yourdomain.com`
- test `https://www.yourdomain.com` if used
- make sure webhook URLs use `https`

Important:

- do not run Certbot until DNS is already pointing to the EC2 server
- Let's Encrypt will not issue a normal certificate for the raw EC2 public IP
- after SSL is enabled, update any third-party callback or webhook URLs that still use the IP

## 4. Cloudinary

This project uses Cloudinary for media in production.

The client should have their own Cloudinary account.

Update these env values:

```env
CLOUDINARY_CLOUD_NAME=client-value
CLOUDINARY_API_KEY=client-value
CLOUDINARY_API_SECRET=client-value
```

If your current Cloudinary account already stores production media, do one of these:

- keep it temporarily and document that media is still on your account
- or migrate media into the client's Cloudinary account before final delivery

Professional answer: migrate to the client's account.

## 5. Razorpay

The client must own the Razorpay account used in production.

Update:

```env
RAZORPAY_KEY_ID=client-live-key
RAZORPAY_KEY_SECRET=client-live-secret
```

Before switching live keys:

- complete the client's Razorpay KYC
- confirm bank settlement account belongs to the client
- test one live payment only after the domain and SSL are ready

Do not leave your own Razorpay account connected to the client's production site.

## 6. Shiprocket

The client should own the Shiprocket account and pickup location.

Update:

```env
SHIPROCKET_ENABLED=true
SHIPROCKET_EMAIL=client-api-email
SHIPROCKET_PASSWORD=client-api-password
SHIPROCKET_WEBHOOK_TOKEN=client-webhook-secret
```

Before handoff:

- create or verify the pickup location in Shiprocket
- verify Shiprocket API credentials belong to the client
- set the webhook URL to `https://yourdomain.com/webhook/shipping/`
- set the same webhook security token in Shiprocket and the env file

If you tested Shiprocket earlier using the EC2 IP or a temporary URL, replace it during cutover.

Final expected webhook target:

```text
https://yourdomain.com/webhook/shipping/
```

Important:

- this code verifies the webhook token from the `x-api-key` header
- if Shiprocket sends a different header in production, update the app before handoff

## 7. Email / SMTP

Production email should not use your personal mailbox.

Update these env values to the client's mailbox or transactional email service:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=client-email@example.com
EMAIL_HOST_PASSWORD=client-secret
DEFAULT_FROM_EMAIL=client-email@example.com
```

If using Gmail:

- use an app password, not the main password
- keep `DEFAULT_FROM_EMAIL` the same as `EMAIL_HOST_USER` unless a verified sender is configured

## 8. Django Admin and Superuser

Create the final admin access for the client.

Recommended:

- create a client admin user
- verify the client can log in
- remove temporary admin users that should not remain
- do not hand over your own reused password

Command if needed:

```bash
cd /srv/daillyfresh
source .venv/bin/activate
set -a
source /etc/daillyfresh/daillyfresh.env
set +a
python manage.py createsuperuser
```

## 9. Environment File Review

Before handoff, review `/etc/daillyfresh/daillyfresh.env` and make sure all values belong to the client.

Check these especially:

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `CLOUDINARY_*`
- `EMAIL_*`
- `DEFAULT_FROM_EMAIL`
- `RAZORPAY_*`
- `SHIPROCKET_*`

After changing env values:

```bash
sudo systemctl restart daillyfresh
sudo systemctl status daillyfresh
```

## 10. Backups

Do not hand off a production server without a backup method.

At minimum, document the PostgreSQL backup command:

```bash
mkdir -p /var/backups/daillyfresh
PGPASSWORD='db-password' pg_dump -U dailyfresh_user -h 127.0.0.1 dailyfresh > /var/backups/daillyfresh/dailyfresh-$(date +%F).sql
```

Also document restore:

```bash
PGPASSWORD='db-password' psql -U dailyfresh_user -h 127.0.0.1 -d dailyfresh < /path/to/backup.sql
```

Client should know:

- where backups are stored
- how often backups run
- how to restore them

## 11. Code Update Method

Right now, if the server was populated by copying files manually, updates are harder.

Before final handoff, prefer this:

- make `/srv/daillyfresh` a proper Git working tree
- keep deployment on the intended production branch
- document the update commands

Typical future update flow:

```bash
cd /srv/daillyfresh
git pull origin <deployment-branch>
source .venv/bin/activate
pip install -r requirements.txt
set -a
source /etc/daillyfresh/daillyfresh.env
set +a
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart daillyfresh
```

## 12. Final Verification Checklist

Before you call the project handed over, verify all of this:

- homepage loads on the real domain
- `http://yourdomain.com` redirects or resolves as expected
- admin works
- static files load correctly
- media uploads still work
- a test order can be placed
- Razorpay works with client keys
- Shiprocket order push works with client credentials
- Shiprocket webhook reaches `/webhook/shipping/`
- `https` works
- Gunicorn service restarts cleanly
- Nginx restarts cleanly
- backup command is documented

## 13. What You Should Give the Client

Provide one handoff package containing:

- server IP and login method
- deployed branch name
- domain and DNS details
- location of env file
- service names: `daillyfresh`, `nginx`, `postgresql`
- admin URL
- backup and restore commands
- update procedure
- list of third-party services connected to the app

## 14. Real Domain Cutover Checklist

Use this when the EC2 test deployment is already working by IP and the client has now purchased the final domain.

### A. Prepare the client-owned services

- confirm the domain is owned by the client
- confirm AWS account access is in the client's control
- confirm Cloudinary, Razorpay, Shiprocket, and SMTP accounts belong to the client or are scheduled for migration

### B. Update DNS

- point `yourdomain.com` to the EC2 public IP
- point `www.yourdomain.com` to the same target if `www` is needed
- wait for DNS propagation

### C. Update Django env values

Edit `/etc/daillyfresh/daillyfresh.env` and replace temporary IP-based values with domain-based values:

```env
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

If you want a short rollback window, keep the EC2 IP in `ALLOWED_HOSTS` for one deployment cycle only.

### D. Update Nginx

Edit `/etc/nginx/sites-available/daillyfresh`:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Then apply:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart daillyfresh
```

### E. Issue SSL

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### F. Update third-party integrations to the final hostname

- Shiprocket webhook URL -> `https://yourdomain.com/webhook/shipping/`
- any manual admin links, documentation, or bookmarks that still use the EC2 IP
- frontend payment references, if you documented any test URL outside the app

### G. Verify end to end

```bash
curl -I http://yourdomain.com
curl -I https://yourdomain.com
sudo systemctl status daillyfresh
sudo systemctl status nginx
```

Then manually test:

- homepage
- admin login
- static assets
- checkout flow
- payment flow
- Shiprocket push
- Shiprocket webhook callback

### H. Remove temporary IP-based configuration

After the domain is stable:

- remove the EC2 IP from `ALLOWED_HOSTS`
- stop using the EC2 IP in external integrations
- keep the domain as the only public application hostname

## 15. Recommended Final Cutover Order

Use this order when moving from your temporary setup to the final client-owned setup:

1. Prepare all client accounts.
2. Move or recreate the deployment in the client's AWS account.
3. Point the client's domain to the live server.
4. Update env values to the client's credentials.
5. Run SSL setup.
6. Test homepage, admin, payments, shipping, and webhook flow.
7. Hand over credentials and documentation.
8. Remove your own production access where appropriate.