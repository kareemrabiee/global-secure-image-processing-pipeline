{
	"Version": "2012-10-17",
	"Id": "key-consolepolicy-3",
	"Statement": [
		{
			"Sid": "Enable IAM User Permissions",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:root"
			},
			"Action": "kms:*",
			"Resource": "*"
		},
		{
			"Sid": "AllowS3secondarySSE-KMS",
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
					"aws:SourceArn": "arn:aws:s3:::kareem-img-proc-processed-secondary-${AWS_ACCOUNT_ID}-us-west-1-an"
				}
			}
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
			"Sid": "Allowsescribeofthekey",
			"Effect": "Allow",
			"Principal": {
				"AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:user/admin1"
			},
			"Action": "kms:DescribeKey",
			"Resource": "*"
		}
	]
}