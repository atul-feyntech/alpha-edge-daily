#!/bin/bash
# ============================================
# The Daily Unhinged - Deployment Script
# Your daily dose of news with the BS filter engaged.
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           THE DAILY UNHINGED - DEPLOYMENT                 ║"
echo "║     Your daily dose of news with the BS filter engaged    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================
# CONFIGURATION
# ============================================
FUNCTION_NAME="daily-unhinged"
BUCKET_NAME="daily-unhinged-$(date +%s)"
REGION="ap-south-1"  # Mumbai - closer to India, better latency
EMAIL_RECIPIENT="atul@feyntech.in"  # Change this to your email
EMAIL_SENDER="atul@feyntech.in"     # Must be SES verified
RUNTIME="python3.12"
HANDLER="lambda_function.lambda_handler"
MEMORY_SIZE=512
TIMEOUT=180
ARCHITECTURE="arm64"
AWS_PROFILE="default"

# Export profile and region for all AWS commands
export AWS_PROFILE
export AWS_DEFAULT_REGION="${REGION}"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${YELLOW}Configuration:${NC}"
echo "  Function Name: ${FUNCTION_NAME}"
echo "  Region: ${REGION}"
echo "  AWS Account: ${ACCOUNT_ID}"
echo "  AWS Profile: ${AWS_PROFILE}"
echo ""

# ============================================
# 1. CREATE S3 BUCKET
# ============================================
echo -e "${GREEN}[1/6] Creating S3 bucket: ${BUCKET_NAME}${NC}"

aws s3 mb s3://${BUCKET_NAME} --region ${REGION} 2>/dev/null || echo "Bucket may already exist"

aws s3api put-public-access-block \
  --bucket ${BUCKET_NAME} \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "  S3 bucket created with public access blocked"

# ============================================
# 2. CREATE IAM ROLE FOR LAMBDA
# ============================================
echo -e "${GREEN}[2/6] Creating IAM role${NC}"

# Trust policy
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name ${FUNCTION_NAME}-role \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  2>/dev/null || echo "  Role already exists"

# Wait for role to propagate
echo "  Waiting for IAM role to propagate..."
sleep 10

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name ${FUNCTION_NAME}-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
  2>/dev/null || true

# Custom policy for Bedrock + S3
cat > /tmp/lambda-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}",
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${FUNCTION_NAME}-role \
  --policy-name ${FUNCTION_NAME}-custom-policy \
  --policy-document file:///tmp/lambda-policy.json

echo "  IAM role and policies configured"

# Wait a bit more for policies to propagate
sleep 5

# ============================================
# 3. PACKAGE LAMBDA FUNCTION
# ============================================
echo -e "${GREEN}[3/6] Packaging Lambda function${NC}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rm -rf /tmp/lambda-package
mkdir -p /tmp/lambda-package

echo "  Installing Python dependencies..."
pip3 install feedparser requests -t /tmp/lambda-package --quiet --upgrade

echo "  Copying Lambda function code..."
cp "${SCRIPT_DIR}/lambda_function.py" /tmp/lambda-package/

cd /tmp/lambda-package
echo "  Creating deployment package..."
zip -r9 ../function.zip . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" > /dev/null
cd - > /dev/null

PACKAGE_SIZE=$(du -h /tmp/function.zip | cut -f1)
echo "  Package size: ${PACKAGE_SIZE}"

# ============================================
# 4. CREATE/UPDATE LAMBDA FUNCTION
# ============================================
echo -e "${GREEN}[4/6] Creating Lambda function${NC}"

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${FUNCTION_NAME}-role"

if aws lambda get-function --function-name ${FUNCTION_NAME} 2>/dev/null; then
  echo "  Updating existing function..."

  aws lambda update-function-code \
    --function-name ${FUNCTION_NAME} \
    --zip-file fileb:///tmp/function.zip > /dev/null

  echo "  Waiting for function update..."
  aws lambda wait function-updated --function-name ${FUNCTION_NAME}

  aws lambda update-function-configuration \
    --function-name ${FUNCTION_NAME} \
    --runtime ${RUNTIME} \
    --handler ${HANDLER} \
    --memory-size ${MEMORY_SIZE} \
    --timeout ${TIMEOUT} \
    --environment "Variables={BUCKET_NAME=${BUCKET_NAME},LOG_LEVEL=INFO,BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0,MAX_ITEMS=25,EMAIL_RECIPIENT=${EMAIL_RECIPIENT},EMAIL_SENDER=${EMAIL_SENDER}}" > /dev/null
