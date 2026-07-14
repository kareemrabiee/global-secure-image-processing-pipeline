{
	"Version": "2012-10-17",
	"Id": "key-consolepolicy-3",
	"Statement": [
		{
			"Sid": "EnableIAMUserPermissions",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:root"
			},
			"Action": "kms:*",
			"Resource": "*"
		},
		{
			"Sid": "AllowCloudFrontServicePrincipalSSE-KMS",
			"Effect": "Allow",
			"Principal": {
				"Service": "cloudfront.amazonaws.com"
			},
			"Action": [
				"kms:Decrypt",
				"kms:GenerateDataKey*"
			],
			"Resource": "*",
			"Condition": {
				"StringEquals": {
					"aws:SourceArn": "arn:aws:cloudfront::${AWS_ACCOUNT_ID}:distribution/EXAMPLE1234567"
				}
			}
		},
		{
			"Sid": "AllowS3UploadBucketSSE-KMS",
			"Effect": "Allow",
			"Principal": {
				"Service": "s3.amazonaws.com"
			},
			"Action": [
				"kms:GenerateDataKey*",
				"kms:Decrypt"
			],
			"Resource": "*",
			"Condition": {
				"StringEquals": {
					"aws:SourceAccount": "${AWS_ACCOUNT_ID}"
				},
				"ArnLike": {
					"aws:SourceArn": "arn:aws:s3:::kareem-img-proc-upload-${AWS_ACCOUNT_ID}-us-east-1-an"
				}
			}
		},
		{
			"Sid": "AllowSQSPrincipalSSE-KMS",
			"Effect": "Allow",
			"Principal": {
				"Service": "sqs.amazonaws.com"
			},
			"Action": [
				"kms:Decrypt",
				"kms:GenerateDataKey*"
			],
			"Resource": "*",
			"Condition": {
				"StringEquals": {
					"aws:SourceArn": "arn:aws:sqs:us-east-1:${AWS_ACCOUNT_ID}:kareem-img-proc-queue"
				}
			}
		},
		{
			"Sid": "AllowDLQPrincipalSSE-KMS",
			"Effect": "Allow",
			"Principal": {
				"Service": "sqs.amazonaws.com"
			},
			"Action": [
				"kms:Decrypt",
				"kms:GenerateDataKey*"
			],
			"Resource": "*",
			"Condition": {
				"StringEquals": {
					"aws:SourceArn": "arn:aws:sqs:us-east-1:${AWS_ACCOUNT_ID}:kareem-img-proc-dlq"
				}
			}
		},
		{
			"Sid": "AllowaccessforKeyAdministrators",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:user/admin1"
			},
			"Action": [
				"kms:Create*",
				"kms:Describe*",
				"kms:Enable*",
				"kms:List*",
				"kms:Put*",
				"kms:Update*",
				"kms:Revoke*",
				"kms:Disable*",
				"kms:Get*",
				"kms:Delete*",
				"kms:TagResource",
				"kms:UntagResource",
				"kms:ScheduleKeyDeletion",
				"kms:CancelKeyDeletion",
				"kms:ReplicateKey",
				"kms:UpdatePrimaryRegion",
				"kms:RotateKeyOnDemand"
			],
			"Resource": "*"
		},
		{
			"Sid": "Allowdescribeofthekey",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:user/admin1"
			},
			"Action": "kms:DescribeKey",
			"Resource": "*"
		}
	]
}