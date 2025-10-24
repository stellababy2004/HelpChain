#!/bin/bash
# backup.sh - Automated Backup Script for HelpChain Production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_ROOT="/opt/helpchain/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

# Database configuration (from environment)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-helpchain}"
DB_USER="${DB_USER:-helpchain_user}"

# Cloud storage configuration
S3_BUCKET="${S3_BUCKET:-helpchain-backups}"
S3_REGION="${S3_REGION:-us-east-1}"

echo -e "${BLUE}💾 Starting HelpChain backup process${NC}"

# Create backup directory
echo -e "${BLUE}📁 Creating backup directory...${NC}"
mkdir -p "${BACKUP_DIR}"

# Function to log backup operations
log_backup() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1" >> "${BACKUP_ROOT}/backup.log"
}

# Function to cleanup old backups
cleanup_old_backups() {
    echo -e "${BLUE}🧹 Cleaning up old backups...${NC}"
    find "${BACKUP_ROOT}" -name "20*" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true
    log_backup "Cleaned up backups older than ${RETENTION_DAYS} days"
}

# Database backup
backup_database() {
    echo -e "${BLUE}📊 Backing up PostgreSQL database...${NC}"

    # Create database dump
    PGPASSWORD="${DB_PASSWORD}" pg_dump \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        -F c \
        -f "${BACKUP_DIR}/database.dump"

    # Verify backup integrity
    if PGPASSWORD="${DB_PASSWORD}" pg_restore --list "${BACKUP_DIR}/database.dump" > /dev/null; then
        echo -e "${GREEN}✅ Database backup created successfully${NC}"
        log_backup "Database backup created: ${BACKUP_DIR}/database.dump"
    else
        echo -e "${RED}❌ Database backup verification failed${NC}"
        rm -f "${BACKUP_DIR}/database.dump"
        return 1
    fi
}

# Redis backup
backup_redis() {
    echo -e "${BLUE}🔴 Backing up Redis data...${NC}"

    # Create Redis dump
    docker exec helpchain-redis redis-cli SAVE

    # Copy dump file
    docker cp helpchain-redis:/data/dump.rdb "${BACKUP_DIR}/redis.dump"

    if [[ -f "${BACKUP_DIR}/redis.dump" ]]; then
        echo -e "${GREEN}✅ Redis backup created successfully${NC}"
        log_backup "Redis backup created: ${BACKUP_DIR}/redis.dump"
    else
        echo -e "${RED}❌ Redis backup failed${NC}"
        return 1
    fi
}

# Application files backup
backup_application_files() {
    echo -e "${BLUE}📁 Backing up application files...${NC}"

    # Backup configuration files
    cp -r /opt/helpchain/config "${BACKUP_DIR}/config" 2>/dev/null || true
    cp /opt/helpchain/docker-compose.yml "${BACKUP_DIR}/" 2>/dev/null || true
    cp /opt/helpchain/.env.production "${BACKUP_DIR}/" 2>/dev/null || true

    # Backup SSL certificates (if they exist)
    if [[ -d "/etc/letsencrypt" ]]; then
        cp -r /etc/letsencrypt "${BACKUP_DIR}/ssl_certificates"
    fi

    # Backup nginx configuration
    cp -r /etc/nginx/sites-available "${BACKUP_DIR}/nginx_config" 2>/dev/null || true

    echo -e "${GREEN}✅ Application files backup completed${NC}"
    log_backup "Application files backup created: ${BACKUP_DIR}/files"
}

