# Naked Roadmap Deployment Guide

This guide covers deploying the Naked Roadmap application on Digital Ocean using Docker.

## Prerequisites

- A Digital Ocean account
- Docker and Docker Compose installed on your local machine
- Basic familiarity with the command line
- Domain name (optional, but recommended)

## Local Testing

Before deploying to Digital Ocean, test the Docker setup locally:

1. Clone the repository and navigate to the project directory
2. Build and start the Docker container:

```bash
docker-compose up --build
```

3. Access the application at http://localhost:5000
4. Verify that the initialization process works correctly (database migrations, role creation, admin user setup)

## Digital Ocean Deployment

### 1. Create a Droplet

1. Log in to your Digital Ocean account
2. Click "Create" and select "Droplets"
3. Choose an image: "Marketplace" > "Docker"
4. Select a plan (Basic is usually sufficient to start)
5. Choose a datacenter region close to your users
6. Add your SSH keys
7. Choose a hostname and click "Create Droplet"

### 2. Configure the Server

1. SSH into your new Droplet:

```bash
ssh root@your_droplet_ip
```

2. Update the system:

```bash
apt update && apt upgrade -y
```

3. Install Docker Compose (if not already installed):

```bash
apt install -y docker-compose
```

### 3. Deploy the Application

1. Create a directory for your application:

```bash
mkdir -p /opt/naked-roadmap
cd /opt/naked-roadmap
```

2. Transfer your application files to the server. You can use SCP or git:

```bash
# Using git
git clone https://github.com/Naked-Roadmap/naked-roadmap.git .

# OR using SCP from your local machine
scp -r ./* root@your_droplet_ip:/opt/naked-roadmap/
```

3. Create a `.env` file with your environment variables:

```bash
nano .env
```

Add the following content, customizing as needed:

```
SECRET_KEY=your_secure_secret_key
ADMIN_USERNAME=admin
ADMIN_EMAIL=your_email@example.com
ADMIN_PASSWORD=your_secure_password
```

4. Start the application:

```bash
docker-compose up -d
```

### 4. Set Up a Domain and HTTPS (Optional but Recommended)

1. Point your domain to your Digital Ocean Droplet's IP address
2. Install Nginx as a reverse proxy:

```bash
apt install -y nginx
```

3. Create an Nginx configuration file:

```bash
nano /etc/nginx/sites-available/naked-roadmap
```

4. Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

5. Enable the site and restart Nginx:

```bash
sudo ufw allow 'Nginx HTTP'
ln -s /etc/nginx/sites-available/naked-roadmap /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

6. Set up HTTPS with Certbot:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow the prompts to complete the HTTPS setup.

## Maintenance

### Backup

Set up regular database backups:

```bash
# Create a backup script
nano /opt/backups/backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/opt/backups"
mkdir -p $BACKUP_DIR

# Copy the SQLite database file
cp /opt/naked-roadmap/instance/app.db $BACKUP_DIR/app_$DATE.db

# Optional: Clean up old backups (keep last 7 days)
find $BACKUP_DIR -name "app_*.db" -type f -mtime +7 -delete
```

```bash
chmod +x /opt/backups/backup.sh
```

Add a daily cron job:

```bash
crontab -e
```

Add the following line:

```
0 3 * * * /opt/backups/backup.sh
```

### Updating the Application

To update the application:

1. Pull the latest changes:

```bash
cd /opt/naked-roadmap
git pull
```

2. Rebuild and restart the containers:

```bash
docker-compose down
docker-compose up -d --build
```

## Troubleshooting

### Check Logs

```bash
docker-compose logs -f
```

### Database Issues

If you encounter database issues, you can access the database directly:

```bash
docker-compose exec app sqlite3 instance/app.db
```

### Container Not Starting

Check the status of the container:

```bash
docker-compose ps
```

If the container is stopped, check the logs for errors:

```bash
docker-compose logs app
```

## Security Considerations

1. Always use strong passwords for admin users
2. Regularly update your server and dependencies
3. Consider setting up a firewall (e.g., UFW)
4. Use HTTPS for all connections
5. Implement regular backups

For additional security measures, consult the security guidelines in your application documentation.