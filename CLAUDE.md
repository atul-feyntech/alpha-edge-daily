# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**The Daily Unhinged** - Your daily dose of news with the BS filter engaged.

An automated news digest system running on AWS that fetches news via RSS, filters/ranks articles using TF-IDF and keyword scoring, generates irreverent George Carlin-meets-Richard Feynman style commentary via AWS Bedrock (Claude 3.5 Haiku), and uploads markdown digests to S3.

## Architecture

- **EventBridge Scheduler**: Triggers Lambda daily at 7 AM IST
- **Lambda (Python 3.12, ARM64)**: Fetches RSS feeds, filters content, calls Bedrock, uploads to S3
- **AWS Bedrock**: LLM for generating commentary (Claude 3.5 Haiku or Nova Micro)
- **S3**: Stores generated markdown digests

Key design decisions: No VPC (avoids NAT Gateway costs), ARM64 architecture (20% cheaper), 7-day log retention.

## Build and Deploy Commands

```bash
# Deploy the entire stack
chmod +x deploy.sh
./deploy.sh

# Test the Lambda function
aws lambda invoke --function-name daily-unhinged /tmp/out.json && cat /tmp/out.json

# View logs
aws logs tail /aws/lambda/daily-unhinged --follow

# Check S3 output
aws s3 ls s3://your-bucket/digests/

# Tear down all resources
chmod +x teardown.sh
./teardown.sh
```

## Prerequisites

1. AWS CLI v2 configured with credentials (`aws configure`)
2. Bedrock model access enabled in AWS Console for Claude 3.5 Haiku or Nova
3. Python dependencies: `feedparser`, `requests`, `scikit-learn`

## Key Files

- `lambda_function.py`: Main Lambda handler with RSS fetching, ranking, and Bedrock integration
- `deploy.sh`: Creates S3 bucket, IAM roles, Lambda function, and EventBridge schedule
- `teardown.sh`: Removes all AWS resources
- `.deploy-config`: Auto-generated file storing deployment configuration

## Token Optimization Strategy

The system uses three-stage filtering to minimize LLM costs:
1. **Keyword pre-filtering**: Score headlines by priority keywords (zero cost)
2. **TF-IDF ranking**: Rank by relevance using scikit-learn (zero cost)
3. **LLM processing**: Only top 20-30 items sent to Bedrock

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUCKET_NAME` | S3 bucket for output | Required |
| `BEDROCK_MODEL` | Model ID | `anthropic.claude-3-haiku-20240307-v1:0` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_ITEMS` | Max items to process | `25` |
| `EMAIL_RECIPIENT` | Email address to send digest to | (optional) |
| `EMAIL_SENDER` | SES verified sender email | (optional) |
