#!/bin/bash
# ============================================
# The Daily Unhinged - Teardown Script
# Removes all AWS resources created by deploy.sh
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${RED}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           THE DAILY UNHINGED - TEARDOWN                   ║"
echo "║     Removing all AWS resources                            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Load config from deployment
if [ -f "${SCRIPT_DIR}/.deploy-config" ]; then
  source "${SCRIPT_DIR}/.deploy-config"
  echo "Loaded configuration from .deploy-config"
else
  echo -e "${YELLOW}No .deploy-config found. Using defaults.${NC}"
  FUNCTION_NAME="daily-unhinged"
  BUCKET_NAME=""
  REGION="ap-south-1"
  AWS_PROFILE="default"
fi

export AWS_PROFILE
export AWS_DEFAULT_REGION="${REGION}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")

echo ""
echo "Configuration:"
echo "  Function: ${FUNCTION_NAME}"
echo "  Bucket: ${BUCKET_NAME:-'(not set - will skip)'}"
echo "  Region: ${REGION}"
echo "  Profile: ${AWS_PROFILE}"
echo "  Account: ${ACCOUNT_ID}"
echo ""

read -p "Are you sure you want to delete all resources? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

echo ""

# ============================================
# 1. DELETE EVENTBRIDGE SCHEDULE
# ============================================
echo -e "${GREEN}[1/5] Deleting EventBridge schedule...${NC}"
aws scheduler delete-schedule --name ${FUNCTION_NAME}-daily 2>/dev/null && echo "  Schedule deleted" || echo "  Schedule not found (skipped)"

# ============================================
# 2. DELETE LAMBDA FUNCTION
# ============================================
echo -e "${GREEN}[2/5] Deleting Lambda function...${NC}"
aws lambda delete-function --function-name ${FUNCTION_NAME} 2>/dev/null && echo "  Function deleted" || echo "  Function not found (skipped)"

# ============================================
# 3. DELETE CLOUDWATCH LOG GROUP
# ============================================
echo -e "${GREEN}[3/5] Deleting CloudWatch log group...${NC}"
aws logs delete-log-group --log-group-name /aws/lambda/${FUNCTION_NAME} 2>/dev/null && echo "  Log group deleted" || echo "  Log group not found (skipped)"

# ============================================
# 4. DELETE S3 BUCKET
# ============================================
echo -e "${GREEN}[4/5] Deleting S3 bucket...${NC}"
if [ -n "${BUCKET_NAME}" ]; then
  # Empty the bucket first
  aws s3 rm s3://${BUCKET_NAME} --recursive 2>/dev/null && echo "  Bucket emptied" || echo "  Bucket already empty or not found"
  # Delete the bucket
  aws s3 rb s3://${BUCKET_NAME} 2>/dev/null && echo "  Bucket deleted" || echo "  Bucket not found (skipped)"
else
  echo "  Bucket name not set (skipped)"
fi

# ============================================
# 5. DELETE IAM ROLES AND POLICIES
# ============================================
echo -e "${GREEN}[5/5] Deleting IAM roles and policies...${NC}"

# Lambda role
aws iam delete-role-policy \
  --role-name ${FUNCTION_NAME}-role \
  --policy-name ${FUNCTION_NAME}-custom-policy 2>/dev/null && echo "  Lambda custom policy deleted" || true

aws iam detach-role-policy \
  --role-name ${FUNCTION_NAME}-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null && echo "  Lambda execution policy detached" || true

aws iam delete-role --role-name ${FUNCTION_NAME}-role 2>/dev/null && echo "  Lambda role deleted" || echo "  Lambda role not found (skipped)"

# Scheduler role
aws iam delete-role-policy \
  --role-name ${FUNCTION_NAME}-scheduler-role \
  --policy-name invoke-lambda-policy 2>/dev/null && echo "  Scheduler policy deleted" || true

aws iam delete-role --role-name ${FUNCTION_NAME}-scheduler-role 2>/dev/null && echo "  Scheduler role deleted" || echo "  Scheduler role not found (skipped)"

# ============================================
# CLEANUP LOCAL FILES
# ============================================
rm -f "${SCRIPT_DIR}/.deploy-config"

# ============================================
# DONE
# ============================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              TEARDOWN COMPLETE!                           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "All resources have been removed. The Daily Unhinged has been... hinged."
echo ""