else
  echo "  Creating new function..."

  aws lambda create-function \
    --function-name ${FUNCTION_NAME} \
    --runtime ${RUNTIME} \
    --handler ${HANDLER} \
    --role ${ROLE_ARN} \
    --zip-file fileb:///tmp/function.zip \
    --memory-size ${MEMORY_SIZE} \
    --timeout ${TIMEOUT} \
    --architectures ${ARCHITECTURE} \
    --environment "Variables={BUCKET_NAME=${BUCKET_NAME},LOG_LEVEL=INFO,BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0,MAX_ITEMS=25,EMAIL_RECIPIENT=${EMAIL_RECIPIENT},EMAIL_SENDER=${EMAIL_SENDER}}" > /dev/null
fi

echo "  Waiting for function to be active..."
aws lambda wait function-active --function-name ${FUNCTION_NAME}
echo "  Lambda function ready"

# ============================================
# 5. CREATE EVENTBRIDGE SCHEDULER
# ============================================
echo -e "${GREEN}[5/6] Creating EventBridge schedule (7 AM IST daily)${NC}"

# Create scheduler IAM role
cat > /tmp/scheduler-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "scheduler.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name ${FUNCTION_NAME}-scheduler-role \
  --assume-role-policy-document file:///tmp/scheduler-trust.json \
  2>/dev/null || echo "  Scheduler role already exists"

cat > /tmp/scheduler-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${FUNCTION_NAME}-scheduler-role \
  --policy-name invoke-lambda-policy \
  --policy-document file:///tmp/scheduler-policy.json

sleep 10

SCHEDULER_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${FUNCTION_NAME}-scheduler-role"
LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

# Delete existing schedule if exists
aws scheduler delete-schedule --name ${FUNCTION_NAME}-daily 2>/dev/null || true

# Create schedule - 7 AM IST (1:30 AM UTC)
aws scheduler create-schedule \
  --name ${FUNCTION_NAME}-daily \
  --schedule-expression "cron(0 7 * * ? *)" \
  --schedule-expression-timezone "Asia/Kolkata" \
  --flexible-time-window '{"Mode": "OFF"}' \
  --target "{
    \"Arn\": \"${LAMBDA_ARN}\",
    \"RoleArn\": \"${SCHEDULER_ROLE_ARN}\",
    \"RetryPolicy\": {\"MaximumRetryAttempts\": 3}
  }" \
  --state ENABLED > /dev/null

echo "  EventBridge schedule created: 7:00 AM IST daily"

# ============================================
# 6. SET LOG RETENTION
# ============================================
echo -e "${GREEN}[6/6] Setting CloudWatch log retention${NC}"

# Create log group if it doesn't exist
aws logs create-log-group --log-group-name /aws/lambda/${FUNCTION_NAME} 2>/dev/null || true

aws logs put-retention-policy \
  --log-group-name /aws/lambda/${FUNCTION_NAME} \
  --retention-in-days 7

echo "  Log retention set to 7 days"

# ============================================
# SAVE CONFIG FOR TEARDOWN
# ============================================
cat > "${SCRIPT_DIR}/.deploy-config" << EOF
BUCKET_NAME=${BUCKET_NAME}
FUNCTION_NAME=${FUNCTION_NAME}
REGION=${REGION}
AWS_PROFILE=${AWS_PROFILE}
ACCOUNT_ID=${ACCOUNT_ID}
EOF

# ============================================
# DONE
# ============================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DEPLOYMENT COMPLETE!                         ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Summary:"
echo "  Function: ${FUNCTION_NAME}"
echo "  Bucket: ${BUCKET_NAME}"
echo "  Region: ${REGION}"
echo "  Schedule: Daily at 7:00 AM IST"
echo ""
echo -e "${YELLOW}Test the function:${NC}"
echo "  aws lambda invoke --function-name ${FUNCTION_NAME} --profile ${AWS_PROFILE} /tmp/out.json && cat /tmp/out.json"
echo ""
echo -e "${YELLOW}View logs:${NC}"
echo "  aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --profile ${AWS_PROFILE}"
echo ""
echo -e "${YELLOW}Check S3 output:${NC}"
echo "  aws s3 ls s3://${BUCKET_NAME}/digests/ --profile ${AWS_PROFILE}"
echo ""
echo -e "${RED}IMPORTANT:${NC} Make sure Claude 3.5 Haiku is enabled in AWS Bedrock!"
echo "  Go to: AWS Console -> Bedrock -> Model access -> Request access"
echo ""
