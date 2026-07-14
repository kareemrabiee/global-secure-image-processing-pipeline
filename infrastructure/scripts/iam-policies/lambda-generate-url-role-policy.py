{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "PutUploadObjects",
			"Effect": "Allow",
			"Action": [
				"s3:PutObject"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-upload-${AWS_ACCOUNT_ID}-us-east-1-an/*"
		},
		{
			"Sid": "KMSUsage",
			"Effect": "Allow",
			"Action": [
				"kms:Decrypt",
				"kms:GenerateDataKey"
			],
			"Resource": "arn:aws:kms:us-east-1:${AWS_ACCOUNT_ID}:key/mrk-51a95f6d174540158f3e0355608624f9"
		},
		{
			"Sid": "Logs",
			"Effect": "Allow",
			"Action": [
				"logs:CreateLogGroup",
				"logs:CreateLogStream",
				"logs:PutLogEvents"
			],
			"Resource": "arn:aws:logs:us-east-1:${AWS_ACCOUNT_ID}:*"
		}
	]
}