# Upload to cloud storage
upload_to_cloud() {
    echo -e "${BLUE}☁️  Uploading backup to cloud storage...${NC}"

    if command -v aws >/dev/null 2>&1; then
        # Upload to S3
        aws s3 cp "${BACKUP_DIR}" "s3://${S3_BUCKET}/${TIMESTAMP}/" --recursive --region "${S3_REGION}"

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Backup uploaded to S3 successfully${NC}"
            log_backup "Backup uploaded to S3: s3://${S3_BUCKET}/${TIMESTAMP}/"
        else
            echo -e "${RED}❌ S3 upload failed${NC}"
            return 1
        fi
    elif command -v az >/dev/null 2>&1; then
        # Upload to Azure Blob Storage
        az storage blob upload-batch \
            --destination "${AZURE_CONTAINER}" \
            --source "${BACKUP_DIR}" \
            --account-name "${AZURE_STORAGE_ACCOUNT}"

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Backup uploaded to Azure successfully${NC}"
            log_backup "Backup uploaded to Azure: ${AZURE_CONTAINER}/${TIMESTAMP}/"
        else
            echo -e "${RED}❌ Azure upload failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  No cloud storage client found. Backup stored locally only.${NC}"
    fi
}

# Create backup manifest
create_manifest() {
    echo -e "${BLUE}📋 Creating backup manifest...${NC}"

    cat > "${BACKUP_DIR}/MANIFEST.txt" << EOF
HelpChain Backup Manifest
========================
Timestamp: ${TIMESTAMP}
Date: $(date)
Version: $(git rev-parse HEAD 2>/dev/null || echo "N/A")

Contents:
$(ls -la "${BACKUP_DIR}")

System Information:
- Hostname: $(hostname)
- OS: $(uname -a)
- Docker: $(docker --version 2>/dev/null || echo "Not available")
- PostgreSQL: $(psql --version 2>/dev/null || echo "Not available")

Backup Configuration:
- Retention: ${RETENTION_DAYS} days
- Database: ${DB_NAME}
- Cloud Storage: ${S3_BUCKET:-${AZURE_CONTAINER:-Local only}}
EOF

    echo -e "${GREEN}✅ Backup manifest created${NC}"
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"

    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        curl -X POST -H 'Content-type: application/json' \
             --data "{\"text\":\"${status}: HelpChain backup ${message}\"}" \
             "$SLACK_WEBHOOK_URL" 2>/dev/null || true
    fi

    if [[ -n "$EMAIL_RECIPIENT" ]]; then
        echo "HelpChain backup ${message}" | mail -s "HelpChain Backup ${status}" "$EMAIL_RECIPIENT" 2>/dev/null || true
    fi
}

# Main backup process
main() {
    log_backup "Starting backup process"

    # Pre-backup checks
    echo -e "${YELLOW}🔍 Running pre-backup checks...${NC}"

    # Check disk space
    local available_space=$(df "${BACKUP_ROOT}" | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 1048576 ]]; then  # Less than 1GB
        echo -e "${RED}❌ Insufficient disk space for backup${NC}"
        send_notification "FAILED" "insufficient disk space"
        exit 1
    fi

    # Check database connectivity
    if ! PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" >/dev/null 2>&1; then
        echo -e "${RED}❌ Cannot connect to database${NC}"
        send_notification "FAILED" "database connection failed"
        exit 1
    fi

    # Perform backups
    local backup_failed=false

    if ! backup_database; then
        backup_failed=true
    fi

    if ! backup_redis; then
        backup_failed=true
    fi

    backup_application_files

    create_manifest

    # Upload to cloud if backups succeeded
    if [[ "$backup_failed" == false ]]; then
        if ! upload_to_cloud; then
            backup_failed=true
        fi
    fi

    # Cleanup
    cleanup_old_backups

    # Final status
    if [[ "$backup_failed" == false ]]; then
        echo -e "${GREEN}🎉 Backup completed successfully!${NC}"
        echo -e "${BLUE}📊 Backup Summary:${NC}"
        echo -e "   Location: ${BACKUP_DIR}"
        echo -e "   Size: $(du -sh "${BACKUP_DIR}" | cut -f1)"
        echo -e "   Files: $(find "${BACKUP_DIR}" -type f | wc -l)"

        log_backup "Backup completed successfully"
        send_notification "SUCCESS" "completed successfully"
    else
        echo -e "${RED}❌ Backup completed with errors${NC}"
        log_backup "Backup completed with errors"
        send_notification "WARNING" "completed with errors"
        exit 1
    fi
}

# Run main function
main "$@"
